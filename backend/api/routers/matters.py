import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.models import Matter, MatterStatus, MatterType, User
from db.session import get_db

router = APIRouter(prefix="/api/matters", tags=["matters"])


class MatterCreate(BaseModel):
    title: str
    matter_type: str
    jurisdiction: str | None = None
    practice_area: str | None = None
    industry: str | None = None


class MatterUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    jurisdiction: str | None = None
    practice_area: str | None = None
    industry: str | None = None


def _matter_response(m: Matter) -> dict:
    return {
        "id": str(m.id),
        "firm_id": str(m.firm_id),
        "title": m.title,
        "matter_type": m.matter_type,
        "status": m.status,
        "jurisdiction": m.jurisdiction,
        "practice_area": m.practice_area,
        "industry": m.industry,
        "created_at": m.created_at.isoformat(),
    }


@router.get("")
async def list_matters(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Matter).where(Matter.firm_id == current_user.firm_id).order_by(Matter.created_at.desc())
    )
    matters = result.scalars().all()
    return {"data": [_matter_response(m) for m in matters], "error": None}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_matter(
    body: MatterCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    matter = Matter(
        id=uuid.uuid4(),
        firm_id=current_user.firm_id,
        title=body.title,
        matter_type=body.matter_type,
        status=MatterStatus.active,
        jurisdiction=body.jurisdiction,
        practice_area=body.practice_area,
        industry=body.industry,
    )
    db.add(matter)
    await db.commit()
    await db.refresh(matter)
    return {"data": _matter_response(matter), "error": None}


@router.get("/{matter_id}")
async def get_matter(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(matter_id),
            Matter.firm_id == current_user.firm_id,
        )
    )
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    return {"data": _matter_response(matter), "error": None}


@router.patch("/{matter_id}")
async def update_matter(
    matter_id: str,
    body: MatterUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(matter_id),
            Matter.firm_id == current_user.firm_id,
        )
    )
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    updates = body.model_dump(exclude_none=True)
    if updates:
        await db.execute(
            update(Matter).where(Matter.id == uuid.UUID(matter_id)).values(**updates)
        )
        await db.commit()
        await db.refresh(matter)

    return {"data": _matter_response(matter), "error": None}
