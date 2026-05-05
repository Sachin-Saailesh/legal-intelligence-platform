import asyncio
import json
import time
from typing import Any

from core.logging import get_logger
from rag.embeddings import AzureLLMClient
from rag.hallucination_guard import HallucinationGuard
from rag.reranker import FlashRankReranker, RankedChunk
from rag.retriever import HybridRetriever

logger = get_logger(__name__)

_SYSTEM = """You are a litigation risk analyst. You predict litigation outcomes based on case facts
and analogous precedents.

IMPORTANT: Your probability estimates must be grounded in the provided case law sources.
Do not fabricate win probabilities — they must reflect the actual precedent landscape.

Produce JSON with this exact structure:
{
  "win_probability": 0.65,
  "confidence_interval": [0.52, 0.78],
  "key_factors": [
    {
      "factor": "description of risk/strength factor",
      "impact": "positive|negative|neutral",
      "weight": "high|medium|low",
      "supporting_precedent": "case name if applicable"
    }
  ],
  "analogous_cases": [
    {
      "case_name": "Parties v. Parties, Court Year",
      "citation": "formal citation",
      "outcome": "plaintiff|defendant|settlement",
      "key_similarity": "what makes this case analogous",
      "distinguishing_factors": "how this case differs",
      "chunk_id": "source chunk_id"
    }
  ],
  "recommendation": "strategic recommendation in 3-5 sentences",
  "settlement_range": {
    "low": 500000,
    "high": 2000000,
    "currency": "USD",
    "rationale": "basis for range estimate"
  },
  "risk_summary": "2-3 sentence executive summary of litigation risk"
}

Rules:
- win_probability must be between 0.0 and 1.0 (from defendant's perspective unless otherwise stated)
- confidence_interval must reflect genuine uncertainty; narrow intervals require strong precedent support
- analogous_cases must cite chunk_ids from the provided sources
- settlement_range is optional — include only if damages are quantifiable from the sources
- Flag if the probability estimate has low confidence due to limited precedent
"""


async def run_litigation_risk(
    state: dict[str, Any],
    retriever: HybridRetriever,
    reranker: FlashRankReranker,
    llm: AzureLLMClient,
    guard: HallucinationGuard,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = state["query"]
    matter_id = state["matter_id"]

    logger.info("litigation_risk_start", matter_id=matter_id, query_preview=query[:80])

    # Retrieve from matter and case law concurrently
    matter_chunks, caselaw_chunks = await asyncio.gather(
        retriever.retrieve(query, matter_id, top_k=100, final_top_k=20),
        retriever.retrieve(query, "caselaw", top_k=100, final_top_k=20)
    )

    all_chunks = matter_chunks + caselaw_chunks
    ranked = await asyncio.to_thread(reranker.rerank, query, all_chunks, top_k=10)

    top_score = ranked[0].rerank_score if ranked else 0.0
    logger.info(
        "litigation_risk_retrieved",
        matter_chunks=len(matter_chunks),
        caselaw_chunks=len(caselaw_chunks),
        reranked_count=len(ranked),
        top_rerank_score=round(top_score, 4),
    )

    context = _build_context(ranked)
    jurisdiction = state.get("metadata", {}).get("jurisdiction", "not specified")

    raw_output = await llm.complete(
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Case/Query: {query}\n"
                    f"Jurisdiction: {jurisdiction}\n\n"
                    f"Relevant Sources:\n{context}"
                ),
            }
        ],
        temperature=0.1,
        max_tokens=4096,
        trace_name="litigation_risk",
    )

    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        output = {"raw": raw_output, "parse_error": True}

    risk_summary = output.get("risk_summary", raw_output[:300])
    guard_result = await guard.validate(risk_summary, ranked)

    elapsed = time.perf_counter() - t0
    logger.info(
        "litigation_risk_complete",
        matter_id=matter_id,
        win_probability=output.get("win_probability"),
        guard_passed=guard_result.passed,
        guard_confidence=round(guard_result.confidence, 4),
        elapsed_ms=round(elapsed * 1000, 2),
    )

    return {
        "agent_outputs": {
            "litigation_risk": {
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


def _build_context(chunks: list[RankedChunk]) -> str:
    parts = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[{i}] chunk_id={chunk.chunk_id} | page={chunk.page_number} | "
            f"score={chunk.rerank_score:.3f}\n{chunk.text}"
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
