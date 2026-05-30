"""Jobs API routes for async task management.

Phase 59: Async Processing Queue - job status, listing, cancellation.
"""

import logging
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.auth.dependencies import (
    assert_tenant_access,
    get_current_role,
    get_current_tenant,
)
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


async def get_redis() -> ArqRedis:
    """Get Redis connection pool."""
    return await create_pool(RedisSettings.from_dsn(settings.queue.redis_url))


def _decode_hash(data: dict[Any, Any]) -> dict[str, str]:
    """Decode a Redis hash to str->str (arq's ArqRedis does not set decode_responses)."""

    def _s(v: Any) -> str:
        return v.decode("utf-8") if isinstance(v, bytes) else str(v)

    return {_s(k): _s(v) for k, v in data.items()}


async def _hgetall(redis: ArqRedis, key: str) -> dict[str, str]:
    # redis-py async stub types methods as Awaitable[T] | T; the async client IS awaitable.
    return _decode_hash(await redis.hgetall(key))  # type: ignore[misc]


async def _hset(redis: ArqRedis, key: str, mapping: dict[str, str]) -> None:
    await redis.hset(key, mapping=mapping)  # type: ignore[misc]


async def get_job_status(job_id: str) -> JobInfo | None:
    """Get job status from Redis."""
    try:
        redis = await get_redis()
        key = f"job:{job_id}"
        data = await _hgetall(redis, key)

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
async def enqueue_job(
    request: JobCreateRequest,
    _current_tenant: str = Depends(get_current_tenant),
    _role: str = Depends(get_current_role),
) -> dict[str, str]:
    """Enqueue a new background job.

    Args:
        request: Job creation request

    Returns:
        dict with job_id

    IDOR guard (roadmap 260509 §2.3): non-admin callers can only enqueue jobs
    for their own tenant. Admins may target any tenant via `request.tenant_id`.

    Defence-in-depth: `task_kwargs` may also smuggle a `tenant_id` straight to
    the worker via `**kwargs` expansion below — that path must be guarded too,
    otherwise a non-admin who owns tenant=self can pass
    `task_kwargs={"tenant_id": "victim"}` and reach victim's data. See
    test_jobs_enqueue_blocks_tenant_in_task_kwargs.
    """
    assert_tenant_access(request.tenant_id, _current_tenant, _role)
    nested_tenant = request.task_kwargs.get("tenant_id")
    if nested_tenant is not None:
        assert_tenant_access(nested_tenant, _current_tenant, _role)
    if not settings.queue.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue is disabled. Set QUEUE__ENABLED=true to enable.",
        )

    try:
        redis = await get_redis()

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
        job = await redis.enqueue_job(
            task_path, **request.task_kwargs, _queue_name=settings.queue.queue_name
        )
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Enqueue returned no job (duplicate or deferred job_id).",
            )
        job_id = job.job_id

        # Initialize job status
        await _hset(redis, f"job:{job_id}", {"status": "pending", "progress": "0"})
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
        keys: list[str] = []
        async for raw_key in redis.scan_iter(match=pattern):
            keys.append(raw_key.decode("utf-8") if isinstance(raw_key, bytes) else raw_key)

        jobs = []
        active = 0

        for key in keys[:limit]:
            data = await _hgetall(redis, key)
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
        data = await _hgetall(redis, key)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )

        # Update status to cancelled
        await _hset(redis, key, {"status": "cancelled", "progress": "-1"})

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
async def stream_job_progress(job_id: str) -> StreamingResponse:
    """Stream job progress via Server-Sent Events (SSE).

    Args:
        job_id: Job ID

    Returns:
        StreamingResponse with progress events
    """

    async def event_stream() -> AsyncIterator[str]:
        """Generate SSE events for job progress."""
        try:
            redis = await get_redis()
            key = f"job:{job_id}"

            while True:
                data = await _hgetall(redis, key)

                if not data:
                    yield "event: error\ndata: {'message': 'Job not found'}\n\n"
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
