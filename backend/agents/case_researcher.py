import json
import time
from typing import Any

from core.logging import get_logger
from rag.embeddings import AzureLLMClient
from rag.hallucination_guard import HallucinationGuard
from rag.reranker import FlashRankReranker, RankedChunk
from rag.retriever import HybridRetriever

logger = get_logger(__name__)

_SYSTEM = """You are a legal research specialist. You identify relevant precedents and case law.

Given a legal research query and retrieved case law chunks, produce JSON with this exact structure:
{
  "cases": [
    {
      "case_name": "Parties v. Parties, Court Year",
      "citation": "formal legal citation",
      "relevance_score": 0.95,
      "key_holding": "The specific legal holding that is relevant to the query",
      "supporting_quote": "exact quote from the retrieved chunk",
      "chunk_id": "source chunk_id",
      "court": "court name",
      "year": 2023,
      "jurisdiction": "jurisdiction string"
    }
  ],
  "conflicting_precedents": [
    {
      "case_name": "string",
      "conflict_description": "how this case conflicts with the leading authority"
    }
  ],
  "circuit_split": "description of circuit split if applicable, or null",
  "research_summary": "3-4 sentence synthesis of the case law landscape",
  "recommended_cases_to_cite": ["top 3 case names to cite in briefing"]
}

Rules:
- Only include cases actually supported by the retrieved chunks — do not fabricate citations
- Extract supporting quotes verbatim from chunk text
- Note any circuit splits explicitly
- Flag conflicting precedents that could be used against the client's position
- Rank by relevance_score descending, return top 5
"""


async def run_case_researcher(
    state: dict[str, Any],
    retriever: HybridRetriever,
    reranker: FlashRankReranker,
    llm: AzureLLMClient,
    guard: HallucinationGuard,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    query = state["query"]
    matter_id = state["matter_id"]

    # Get matter jurisdiction from state metadata if available
    jurisdiction = state.get("metadata", {}).get("jurisdiction")

    logger.info(
        "case_researcher_start",
        matter_id=matter_id,
        query_preview=query[:80],
        jurisdiction=jurisdiction,
    )

    # Search both matter corpus and global case law collection concurrently
    import asyncio
    matter_chunks, caselaw_chunks = await asyncio.gather(
        retriever.retrieve(query, matter_id, top_k=100, jurisdiction=jurisdiction, final_top_k=20),
        retriever.retrieve(query, "caselaw", top_k=100, jurisdiction=jurisdiction, final_top_k=20)
    )

    all_chunks = matter_chunks + caselaw_chunks
    ranked = await asyncio.to_thread(reranker.rerank, query, all_chunks, top_k=10)

    top_score = ranked[0].rerank_score if ranked else 0.0
    logger.info(
        "case_researcher_retrieved",
        matter_chunk_count=len(matter_chunks),
        caselaw_chunk_count=len(caselaw_chunks),
        reranked_count=len(ranked),
        top_rerank_score=round(top_score, 4),
    )

    context = _build_context(ranked)

    raw_output = await llm.complete(
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Research Query: {query}\n\nJurisdiction: {jurisdiction or 'Not specified'}\n\nRetrieved Case Law:\n{context}",
            }
        ],
        temperature=0.1,
        max_tokens=4096,
        trace_name="case_researcher",
    )

    try:
        output = json.loads(raw_output)
    except json.JSONDecodeError:
        output = {"raw": raw_output, "parse_error": True}

    summary = output.get("research_summary", raw_output[:300])
    guard_result = await guard.validate(summary, ranked)

    elapsed = time.perf_counter() - t0
    logger.info(
        "case_researcher_complete",
        matter_id=matter_id,
        cases_found=len(output.get("cases", [])),
        guard_passed=guard_result.passed,
        guard_confidence=round(guard_result.confidence, 4),
        elapsed_ms=round(elapsed * 1000, 2),
    )

    return {
        "agent_outputs": {
            "case_researcher": {
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
