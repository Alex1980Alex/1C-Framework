"""Evaluation tasks for ARQ worker.

Phase 59: Async Processing Queue - run evaluation datasets.
"""

import logging
from pathlib import Path

from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def update_progress(ctx: dict, job_id: str, progress: int, status: str) -> None:
    """Update job progress in Redis."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = ctx.get("redis")
        if not redis:
            redis = await create_pool(RedisSettings.from_dsn(settings.queue.redis_url))
            ctx["redis"] = redis

        key = f"job:{ctx.get('job_id', 'unknown')}"
        await redis.hset(
            key,
            mapping={
                "progress": str(progress),
                "status": status,
            }
        )
        await redis.expire(key, settings.queue.job_timeout)
    except Exception as e:
        logger.warning(f"[TASK] Failed to update progress: {e}")


async def run_evaluation(
    ctx: dict,
    dataset_path: str,
    eval_config: dict | None = None,
) -> dict:
    """Run evaluation on a dataset.

    Args:
        ctx: ARQ context
        dataset_path: Path to evaluation dataset (JSON/CSV)
        eval_config: Evaluation configuration (metrics, strategies, etc.)

    Returns:
        dict: Evaluation results
    """
    job_id = ctx.get("job_id", "unknown")
    eval_config = eval_config or {}

    logger.info(f"[EVAL] Starting: {dataset_path}")

    try:
        await update_progress(ctx, job_id, 0, "loading")

        # Load dataset
        dataset_file = Path(dataset_path)
        if not dataset_file.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        from src.pdf_framework.evaluation import load_dataset, run_ragas_evaluation

        dataset = await load_dataset(dataset_file)

        await update_progress(ctx, job_id, 20, "evaluating")

        # Get components
        from src.api.dependencies.components import get_components

        components = await get_components()

        # Run evaluation
        results = await run_ragas_evaluation(
            dataset=dataset,
            search_manager=components.search_manager,
            eval_config=eval_config,
        )

        await update_progress(ctx, job_id, 100, "complete")

        logger.info(f"[EVAL] Complete: {len(results)} queries")

        return {
            "dataset_path": dataset_path,
            "queries_count": len(results),
            "results": results,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"[EVAL] Failed: {e}")
        await update_progress(ctx, job_id, -1, f"failed: {e}")
        raise
