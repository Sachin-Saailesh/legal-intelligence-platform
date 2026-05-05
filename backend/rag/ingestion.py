import asyncio
import re
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from core.config import settings
from core.logging import get_logger
from db.models import Document, IngestionStatus
from graph.neo4j_client import Neo4jClient
from rag.embeddings import AzureEmbeddingClient, AzureLLMClient

logger = get_logger(__name__)

# ── Clause boundary patterns ───────────────────────────────────────────────────
_CLAUSE_BOUNDARY = re.compile(
    r"""
    (?:^|\n)                                      # start of line
    (?:
        (?:ARTICLE|SECTION|EXHIBIT|SCHEDULE|ANNEX)\s+[IVXLC\d]+  # ARTICLE IV
        | \d+(?:\.\d+)*\.?\s+[A-Z]               # 1.2 Heading
        | [A-Z]{2,}(?:\s+[A-Z]{2,})+             # ALL CAPS HEADING
    )
    """,
    re.VERBOSE | re.MULTILINE,
)

_CONTRACT_DOC_TYPES = {"contract", "agreement", "nda", "msa", "sow"}


def _is_contract(doc_type: str | None) -> bool:
    if doc_type is None:
        return False
    return any(t in doc_type.lower() for t in _CONTRACT_DOC_TYPES)


def _recursive_char_split(
    text: str, chunk_size: int = 800, overlap: int = 150
) -> list[str]:
    """Token-approximate recursive character text splitter."""
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " ", ""]
    for sep in separators:
        if sep and sep in text:
            parts = text.split(sep)
            chunks: list[str] = []
            current = ""
            for part in parts:
                candidate = (current + sep + part).strip()
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = part
            if current:
                chunks.append(current)

            # Re-merge tiny trailing chunks with overlap
            merged: list[str] = []
            for i, chunk in enumerate(chunks):
                if i == 0:
                    merged.append(chunk)
                else:
                    overlap_text = merged[-1][-overlap:] if merged else ""
                    merged.append((overlap_text + " " + chunk).strip())
            return [c for c in merged if c]

    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]


def _contract_clause_chunks(text: str) -> list[dict]:
    """Split contract text on clause boundaries, returning dicts with section metadata."""
    matches = list(_CLAUSE_BOUNDARY.finditer(text))
    if len(matches) < 2:
        return [{"text": text, "clause_type": "general", "section_heading": ""}]

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        clause_text = text[start:end].strip()
        if clause_text:
            heading = match.group().strip()[:200]
            chunks.append({
                "text": clause_text,
                "clause_type": _classify_clause_type(heading),
                "section_heading": heading,
            })
    return chunks


def _classify_clause_type(heading: str) -> str:
    h = heading.lower()
    if any(w in h for w in ["indemnif", "liabilit"]):
        return "indemnification"
    if any(w in h for w in ["terminat", "expir"]):
        return "termination"
    if any(w in h for w in ["payment", "fee", "price", "compens"]):
        return "payment"
    if any(w in h for w in ["confidential", "non-disclosure", "nda"]):
        return "confidentiality"
    if any(w in h for w in ["govern", "law", "jurisdiction"]):
        return "governing_law"
    if any(w in h for w in ["intellectual", "ip ", "proprietary"]):
        return "ip"
    if any(w in h for w in ["warrant", "represent"]):
        return "warranties"
    if any(w in h for w in ["disput", "arbitr", "mediat"]):
        return "dispute_resolution"
    return "general"


async def _parse_document(file_path: str) -> list[dict]:
    """Parse document using docling; fall back to Tesseract for low-confidence pages."""
    path = Path(file_path)
    pages: list[dict] = []

    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document
        # docling provides export_to_markdown and page-level access
        full_text = doc.export_to_markdown()
        pages.append({"text": full_text, "page": 1, "confidence": 1.0})
    except Exception as e:
        logger.warning("docling_parse_failed", error=str(e), file=str(path))
        # Tesseract fallback
        pages = await _tesseract_fallback(path)

    return pages


async def _tesseract_fallback(path: Path) -> list[dict]:
    import pytesseract
    from PIL import Image

    pages = []
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(str(path))
            for i, img in enumerate(images):
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                confidences = [c for c in data["conf"] if c != -1]
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                text = pytesseract.image_to_string(img)
                pages.append({"text": text, "page": i + 1, "confidence": avg_conf / 100})
        except Exception as e:
            logger.error("tesseract_pdf_fallback_failed", error=str(e))
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff"):
        img = Image.open(str(path))
        text = pytesseract.image_to_string(img)
        pages.append({"text": text, "page": 1, "confidence": 0.7})

    return pages


async def _extract_entities_for_graph(
    chunks: list[dict], doc_id: str, llm: AzureLLMClient
) -> list[dict]:
    """Use GPT-4o structured output to extract legal entities for Neo4j."""
    system = (
        "You are a legal entity extractor. Given a contract clause, return JSON with keys: "
        "parties (list of party names), defined_terms (list), governing_law (str or null), "
        "referenced_clauses (list of clause section numbers or headings cited in the text). "
        "Return only valid JSON, no markdown."
    )
    entities_per_chunk = []
    for chunk in chunks[:20]:  # limit graph extraction to first 20 chunks per doc
        try:
            raw = await llm.complete(
                system=system,
                messages=[{"role": "user", "content": chunk["text"][:2000]}],
                temperature=0,
                max_tokens=500,
                trace_name="entity_extraction",
            )
            import json
            data = json.loads(raw)
            data["chunk_id"] = chunk["chunk_id"]
            data["doc_id"] = doc_id
            entities_per_chunk.append(data)
        except Exception as e:
            logger.warning("entity_extraction_failed", chunk_id=chunk.get("chunk_id"), error=str(e))
    return entities_per_chunk


class DocumentIngestionPipeline:
    def __init__(
        self,
        embedding_client: AzureEmbeddingClient,
        llm_client: AzureLLMClient,
        qdrant_client: Any,
        neo4j_client: "Neo4jClient | None",
    ) -> None:
        self._embedder = embedding_client
        self._llm = llm_client
        self._qdrant = qdrant_client
        self._neo4j = neo4j_client

    async def ingest(
        self,
        document: Document,
        db: AsyncSession,
    ) -> int:
        t0 = time.perf_counter()
        doc_id = str(document.id)
        matter_id = str(document.matter_id)

        logger.info("ingestion_start", doc_id=doc_id, filename=document.filename)

        # Update status
        await db.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(ingestion_status=IngestionStatus.processing)
        )
        await db.commit()

        try:
            # 1. Parse
            pages = await _parse_document(document.file_path)

            # 2. Chunk
            all_chunks: list[dict] = []
            chunk_idx = 0
            for page in pages:
                text = page["text"]
                if not text.strip():
                    continue

                if _is_contract(document.doc_type):
                    raw_chunks = _contract_clause_chunks(text)
                else:
                    raw_chunks = [
                        {"text": c, "clause_type": "general", "section_heading": ""}
                        for c in _recursive_char_split(text)
                    ]

                for rc in raw_chunks:
                    chunk_text = rc["text"].strip()
                    if len(chunk_text) < 50:
                        continue
                    all_chunks.append({
                        "chunk_id": f"{doc_id}_{chunk_idx}",
                        "doc_id": doc_id,
                        "matter_id": matter_id,
                        "page_number": page["page"],
                        "chunk_index": chunk_idx,
                        "clause_type": rc.get("clause_type", "general"),
                        "section_heading": rc.get("section_heading", ""),
                        "text": chunk_text,
                    })
                    chunk_idx += 1

            # 3. Embed
            texts = [c["text"] for c in all_chunks]
            embeddings = await self._embedder.embed_batch(texts)

            # 4. Upsert to Qdrant
            from qdrant_client.models import PointStruct
            points = [
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, c["chunk_id"])),
                    vector=emb,
                    payload={
                        "chunk_id": c["chunk_id"],
                        "doc_id": c["doc_id"],
                        "matter_id": c["matter_id"],
                        "page_number": c["page_number"],
                        "chunk_index": c["chunk_index"],
                        "clause_type": c["clause_type"],
                        "section_heading": c["section_heading"],
                        "text": c["text"],
                    },
                )
                for c, emb in zip(all_chunks, embeddings)
            ]
            await self._qdrant.upsert(
                collection_name=settings.qdrant_collection,
                points=points,
                wait=True,
            )

            # 5. Build knowledge graph edges (skipped if Neo4j is disabled)
            if self._neo4j is not None:
                entities_list = await _extract_entities_for_graph(all_chunks, doc_id, self._llm)
                await self._neo4j.ingest_document_entities(doc_id, matter_id, entities_list)

            # 6. Update document status
            await db.execute(
                update(Document)
                .where(Document.id == document.id)
                .values(
                    ingestion_status=IngestionStatus.complete,
                    chunk_count=len(all_chunks),
                )
            )
            await db.commit()

            elapsed = time.perf_counter() - t0
            logger.info(
                "ingestion_complete",
                doc_id=doc_id,
                chunk_count=len(all_chunks),
                elapsed_s=round(elapsed, 2),
            )
            return len(all_chunks)

        except Exception as e:
            await db.execute(
                update(Document)
                .where(Document.id == document.id)
                .values(ingestion_status=IngestionStatus.failed)
            )
            await db.commit()
            logger.error("ingestion_failed", doc_id=doc_id, error=str(e))
            raise
