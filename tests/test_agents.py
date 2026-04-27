"""Tests for the multi-agent orchestrator and specialist agents."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.reranker import RankedChunk
from rag.retriever import Chunk


def make_ranked_chunk(i: int = 0) -> RankedChunk:
    return RankedChunk(
        chunk_id=f"c{i}",
        doc_id="doc1",
        matter_id="matter1",
        text=f"Contract clause {i}: Indemnification terms apply.",
        page_number=i + 1,
        chunk_index=i,
        clause_type="indemnification",
        rerank_score=0.9 - i * 0.05,
    )


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.retrieve = AsyncMock(return_value=[make_ranked_chunk(i) for i in range(5)])
    return r


@pytest.fixture
def mock_reranker():
    r = MagicMock()
    r.rerank = MagicMock(return_value=[make_ranked_chunk(i) for i in range(3)])
    return r


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value=json.dumps({
            "clauses": [
                {
                    "clause_id": "c0",
                    "risk_level": "high",
                    "risk_explanation": "Broad indemnification without cap.",
                    "dependent_clauses": [],
                    "recommended_action": "Add liability cap.",
                    "jurisdiction_notes": "",
                }
            ],
            "missing_standard_clauses": ["limitation of liability"],
            "overall_risk": "high",
            "summary": "The contract has a high-risk uncapped indemnification clause.",
        })
    )
    return llm


@pytest.fixture
def mock_guard():
    g = AsyncMock()
    from rag.hallucination_guard import GuardResult
    g.validate = AsyncMock(
        return_value=GuardResult(
            passed=True,
            confidence=0.88,
            citation_indices=[0],
            reasoning="Supported by chunk 0.",
        )
    )
    return g


@pytest.mark.asyncio
async def test_contract_analyst_agent(mock_retriever, mock_reranker, mock_llm, mock_guard):
    """Contract analyst should return structured output with risk levels."""
    from agents.contract_analyst import run_contract_analyst

    state = {
        "query": "Analyze the indemnification clause",
        "matter_id": "matter1",
        "user_id": "user1",
        "metadata": {},
    }

    result = await run_contract_analyst(
        state=state,
        retriever=mock_retriever,
        reranker=mock_reranker,
        llm=mock_llm,
        guard=mock_guard,
    )

    assert "agent_outputs" in result
    assert "contract_analyst" in result["agent_outputs"]
    output = result["agent_outputs"]["contract_analyst"]["output"]
    assert "clauses" in output or "raw" in output  # may be parsed or raw
    assert "retrieved_chunks" in result
    assert "requires_human_review" in result


@pytest.mark.asyncio
async def test_contract_analyst_guard_failure_triggers_review(
    mock_retriever, mock_reranker, mock_llm
):
    """When guard fails, requires_human_review must be True."""
    from agents.contract_analyst import run_contract_analyst
    from rag.hallucination_guard import GuardResult, HallucinationGuard

    failing_guard = AsyncMock()
    failing_guard.validate = AsyncMock(
        return_value=GuardResult(
            passed=False,
            confidence=0.40,
            citation_indices=[],
            reasoning="Not supported.",
            escalation_reason="Low confidence: 0.40 below 0.70",
        )
    )

    state = {
        "query": "Analyze the indemnification clause",
        "matter_id": "matter1",
        "user_id": "user1",
        "metadata": {},
    }

    result = await run_contract_analyst(
        state=state,
        retriever=mock_retriever,
        reranker=mock_reranker,
        llm=mock_llm,
        guard=failing_guard,
    )

    assert result["requires_human_review"] is True


@pytest.mark.asyncio
async def test_legal_drafter_agent(mock_retriever, mock_reranker, mock_guard):
    """Legal drafter should return three risk-tolerance variants."""
    from agents.legal_drafter import run_legal_drafter

    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=json.dumps({
            "aggressive": {
                "text": "Licensee shall indemnify to the fullest extent permitted by law.",
                "precedent_citation": "c0",
                "risk_notes": "Maximum exposure for counterparty.",
            },
            "standard": {
                "text": "Licensee shall indemnify Licensor against third-party claims.",
                "precedent_citation": "c1",
                "risk_notes": "Market standard.",
            },
            "conservative": {
                "text": "Licensee indemnifies only for gross negligence.",
                "precedent_citation": "c2",
                "risk_notes": "Narrow scope.",
            },
            "drafting_notes": "Three variants provided.",
            "jurisdiction_considerations": "Delaware law applies.",
        })
    )

    state = {
        "query": "Draft an indemnification clause",
        "matter_id": "matter1",
        "user_id": "user1",
        "metadata": {"jurisdiction": "Delaware"},
    }

    result = await run_legal_drafter(
        state=state,
        retriever=mock_retriever,
        reranker=mock_reranker,
        llm=mock_llm,
        guard=mock_guard,
    )

    output = result["agent_outputs"]["legal_drafter"]["output"]
    assert "aggressive" in output
    assert "standard" in output
    assert "conservative" in output


@pytest.mark.asyncio
async def test_classify_intent():
    """Intent classifier should return a valid intent string."""
    from agents.orchestrator import classify_intent

    mock_llm_client = AsyncMock()
    mock_llm_client.complete = AsyncMock(
        return_value=json.dumps({
            "intent": "contract_review",
            "sub_tasks": ["identify risky clauses", "check for missing standard clauses"],
            "confidence": 0.95,
        })
    )

    with patch("agents.orchestrator.llm_client", mock_llm_client):
        state = {
            "session_id": "test-session",
            "query": "Review the indemnification clause in this contract",
            "matter_id": "matter1",
            "user_id": "user1",
            "intent": "",
            "sub_tasks": [],
            "agent_outputs": {},
            "retrieved_chunks": [],
            "final_output": "",
            "confidence": 0.0,
            "requires_human_review": False,
            "metadata": {},
            "stream_callback": None,
        }
        result = await classify_intent(state)

    assert result["intent"] == "contract_review"
    assert len(result["sub_tasks"]) >= 1


@pytest.mark.asyncio
async def test_route_to_agents():
    """Router should return correct agent nodes for each intent."""
    from agents.orchestrator import route_to_agents

    assert "contract_analyst_node" in route_to_agents({"intent": "contract_review"})
    assert "case_researcher_node" in route_to_agents({"intent": "case_research"})
    assert "compliance_monitor_node" in route_to_agents({"intent": "compliance_check"})
    assert "legal_drafter_node" in route_to_agents({"intent": "drafting"})
    assert "litigation_risk_node" in route_to_agents({"intent": "litigation_risk"})
