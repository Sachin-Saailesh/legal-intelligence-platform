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
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, VectorParams

    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    collections_response = await qdrant.get_collections()
    existing = [c.name for c in collections_response.collections]
    if settings.qdrant_collection not in existing:
        await qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimensions,
                distance=Distance.COSINE,
            ),
        )
        logger.info("qdrant_collection_created", collection=settings.qdrant_collection)

    # Ensure payload index exists on matter_id — required for filtered search/scroll
    # in Qdrant server 1.12+. create_payload_index is idempotent.
    from qdrant_client.models import PayloadSchemaType
    await qdrant.create_payload_index(
        collection_name=settings.qdrant_collection,
        field_name="matter_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    logger.info("qdrant_index_ensured", field="matter_id")
    app.state.qdrant_client = qdrant

    # Neo4j (optional — disabled in cloud deployment via NEO4J_ENABLED=false)
    neo4j = None
    if settings.neo4j_enabled:
        from graph.neo4j_client import Neo4jClient
        neo4j = Neo4jClient()
        await neo4j.connect()
        await neo4j.create_schema_constraints()
        logger.info("neo4j_connected")
    else:
        logger.info("neo4j_disabled")
    app.state.neo4j_client = neo4j

    # Redis (optional — used for BM25 cache and Celery; disabled via REDIS_ENABLED=false)
    redis_client = None
    if settings.redis_enabled:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        logger.info("redis_connected")
    else:
        logger.info("redis_disabled")
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
    if neo4j:
        await neo4j.close()
    if redis_client:
        await redis_client.aclose()
    await qdrant.close()
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
    allow_origin_regex=r"https://.*\.vercel\.app",
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
    from datetime import datetime, timezone, timedelta
    from db.session import AsyncSessionFactory
    from db.models import (
        Matter, AgentSession, ComplianceAlert, AlertStatus, SessionStatus,
        User, TimelineEvent, DiscoveryItem,
    )
    from sqlalchemy import select, func

    async with AsyncSessionFactory() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if not user:
            return {
                "data": {
                    "open_matters": 0, "pending_reviews": 0, "unread_alerts": 0,
                    "overdue_timeline": 0, "critical_deadlines": 0,
                    "recent_sessions": [], "upcoming_events": [], "critical_discovery": [],
                },
                "error": None,
            }

        open_matters = await db.scalar(
            select(func.count(Matter.id)).where(
                Matter.firm_id == user.firm_id, Matter.status == "active",
            )
        )
        pending_reviews = await db.scalar(
            select(func.count(AgentSession.id)).where(
                AgentSession.status == SessionStatus.pending_review
            )
        )

        firm_matters_result = await db.execute(
            select(Matter.id, Matter.title).where(Matter.firm_id == user.firm_id)
        )
        firm_matter_rows = firm_matters_result.fetchall()
        firm_matter_ids = [r[0] for r in firm_matter_rows]
        matter_titles = {r[0]: r[1] for r in firm_matter_rows}

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

        now = datetime.now(timezone.utc)
        week_ahead = now + timedelta(days=7)

        # Overdue timeline events count
        overdue_timeline = 0
        upcoming_events_list = []
        if firm_matter_ids:
            overdue_timeline = await db.scalar(
                select(func.count(TimelineEvent.id)).where(
                    TimelineEvent.matter_id.in_(firm_matter_ids),
                    TimelineEvent.status == "overdue",
                )
            ) or 0

            upcoming_result = await db.execute(
                select(TimelineEvent)
                .where(
                    TimelineEvent.matter_id.in_(firm_matter_ids),
                    TimelineEvent.status == "upcoming",
                    TimelineEvent.event_date >= now,
                )
                .order_by(TimelineEvent.event_date.asc())
                .limit(5)
            )
            for ev in upcoming_result.scalars().all():
                upcoming_events_list.append({
                    "id": str(ev.id),
                    "matter_id": str(ev.matter_id),
                    "matter_title": matter_titles.get(ev.matter_id, ""),
                    "event_type": ev.event_type,
                    "title": ev.title,
                    "event_date": ev.event_date.isoformat(),
                    "status": ev.status,
                })

        # Critical discovery deadlines (next 7 days or overdue)
        critical_deadlines_count = 0
        critical_discovery_list = []
        if firm_matter_ids:
            critical_deadlines_count = await db.scalar(
                select(func.count(DiscoveryItem.id)).where(
                    DiscoveryItem.matter_id.in_(firm_matter_ids),
                    DiscoveryItem.status.in_(["pending", "in_progress", "overdue"]),
                    DiscoveryItem.deadline <= week_ahead,
                )
            ) or 0

            deadline_result = await db.execute(
                select(DiscoveryItem)
                .where(
                    DiscoveryItem.matter_id.in_(firm_matter_ids),
                    DiscoveryItem.status.in_(["pending", "in_progress", "overdue"]),
                    DiscoveryItem.deadline.isnot(None),
                )
                .order_by(DiscoveryItem.deadline.asc())
                .limit(5)
            )
            for item in deadline_result.scalars().all():
                critical_discovery_list.append({
                    "id": str(item.id),
                    "matter_id": str(item.matter_id),
                    "matter_title": matter_titles.get(item.matter_id, ""),
                    "title": item.title,
                    "item_type": item.item_type,
                    "deadline": item.deadline.isoformat() if item.deadline else None,
                    "priority": item.priority,
                    "status": item.status,
                })

    return {
        "data": {
            "open_matters": open_matters or 0,
            "pending_reviews": pending_reviews or 0,
            "unread_alerts": unread_alerts or 0,
            "overdue_timeline": overdue_timeline,
            "critical_deadlines": critical_deadlines_count,
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
            "upcoming_events": upcoming_events_list,
            "critical_discovery": critical_discovery_list,
        },
        "error": None,
    }


# ── Register routers ──────────────────────────────────────────────────────────

from api.routers import matters, documents, queries, review, alerts, timeline, discovery, global_views

app.include_router(matters.router)
app.include_router(documents.router)
app.include_router(queries.router)
app.include_router(review.router)
app.include_router(alerts.router)
app.include_router(timeline.router)
app.include_router(discovery.router)
app.include_router(global_views.router)
