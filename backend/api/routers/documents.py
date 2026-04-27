import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.config import settings
from core.logging import get_logger
from db.models import Document, IngestionStatus, Matter, User
from db.session import get_db, AsyncSessionFactory

router = APIRouter(prefix="/api/matters", tags=["documents"])
logger = get_logger(__name__)


async def _run_ingestion(document_id: str) -> None:
    from rag.ingestion import DocumentIngestionPipeline
    from rag.embeddings import embedding_client, llm_client
    from graph.neo4j_client import Neo4jClient

    async with AsyncSessionFactory() as db:
        result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        document = result.scalar_one_or_none()
        if not document:
            logger.error("ingestion_doc_not_found", document_id=document_id)
            return

        # Get qdrant client from app state
        from api.main import app
        qdrant = app.state.qdrant_client
        neo4j = app.state.neo4j_client

        pipeline = DocumentIngestionPipeline(
            embedding_client=embedding_client,
            llm_client=llm_client,
            qdrant_client=qdrant,
            neo4j_client=neo4j,
        )
        await pipeline.ingest(document, db)


@router.post("/{matter_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    matter_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify matter belongs to user's firm
    result = await db.execute(
        select(Matter).where(
            Matter.id == uuid.UUID(matter_id),
            Matter.firm_id == current_user.firm_id,
        )
    )
    matter = result.scalar_one_or_none()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")

    # Validate size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.max_upload_size_mb}MB",
        )

    # Save to disk
    upload_dir = Path(settings.upload_dir) / matter_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    filename = file.filename or f"{doc_id}"
    file_path = upload_dir / f"{doc_id}_{filename}"
    file_path.write_bytes(contents)

    # Detect doc type from extension
    ext = Path(filename).suffix.lower().lstrip(".")
    doc_type_map = {
        "pdf": "pdf",
        "docx": "contract",
        "doc": "contract",
        "txt": "text",
    }
    doc_type = doc_type_map.get(ext, ext)

    document = Document(
        id=doc_id,
        matter_id=uuid.UUID(matter_id),
        filename=filename,
        file_path=str(file_path),
        doc_type=doc_type,
        ingestion_status=IngestionStatus.pending,
    )
    db.add(document)
    await db.commit()

    background_tasks.add_task(_run_ingestion, str(doc_id))

    return {
        "data": {
            "id": str(doc_id),
            "matter_id": matter_id,
            "filename": filename,
            "doc_type": doc_type,
            "ingestion_status": IngestionStatus.pending,
        },
        "error": None,
    }


@router.get("/{matter_id}/documents")
async def list_documents(
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
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Matter not found")

    docs_result = await db.execute(
        select(Document)
        .where(Document.matter_id == uuid.UUID(matter_id))
        .order_by(Document.created_at.desc())
    )
    docs = docs_result.scalars().all()
    return {
        "data": [
            {
                "id": str(d.id),
                "matter_id": matter_id,
                "filename": d.filename,
                "doc_type": d.doc_type,
                "ingestion_status": d.ingestion_status,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "error": None,
    }
