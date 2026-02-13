"""Cache management API endpoints.

Provides REST API for cache statistics and clearing.
"""

import logging

from fastapi import APIRouter

from src.pdf_framework.agents.cache import get_llm_cache
from src.pdf_framework.embeddings.cache import get_embedding_cache
from src.pdf_framework.processing.cache import get_document_cache
from src.pdf_framework.search.semantic_cache import get_semantic_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def cache_stats():
    """Get statistics for all caches."""
    embedding_cache = get_embedding_cache()
    llm_cache = get_llm_cache()
    doc_cache = get_document_cache()

    emb_stats = embedding_cache.get_stats()
    llm_stats = llm_cache.get_stats()
    doc_stats = doc_cache.get_stats()

    result = {
        "embedding": {
            "hits": emb_stats.hits,
            "misses": emb_stats.misses,
            "hit_rate": emb_stats.hit_rate,
        },
        "llm": {
            "hits": llm_stats.get("hits", 0),
            "misses": llm_stats.get("misses", 0),
            "hit_rate": llm_stats.get("hit_rate", 0),
        },
        "document": {
            "hits": doc_stats.get("hits", 0),
            "misses": doc_stats.get("misses", 0),
            "entries": doc_stats.get("stale", 0),
        },
    }

    # Phase 17: Semantic cache stats
    semantic_cache = get_semantic_cache()
    if semantic_cache is not None:
        result["semantic"] = semantic_cache.get_stats()

    return result


@router.post("/clear")
async def clear_all_caches():
    """Clear all caches (embeddings, LLM, documents)."""
    embedding_cache = get_embedding_cache()
    llm_cache = get_llm_cache()
    doc_cache = get_document_cache()

    cleared = 0
    cleared += await embedding_cache.clear()
    cleared += await llm_cache.clear()
    cleared += doc_cache.clear()

    # Phase 17: Clear semantic cache
    semantic_cache = get_semantic_cache()
    if semantic_cache is not None:
        cleared += await semantic_cache.invalidate_all()

    logger.info(f"[CACHE] Cleared {cleared} total entries")
    return {"cleared": cleared}
