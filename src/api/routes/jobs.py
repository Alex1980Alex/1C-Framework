"""Jobs API routes for async task management.

Phase 59: Async Processing Queue - job status, listing, cancellation.
"""

import logging
from enum import Enum
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobInfo(BaseModel):
    """Job information model."""

    job_id: str
    status: JobStatus
    progress: int = Field(default=0, ge=-1, le=100)
    error_message: str | None = None
    result: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class JobCreateRequest(BaseModel):
    """Request to create a new job."""

    task_name: str = Field(..., description="Name of the task to execute")
    task_kwargs: dict[str, Any] = Field(default_factory=dict, description="Task arguments")
    tenant_id: str = Field(default="default", description="Tenant ID")


class JobListResponse(BaseModel):
    """Response for job listing."""

    jobs: list[JobInfo]
    total: int
    active: int


async def get_redis():
    """Get Redis connection pool."""
    return await create_pool(RedisSettings.from_dsn(settings.queue.redis_url))


async def get_job_status(job_id: str) -> JobInfo | None:
    """Get job status from Redis."""
    try:
        redis = await get_redis()
        key = f"job:{job_id}"
        data = await redis.hgetall(key, encoding="utf-8")

        if not data:
            return None

        return JobInfo(
            job_id=job_id,
            status=JobStatus(data.get("status", "pending")),
            progress=int(data.get("progress", 0)),
        )
    except Exception as e:
        logger.error(f"[JOBS] Failed to get job status: {e}")
        return None


@router.post("/enqueue", response_model=dict[str, str])
async def enqueue_job(request: JobCreateRequest) -> dict[str, str]:
    """Enqueue a new background job.

    Args:
        request: Job creation request

    Returns:
        dict with job_id
    """
    if not settings.queue.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue is disabled. Set QUEUE__ENABLED=true to enable.",
        )

    try:
        from arq.connections import RedisSettings
        from arq import create_pool

        redis = await create_pool(RedisSettings.from_dsn(settings.queue.redis_url))

        # Get task function
        task_map = {
            "index_document": "src.workers.tasks.indexing.index_document",
            "rebuild_bm25": "src.workers.tasks.indexing.rebuild_bm25",
            "rebuild_graph": "src.workers.tasks.graph.rebuild_graph",
            "rebuild_embeddings": "src.workers.tasks.indexing.rebuild_embeddings",
            "run_evaluation": "src.workers.tasks.evaluation.run_evaluation",
        }

        task_path = task_map.get(request.task_name)
        if not task_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown task: {request.task_name}",
            )

        # Enqueue job
        job_id = await redis.enqueue_job(
            task_path,
            **request.task_kwargs,
            _queue_name=settings.queue.queue_name,
        )

        # Initialize job status
        await redis.hset(
            f"job:{job_id}",
            mapping={
                "status": "pending",
                "progress": "0",
            }
        )
        await redis.expire(f"job:{job_id}", settings.queue.job_timeout)

        logger.info(f"[JOBS] Enqueued: {job_id} ({request.task_name})")

        return {"job_id": job_id, "status": "pending"}

    except Exception as e:
        logger.error(f"[JOBS] Failed to enqueue job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{job_id}", response_model=JobInfo)
async def get_job(job_id: str) -> JobInfo:
    """Get job status and progress.

    Args:
        job_id: Job ID

    Returns:
        JobInfo with current status
    """
    job = await get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    limit: int = 100,
    status_filter: JobStatus | None = None,
) -> JobListResponse:
    """List recent and active jobs.

    Args:
        limit: Maximum number of jobs to return
        status_filter: Optional status filter

    Returns:
        JobListResponse with job list
    """
    try:
        redis = await get_redis()

        # Get all job keys
        pattern = "job:*"
        keys = []
        async for key in redis.iscan(match=pattern):
            keys.append(key)

        jobs = []
        active = 0

        for key in keys[:limit]:
            data = await redis.hgetall(key, encoding="utf-8")
            if data:
                job_status = JobStatus(data.get("status", "pending"))
                if status_filter is None or job_status == status_filter:
                    job = JobInfo(
                        job_id=key.replace("job:", ""),
                        status=job_status,
                        progress=int(data.get("progress", 0)),
                    )
                    jobs.append(job)

                    if job_status in [JobStatus.PENDING, JobStatus.IN_PROGRESS]:
                        active += 1

        return JobListResponse(
            jobs=jobs,
            total=len(jobs),
            active=active,
        )

    except Exception as e:
        logger.error(f"[JOBS] Failed to list jobs: {e}")
        return JobListResponse(jobs=[], total=0, active=0)


@router.delete("/{job_id}", response_model=dict[str, str])
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a running job.

    Args:
        job_id: Job ID

    Returns:
        dict with status
    """
    try:
        redis = await get_redis()

        # Check if job exists
        key = f"job:{job_id}"
        data = await redis.hgetall(key, encoding="utf-8")

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )

        # Update status to cancelled
        await redis.hset(
            key,
            mapping={
                "status": "cancelled",
                "progress": "-1",
            }
        )

        logger.info(f"[JOBS] Cancelled: {job_id}")

        return {"job_id": job_id, "status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[JOBS] Failed to cancel job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """Stream job progress via Server-Sent Events (SSE).

    Args:
        job_id: Job ID

    Returns:
        StreamingResponse with progress events
    """

    async def event_stream():
        """Generate SSE events for job progress."""
        try:
            redis = await get_redis()
            key = f"job:{job_id}"

            while True:
                data = await redis.hgetall(key, encoding="utf-8")

                if not data:
                    yield f"event: error\ndata: {{'message': 'Job not found'}}\n\n"
                    break

                job_status = data.get("status", "pending")
                progress = data.get("progress", "0")

                # Send SSE event
                yield f"event: progress\ndata: {{'status': '{job_status}', 'progress': {progress}}}\n\n"

                # Check if job is complete
                if job_status in ["complete", "failed", "cancelled"]:
                    yield f"event: complete\ndata: {{'status': '{job_status}'}}\n\n"
                    break

                # Wait before next poll
                import asyncio

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"[JOBS] SSE stream error: {e}")
            yield f"event: error\ndata: {{'message': '{str(e)}'}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
