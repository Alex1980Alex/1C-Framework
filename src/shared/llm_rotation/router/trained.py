"""Trained delegation router via embedding cosine similarity.

Pattern: RouteLLM `sw_ranking`. Source — roadmap 260320 §4.5.1
(Iter 4.1 Similarity Router). Replaces brittle keyword matching when
LinUCB bandit (Iter 3) has insufficient context to decide delegation
level for a fresh prompt.

Architecture:
  1. Load EXEMPLARS dict (level → list[str]) from `.exemplars`.
  2. Embed exemplars once via framework's `get_embedding_engine()`.
  3. On classify(prompt): embed prompt, cosine-similarity vs each
     level's mean exemplar vector, return argmax-level + score.

Exemplar set is bootstrap-only (Iter 4.1). Iter 4.2 (GEPA evolutionary
optimization on rules) and Iter 4.3-4.4 (eval + A/B canary) deferred —
see parent roadmap.

NOT wired into LLM rotation runtime yet. Caller is expected to use:

    router = TrainedRouter()
    await router.warmup()  # one-time exemplar embeddings
    level, score = await router.classify_async("...")

Sync API `classify_sync` is also exposed for hot-path callers that
don't have an event loop.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Any

from src.shared.llm_rotation.router.exemplars import EXEMPLARS

logger = logging.getLogger(__name__)

# Confidence threshold below which classifier abstains.
# Determined empirically — adjust via env if needed.
ABSTAIN_THRESHOLD = 0.30

# Default level when classifier abstains or fails.
# "Medium" is safest middle ground (delegate but flag for review).
DEFAULT_LEVEL = "Medium"


@dataclass
class ClassificationResult:
    """Outcome of a single classify() call.

    Attributes:
        level: One of "Soft" / "Medium" / "Hard" / "Never".
        score: Cosine similarity vs winning level's mean exemplar
            embedding. Range [-1.0, 1.0]; > 0.30 considered confident.
        abstained: True when classifier returned DEFAULT_LEVEL because
            no level scored above ABSTAIN_THRESHOLD.
        scores: Full per-level similarity scores (for explainability).
    """

    level: str
    score: float
    abstained: bool = False
    scores: dict[str, float] = field(default_factory=dict)


def _cosine(a: list[float], b: list[float]) -> float:
    """Stable cosine similarity for two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    """Element-wise mean of equal-length vectors."""
    if not vectors:
        return []
    n = len(vectors)
    dim = len(vectors[0])
    means: list[float] = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            means[i] += v
    return [s / n for s in means]


class TrainedRouter:
    """Embedding-similarity delegation classifier.

    Holds cached mean exemplar embeddings per level. Construction is
    cheap; first `warmup()` call loads the embedding engine and
    pre-computes per-level vectors (one-time cost, ~50-200ms).
    """

    def __init__(self, exemplars: dict[str, list[str]] | None = None) -> None:
        self._exemplars: dict[str, list[str]] = exemplars or EXEMPLARS
        self._level_means: dict[str, list[float]] = {}
        self._engine: Any = None
        self._warmup_lock = asyncio.Lock()

    async def warmup(self) -> None:
        """Embed every exemplar once and cache per-level means.

        Idempotent — subsequent calls return immediately.
        """
        async with self._warmup_lock:
            if self._level_means:
                return
            try:
                from src.pdf_framework.embeddings import get_embedding_engine

                self._engine = get_embedding_engine()
            except Exception as exc:
                logger.warning("TrainedRouter: embedding engine init failed: %s", exc)
                return

            for level, examples in self._exemplars.items():
                if not examples:
                    continue
                try:
                    embs = await self._engine.embed_batch(examples)
                except Exception as exc:
                    logger.warning(
                        "TrainedRouter: embed_batch failed for level=%s: %s",
                        level,
                        exc,
                    )
                    continue
                self._level_means[level] = _mean_vector(embs)
            logger.info(
                "TrainedRouter warmup OK: %d levels, %d total exemplars",
                len(self._level_means),
                sum(len(v) for v in self._exemplars.values()),
            )

    async def classify_async(self, prompt: str) -> ClassificationResult:
        """Classify a fresh prompt against cached exemplar means.

        Returns ClassificationResult; never raises (graceful degradation
        on missing engine, empty exemplars, embedding failure).
        """
        if not prompt or not prompt.strip():
            return ClassificationResult(
                level=DEFAULT_LEVEL,
                score=0.0,
                abstained=True,
                scores={},
            )

        if not self._level_means:
            await self.warmup()
            if not self._level_means:
                # warmup failed — abstain
                return ClassificationResult(
                    level=DEFAULT_LEVEL,
                    score=0.0,
                    abstained=True,
                    scores={},
                )

        try:
            q_emb = await self._engine.embed_text(prompt)
        except Exception as exc:
            logger.warning("TrainedRouter: embed_text failed: %s", exc)
            return ClassificationResult(
                level=DEFAULT_LEVEL,
                score=0.0,
                abstained=True,
                scores={},
            )

        scores: dict[str, float] = {
            level: _cosine(q_emb, mean) for level, mean in self._level_means.items()
        }
        best_level, best_score = max(scores.items(), key=lambda kv: kv[1])

        if best_score < ABSTAIN_THRESHOLD:
            return ClassificationResult(
                level=DEFAULT_LEVEL,
                score=best_score,
                abstained=True,
                scores=scores,
            )

        return ClassificationResult(
            level=best_level,
            score=best_score,
            abstained=False,
            scores=scores,
        )


# ─── Sync helpers (hot-path convenience) ─────────────────────────────


_SINGLETON: TrainedRouter | None = None


def _get_singleton() -> TrainedRouter:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = TrainedRouter()
    return _SINGLETON


def classify_sync(prompt: str) -> ClassificationResult:
    """Synchronous wrapper for callers without an event loop.

    Spins a fresh loop only if one is not already running. If called
    from inside an event loop, raises RuntimeError — use
    `TrainedRouter().classify_async(prompt)` instead.
    """
    router = _get_singleton()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        raise RuntimeError(
            "classify_sync called from within a running event loop; "
            "use 'await router.classify_async(prompt)' instead"
        )

    return asyncio.run(router.classify_async(prompt))
