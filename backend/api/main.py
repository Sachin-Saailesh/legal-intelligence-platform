from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("lexmind_startup", env=settings.app_env)

    # Postgres connection & migrations
    from db.session import engine
    from db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Qdrant client + collection bootstrap
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    qdrant = QdrantClient(url=settings.qdrant_url)
    existing = [c.name for c in qdrant.get_collections().collections]
    if settings.qdrant_collection not in existing:
        qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimensions,
                distance=Distance.COSINE,
            ),
        )
        logger.info("qdrant_collection_created", collection=settings.qdrant_collection)
    app.state.qdrant_client = qdrant

    # Neo4j
    from graph.neo4j_client import Neo4jClient
    neo4j = Neo4jClient()
    await neo4j.connect()
    await neo4j.create_schema_constraints()
    app.state.neo4j_client = neo4j

    # Redis
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.redis_client = redis_client

    # Init orchestrator singletons
    from rag.embeddings import embedding_client, llm_client
    from rag.retriever import HybridRetriever
    from rag.hallucination_guard import HallucinationGuard
    from agents.orchestrator import init_orchestrator

    retriever = HybridRetriever(
        embedding_client=embedding_client,
        qdrant_client=qdrant,
        redis_client=redis_client,
    )
    guard = HallucinationGuard(llm_client=llm_client)
    init_orchestrator(retriever, guard)
    app.state.retriever = retriever
    app.state.guard = guard

    # Upload dir
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    logger.info("lexmind_ready")
    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    await neo4j.close()
    await redis_client.aclose()
    await engine.dispose()
    logger.info("lexmind_shutdown")


app = FastAPI(
    title="LexMind API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"data": None, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
    )


@app.get("/api/health")
async def health():
    return {"data": {"status": "ok"}, "error": None}


@app.get("/api/dashboard/stats")
async def dashboard_stats():
    from db.session import AsyncSessionFactory
    from db.models import Matter, AgentSession, ComplianceAlert, AlertStatus, SessionStatus, User
    from sqlalchemy import select, func

    async with AsyncSessionFactory() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            return {"data": {"open_matters": 0, "pending_reviews": 0, "unread_alerts": 0, "recent_sessions": []}, "error": None}

        open_matters = await db.scalar(
            select(func.count(Matter.id)).where(
                Matter.firm_id == user.firm_id,
                Matter.status == "active",
            )
        )
        pending_reviews = await db.scalar(
            select(func.count(AgentSession.id)).where(
                AgentSession.status == SessionStatus.pending_review
            )
        )
        # Get matter IDs for firm
        firm_matters = await db.execute(select(Matter.id).where(Matter.firm_id == user.firm_id))
        firm_matter_ids = [row[0] for row in firm_matters.fetchall()]

        unread_alerts = await db.scalar(
            select(func.count(ComplianceAlert.id)).where(
                ComplianceAlert.matter_id.in_(firm_matter_ids),
                ComplianceAlert.status == AlertStatus.unread,
            )
        ) if firm_matter_ids else 0

        recent_sessions = await db.execute(
            select(AgentSession)
            .where(AgentSession.matter_id.in_(firm_matter_ids))
            .order_by(AgentSession.created_at.desc())
            .limit(5)
        )
        sessions = recent_sessions.scalars().all()

    return {
        "data": {
            "open_matters": open_matters or 0,
            "pending_reviews": pending_reviews or 0,
            "unread_alerts": unread_alerts or 0,
            "recent_sessions": [
                {
                    "id": str(s.id),
                    "matter_id": str(s.matter_id),
                    "query_text": s.query_text[:100],
                    "status": s.status,
                    "created_at": s.created_at.isoformat(),
                }
                for s in sessions
            ],
        },
        "error": None,
    }


# ── Register routers ──────────────────────────────────────────────────────────

from api.routers import matters, documents, queries, review, alerts

app.include_router(matters.router)
app.include_router(documents.router)
app.include_router(queries.router)
app.include_router(review.router)
app.include_router(alerts.router)
