import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.models import ComplianceAlert, AlertStatus, Matter, User
from db.session import get_db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertStatusUpdate(BaseModel):
    status: str


@router.get("")
async def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    matter_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    # Get matter IDs for firm
    matters_result = await db.execute(
        select(Matter.id).where(Matter.firm_id == current_user.firm_id)
    )
    firm_matter_ids = [row[0] for row in matters_result.fetchall()]

    query = select(ComplianceAlert).where(
        ComplianceAlert.matter_id.in_(firm_matter_ids)
    )
    if matter_id:
        query = query.where(ComplianceAlert.matter_id == uuid.UUID(matter_id))
    if severity:
        query = query.where(ComplianceAlert.severity == severity)
    if status:
        query = query.where(ComplianceAlert.status == status)

    # Sort: critical first, then by creation date
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    query = query.order_by(ComplianceAlert.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return {
        "data": [
            {
                "id": str(a.id),
                "matter_id": str(a.matter_id) if a.matter_id else None,
                "regulation_title": a.regulation_title,
                "regulation_url": a.regulation_url,
                "delta_summary": a.delta_summary,
                "severity": a.severity,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
        "error": None,
    }


@router.patch("/{alert_id}")
async def update_alert_status(
    alert_id: str,
    body: AlertStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if body.status not in {AlertStatus.read, AlertStatus.dismissed}:
        raise HTTPException(status_code=400, detail="Invalid status. Use 'read' or 'dismissed'")

    result = await db.execute(
        select(ComplianceAlert).where(ComplianceAlert.id == uuid.UUID(alert_id))
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Verify belongs to firm
    if alert.matter_id:
        matter_result = await db.execute(
            select(Matter).where(
                Matter.id == alert.matter_id,
                Matter.firm_id == current_user.firm_id,
            )
        )
        if not matter_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    alert.status = body.status
    await db.commit()
    return {"data": {"alert_id": alert_id, "status": body.status}, "error": None}
