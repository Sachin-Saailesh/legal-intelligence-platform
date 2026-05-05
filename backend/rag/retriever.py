import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from core.config import settings
from core.logging import get_logger
from rag.embeddings import AzureEmbeddingClient

logger = get_logger(__name__)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    matter_id: str
    text: str
    page_number: int = 0
    chunk_index: int = 0
    clause_type: str = "general"
    section_heading: str = ""
    dense_rank: int = 0
    sparse_rank: int = 0
    rrf_score: float = 0.0
    metadata: dict = field(default_factory=dict)


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _reciprocal_rank_fusion(
    dense_chunks: list[Chunk],
    sparse_chunks: list[Chunk],
    top_k: int = 20,
) -> list[Chunk]:
    scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}

    for rank, chunk in enumerate(dense_chunks, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + _rrf_score(rank)
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(sparse_chunks, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + _rrf_score(rank)
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    result = []
    for cid, score in ranked:
        c = chunk_map[cid]
        c.rrf_score = score
        result.append(c)
    return result


class HybridRetriever:
    def __init__(
        self,
        embedding_client: AzureEmbeddingClient,
        qdrant_client: Any,
        redis_client: Any,
    ) -> None:
        self._embedder = embedding_client
        self._qdrant = qdrant_client
        self._redis = redis_client
        self._bm25_cache_ttl = 3600  # 1 hour

    async def retrieve(
        self,
        query: str,
        matter_id: str,
        top_k: int = 100,
        jurisdiction: str | None = None,
        final_top_k: int = 20,
    ) -> list[Chunk]:
        t0 = time.perf_counter()

        dense_task = asyncio.create_task(
            self._dense_search(query, matter_id, top_k, jurisdiction)
        )
        sparse_task = asyncio.create_task(
            self._sparse_search(query, matter_id, top_k)
        )
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

        merged = _reciprocal_rank_fusion(dense_results, sparse_results, top_k=final_top_k)

        elapsed = time.perf_counter() - t0
        logger.info(
            "hybrid_retrieve",
            matter_id=matter_id,
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            merged_count=len(merged),
            elapsed_ms=round(elapsed * 1000, 2),
        )
        return merged

    async def _dense_search(
        self,
        query: str,
        matter_id: str,
        top_k: int,
        jurisdiction: str | None,
    ) -> list[Chunk]:
        query_vec = await self._embedder.embed_text(query)

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        must_conditions = [
            FieldCondition(key="matter_id", match=MatchValue(value=matter_id))
        ]
        if jurisdiction:
            must_conditions.append(
                FieldCondition(key="jurisdiction", match=MatchValue(value=jurisdiction))
            )

        results = await self._qdrant.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vec,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
            with_payload=True,
        )

        chunks = []
        for rank, hit in enumerate(results, start=1):
            payload = hit.payload or {}
            chunks.append(
                Chunk(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    doc_id=payload.get("doc_id", ""),
                    matter_id=payload.get("matter_id", matter_id),
                    text=payload.get("text", ""),
                    page_number=payload.get("page_number", 0),
                    chunk_index=payload.get("chunk_index", 0),
                    clause_type=payload.get("clause_type", "general"),
                    section_heading=payload.get("section_heading", ""),
                    dense_rank=rank,
                    metadata=payload,
                )
            )
        return chunks

    async def _sparse_search(
        self, query: str, matter_id: str, top_k: int
    ) -> list[Chunk]:
        corpus, chunk_ids, chunk_map = await self._get_bm25_corpus(matter_id)
        if not corpus:
            return []

        from rank_bm25 import BM25Okapi

        tokenized_corpus = [doc.lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        chunks = []
        for rank, idx in enumerate(ranked_indices, start=1):
            cid = chunk_ids[idx]
            if scores[idx] <= 0:
                break
            c = chunk_map[cid]
            c.sparse_rank = rank
            chunks.append(c)
        return chunks

    async def _get_bm25_corpus(
        self, matter_id: str
    ) -> tuple[list[str], list[str], dict[str, Chunk]]:
        cache_key = f"bm25_corpus:{matter_id}"

        # Check Redis cache only if Redis is available
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                corpus = data["texts"]
                chunk_ids = data["chunk_ids"]
                chunk_payloads = data["payloads"]
                chunk_map = {
                    cid: Chunk(
                        chunk_id=cid,
                        doc_id=p.get("doc_id", ""),
                        matter_id=matter_id,
                        text=p.get("text", ""),
                        page_number=p.get("page_number", 0),
                        chunk_index=p.get("chunk_index", 0),
                        clause_type=p.get("clause_type", "general"),
                        section_heading=p.get("section_heading", ""),
                        metadata=p,
                    )
                    for cid, p in zip(chunk_ids, chunk_payloads)
                }
                return corpus, chunk_ids, chunk_map

        # Scroll all matter chunks from Qdrant
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        corpus = []
        chunk_ids = []
        chunk_payloads = []
        offset = None

        while True:
            results, next_offset = await self._qdrant.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="matter_id", match=MatchValue(value=matter_id))]
                ),
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in results:
                payload = point.payload or {}
                cid = payload.get("chunk_id", str(point.id))
                chunk_ids.append(cid)
                corpus.append(payload.get("text", ""))
                chunk_payloads.append(payload)

            if next_offset is None:
                break
            offset = next_offset

        # Cache corpus if Redis is available
        if self._redis is not None:
            await self._redis.setex(
                cache_key,
                self._bm25_cache_ttl,
                json.dumps({"texts": corpus, "chunk_ids": chunk_ids, "payloads": chunk_payloads}),
            )
        chunk_map = {
            cid: Chunk(
                chunk_id=cid,
                doc_id=p.get("doc_id", ""),
                matter_id=matter_id,
                text=p.get("text", ""),
                page_number=p.get("page_number", 0),
                chunk_index=p.get("chunk_index", 0),
                clause_type=p.get("clause_type", "general"),
                section_heading=p.get("section_heading", ""),
                metadata=p,
            )
            for cid, p in zip(chunk_ids, chunk_payloads)
        }
        return corpus, chunk_ids, chunk_map
