"""Tests for the hybrid retriever."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.retriever import Chunk, HybridRetriever, _reciprocal_rank_fusion


@pytest.fixture
def mock_embedding_client():
    client = AsyncMock()
    client.embed_text = AsyncMock(return_value=[0.1] * 1536)
    return client


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"doc1_{i}",
            doc_id="doc1",
            matter_id="matter1",
            text=f"This is clause {i} about indemnification and liability.",
            page_number=i,
            chunk_index=i,
            clause_type="indemnification",
        )
        for i in range(10)
    ]


def test_rrf_basic():
    """RRF should rank items higher when they appear in both lists."""
    dense = [
        Chunk(chunk_id="a", doc_id="d1", matter_id="m", text="", dense_rank=1),
        Chunk(chunk_id="b", doc_id="d1", matter_id="m", text="", dense_rank=2),
        Chunk(chunk_id="c", doc_id="d1", matter_id="m", text="", dense_rank=3),
    ]
    sparse = [
        Chunk(chunk_id="b", doc_id="d1", matter_id="m", text="", sparse_rank=1),
        Chunk(chunk_id="a", doc_id="d1", matter_id="m", text="", sparse_rank=2),
        Chunk(chunk_id="d", doc_id="d1", matter_id="m", text="", sparse_rank=3),
    ]
    merged = _reciprocal_rank_fusion(dense, sparse, top_k=4)
    ids = [c.chunk_id for c in merged]
    # Both 'a' and 'b' appear in both lists — they should rank above 'c' and 'd'
    assert ids[0] in ("a", "b")
    assert ids[1] in ("a", "b")
    assert len(merged) == 4


def test_rrf_deduplication():
    """RRF should not return duplicate chunk IDs."""
    chunks = [
        Chunk(chunk_id="x", doc_id="d", matter_id="m", text=""),
        Chunk(chunk_id="x", doc_id="d", matter_id="m", text=""),
        Chunk(chunk_id="y", doc_id="d", matter_id="m", text=""),
    ]
    merged = _reciprocal_rank_fusion(chunks, chunks, top_k=10)
    ids = [c.chunk_id for c in merged]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs returned"


@pytest.mark.asyncio
async def test_retriever_top1_recall(mock_embedding_client):
    """Given a document in Qdrant that matches the query, verify top-1 is returned."""
    target_chunk_id = "target_chunk_001"
    target_text = "The indemnification clause requires the licensee to hold harmless the licensor."

    # Mock Qdrant to return target as top-1
    mock_qdrant = MagicMock()
    mock_qdrant.search = MagicMock(
        return_value=[
            MagicMock(
                id="some-uuid",
                score=0.95,
                payload={
                    "chunk_id": target_chunk_id,
                    "doc_id": "doc1",
                    "matter_id": "matter1",
                    "text": target_text,
                    "page_number": 5,
                    "chunk_index": 0,
                    "clause_type": "indemnification",
                    "section_heading": "ARTICLE 3",
                },
            )
        ]
    )

    # Mock Redis to return corpus with the target chunk
    mock_redis = AsyncMock()
    corpus_data = {
        "texts": [target_text],
        "chunk_ids": [target_chunk_id],
        "payloads": [
            {
                "chunk_id": target_chunk_id,
                "doc_id": "doc1",
                "matter_id": "matter1",
                "text": target_text,
                "page_number": 5,
                "chunk_index": 0,
                "clause_type": "indemnification",
                "section_heading": "ARTICLE 3",
            }
        ],
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(corpus_data))

    retriever = HybridRetriever(
        embedding_client=mock_embedding_client,
        qdrant_client=mock_qdrant,
        redis_client=mock_redis,
    )

    results = await retriever.retrieve(
        query="indemnification hold harmless licensor",
        matter_id="matter1",
        top_k=10,
        final_top_k=5,
    )

    assert len(results) > 0, "Retriever should return at least 1 result"
    top_ids = [r.chunk_id for r in results]
    assert target_chunk_id in top_ids, f"Target chunk not in results: {top_ids}"


@pytest.mark.asyncio
async def test_retriever_empty_corpus(mock_embedding_client):
    """Retriever should handle empty corpus gracefully."""
    mock_qdrant = MagicMock()
    mock_qdrant.search = MagicMock(return_value=[])
    mock_qdrant.scroll = MagicMock(return_value=([], None))

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    retriever = HybridRetriever(
        embedding_client=mock_embedding_client,
        qdrant_client=mock_qdrant,
        redis_client=mock_redis,
    )

    results = await retriever.retrieve(
        query="anything",
        matter_id="empty_matter",
        top_k=10,
        final_top_k=5,
    )
    assert results == [], "Empty corpus should return empty list"
