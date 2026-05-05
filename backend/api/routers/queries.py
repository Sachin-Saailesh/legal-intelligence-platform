import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.logging import get_logger
from db.models import AgentSession, Matter, SourceChunk, User
from db.session import get_db

router = APIRouter(prefix="/api/queries", tags=["queries"])
logger = get_logger(__name__)

# In-memory queue: session_id -> asyncio.Queue of frames
_stream_queues: dict[str, asyncio.Queue] = {}
# Pending orchestrator params: session_id -> params dict
_pending_sessions: dict[str, dict] = {}


class QueryCreate(BaseModel):
    query: str
    matter_id: str
    metadata: dict | None = None


async def _run_orchestrator(
    query: str,
    matter_id: str,
    user_id: str,
    session_id: str,
    metadata: dict | None,
) -> None:
    queue = _stream_queues.get(session_id)

    async def stream_callback(frame: dict) -> None:
        if queue:
            await queue.put(frame)

    try:
        from agents.orchestrator import run_session as _run
        await _run(
            query=query,
            matter_id=matter_id,
            user_id=user_id,
            metadata=metadata,
            stream_callback=stream_callback,
            session_id=session_id,
        )
    except Exception as e:
        logger.error("orchestrator_error", session_id=session_id, error=str(e))
        if queue:
            await queue.put({"type": "error", "message": str(e)})
    finally:
        if queue:
            await queue.put(None)  # sentinel: stream done

        # Defer cleanup to allow reconnects to drain the queue
        async def _cleanup():
            await asyncio.sleep(60)
            _stream_queues.pop(session_id, None)
            _pending_sessions.pop(session_id, None)
        asyncio.create_task(_cleanup())


@router.post("")
async def create_query(
    body: QueryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify matter
    result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(body.matter_id),
            Matter.firm_id == current_user.firm_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Matter not found")

    session_id = str(uuid.uuid4())
    _stream_queues[session_id] = asyncio.Queue(maxsize=500)
    _pending_sessions[session_id] = {
        "query": body.query,
        "matter_id": body.matter_id,
        "user_id": str(current_user.id),
        "metadata": body.metadata,
    }

    return {"data": {"session_id": session_id}, "error": None}


@router.get("")
async def list_sessions(
    matter_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
):
    matter_result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(matter_id),
            Matter.firm_id == current_user.firm_id,
        )
    )
    if not matter_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Matter not found")

    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.matter_id == uuid.UUID(matter_id))
        .order_by(AgentSession.created_at.asc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return {
        "data": [
            {
                "id": str(s.id),
                "matter_id": str(s.matter_id),
                "query_text": s.query_text,
                "final_output": s.final_output,
                "confidence_score": s.confidence_score,
                "status": s.status,
                "agent_route": s.agent_route,
                "review_reason": s.review_reason,
                "created_at": s.created_at.isoformat(),
                "source_chunks": [],
            }
            for s in sessions
        ],
        "error": None,
    }


@router.websocket("/{session_id}/stream")
async def stream_session(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()
    queue = _stream_queues.get(session_id)

    if not queue:
        # Session not found — already completed or expired
        await websocket.close()
        return

    # Start the orchestrator task here, inside the active WebSocket request.
    # Cloud Run keeps CPU allocated for the duration of any active HTTP connection
    # (WebSockets included), so this avoids the CPU-throttling issue that kills
    # tasks started as FastAPI BackgroundTasks after the POST response is sent.
    params = _pending_sessions.pop(session_id, None)
    if params:
        asyncio.create_task(_run_orchestrator(session_id=session_id, **params))

    try:
        while True:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue

            if frame is None:
                break

            await websocket.send_text(json.dumps(frame))

        await websocket.close()
    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", session_id=session_id)
    finally:
        pass  # DO NOT pop the queue here to allow reconnects


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify matter belongs to firm
    matter_result = await db.execute(
        select(Matter).where(
            Matter.id == session.matter_id,
            Matter.firm_id == current_user.firm_id,
        )
    )
    if not matter_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    chunks_result = await db.execute(
        select(SourceChunk)
        .where(SourceChunk.session_id == uuid.UUID(session_id))
        .order_by(SourceChunk.rank_position)
    )
    chunks = chunks_result.scalars().all()

    return {
        "data": {
            "id": str(session.id),
            "matter_id": str(session.matter_id),
            "query_text": session.query_text,
            "final_output": session.final_output,
            "confidence_score": session.confidence_score,
            "status": session.status,
            "agent_route": session.agent_route,
            "review_reason": session.review_reason,
            "created_at": session.created_at.isoformat(),
            "source_chunks": [
                {
                    "id": str(c.id),
                    "text": c.chunk_text,
                    "source_doc_id": str(c.source_doc_id) if c.source_doc_id else None,
                    "page_number": c.page_number,
                    "confidence_score": c.confidence_score,
                    "rank_position": c.rank_position,
                }
                for c in chunks
            ],
        },
        "error": None,
    }
