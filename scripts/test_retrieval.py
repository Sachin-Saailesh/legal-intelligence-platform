#!/usr/bin/env python3
"""Retrieval benchmark: measures top-1 recall and latency against known query/document pairs."""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

BENCHMARK_PAIRS = [
    {
        "query": "indemnification hold harmless licensor liability",
        "expected_keywords": ["indemnif", "hold harmless", "defend"],
        "matter_id": None,  # set at runtime
    },
    {
        "query": "termination notice period contract renewal",
        "expected_keywords": ["terminat", "notice", "renew"],
        "matter_id": None,
    },
    {
        "query": "limitation of liability consequential damages cap",
        "expected_keywords": ["limitation", "liability", "consequential"],
        "matter_id": None,
    },
]


async def run_benchmark(matter_id: str):
    from rag.embeddings import AzureEmbeddingClient
    from rag.retriever import HybridRetriever
    from rag.reranker import FlashRankReranker
    from qdrant_client import QdrantClient
    import redis.asyncio as aioredis
    from core.config import settings

    embedder = AzureEmbeddingClient()
    qdrant = QdrantClient(url=settings.qdrant_url)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    retriever = HybridRetriever(embedding_client=embedder, qdrant_client=qdrant, redis_client=redis)
    ranker = FlashRankReranker()

    total = 0
    hits = 0

    for pair in BENCHMARK_PAIRS:
        pair["matter_id"] = matter_id
        query = pair["query"]
        expected_kws = pair["expected_keywords"]

        t0 = time.perf_counter()
        chunks = await retriever.retrieve(query, matter_id, top_k=100, final_top_k=20)
        ranked = ranker.rerank(query, chunks, top_k=5)
        elapsed = time.perf_counter() - t0

        total += 1
        if ranked:
            top_text = ranked[0].text.lower()
            if any(kw.lower() in top_text for kw in expected_kws):
                hits += 1
                status = "✓ HIT"
            else:
                status = "✗ MISS"
        else:
            status = "✗ NO RESULTS"

        print(f"{status} | {elapsed*1000:.0f}ms | Query: {query[:50]}")
        if ranked:
            print(f"       Top-1: {ranked[0].text[:120].strip()}...")

    recall = hits / total if total > 0 else 0
    print(f"\nRecall@1: {recall:.2%} ({hits}/{total})")
    await redis.aclose()


if __name__ == "__main__":
    matter_id = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-0000-0000-000000000000"
    asyncio.run(run_benchmark(matter_id))
