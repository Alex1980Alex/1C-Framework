"""Trained router for delegation classification (roadmap 260509 §4.5.1).

Pattern: RouteLLM `sw_ranking` (embedding similarity vs canonical
exemplars). Replaces brittle keyword-matching enforcement when LinUCB
bandit (Iter 3) has insufficient context.

Public API:
    from src.shared.llm_rotation.router import TrainedRouter, classify

    router = TrainedRouter()
    level = await router.classify_async("напиши тесты для модуля X")
    # → "Hard" (matches against EXEMPLARS["Hard"])

Status: Iter 4.1 bootstrap (exemplar-based). Iter 4.2-4.4 (GEPA evolution,
eval, A/B canary) DEFERRED — see parent roadmap 260320 §4.5.

See [docs/roadmap/260320_ROADMAP_DELEGATION_LEARNING.md] §4.5.1 for
design rationale.
"""

from src.shared.llm_rotation.router.exemplars import EXEMPLARS
from src.shared.llm_rotation.router.trained import TrainedRouter, classify_sync

__all__ = ["EXEMPLARS", "TrainedRouter", "classify_sync"]
