import json
import time
from typing import Any

from core.logging import get_logger
from rag.embeddings import AzureLLMClient
from rag.hallucination_guard import HallucinationGuard
from rag.reranker import FlashRankReranker, RankedChunk
from rag.retriever import HybridRetriever

logger = get_logger(__name__)

_SYSTEM = """You are an expert legal drafter. You generate contract clauses at three risk tolerances.

Given a drafting request and precedent clauses from the firm's document library, produce JSON:
{
  "aggressive": {
    "text": "Full clause text — maximally favorable to the firm/client",
    "precedent_citation": "chunk_id or description of source precedent",
    "risk_notes": "what risks this aggressive version creates for counterparty"
  },
  "standard": {
    "text": "Full clause text — market-standard, balanced language",
    "precedent_citation": "chunk_id or description of source precedent",
    "risk_notes": "balanced risk allocation notes"
  },
  "conservative": {
    "text": "Full clause text — maximally favorable to counterparty / minimal risk",
    "precedent_citation": "chunk_id or description of source precedent",
    "risk_notes": "how this protects against worst-case scenarios"
  },
  "drafting_notes": "2-3 sentences explaining key drafting choices and tradeoffs",
  "jurisdiction_considerations": "jurisdiction-specific requirements if governing law is known"
}

Rules:
- Each variant must be a complete, self-contained clause ready for insertion
- Cite the primary precedent chunk_id used as the basis for each variant
- Use proper legal formatting (numbered sub-sections where appropriate)
- Flag any jurisdiction-specific requirements that must be addressed
- Do not include placeholder text — all brackets must be filled with appropriate fallback language
"""


async def run_legal_drafter(
    state: dict[str, Any],
    retriever: HybridRetriever,
    reranker: FlashRankReranker,
    llm: AzureLLMClient,
    guard: HallucinationGuard,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = state["query"]
    matter_id = state["matter_id"]

    logger.info("legal_drafter_start", matter_id=matter_id, query_preview=query[:80])

    # Retrieve precedent clauses
    chunks = await retriever.retrieve(query, matter_id, top_k=100, final_top_k=30)
    ranked = reranker.rerank(query, chunks, top_k=10)

    top_score = ranked[0].rerank_score if ranked else 0.0
    logger.info(
        "legal_drafter_retrieved",
        chunk_count=len(chunks),
        reranked_count=len(ranked),
        top_rerank_score=round(top_score, 4),
    )

    context = _build_precedent_context(ranked)
    jurisdiction = state.get("metadata", {}).get("jurisdiction", "not specified")

    raw_output = await llm.complete(
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Drafting Request: {query}\n"
                    f"Jurisdiction: {jurisdiction}\n\n"
                    f"Precedent Clauses from Firm Library:\n{context}"
                ),
            }
        ],
        temperature=0.2,
        max_tokens=4096,
        trace_name="legal_drafter",
    )

    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        output = {"raw": raw_output, "parse_error": True}

    # Guard the standard variant (most commonly used)
    standard_text = output.get("standard", {}).get("text", raw_output[:300])
    guard_result = await guard.validate(standard_text, ranked)

    elapsed = time.perf_counter() - t0
    logger.info(
        "legal_drafter_complete",
        matter_id=matter_id,
        guard_passed=guard_result.passed,
        guard_confidence=round(guard_result.confidence, 4),
        elapsed_ms=round(elapsed * 1000, 2),
    )

    return {
        "agent_outputs": {
            "legal_drafter": {
                "output": output,
                "guard": {
                    "passed": guard_result.passed,
                    "confidence": guard_result.confidence,
                    "citation_indices": guard_result.citation_indices,
                },
            }
        },
        "retrieved_chunks": [_chunk_to_dict(c) for c in ranked],
        "requires_human_review": not guard_result.passed,
    }


def _build_precedent_context(chunks: list[RankedChunk]) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Precedent {i}] chunk_id={chunk.chunk_id} | {chunk.clause_type} | "
            f"page={chunk.page_number} | score={chunk.rerank_score:.3f}\n{chunk.text}"
        )
    return "\n\n---\n\n".join(parts)


def _chunk_to_dict(chunk: RankedChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "text": chunk.text,
        "page_number": chunk.page_number,
        "clause_type": chunk.clause_type,
        "section_heading": chunk.section_heading,
        "rerank_score": chunk.rerank_score,
        "rrf_score": chunk.rrf_score,
    }
