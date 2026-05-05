import threading
import time
from dataclasses import dataclass, field

from core.logging import get_logger
from rag.retriever import Chunk

logger = get_logger(__name__)


@dataclass
class RankedChunk(Chunk):
    rerank_score: float = 0.0


class FlashRankReranker:
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2") -> None:
        self._model_name = model_name
        self._ranker = None
        self._lock = threading.Lock()

    def _get_ranker(self):
        if self._ranker is None:
            with self._lock:
                if self._ranker is None:
                    from flashrank import Ranker
                    self._ranker = Ranker(model_name=self._model_name)
        return self._ranker

    def rerank(
        self, query: str, chunks: list[Chunk], top_k: int = 10
    ) -> list[RankedChunk]:
        if not chunks:
            return []

        t0 = time.perf_counter()
        ranker = self._get_ranker()

        from flashrank import RerankRequest
        rerank_request = RerankRequest(
            query=query,
            passages=[{"id": i, "text": c.text} for i, c in enumerate(chunks)],
        )
        results = ranker.rerank(rerank_request)

        ranked: list[RankedChunk] = []
        for result in results[:top_k]:
            original = chunks[result["id"]]
            rc = RankedChunk(
                chunk_id=original.chunk_id,
                doc_id=original.doc_id,
                matter_id=original.matter_id,
                text=original.text,
                page_number=original.page_number,
                chunk_index=original.chunk_index,
                clause_type=original.clause_type,
                section_heading=original.section_heading,
                dense_rank=original.dense_rank,
                sparse_rank=original.sparse_rank,
                rrf_score=original.rrf_score,
                metadata=original.metadata,
                rerank_score=result["score"],
            )
            ranked.append(rc)

        ranked.sort(key=lambda x: x.rerank_score, reverse=True)

        latency_ms = (time.perf_counter() - t0) * 1000
        scores = [r.rerank_score for r in ranked]
        logger.info(
            "rerank_complete",
            model=self._model_name,
            input_count=len(chunks),
            output_count=len(ranked),
            top_score=round(scores[0], 4) if scores else 0,
            p25_score=round(scores[len(scores) // 4], 4) if scores else 0,
            latency_ms=round(latency_ms, 2),
        )
        return ranked


reranker = FlashRankReranker()
