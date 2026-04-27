"""Tests for the hallucination guard."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from rag.hallucination_guard import GuardResult, HallucinationGuard
from rag.reranker import RankedChunk


def make_chunk(chunk_id: str, text: str, score: float = 0.8) -> RankedChunk:
    return RankedChunk(
        chunk_id=chunk_id,
        doc_id="doc1",
        matter_id="matter1",
        text=text,
        page_number=1,
        rerank_score=score,
    )


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.mark.asyncio
async def test_guard_passes_supported_claim(mock_llm):
    """A claim well-supported by source chunks should pass."""
    mock_llm.complete = AsyncMock(
        return_value=json.dumps({
            "confidence": 0.92,
            "citation_indices": [0],
            "reasoning": "Chunk 0 directly states that payment is due within 30 days.",
        })
    )
    guard = HallucinationGuard(llm_client=mock_llm, confidence_threshold=0.70)
    chunks = [make_chunk("c1", "Payment is due within 30 days of invoice date.", 0.9)]

    result = await guard.validate("Payment is due within 30 days.", chunks)
    assert result.passed is True
    assert result.confidence >= 0.70
    assert 0 in result.citation_indices


@pytest.mark.asyncio
async def test_guard_fails_unsupported_claim(mock_llm):
    """A claim not supported by chunks should fail and set escalation_reason."""
    mock_llm.complete = AsyncMock(
        return_value=json.dumps({
            "confidence": 0.30,
            "citation_indices": [],
            "reasoning": "No chunk mentions a 90-day payment window.",
        })
    )
    guard = HallucinationGuard(llm_client=mock_llm, confidence_threshold=0.70)
    chunks = [make_chunk("c1", "Payment is due within 30 days of invoice date.", 0.9)]

    result = await guard.validate("Payment is due within 90 days.", chunks)
    assert result.passed is False
    assert result.escalation_reason is not None
    assert "0.30" in result.escalation_reason or "below threshold" in result.escalation_reason.lower()


@pytest.mark.asyncio
async def test_guard_fails_with_no_chunks(mock_llm):
    """Guard with no source chunks must always fail."""
    guard = HallucinationGuard(llm_client=mock_llm, confidence_threshold=0.70)
    result = await guard.validate("Any claim", [])
    assert result.passed is False
    assert result.confidence == 0.0
    assert result.escalation_reason is not None
    mock_llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_guard_handles_malformed_llm_response(mock_llm):
    """Guard must handle malformed JSON from LLM without raising."""
    mock_llm.complete = AsyncMock(return_value="this is not valid json")
    guard = HallucinationGuard(llm_client=mock_llm, confidence_threshold=0.70)
    chunks = [make_chunk("c1", "Some supporting text.", 0.8)]

    result = await guard.validate("A claim.", chunks)
    assert result.passed is False  # defaults to fail on parse error
    assert isinstance(result.confidence, float)


@pytest.mark.asyncio
async def test_guard_confidence_threshold_boundary(mock_llm):
    """Confidence exactly at threshold should pass."""
    mock_llm.complete = AsyncMock(
        return_value=json.dumps({
            "confidence": 0.70,
            "citation_indices": [0],
            "reasoning": "Exactly at threshold.",
        })
    )
    guard = HallucinationGuard(llm_client=mock_llm, confidence_threshold=0.70)
    chunks = [make_chunk("c1", "Supporting text.", 0.7)]

    result = await guard.validate("Claim at threshold.", chunks)
    assert result.passed is True
