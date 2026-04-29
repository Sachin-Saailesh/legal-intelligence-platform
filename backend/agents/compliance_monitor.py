import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import Any

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from core.config import settings
from core.logging import get_logger
from db.models import ComplianceAlert, AlertSeverity, Matter
from rag.embeddings import AzureLLMClient
from rag.hallucination_guard import HallucinationGuard
from rag.reranker import FlashRankReranker
from rag.retriever import HybridRetriever

logger = get_logger(__name__)

_DIFF_SYSTEM = """You are a regulatory compliance analyst. You compare two versions of a regulation
and identify material changes that would affect law firm clients.

Given the old and new regulatory text, produce JSON:
{
  "has_material_changes": true,
  "delta_summary": "Clear 2-3 sentence description of what changed and why it matters",
  "affected_practice_areas": ["list of practice areas affected"],
  "effective_date": "YYYY-MM-DD or null if not specified",
  "severity": "low|medium|high|critical",
  "action_required": "what attorneys should do in response"
}

Severity guide:
- critical: immediate compliance action required, deadline within 30 days
- high: significant change requiring client notification within 90 days
- medium: notable change for monitoring and next contract review cycle
- low: minor clarification or non-material amendment
"""

_MATCH_SYSTEM = """You are a compliance relevance classifier. Given a regulation change and a matter's
metadata (type, jurisdiction, practice area, industry), determine if the regulation is relevant.

Respond with JSON:
{
  "is_relevant": true,
  "relevance_score": 0.85,
  "reason": "why this regulation affects this matter"
}
"""


async def _fetch_federal_register(session: aiohttp.ClientSession, query: str) -> list[dict]:
    """Fetch recent documents from the Federal Register API."""
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {
        "conditions[term]": query,
        "conditions[type][]": ["Rule", "Proposed Rule", "Notice"],
        "order": "newest",
        "per_page": 20,
        "fields[]": ["title", "abstract", "document_number", "publication_date",
                     "html_url", "full_text_xml_url", "agencies"],
    }
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("results", [])
    except Exception as e:
        logger.warning("federal_register_fetch_failed", error=str(e))
    return []


async def _fetch_sec_edgar(session: aiohttp.ClientSession, query: str) -> list[dict]:
    """Fetch recent SEC guidance from EDGAR full-text search."""
    url = "https://efts.sec.gov/LATEST/search-index?q=%22" + query.replace(" ", "%20") + "%22&dateRange=custom&startdt=2024-01-01&forms=33-Act,34-Act"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                hits = data.get("hits", {}).get("hits", [])
                return [
                    {
                        "title": h["_source"].get("file_date", "") + " - " + h["_source"].get("form_type", ""),
                        "abstract": h["_source"].get("entity_name", ""),
                        "html_url": f"https://www.sec.gov/Archives/edgar/{h['_source'].get('file_date','').replace('-','/')}/{h['_id']}",
                        "publication_date": h["_source"].get("file_date", ""),
                    }
                    for h in hits[:10]
                ]
    except Exception as e:
        logger.warning("sec_edgar_fetch_failed", error=str(e))
    return []


async def fetch_regulatory_updates(practice_areas: list[str]) -> list[dict]:
    """Aggregate regulatory updates from multiple sources."""
    queries = practice_areas if practice_areas else ["securities", "employment", "privacy", "antitrust"]
    all_docs: list[dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for query in queries[:3]:  # limit to 3 queries
            tasks.append(_fetch_federal_register(session, query))
            tasks.append(_fetch_sec_edgar(session, query))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            all_docs.extend(result)

    return all_docs


def _doc_fingerprint(doc: dict) -> str:
    content = f"{doc.get('title','')}{doc.get('abstract','')}{doc.get('publication_date','')}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def run_compliance_monitor(
    state: dict[str, Any],
    retriever: HybridRetriever,
    reranker: FlashRankReranker,
    llm: AzureLLMClient,
    guard: HallucinationGuard,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    matter_id = state["matter_id"]
    query = state.get("query", "regulatory compliance changes")

    logger.info("compliance_monitor_start", matter_id=matter_id)

    # Retrieve context from matter corpus
    import asyncio
    chunks = await retriever.retrieve(query, matter_id, top_k=50, final_top_k=10)
    ranked = await asyncio.to_thread(reranker.rerank, query, chunks, top_k=5)

    # Fetch live regulatory updates
    practice_areas = state.get("metadata", {}).get("practice_areas", ["general"])
    reg_docs = await fetch_regulatory_updates(practice_areas)

    if not reg_docs:
        logger.info("compliance_monitor_no_updates", matter_id=matter_id)
        return {
            "agent_outputs": {
                "compliance_monitor": {
                    "output": {
                        "alerts": [],
                        "summary": "No new regulatory updates found for this matter.",
                    }
                }
            },
            "retrieved_chunks": [],
        }

    # Analyze each regulatory document against matter context
    alerts = []
    matter_context = "\n".join([c.text[:300] for c in ranked[:5]])

    for doc in reg_docs[:10]:
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")
        url = doc.get("html_url", "")
        pub_date = doc.get("publication_date", "")

        # Check relevance to matter
        relevance_raw = await llm.complete(
            system=_MATCH_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Regulation: {title}\nSummary: {abstract[:500]}\n\n"
                        f"Matter Context:\n{matter_context}"
                    ),
                }
            ],
            temperature=0,
            max_tokens=300,
            trace_name="compliance_relevance_check",
        )
        try:
            relevance = json.loads(relevance_raw)
        except json.JSONDecodeError:
            continue

        if not relevance.get("is_relevant") or relevance.get("relevance_score", 0) < 0.5:
            continue

        # Generate delta analysis
        delta_raw = await llm.complete(
            system=_DIFF_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Regulation Title: {title}\n"
                        f"Publication Date: {pub_date}\n"
                        f"Abstract/Content: {abstract[:1500]}\n\n"
                        f"Matter Practice Area: {', '.join(practice_areas)}"
                    ),
                }
            ],
            temperature=0.1,
            max_tokens=600,
            trace_name="compliance_delta_analysis",
        )
        try:
            delta = json.loads(delta_raw)
        except json.JSONDecodeError:
            continue

        if not delta.get("has_material_changes"):
            continue

        alert_data = {
            "regulation_title": title,
            "regulation_url": url,
            "delta_summary": delta.get("delta_summary", abstract[:500]),
            "severity": delta.get("severity", AlertSeverity.medium),
            "effective_date": delta.get("effective_date"),
            "action_required": delta.get("action_required", ""),
            "affected_practice_areas": delta.get("affected_practice_areas", []),
        }
        alerts.append(alert_data)

        # Persist to DB if context available
        if db:
            import uuid
            from sqlalchemy import insert
            await db.execute(
                insert(ComplianceAlert).values(
                    id=uuid.uuid4(),
                    matter_id=matter_id,
                    regulation_title=title,
                    regulation_url=url,
                    delta_summary=delta.get("delta_summary", ""),
                    severity=delta.get("severity", AlertSeverity.medium),
                )
            )
            await db.commit()

    guard_result = await guard.validate(
        f"Found {len(alerts)} new regulatory alerts for this matter.",
        ranked,
    )

    elapsed = time.perf_counter() - t0
    logger.info(
        "compliance_monitor_complete",
        matter_id=matter_id,
        alerts_found=len(alerts),
        guard_passed=guard_result.passed,
        elapsed_ms=round(elapsed * 1000, 2),
    )

    return {
        "agent_outputs": {
            "compliance_monitor": {
                "output": {
                    "alerts": alerts,
                    "summary": f"Found {len(alerts)} regulatory changes requiring attention.",
                },
                "guard": {
                    "passed": guard_result.passed,
                    "confidence": guard_result.confidence,
                },
            }
        },
        "retrieved_chunks": [_chunk_to_dict(c) for c in ranked],
        "requires_human_review": len(alerts) > 0 and not guard_result.passed,
    }


def _chunk_to_dict(chunk) -> dict:
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
