"""Indexing tasks for ARQ worker.

Phase 59: Async Processing Queue - document indexing, BM25/Embeddings rebuild.
"""

import logging
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings

from src.pdf_framework.indexing import index_with_delta
from src.pdf_framework.search.bm25_store import BM25Store
from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore
from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def update_progress(ctx: dict, job_id: str, progress: int, status: str) -> None:
    """Update job progress in Redis."""
    try:
        redis = ctx.get("redis")
        if not redis:
            redis = await create_pool(RedisSettings.from_dsn(settings.queue.redis_url))
            ctx["redis"] = redis

        key = f"job:{job_id}"
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


async def index_document(
    ctx: dict,
    file_path: str,
    document_id: str | None = None,
    tenant_id: str = "default",
    options: dict | None = None,
) -> dict:
    """Index a PDF document asynchronously.

    Args:
        ctx: ARQ context
        file_path: Path to PDF file
        document_id: Optional document ID
        tenant_id: Tenant ID for multi-tenant isolation
        options: Indexing options (chunk_size, overlap, etc.)

    Returns:
        dict: Result with document_id, chunks_count, status
    """
    options = options or {}
    job_id = ctx.get("job_id", "unknown")

    logger.info(f"[INDEX] Starting: {file_path}")

    try:
        await update_progress(ctx, job_id, 0, "loading")

        # Load and index document
        file = Path(file_path)
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        await update_progress(ctx, job_id, 10, "chunking")

        # Get components
        from src.api.dependencies.components import get_components

        components = await get_components()
        indexer = components.indexer

        await update_progress(ctx, job_id, 30, "indexing")

        # Index with delta (incremental)
        result = await index_with_delta(
            file_path=file_path,
            document_id=document_id,
            tenant_id=tenant_id,
            indexer=indexer,
        )

        await update_progress(ctx, job_id, 80, "embedding")

        # Store embeddings
        vector_store = components.vector_store
        if hasattr(result, "chunks"):
            await vector_store.add_chunks(
                chunks=result.chunks,
                tenant_id=tenant_id,
            )

        await update_progress(ctx, job_id, 90, "bm25")

        # Update BM25
        bm25_store = components.bm25_store
        if hasattr(bm25_store, "add_document"):
            await bm25_store.add_document(
                document_id=result.document_id,
                chunks=result.chunks,
                tenant_id=tenant_id,
            )

        await update_progress(ctx, job_id, 100, "complete")

        logger.info(f"[INDEX] Complete: {result.document_id}")

        return {
            "document_id": result.document_id,
            "chunks_count": len(getattr(result, "chunks", [])),
            "status": "success",
        }

    except Exception as e:
        logger.error(f"[INDEX] Failed: {e}")
        await update_progress(ctx, job_id, -1, f"failed: {e}")
        raise


async def rebuild_bm25(
    ctx: dict,
    document_id: str,
    tenant_id: str = "default",
) -> dict:
    """Rebuild BM25 index for a document.

    Args:
        ctx: ARQ context
        document_id: Document ID
        tenant_id: Tenant ID

    Returns:
        dict: Result with status
    """
    job_id = ctx.get("job_id", "unknown")

    logger.info(f"[BM25] Rebuilding: {document_id}")

    try:
        await update_progress(ctx, job_id, 0, "retrieving")

        from src.api.dependencies.components import get_components

        components = await get_components()
        bm25_store = components.bm25_store

        await update_progress(ctx, job_id, 50, "rebuilding")

        # Get document chunks
        vector_store = components.vector_store
        chunks = await vector_store.get_chunks(document_id, tenant_id)

        # Rebuild BM25
        await bm25_store.rebuild_document(document_id, chunks, tenant_id)

        await update_progress(ctx, job_id, 100, "complete")

        logger.info(f"[BM25] Complete: {document_id}")

        return {"document_id": document_id, "status": "success"}

    except Exception as e:
        logger.error(f"[BM25] Failed: {e}")
        await update_progress(ctx, job_id, -1, f"failed: {e}")
        raise


async def rebuild_embeddings(
    ctx: dict,
    document_id: str,
    tenant_id: str = "default",
) -> dict:
    """Rebuild embeddings for a document.

    Args:
        ctx: ARQ context
        document_id: Document ID
        tenant_id: Tenant ID

    Returns:
        dict: Result with status
    """
    job_id = ctx.get("job_id", "unknown")

    logger.info(f"[EMBED] Rebuilding: {document_id}")

    try:
        await update_progress(ctx, job_id, 0, "retrieving")

        from src.api.dependencies.components import get_components

        components = await get_components()
        vector_store = components.vector_store
        embedding_service = components.embedding_service

        await update_progress(ctx, job_id, 30, "generating")

        # Get chunks and regenerate embeddings
        chunks = await vector_store.get_chunks(document_id, tenant_id)
        texts = [c.text for c in chunks]

        embeddings = await embedding_service.embed_texts(texts)

        await update_progress(ctx, job_id, 70, "storing")

        # Update embeddings
        await vector_store.update_embeddings(document_id, embeddings, tenant_id)

        await update_progress(ctx, job_id, 100, "complete")

        logger.info(f"[EMBED] Complete: {document_id}")

        return {"document_id": document_id, "status": "success"}

    except Exception as e:
        logger.error(f"[EMBED] Failed: {e}")
        await update_progress(ctx, job_id, -1, f"failed: {e}")
        raise
