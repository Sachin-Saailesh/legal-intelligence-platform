"""Celery beat task for scheduled compliance monitoring."""
import asyncio
from celery import Celery
from celery.schedules import crontab

from core.config import settings

app = Celery(
    "lexmind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "monitor-regulations-every-6h": {
            "task": "tasks.compliance_beat.monitor_regulations",
            "schedule": crontab(minute=0, hour="*/6"),
        },
    },
)


def _run_async(coro):
    """Run an async coroutine from sync Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(
    name="tasks.compliance_beat.monitor_regulations",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=3600,
)
def monitor_regulations(self):
    """Scheduled task: fetch regulatory updates and create alerts for active matters."""
    try:
        _run_async(_async_monitor_regulations())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _async_monitor_regulations():
    import json
    from sqlalchemy import select
    from db.session import AsyncSessionFactory
    from db.models import Matter, MatterStatus
    from rag.embeddings import embedding_client, llm_client
    from rag.retriever import HybridRetriever
    from rag.reranker import FlashRankReranker, reranker
    from rag.hallucination_guard import HallucinationGuard
    from agents.compliance_monitor import run_compliance_monitor
    from core.logging import get_logger
    import redis.asyncio as aioredis

    logger = get_logger(__name__)
    logger.info("compliance_beat_start")

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        from qdrant_client import QdrantClient
        qdrant = QdrantClient(url=settings.qdrant_url)

        retriever = HybridRetriever(
            embedding_client=embedding_client,
            qdrant_client=qdrant,
            redis_client=redis_client,
        )
        guard = HallucinationGuard(llm_client=llm_client)

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                select(Matter).where(Matter.status == MatterStatus.active)
            )
            matters = result.scalars().all()
            logger.info("compliance_beat_matters", count=len(matters))

            for matter in matters:
                try:
                    state = {
                        "query": "regulatory compliance changes affecting this matter",
                        "matter_id": str(matter.id),
                        "matter_type": matter.matter_type,
                        "metadata": {
                            "jurisdiction": matter.jurisdiction,
                            "practice_areas": [matter.practice_area] if matter.practice_area else [],
                            "industry": matter.industry,
                        },
                    }

                    result_data = await run_compliance_monitor(
                        state=state,
                        retriever=retriever,
                        reranker=reranker,
                        llm=llm_client,
                        guard=guard,
                        db=db,
                    )

                    alerts = result_data.get("agent_outputs", {}).get(
                        "compliance_monitor", {}
                    ).get("output", {}).get("alerts", [])

                    if alerts:
                        # Push WebSocket notification to connected users via Redis pub/sub
                        notification = json.dumps({
                            "type": "compliance_alert",
                            "matter_id": str(matter.id),
                            "alert_count": len(alerts),
                            "alerts": alerts[:3],
                        })
                        await redis_client.publish(
                            f"matter:{matter.id}:alerts", notification
                        )
                        logger.info(
                            "compliance_beat_alerts_published",
                            matter_id=str(matter.id),
                            alert_count=len(alerts),
                        )

                except Exception as e:
                    logger.error(
                        "compliance_beat_matter_error",
                        matter_id=str(matter.id),
                        error=str(e),
                    )
                    continue

    finally:
        await redis_client.aclose()

    logger.info("compliance_beat_complete")
