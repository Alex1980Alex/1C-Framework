"""DSPy Prompt Optimization API endpoints (Phase 34).

Endpoints for managing evaluation datasets, running optimization,
and comparing original vs optimized prompts.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies.components import get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["optimization"])


class OptimizeRequest(BaseModel):
    max_trials: int = 50
    modules: list[str] | None = None  # None = optimize all


class AddPairRequest(BaseModel):
    question: str
    answer: str
    question_type: str = "factual"
    context: str = ""
    source: str = ""


class AddPairsRequest(BaseModel):
    pairs: list[AddPairRequest]


@router.get("/stats")
async def get_optimization_stats():
    """Get DSPy optimization statistics."""
    components = await get_components()
    optimizer = getattr(components, "dspy_optimizer", None)
    if optimizer is None:
        return {"enabled": False, "message": "DSPy optimization not configured"}

    return {"enabled": True, **optimizer.get_stats()}


@router.post("/optimize")
async def run_optimization(request: OptimizeRequest):
    """Start DSPy MIPROv2 optimization run.

    Optimizes prompt templates for specified modules using the evaluation dataset.
    """
    components = await get_components()
    optimizer = getattr(components, "dspy_optimizer", None)
    if optimizer is None:
        raise HTTPException(status_code=501, detail="DSPy optimization not configured")

    result = await optimizer.optimize(
        max_trials=request.max_trials,
        module_names=request.modules,
    )

    return result.model_dump()


@router.get("/dataset")
async def get_evaluation_dataset():
    """View the current evaluation dataset."""
    components = await get_components()
    optimizer = getattr(components, "dspy_optimizer", None)
    if optimizer is None:
        raise HTTPException(status_code=501, detail="DSPy optimization not configured")

    dataset = optimizer.load_dataset()
    return {
        "pairs": [p.model_dump() for p in dataset],
        "total": len(dataset),
    }


@router.post("/dataset/add")
async def add_evaluation_pairs(request: AddPairsRequest):
    """Add question-answer pairs to the evaluation dataset."""
    components = await get_components()
    optimizer = getattr(components, "dspy_optimizer", None)
    if optimizer is None:
        raise HTTPException(status_code=501, detail="DSPy optimization not configured")

    from src.pdf_framework.optimization.dspy_optimizer import EvaluationPair

    optimizer.load_dataset()
    for pair in request.pairs:
        optimizer.add_pair(EvaluationPair(
            question=pair.question,
            answer=pair.answer,
            question_type=pair.question_type,
            context=pair.context,
            source=pair.source,
        ))
    optimizer.save_dataset()

    return {"added": len(request.pairs), "total": optimizer.dataset_size}


@router.get("/last-result")
async def get_last_result():
    """Get the result of the last optimization run."""
    components = await get_components()
    optimizer = getattr(components, "dspy_optimizer", None)
    if optimizer is None:
        raise HTTPException(status_code=501, detail="DSPy optimization not configured")

    result = optimizer.last_result
    if result is None:
        return {"status": "no_runs"}

    return result.model_dump()
