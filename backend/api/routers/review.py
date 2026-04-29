import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.models import AgentSession, AttorneyCorrection, Matter, SessionStatus, User
from db.session import get_db

router = APIRouter(prefix="/api/review", tags=["review"])


class ApproveBody(BaseModel):
    corrected_output: str | None = None
    correction_type: str | None = None


class RejectBody(BaseModel):
    reason: str


@router.get("/queue")
async def get_review_queue(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Get all matters for this firm
    matters_result = await db.execute(
        select(Matter.id).where(Matter.firm_id == current_user.firm_id)
    )
    matter_ids = [row[0] for row in matters_result.fetchall()]

    if not matter_ids:
        return {"data": [], "error": None}

    sessions_result = await db.execute(
        select(AgentSession)
        .where(
            AgentSession.matter_id.in_(matter_ids),
            AgentSession.status == SessionStatus.pending_review,
        )
        .order_by(AgentSession.created_at.desc())
    )
    sessions = sessions_result.scalars().all()

    return {
        "data": [
            {
                "id": str(s.id),
                "matter_id": str(s.matter_id),
                "user_id": str(s.user_id),
                "query_text": s.query_text,
                "final_output": s.final_output,
                "confidence_score": s.confidence_score,
                "agent_route": s.agent_route,
                "review_reason": s.review_reason,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ],
        "error": None,
    }


@router.post("/{session_id}/approve")
async def approve_session(
    session_id: str,
    body: ApproveBody,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = await _get_session_for_firm(session_id, current_user, db)

    session.status = SessionStatus.approved
    if body.corrected_output and body.corrected_output != session.final_output:
        correction = AttorneyCorrection(
            id=uuid.uuid4(),
            session_id=uuid.UUID(session_id),
            original_output=session.final_output or "",
            corrected_output=body.corrected_output,
            correction_type=body.correction_type or "factual",
        )
        db.add(correction)
        session.final_output = body.corrected_output

        # Re-ingest corrected output as high-weight chunk
        background_tasks.add_task(
            _reingest_correction,
            session_id=session_id,
            corrected_text=body.corrected_output,
            matter_id=str(session.matter_id),
        )

    await db.commit()
    return {"data": {"session_id": session_id, "status": "approved"}, "error": None}


@router.post("/{session_id}/reject")
async def reject_session(
    session_id: str,
    body: RejectBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = await _get_session_for_firm(session_id, current_user, db)
    session.status = SessionStatus.rejected
    session.final_output = f"[REJECTED] {body.reason}\n\nOriginal output:\n{session.final_output}"
    await db.commit()
    return {"data": {"session_id": session_id, "status": "rejected"}, "error": None}


async def _get_session_for_firm(
    session_id: str, user: User, db: AsyncSession
) -> AgentSession:
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    matter_result = await db.execute(
        select(Matter).where(
            Matter.id == session.matter_id,
            Matter.firm_id == user.firm_id,
        )
    )
    if not matter_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status != SessionStatus.pending_review:
        raise HTTPException(status_code=400, detail=f"Session is not pending review (status: {session.status})")

    return session


async def _reingest_correction(session_id: str, corrected_text: str, matter_id: str) -> None:
    """Re-ingest attorney correction as a high-weight chunk in the vector store."""
    from api.main import app
    from rag.embeddings import embedding_client
    from core.config import settings
    import uuid as uuid_mod
    from qdrant_client.models import PointStruct

    try:
        vector = await embedding_client.embed_text(corrected_text)
        chunk_id = f"correction_{session_id}"
        point = PointStruct(
            id=str(uuid_mod.uuid5(uuid_mod.NAMESPACE_DNS, chunk_id)),
            vector=vector,
            payload={
                "chunk_id": chunk_id,
                "doc_id": f"correction_{session_id}",
                "matter_id": matter_id,
                "page_number": 0,
                "chunk_index": 0,
                "clause_type": "attorney_correction",
                "section_heading": "Attorney Correction",
                "text": corrected_text,
                "is_correction": True,
            },
        )
        app.state.qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=[point],
            wait=True,
        )
    except Exception as e:
        from core.logging import get_logger
        get_logger(__name__).error("correction_reingest_failed", error=str(e))
