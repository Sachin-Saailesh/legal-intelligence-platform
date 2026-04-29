import json
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.logging import get_logger
from db.models import AgentSession, DiscoveryItem, Matter, SourceChunk, TimelineEvent, User
from db.session import get_db

router = APIRouter(prefix="/api/matters/{matter_id}/discovery", tags=["discovery"])
logger = get_logger(__name__)

# ── Pydantic schemas ─────────────────────────────────────────────────────────


class DiscoveryCreate(BaseModel):
    item_type: str = "other"
    title: str
    description: str | None = None
    deadline: str | None = None  # ISO-8601
    status: str = "pending"
    priority: str = "medium"
    assigned_to: str | None = None
    notes: str | None = None


class DiscoveryUpdate(BaseModel):
    item_type: str | None = None
    title: str | None = None
    description: str | None = None
    deadline: str | None = None
    status: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    notes: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _serialize_item(item: DiscoveryItem) -> dict:
    return {
        "id": str(item.id),
        "matter_id": str(item.matter_id),
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "status": item.status,
        "priority": item.priority,
        "assigned_to": item.assigned_to,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
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
async def list_discovery_items(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    item_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
):
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    query = select(DiscoveryItem).where(DiscoveryItem.matter_id == matter_uuid)
    if item_type:
        query = query.where(DiscoveryItem.item_type == item_type)
    if status:
        query = query.where(DiscoveryItem.status == status)
    if priority:
        query = query.where(DiscoveryItem.priority == priority)

    # Priority sort: critical > high > medium > low, then by deadline
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    query = query.order_by(DiscoveryItem.deadline.asc().nullslast(), DiscoveryItem.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    # Auto-mark overdue: pending/in_progress items past their deadline
    now = datetime.now(timezone.utc)
    changed = False
    for item in items:
        if item.deadline and item.status in ("pending", "in_progress"):
            deadline_dt = item.deadline
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
            if deadline_dt < now:
                item.status = "overdue"
                changed = True
    if changed:
        await db.commit()

    # Sort by priority after auto-update
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items_sorted = sorted(items, key=lambda i: (priority_rank.get(i.priority, 9), i.deadline or datetime.max.replace(tzinfo=timezone.utc)))

    return {"data": [_serialize_item(i) for i in items_sorted], "error": None}


@router.get("/stats")
async def discovery_stats(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    result = await db.execute(
        select(DiscoveryItem).where(DiscoveryItem.matter_id == matter_uuid)
    )
    items = result.scalars().all()

    now = datetime.now(timezone.utc)
    stats = {
        "total": len(items),
        "pending": 0,
        "in_progress": 0,
        "overdue": 0,
        "completed": 0,
        "responded": 0,
        "objected": 0,
        "by_type": {},
        "by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    }
    for item in items:
        # Auto-compute overdue without writing to DB here
        effective_status = item.status
        if item.deadline and item.status in ("pending", "in_progress"):
            dl = item.deadline if item.deadline.tzinfo else item.deadline.replace(tzinfo=timezone.utc)
            if dl < now:
                effective_status = "overdue"

        if effective_status in stats:
            stats[effective_status] += 1

        stats["by_type"][item.item_type] = stats["by_type"].get(item.item_type, 0) + 1
        if item.priority in stats["by_priority"]:
            stats["by_priority"][item.priority] += 1

    return {"data": stats, "error": None}


@router.post("")
async def create_discovery_item(
    matter_id: str,
    body: DiscoveryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    item = DiscoveryItem(
        matter_id=matter_uuid,
        item_type=body.item_type,
        title=body.title,
        description=body.description,
        deadline=datetime.fromisoformat(body.deadline) if body.deadline else None,
        status=body.status,
        priority=body.priority,
        assigned_to=body.assigned_to,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"data": _serialize_item(item), "error": None}


@router.patch("/{item_id}")
async def update_discovery_item(
    matter_id: str,
    item_id: str,
    body: DiscoveryUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_matter(matter_id, current_user.firm_id, db)

    result = await db.execute(
        select(DiscoveryItem).where(DiscoveryItem.id == uuid.UUID(item_id))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Discovery item not found")

    for field, value in body.model_dump(exclude_none=True).items():
        if field == "deadline":
            setattr(item, field, datetime.fromisoformat(value) if value else None)
        else:
            setattr(item, field, value)

    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return {"data": _serialize_item(item), "error": None}


@router.delete("/{item_id}")
async def delete_discovery_item(
    matter_id: str,
    item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_matter(matter_id, current_user.firm_id, db)

    result = await db.execute(
        select(DiscoveryItem).where(DiscoveryItem.id == uuid.UUID(item_id))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Discovery item not found")

    await db.delete(item)
    await db.commit()
    return {"data": {"deleted": item_id}, "error": None}


@router.post("/analyze-patterns")
async def analyze_patterns(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Use GPT-4o to analyze timeline events + discovery items for patterns and risks."""
    matter_uuid = await _verify_matter(matter_id, current_user.firm_id, db)

    # Fetch timeline events
    ev_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.matter_id == matter_uuid)
        .order_by(TimelineEvent.event_date.asc())
    )
    events = ev_result.scalars().all()

    # Fetch discovery items
    di_result = await db.execute(
        select(DiscoveryItem)
        .where(DiscoveryItem.matter_id == matter_uuid)
        .order_by(DiscoveryItem.deadline.asc().nullslast())
    )
    items = di_result.scalars().all()

    if not events and not items:
        return {
            "data": {
                "patterns": [],
                "summary": "No timeline events or discovery items to analyze yet.",
                "recommendations": ["Add timeline events or discovery items to enable pattern analysis."],
            },
            "error": None,
        }

    # Build structured context for the LLM
    events_text = "\n".join(
        f"- [{e.event_type.upper()}] {e.event_date.strftime('%Y-%m-%d')} | {e.title} | status:{e.status}"
        for e in events
    ) or "None"

    now = datetime.now(timezone.utc)
    items_text = "\n".join(
        f"- [{i.item_type.upper()}] priority:{i.priority} | {i.title} | "
        f"deadline:{i.deadline.strftime('%Y-%m-%d') if i.deadline else 'none'} | status:{i.status}"
        for i in items
    ) or "None"

    prompt = (
        f"TIMELINE EVENTS:\n{events_text}\n\n"
        f"DISCOVERY ITEMS:\n{items_text}\n\n"
        f"Today's date: {now.strftime('%Y-%m-%d')}\n\n"
        "Analyze the above for patterns, risks, and actionable insights. "
        "Return ONLY a valid JSON object:\n"
        '{"patterns": [{"type": "<timeline_gap|deadline_cluster|overdue_risk|discovery_pattern|sequence_anomaly|missing_step>", '
        '"title": "<short title>", "description": "<2-3 sentence detail>", '
        '"severity": "<info|warning|critical>", "items": ["<brief ref>"]}], '
        '"summary": "<2 sentence overall summary>", '
        '"recommendations": ["<action 1>", "<action 2>", "<action 3>"]}'
    )

    from rag.embeddings import llm_client

    try:
        raw = await llm_client.complete(
            system=(
                "You are a legal case analytics AI specializing in discovery process analysis. "
                "Identify meaningful patterns and actionable risks. Return valid JSON only."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2048,
            trace_name="discovery_pattern_analysis",
        )
        data = _parse_json_safe(raw)
        if not data:
            raise ValueError("empty response")
    except Exception as exc:
        logger.error("pattern_analysis_error", error=str(exc))
        return {
            "data": {
                "patterns": [],
                "summary": "Analysis failed. Please try again.",
                "recommendations": [],
            },
            "error": None,
        }

    logger.info("pattern_analysis_success", matter_id=matter_id, pattern_count=len(data.get("patterns", [])))
    return {
        "data": {
            "patterns": data.get("patterns", []),
            "summary": data.get("summary", ""),
            "recommendations": data.get("recommendations", []),
        },
        "error": None,
    }
