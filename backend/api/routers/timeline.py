import json
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.logging import get_logger
from db.models import AgentSession, DiscoveryItem, Matter, SourceChunk, TimelineEvent, User
from db.session import get_db

router = APIRouter(prefix="/api/matters/{matter_id}/timeline", tags=["timeline"])
logger = get_logger(__name__)

# ── Pydantic schemas ─────────────────────────────────────────────────────────


class EventCreate(BaseModel):
    event_type: str = "other"
    title: str
    description: str | None = None
    event_date: str  # ISO-8601 string
    status: str = "upcoming"
    document_ref: str | None = None
    source: str = "manual"


class EventUpdate(BaseModel):
    event_type: str | None = None
    title: str | None = None
    description: str | None = None
    event_date: str | None = None
    status: str | None = None
    document_ref: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _serialize_event(e: TimelineEvent) -> dict:
    return {
        "id": str(e.id),
        "matter_id": str(e.matter_id),
        "event_type": e.event_type,
        "title": e.title,
        "description": e.description,
        "event_date": e.event_date.isoformat(),
        "status": e.status,
        "source": e.source,
        "document_ref": e.document_ref,
        "created_at": e.created_at.isoformat(),
    }


async def _verify_matter(matter_id: str, firm_id: uuid.UUID, db: AsyncSession) -> uuid.UUID:
    result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(matter_id),
            Matter.firm_id == firm_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Matter not found")
    return uuid.UUID(matter_id)


def _parse_json_safe(text: str) -> dict:
    """Try json.loads; fall back to extracting the first {...} block."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("")
async def list_timeline_events(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    event_type: str | None = None,
    status: str | None = None,
):
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    query = select(TimelineEvent).where(TimelineEvent.matter_id == matter_uuid)
    if event_type:
        query = query.where(TimelineEvent.event_type == event_type)
    if status:
        query = query.where(TimelineEvent.status == status)
    query = query.order_by(TimelineEvent.event_date.asc())

    result = await db.execute(query)
    events = result.scalars().all()

    # Auto-mark overdue: upcoming events whose date has passed
    now = datetime.now(timezone.utc)
    changed = False
    for ev in events:
        event_dt = ev.event_date
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        if ev.status == "upcoming" and event_dt < now:
            ev.status = "overdue"
            changed = True
    if changed:
        await db.commit()

    return {"data": [_serialize_event(e) for e in events], "error": None}


@router.post("")
async def create_timeline_event(
    matter_id: str,
    body: EventCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    event = TimelineEvent(
        matter_id=matter_uuid,
        event_type=body.event_type,
        title=body.title,
        description=body.description,
        event_date=datetime.fromisoformat(body.event_date),
        status=body.status,
        source=body.source,
        document_ref=body.document_ref,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"data": _serialize_event(event), "error": None}


@router.patch("/{event_id}")
async def update_timeline_event(
    matter_id: str,
    event_id: str,
    body: EventUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_matter(matter_id, current_user.firm_id, db)

    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.id == uuid.UUID(event_id))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if body.event_type is not None:
        event.event_type = body.event_type
    if body.title is not None:
        event.title = body.title
    if body.description is not None:
        event.description = body.description
    if body.event_date is not None:
        event.event_date = datetime.fromisoformat(body.event_date)
    if body.status is not None:
        event.status = body.status
    if body.document_ref is not None:
        event.document_ref = body.document_ref

    await db.commit()
    await db.refresh(event)
    return {"data": _serialize_event(event), "error": None}


@router.delete("/{event_id}")
async def delete_timeline_event(
    matter_id: str,
    event_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_matter(matter_id, current_user.firm_id, db)

    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.id == uuid.UUID(event_id))
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(event)
    await db.commit()
    return {"data": {"deleted": event_id}, "error": None}


@router.post("/extract")
async def extract_timeline_from_documents(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Use GPT-4o to extract timeline events from stored document chunks."""
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    # Gather source chunks from all sessions under this matter
    chunks_result = await db.execute(
        select(SourceChunk.chunk_text)
        .join(AgentSession, AgentSession.id == SourceChunk.session_id)
        .where(AgentSession.matter_id == matter_uuid)
        .order_by(SourceChunk.rank_position.asc().nullslast())
        .limit(40)
    )
    chunk_texts = [row[0] for row in chunks_result.fetchall()]

    if not chunk_texts:
        return {
            "data": {"events": [], "message": "No document content found. Upload and query documents first."},
            "error": None,
        }

    context = "\n\n---\n\n".join(chunk_texts[:40])

    from rag.embeddings import llm_client

    prompt = (
        "Extract all significant legal timeline events from the following document excerpts. "
        "Return ONLY a valid JSON object with this exact structure:\n"
        '{"events": [{"event_type": "<filing|hearing|deposition|deadline|discovery|settlement|motion|order|other>", '
        '"title": "<concise title>", "description": "<brief details>", "event_date": "<YYYY-MM-DD>", '
        '"document_ref": "<short source reference or null>"}]}\n\n'
        "Only include events with a clearly identifiable date. If the year is ambiguous, omit the event.\n\n"
        f"DOCUMENT EXCERPTS:\n{context}"
    )

    try:
        raw = await llm_client.complete(
            system=(
                "You are a precise legal timeline extraction assistant. "
                "Extract only events with clear dates. Return valid JSON only, no commentary."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
            trace_name="timeline_extract",
        )
        data = _parse_json_safe(raw)
        events = data.get("events", [])
    except Exception as exc:
        logger.error("timeline_extract_error", error=str(exc))
        return {"data": {"events": [], "message": "AI extraction failed. Try again."}, "error": None}

    logger.info("timeline_extract_success", matter_id=matter_id, event_count=len(events))
    return {"data": {"events": events, "message": None}, "error": None}


@router.post("/bulk-save")
async def bulk_save_extracted_events(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: dict,
):
    """Save a list of AI-extracted events after user review."""
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    raw_events: list[dict] = body.get("events", [])
    created = []
    for ev in raw_events:
        try:
            event = TimelineEvent(
                matter_id=matter_uuid,
                event_type=ev.get("event_type", "other"),
                title=ev.get("title", "Untitled"),
                description=ev.get("description"),
                event_date=datetime.fromisoformat(ev["event_date"]),
                status="upcoming",
                source="ai_extracted",
                document_ref=ev.get("document_ref"),
            )
            db.add(event)
            created.append(event)
        except (KeyError, ValueError):
            continue  # skip malformed entries

    await db.commit()
    for e in created:
        await db.refresh(e)
    return {"data": {"saved": len(created)}, "error": None}
