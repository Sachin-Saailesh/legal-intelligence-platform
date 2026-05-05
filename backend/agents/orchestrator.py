"""LangGraph master DAG for LexMind multi-agent orchestration."""
import asyncio
import json
import time
import uuid
from typing import Any, Annotated, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from typing_extensions import TypedDict

from core.config import settings
from core.logging import get_logger
from rag.embeddings import AzureLLMClient, embedding_client, llm_client
from rag.hallucination_guard import HallucinationGuard
from rag.reranker import FlashRankReranker, reranker
from rag.retriever import HybridRetriever

logger = get_logger(__name__)

# ── Intent thresholds ─────────────────────────────────────────────────────────
# Higher-stakes intents require tighter grounding before auto-approval.
INTENT_THRESHOLDS: dict[str, float] = {
    "contract_review": 0.85,   # direct clause analysis — client exposure
    "drafting":        0.85,   # generating legal text — must be source-grounded
    "litigation_risk": 0.87,   # probability predictions — highest bar
    "case_research":   0.72,   # exploratory; attorney reads sources anyway
    "compliance_check":0.72,   # regulatory updates; moderate tolerance
}
DEFAULT_THRESHOLD = 0.72

# ── State schema ───────────────────────────────────────────────────────────────

Intent = Literal[
    "contract_review",
    "case_research",
    "compliance_check",
    "drafting",
    "litigation_risk",
]


class LexMindState(TypedDict):
    query: str
    matter_id: str
    user_id: str
    intent: str
    sub_tasks: list[str]
    agent_outputs: dict[str, Any]
    retrieved_chunks: list[dict]
    final_output: str
    confidence: float
    requires_human_review: bool
    review_reason: str          # accumulated explanation of why review was triggered
    session_id: str
    metadata: dict[str, Any]
    stream_callback: Any  # optional async callable for WebSocket streaming


# ── Intent classification ──────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """You are a legal query classifier. Classify the query into exactly one intent
and decompose it into sub-tasks.

Intents:
- contract_review: Analyzing contract clauses, risks, or terms
- case_research: Finding relevant case law, precedents, or legal authority
- compliance_check: Checking regulatory compliance or regulatory changes
- drafting: Generating or revising contract clauses or legal documents
- litigation_risk: Predicting litigation outcomes or assessing case risk

Respond with JSON only:
{
  "intent": "one of the five intents above",
  "sub_tasks": ["list of 2-4 specific sub-tasks to complete this query"],
  "confidence": 0.95
}
"""


async def classify_intent(state: LexMindState) -> dict:
    logger.info(
        "classify_intent_start",
        session_id=state["session_id"],
        query_preview=state["query"][:80],
    )
    raw = await llm_client.complete(
        system=_CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": state["query"]}],
        temperature=0,
        max_tokens=300,
        trace_name="classify_intent",
    )
    try:
        result = json.loads(raw)
        intent = result.get("intent", "case_research")
        sub_tasks = result.get("sub_tasks", [state["query"]])
    except json.JSONDecodeError:
        intent = "case_research"
        sub_tasks = [state["query"]]

    logger.info(
        "classify_intent_complete",
        session_id=state["session_id"],
        intent=intent,
        sub_tasks=sub_tasks,
    )

    if state.get("stream_callback"):
        await state["stream_callback"]({"type": "intent_classified", "intent": intent})

    return {"intent": intent, "sub_tasks": sub_tasks, "review_reason": ""}


# ── Routing ───────────────────────────────────────────────────────────────────

def route_to_agents(state: LexMindState) -> list[str]:
    """Return the list of agent node names to invoke based on intent."""
    intent = state.get("intent", "case_research")
    routing_map = {
        "contract_review": ["contract_analyst_node"],
        "case_research": ["case_researcher_node"],
        "compliance_check": ["compliance_monitor_node"],
        "drafting": ["legal_drafter_node", "contract_analyst_node"],
        "litigation_risk": ["litigation_risk_node", "case_researcher_node"],
    }
    return routing_map.get(intent, ["case_researcher_node"])


# ── Agent node builders ────────────────────────────────────────────────────────

def _make_agent_node(agent_fn, name: str):
    async def node(state: LexMindState) -> dict:
        if state.get("stream_callback"):
            await state["stream_callback"]({"type": "agent_start", "agent": name})

        from agents.orchestrator import _retriever, _guard
        result = await agent_fn(
            state,
            retriever=_retriever,
            reranker=reranker,
            llm=llm_client,
            guard=_guard,
        )

        # Merge agent_outputs
        merged_agent_outputs = dict(state.get("agent_outputs", {}))
        merged_agent_outputs.update(result.get("agent_outputs", {}))

        # Merge retrieved_chunks (union, deduplicate by chunk_id)
        existing_chunks = {c["chunk_id"]: c for c in state.get("retrieved_chunks", [])}
        for c in result.get("retrieved_chunks", []):
            existing_chunks[c["chunk_id"]] = c

        # Re-adjudicate using intent-specific threshold instead of guard's default.
        # Agents always expose guard.confidence in their agent_outputs.
        intent = state.get("intent", "case_research")
        threshold = INTENT_THRESHOLDS.get(intent, DEFAULT_THRESHOLD)
        agent_guard_conf = (
            result.get("agent_outputs", {})
            .get(name, {})
            .get("guard", {})
            .get("confidence")
        )

        review_reason = state.get("review_reason", "")
        if agent_guard_conf is not None:
            actually_requires_review = agent_guard_conf < threshold
            if actually_requires_review:
                line = (
                    f"{name.replace('_', ' ')} confidence {agent_guard_conf*100:.0f}% "
                    f"is below the {threshold*100:.0f}% threshold required for {intent.replace('_', ' ')} queries"
                )
                review_reason = (review_reason + "; " + line).lstrip("; ")
        else:
            # Agent didn't surface guard confidence — fall back to its own decision
            actually_requires_review = result.get("requires_human_review", False)

        requires_review = state.get("requires_human_review", False) or actually_requires_review

        return {
            "agent_outputs": merged_agent_outputs,
            "retrieved_chunks": list(existing_chunks.values()),
            "requires_human_review": requires_review,
            "review_reason": review_reason,
        }

    node.__name__ = name
    return node


# ── Synthesis node ─────────────────────────────────────────────────────────────

_SYNTH_SYSTEM = """You are a senior legal analyst synthesizing outputs from multiple specialist agents.
Produce a comprehensive, well-structured response that:
1. Directly answers the original query
2. Synthesizes findings from all agents that ran
3. Highlights the most important risks or findings
4. Provides clear, actionable recommendations
5. Cites specific sources by their chunk_id

Format your response in clear sections with markdown headers.
Be precise and professional. Do not speculate beyond what the sources support."""


async def synthesize(state: LexMindState) -> dict:
    logger.info(
        "synthesize_start",
        session_id=state["session_id"],
        agents_ran=list(state.get("agent_outputs", {}).keys()),
    )

    agent_summary = json.dumps(state.get("agent_outputs", {}), indent=2)[:6000]
    chunks = state.get("retrieved_chunks", [])[:10]

    from agents.orchestrator import _guard

    if state.get("stream_callback"):
        await state["stream_callback"]({"type": "agent_start", "agent": "synthesizer"})

    final_output = await llm_client.complete(
        system=_SYNTH_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Original Query: {state['query']}\n\n"
                    f"Agent Outputs:\n{agent_summary}\n\n"
                    f"Top Retrieved Chunks:\n"
                    + "\n".join(f"[{c['chunk_id']}] {c['text'][:400]}" for c in chunks)
                ),
            }
        ],
        temperature=0.1,
        max_tokens=2048,
        trace_name="synthesize",
    )
    if state.get("stream_callback"):
        await state["stream_callback"]({"type": "chunk", "text": final_output})

    # Mandatory hallucination guard on final synthesis — uses intent-specific threshold
    from rag.reranker import RankedChunk
    ranked_chunks = [
        RankedChunk(
            chunk_id=c.get("chunk_id", ""),
            doc_id=c.get("doc_id", ""),
            matter_id=state["matter_id"],
            text=c.get("text", ""),
            page_number=c.get("page_number", 0),
            rerank_score=c.get("rerank_score", 0.0),
        )
        for c in chunks
    ]
    guard_result = await _guard.validate(final_output[:500], ranked_chunks)

    intent = state.get("intent", "case_research")
    threshold = INTENT_THRESHOLDS.get(intent, DEFAULT_THRESHOLD)
    synth_passed = guard_result.confidence >= threshold
    confidence = guard_result.confidence

    review_reason = state.get("review_reason", "")

    # If upstream specialists already flagged review, note that the synthesizer may have passed
    upstream_requires_review = state.get("requires_human_review", False)
    if not synth_passed:
        synth_line = (
            f"synthesizer confidence {confidence*100:.0f}% is below the "
            f"{threshold*100:.0f}% threshold for {intent.replace('_', ' ')} queries"
        )
        review_reason = (review_reason + "; " + synth_line).lstrip("; ")
    elif upstream_requires_review and review_reason:
        # Synthesizer passed but a specialist didn't — make this explicit
        review_reason = (
            review_reason
            + f"; synthesizer passed at {confidence*100:.0f}% — review triggered by specialist agent"
        )

    requires_review = upstream_requires_review or not synth_passed

    if state.get("stream_callback"):
        for c in chunks:
            await state["stream_callback"]({"type": "citation", "chunk": c})
        await state["stream_callback"](
            {
                "type": "complete",
                "confidence": confidence,
                "requires_review": requires_review,
                "review_reason": review_reason or None,
            }
        )

    logger.info(
        "synthesize_complete",
        session_id=state["session_id"],
        synth_guard_passed=synth_passed,
        confidence=round(confidence, 4),
        requires_review=requires_review,
        intent=intent,
        threshold=threshold,
        output_len=len(final_output),
    )

    return {
        "final_output": final_output,
        "confidence": confidence,
        "requires_human_review": requires_review,
        "review_reason": review_reason,
    }


# ── Human review gate ─────────────────────────────────────────────────────────

async def human_review_gate(state: LexMindState) -> dict:
    from db.session import AsyncSessionFactory
    from db.models import AgentSession, SessionStatus, SourceChunk
    import uuid as uuid_mod
    from sqlalchemy import update, insert

    session_id = state["session_id"]

    async with AsyncSessionFactory() as db:
        if state.get("requires_human_review"):
            await db.execute(
                update(AgentSession)
                .where(AgentSession.id == uuid_mod.UUID(session_id))
                .values(
                    status=SessionStatus.pending_review,
                    final_output=state.get("final_output"),
                    confidence_score=state.get("confidence"),
                    agent_route=json.dumps(list(state.get("agent_outputs", {}).keys())),
                    review_reason=state.get("review_reason") or None,
                )
            )
            logger.info("human_review_gate_halted", session_id=session_id)
        else:
            await db.execute(
                update(AgentSession)
                .where(AgentSession.id == uuid_mod.UUID(session_id))
                .values(status=SessionStatus.complete)
            )
        await db.commit()

    return {"session_id": session_id}


# ── Store output node ──────────────────────────────────────────────────────────

async def store_output(state: LexMindState) -> dict:
    from db.session import AsyncSessionFactory
    from db.models import AgentSession, SessionStatus, SourceChunk
    import uuid as uuid_mod
    from sqlalchemy import update, insert

    session_id = state["session_id"]

    async with AsyncSessionFactory() as db:
        await db.execute(
            update(AgentSession)
            .where(AgentSession.id == uuid_mod.UUID(session_id))
            .values(
                status=SessionStatus.complete,
                final_output=state.get("final_output"),
                confidence_score=state.get("confidence"),
                agent_route=json.dumps(list(state.get("agent_outputs", {}).keys())),
                review_reason=state.get("review_reason") or None,
            )
        )

        # Store source chunks
        for i, chunk in enumerate(state.get("retrieved_chunks", [])[:20]):
            doc_id_str = chunk.get("doc_id")
            doc_id = uuid_mod.UUID(doc_id_str) if doc_id_str else None
            await db.execute(
                insert(SourceChunk).values(
                    id=uuid_mod.uuid4(),
                    session_id=uuid_mod.UUID(session_id),
                    chunk_text=chunk.get("text", "")[:2000],
                    source_doc_id=doc_id,
                    page_number=chunk.get("page_number"),
                    confidence_score=chunk.get("rerank_score"),
                    rank_position=i,
                )
            )
        await db.commit()

    logger.info("store_output_complete", session_id=session_id)
    return {"session_id": session_id}


# ── Routing function for conditional edges ─────────────────────────────────────

def needs_review(state: LexMindState) -> Literal["store_output", "human_review_gate"]:
    if state.get("requires_human_review"):
        return "human_review_gate"
    return "store_output"


# ── Module-level singletons (set in main.py lifespan) ─────────────────────────
_retriever: HybridRetriever | None = None
_guard: HallucinationGuard | None = None


def init_orchestrator(retriever: HybridRetriever, guard: HallucinationGuard) -> None:
    global _retriever, _guard
    _retriever = retriever
    _guard = guard


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph(checkpointer=None) -> StateGraph:
    from agents.contract_analyst import run_contract_analyst
    from agents.case_researcher import run_case_researcher
    from agents.compliance_monitor import run_compliance_monitor
    from agents.legal_drafter import run_legal_drafter
    from agents.litigation_risk import run_litigation_risk

    workflow = StateGraph(LexMindState)

    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("contract_analyst_node", _make_agent_node(run_contract_analyst, "contract_analyst"))
    workflow.add_node("case_researcher_node", _make_agent_node(run_case_researcher, "case_researcher"))
    workflow.add_node("compliance_monitor_node", _make_agent_node(run_compliance_monitor, "compliance_monitor"))
    workflow.add_node("legal_drafter_node", _make_agent_node(run_legal_drafter, "legal_drafter"))
    workflow.add_node("litigation_risk_node", _make_agent_node(run_litigation_risk, "litigation_risk"))
    workflow.add_node("synthesize", synthesize)
    workflow.add_node("human_review_gate", human_review_gate)
    workflow.add_node("store_output", store_output)

    workflow.set_entry_point("classify_intent")

    # After classification, fan out to relevant agents
    workflow.add_conditional_edges(
        "classify_intent",
        route_to_agents,
        {
            "contract_analyst_node": "contract_analyst_node",
            "case_researcher_node": "case_researcher_node",
            "compliance_monitor_node": "compliance_monitor_node",
            "legal_drafter_node": "legal_drafter_node",
            "litigation_risk_node": "litigation_risk_node",
        },
    )

    # All agent nodes converge at synthesize
    for node in [
        "contract_analyst_node",
        "case_researcher_node",
        "compliance_monitor_node",
        "legal_drafter_node",
        "litigation_risk_node",
    ]:
        workflow.add_edge(node, "synthesize")

    workflow.add_conditional_edges(
        "synthesize",
        needs_review,
        {"store_output": "store_output", "human_review_gate": "human_review_gate"},
    )
    workflow.add_edge("human_review_gate", END)
    workflow.add_edge("store_output", END)

    return workflow.compile(checkpointer=checkpointer)


# ── Public API ────────────────────────────────────────────────────────────────

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_session(
    query: str,
    matter_id: str,
    user_id: str,
    metadata: dict | None = None,
    stream_callback=None,
    session_id: str | None = None,
) -> str:
    """Create and run an agent session. Returns session_id."""
    import uuid as uuid_mod
    from db.session import AsyncSessionFactory
    from db.models import AgentSession
    from sqlalchemy import insert

    session_id = session_id or str(uuid_mod.uuid4())

    # Upsert session record: the POST handler pre-creates it with status="pending",
    # so we just update to "processing". If for some reason it doesn't exist yet, insert.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    async with AsyncSessionFactory() as db:
        await db.execute(
            pg_insert(AgentSession).values(
                id=uuid_mod.UUID(session_id),
                matter_id=uuid_mod.UUID(matter_id),
                user_id=uuid_mod.UUID(user_id),
                query_text=query,
                status="processing",
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={"status": "processing"},
            )
        )
        await db.commit()

    initial_state: LexMindState = {
        "query": query,
        "matter_id": matter_id,
        "user_id": user_id,
        "intent": "",
        "sub_tasks": [],
        "agent_outputs": {},
        "retrieved_chunks": [],
        "final_output": "",
        "confidence": 0.0,
        "requires_human_review": False,
        "review_reason": "",
        "session_id": session_id,
        "metadata": metadata or {},
        "stream_callback": stream_callback,
    }

    t0 = time.perf_counter()
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        logger.error("session_failed", session_id=session_id, error=str(e))
        from db.session import AsyncSessionFactory
        from db.models import AgentSession, SessionStatus
        from sqlalchemy import update
        import uuid as uuid_mod

        async with AsyncSessionFactory() as db:
            await db.execute(
                update(AgentSession)
                .where(AgentSession.id == uuid_mod.UUID(session_id))
                .values(status=SessionStatus.complete, final_output=f"Error: {str(e)}")
            )
            await db.commit()
        raise

    elapsed = time.perf_counter() - t0
    logger.info("session_complete", session_id=session_id, elapsed_s=round(elapsed, 2))
    return session_id
