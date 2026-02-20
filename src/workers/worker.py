"""ARQ Worker entry point for async task processing.

Phase 59: Async Processing Queue - worker processes jobs from Redis queue.
"""

import logging
from asyncio import sleep

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker, WorkerSettings

from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def startup(ctx: dict) -> None:
    """Worker startup: initialize components."""
    logger.info("[WORKER] Starting ARQ worker...")
    ctx["settings"] = settings


async def shutdown(ctx: dict) -> None:
    """Worker shutdown: cleanup resources."""
    logger.info("[WORKER] Shutting down ARQ worker...")


async def health_check(ctx: dict) -> None:
    """Periodic health check for worker."""
    try:
        # Check Redis connection
        redis = ctx.get("redis")
        if redis:
            await redis.ping()
        logger.debug("[WORKER] Health check passed")
    except Exception as e:
        logger.warning(f"[WORKER] Health check failed: {e}")


def create_worker_settings() -> WorkerSettings:
    """Create ARQ WorkerSettings with retry configuration."""
    return WorkerSettings(
        on_startup=startup,
        on_shutdown=shutdown,
        health_check_interval=settings.queue.health_check_interval,
        health_check_task=health_check if settings.queue.health_check_interval > 0 else None,
        max_jobs=settings.queue.max_jobs,
        job_timeout=settings.queue.job_timeout,
        retry_attempts=settings.queue.retry_attempts,
        retry_delay_seconds=settings.queue.retry_delay_seconds,
    )


def create_worker() -> Worker:
    """Create and configure ARQ worker instance."""
    # Import tasks to register them
    from src.workers.tasks import evaluation, graph, indexing  # noqa: F401

    worker_settings = create_worker_settings()

    # Parse Redis URL
    redis_url = settings.queue.redis_url
    if redis_url.startswith("redis://"):
        redis_url = redis_url.replace("redis://", "")
    if "/" in redis_url:
        host_port, db = redis_url.split("/", 1)
        db = int(db)
    else:
        host_port = redis_url
        db = 0

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 6379

    redis_settings = RedisSettings(
        host=host,
        port=port,
        database=db,
    )

    functions = [
        # Indexing tasks
        indexing.index_document,
        indexing.rebuild_bm25,
        indexing.rebuild_embeddings,
        # Graph tasks
        graph.rebuild_graph,
        # Evaluation tasks
        evaluation.run_evaluation,
    ]

    return Worker(
        functions=functions,
        queue_name=settings.queue.queue_name,
        redis_settings=redis_settings,
        worker_settings=worker_settings,
    )


async def main() -> None:
    """Main entry point for running worker."""
    if not settings.queue.enabled:
        logger.warning("[WORKER] Queue is disabled. Set QUEUE__ENABLED=true to enable.")
        return

    worker = create_worker()
    logger.info(f"[WORKER] Starting worker: queue={settings.queue.queue_name}")
    await worker.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
