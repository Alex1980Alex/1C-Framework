"""Graph tasks for ARQ worker.

Phase 59: Async Processing Queue - knowledge graph rebuild.
"""

import logging

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


async def rebuild_graph(
    ctx: dict,
    document_id: str,
    tenant_id: str = "default",
) -> dict:
    """Rebuild knowledge graph for a document.

    Args:
        ctx: ARQ context
        document_id: Document ID
        tenant_id: Tenant ID

    Returns:
        dict: Result with entities_count, relations_count, status
    """
    job_id = ctx.get("job_id", "unknown")

    logger.info(f"[GRAPH] Rebuilding: {document_id}")

    try:
        await update_progress(ctx, job_id, 0, "retrieving")

        from src.api.dependencies.components import get_components

        components = await get_components()
        graph_store = components.graph_store

        await update_progress(ctx, job_id, 20, "extracting")

        # Get document chunks
        vector_store = components.vector_store
        chunks = await vector_store.get_chunks(document_id, tenant_id)

        # Extract entities and relations
        from src.pdf_framework.graph_store.construction import extract_entities_and_relations

        extraction_result = await extract_entities_and_relations(
            chunks=chunks,
            tenant_id=tenant_id,
        )

        await update_progress(ctx, job_id, 60, "storing")

        # Clear existing graph for document
        await graph_store.delete_document(document_id, tenant_id)

        # Add new entities and relations
        await graph_store.add_entities(
            entities=extraction_result.entities,
            document_id=document_id,
            tenant_id=tenant_id,
        )

        await update_progress(ctx, job_id, 80, "relations")

        await graph_store.add_relations(
            relations=extraction_result.relations,
            tenant_id=tenant_id,
        )

        # Detect communities
        if hasattr(graph_store, "detect_communities"):
            await graph_store.detect_communities(tenant_id)

        await update_progress(ctx, job_id, 100, "complete")

        logger.info(f"[GRAPH] Complete: {document_id}")

        return {
            "document_id": document_id,
            "entities_count": len(extraction_result.entities),
            "relations_count": len(extraction_result.relations),
            "status": "success",
        }

    except Exception as e:
        logger.error(f"[GRAPH] Failed: {e}")
        await update_progress(ctx, job_id, -1, f"failed: {e}")
        raise
