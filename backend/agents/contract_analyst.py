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

_SYSTEM = """You are an expert contract analyst. You identify clause risks, dependencies, and conflicts.

Given a contract query and relevant clauses, produce a JSON response with this exact structure:
{
  "clauses": [
    {
      "clause_id": "string — chunk_id from source",
      "risk_level": "low|medium|high|critical",
      "risk_explanation": "specific explanation with exact clause text cited",
      "dependent_clauses": ["list of section headings or IDs this clause depends on"],
      "recommended_action": "specific remediation step",
      "jurisdiction_notes": "jurisdiction-specific risk if applicable"
    }
  ],
  "missing_standard_clauses": ["list of standard clauses absent from this contract"],
  "overall_risk": "low|medium|high|critical",
  "summary": "2-3 sentence executive summary"
}

Rules:
- Cite exact clause text in risk_explanation (quote the relevant portion)
- Flag missing standard clauses: limitation of liability, indemnification, dispute resolution, governing law, etc.
- Note jurisdiction-specific risks explicitly if governing law metadata is present
- Be specific — vague observations are not useful
"""


async def run_contract_analyst(
    state: dict[str, Any],
    retriever: HybridRetriever,
    reranker: FlashRankReranker,
    llm: AzureLLMClient,
    guard: HallucinationGuard,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = state["query"]
    matter_id = state["matter_id"]

    logger.info("contract_analyst_start", matter_id=matter_id, query_preview=query[:80])

    # Retrieve and rerank
    chunks = await retriever.retrieve(query, matter_id, top_k=100, final_top_k=30)
    ranked = await asyncio.to_thread(reranker.rerank, query, chunks, top_k=15)

    top_score = ranked[0].rerank_score if ranked else 0.0
    logger.info(
        "contract_analyst_retrieved",
        chunk_count=len(chunks),
        reranked_count=len(ranked),
        top_rerank_score=round(top_score, 4),
    )

    # Build context
    context = _build_context(ranked)

    raw_output = await llm.complete(
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Query: {query}\n\nRelevant Contract Clauses:\n{context}",
            }
        ],
        temperature=0.1,
        max_tokens=4096,
        trace_name="contract_analyst",
    )

    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        output = {"raw": raw_output, "parse_error": True}

    # Hallucination guard on summary claim
    summary = output.get("summary", raw_output[:300])
    guard_result = await guard.validate(summary, ranked)

    elapsed = time.perf_counter() - t0
    logger.info(
        "contract_analyst_complete",
        matter_id=matter_id,
        guard_passed=guard_result.passed,
        guard_confidence=round(guard_result.confidence, 4),
        elapsed_ms=round(elapsed * 1000, 2),
    )

    return {
        "agent_outputs": {
            "contract_analyst": {
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
            f"[{i}] chunk_id={chunk.chunk_id} | {chunk.clause_type} | "
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
