import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.models import DiscoveryItem, Matter, TimelineEvent, User
from db.session import get_db

router = APIRouter(tags=["global"])


def _serialize_event_with_matter(e: TimelineEvent, matter_title: str) -> dict:
    return {
        "id": str(e.id),
        "matter_id": str(e.matter_id),
        "matter_title": matter_title,
        "event_type": e.event_type,
        "title": e.title,
        "description": e.description,
        "event_date": e.event_date.isoformat(),
        "status": e.status,
        "source": e.source,
        "document_ref": e.document_ref,
        "created_at": e.created_at.isoformat(),
    }


def _serialize_item_with_matter(item: DiscoveryItem, matter_title: str) -> dict:
    return {
        "id": str(item.id),
        "matter_id": str(item.matter_id),
        "matter_title": matter_title,
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


@router.get("/api/timeline")
async def list_all_timeline_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    matter_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
):
    """Return all timeline events across all matters for the firm."""
    # Get firm matter IDs + titles
    matters_result = await db.execute(
        select(Matter).where(Matter.firm_id == current_user.firm_id)
    )
    matters = matters_result.scalars().all()
    matter_map = {m.id: m.title for m in matters}

    if not matter_map:
        return {"data": [], "error": None}

    # Filter to single matter if requested
    if matter_id:
        try:
            mid = uuid.UUID(matter_id)
            if mid not in matter_map:
                return {"data": [], "error": None}
            target_ids = [mid]
        except ValueError:
            return {"data": [], "error": None}
    else:
        target_ids = list(matter_map.keys())

    query = select(TimelineEvent).where(TimelineEvent.matter_id.in_(target_ids))
    if event_type:
        query = query.where(TimelineEvent.event_type == event_type)
    if status:
        query = query.where(TimelineEvent.status == status)
    query = query.order_by(TimelineEvent.event_date.asc())

    result = await db.execute(query)
    events = result.scalars().all()

    # Auto-mark overdue
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

    return {
        "data": [
            _serialize_event_with_matter(e, matter_map.get(e.matter_id, "Unknown Matter"))
            for e in events
        ],
        "error": None,
    }


@router.get("/api/discovery")
async def list_all_discovery_items(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    matter_id: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
):
    """Return all discovery items across all matters for the firm."""
    matters_result = await db.execute(
        select(Matter).where(Matter.firm_id == current_user.firm_id)
    )
    matters = matters_result.scalars().all()
    matter_map = {m.id: m.title for m in matters}

    if not matter_map:
        return {"data": [], "error": None}

    if matter_id:
        try:
            mid = uuid.UUID(matter_id)
            if mid not in matter_map:
                return {"data": [], "error": None}
            target_ids = [mid]
        except ValueError:
            return {"data": [], "error": None}
    else:
        target_ids = list(matter_map.keys())

    query = select(DiscoveryItem).where(DiscoveryItem.matter_id.in_(target_ids))
    if item_type:
        query = query.where(DiscoveryItem.item_type == item_type)
    if status:
        query = query.where(DiscoveryItem.status == status)
    if priority:
        query = query.where(DiscoveryItem.priority == priority)
    query = query.order_by(DiscoveryItem.deadline.asc().nullslast(), DiscoveryItem.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    # Auto-mark overdue
    now = datetime.now(timezone.utc)
    changed = False
    for item in items:
        if item.deadline and item.status in ("pending", "in_progress"):
            dl = item.deadline if item.deadline.tzinfo else item.deadline.replace(tzinfo=timezone.utc)
            if dl < now:
                item.status = "overdue"
                changed = True
    if changed:
        await db.commit()

    # Sort by priority rank
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    items_sorted = sorted(
        items,
        key=lambda i: (priority_rank.get(i.priority, 9), i.deadline or datetime.max),
    )

    return {
        "data": [
            _serialize_item_with_matter(i, matter_map.get(i.matter_id, "Unknown Matter"))
            for i in items_sorted
        ],
        "error": None,
    }


@router.get("/api/discovery/global-stats")
async def global_discovery_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Aggregated discovery stats across all firm matters."""
    matters_result = await db.execute(
        select(Matter.id).where(Matter.firm_id == current_user.firm_id)
    )
    matter_ids = [row[0] for row in matters_result.fetchall()]

    if not matter_ids:
        return {
            "data": {
                "total": 0, "pending": 0, "in_progress": 0, "overdue": 0,
                "completed": 0, "responded": 0, "objected": 0,
                "by_type": {}, "by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            },
            "error": None,
        }

    result = await db.execute(
        select(DiscoveryItem).where(DiscoveryItem.matter_id.in_(matter_ids))
    )
    items = result.scalars().all()

    now = datetime.now(timezone.utc)
    stats = {
        "total": len(items),
        "pending": 0, "in_progress": 0, "overdue": 0,
        "completed": 0, "responded": 0, "objected": 0,
        "by_type": {},
        "by_priority": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    }
    for item in items:
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
