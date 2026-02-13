"""Feedback API endpoints (Phase 22).

User feedback collection for self-learning system.
Dual-write: old FeedbackCollector (sync) + new FeedbackStore (async).

Author: Claude Code
Version: 2.0.0 - Phase 22: Consolidated feedback with DI
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies.components import Components, get_components
from src.pdf_framework.feedback.collector import (
    FeedbackCollector,
    FeedbackEntry,
    FeedbackStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    """Request to submit feedback."""

    query: str
    answer: str
    feedback: str  # "positive", "negative", "neutral"
    strategy: str = ""
    score: float = 0.0
    sources: list[str] = []
    user_comment: str = ""
    metadata: dict[str, Any] = {}


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""

    success: bool
    feedback_id: int = 0
    message: str = ""


def _get_collector(components: Components) -> FeedbackCollector:
    """Get feedback collector from DI or create one."""
    if components.feedback_collector is not None:
        return components.feedback_collector
    return FeedbackCollector(settings=components.settings)


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    components: Components = Depends(get_components),
):
    """Submit user feedback on a RAG response.

    Dual-writes to both old FeedbackCollector (for StrategyTuner)
    and new async FeedbackStore (for FewShotProvider/ContentBooster).
    """
    try:
        # Write to old sync collector (StrategyTuner compatibility)
        collector = _get_collector(components)
        entry = FeedbackEntry(
            query=request.query,
            answer=request.answer,
            feedback=request.feedback,
            strategy=request.strategy,
            score=request.score,
            sources=request.sources,
            user_comment=request.user_comment,
            metadata=request.metadata,
        )
        feedback_id = collector.add_feedback(entry)

        # Dual-write to async store (FewShotProvider/ContentBooster)
        if components.feedback_store is not None:
            try:
                from src.pdf_framework.feedback.store import (
                    FeedbackEntry as AsyncFeedbackEntry,
                )

                score_map = {"positive": 1, "negative": -1, "neutral": 0}
                await components.feedback_store.add(AsyncFeedbackEntry(
                    feedback_id=f"fb_{int(time.time() * 1000)}",
                    question=request.query,
                    answer=request.answer,
                    score=score_map.get(request.feedback, 0),
                    strategy=request.strategy,
                    chunk_ids=request.sources,
                    chunk_scores=[],
                    comment=request.user_comment,
                ))
            except Exception as e:
                logger.warning(f"[FEEDBACK] Async store write failed: {e}")

        logger.info(
            f"[FEEDBACK] Received {request.feedback} feedback for query: {request.query[:50]}..."
        )

        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            message="Thank you for your feedback!",
        )

    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    components: Components = Depends(get_components),
):
    """Get feedback statistics.

    Returns overall stats and per-strategy performance.
    """
    try:
        collector = _get_collector(components)
        return collector.get_stats()

    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples/positive")
async def get_positive_examples(
    strategy: str | None = None,
    limit: int = 50,
    components: Components = Depends(get_components),
):
    """Get positive feedback entries as examples.

    These can be used as few-shot examples in prompts.
    """
    try:
        collector = _get_collector(components)
        examples = collector.get_positive_examples(strategy=strategy, limit=limit)

        return {
            "total": len(examples),
            "examples": [
                {
                    "query": e.query,
                    "answer": e.answer,
                    "strategy": e.strategy,
                    "score": e.score,
                }
                for e in examples
            ],
        }

    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to get examples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tune")
async def tune_strategies(
    min_samples: int = 20,
    learning_rate: float = 0.1,
    components: Components = Depends(get_components),
):
    """Tune strategy weights based on feedback.

    Adjusts hybrid search weights to favor better-performing strategies.
    """
    try:
        from src.pdf_framework.feedback.tuner import StrategyTuner

        tuner = StrategyTuner(settings=components.settings)
        new_weights = tuner.tune_weights(
            min_samples=min_samples,
            learning_rate=learning_rate,
        )

        return {
            "success": True,
            "message": "Strategy weights updated",
            "weights": {
                "vector": new_weights.vector,
                "hybrid": new_weights.hybrid,
                "graphrag_local": new_weights.graphrag_local,
                "graphrag_global": new_weights.graphrag_global,
                "two_stage": new_weights.two_stage,
            },
        }

    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to tune strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_old_feedback(
    days: int = 30,
    components: Components = Depends(get_components),
):
    """Clear old feedback entries.

    Removes feedback entries older than specified days.
    """
    try:
        collector = _get_collector(components)
        collector.clear_old_feedback(days=days)

        return {"success": True, "message": f"Cleared feedback older than {days} days"}

    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to clear old feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
