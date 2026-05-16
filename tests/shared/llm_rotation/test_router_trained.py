"""Unit tests for TrainedRouter (roadmap 260509 §4.5.1).

Uses a mock embedding engine to keep tests deterministic + fast in CI.
The router itself doesn't care about embedding semantics — it only
needs `embed_text(str) -> list[float]` and `embed_batch(list[str]) ->
list[list[float]]` from whatever provider is plugged in.
"""

from __future__ import annotations

import hashlib

import pytest

from src.shared.llm_rotation.router.exemplars import EXEMPLARS
from src.shared.llm_rotation.router.trained import (
    DEFAULT_LEVEL,
    TrainedRouter,
    _cosine,
    _mean_vector,
)

DIM = 32  # small dim for fast deterministic mock


def _hash_vec(text: str, dim: int = DIM) -> list[float]:
    """Deterministic pseudo-embedding from sha256 — same input → same vec.

    Maps bytes to floats in [-1, 1]. Good enough for similarity tests
    when exemplars and query share substrings (sha256 doesn't cluster
    semantically but identical strings get identical vectors, which is
    what we need to validate routing logic).
    """
    h = hashlib.sha256(text.encode()).digest()
    vec: list[float] = []
    while len(vec) < dim:
        for b in h:
            if len(vec) >= dim:
                break
            vec.append((b - 128) / 128.0)
        h = hashlib.sha256(h).digest()
    return vec


class FakeEngine:
    """Mock embedding engine satisfying BaseEmbeddingEngine protocol."""

    def __init__(self, *, force_fail: bool = False) -> None:
        self.force_fail = force_fail
        self.embed_text_calls = 0
        self.embed_batch_calls = 0

    async def embed_text(self, text: str) -> list[float]:
        self.embed_text_calls += 1
        if self.force_fail:
            raise RuntimeError("forced failure")
        return _hash_vec(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls += 1
        if self.force_fail:
            raise RuntimeError("forced failure")
        return [_hash_vec(t) for t in texts]


# ─── Helper math tests ───────────────────────────────────────────────


def test_cosine_identity() -> None:
    v = [0.1, 0.2, 0.3, 0.4]
    assert _cosine(v, v) == pytest.approx(1.0, rel=1e-9)


def test_cosine_orthogonal() -> None:
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-9)


def test_cosine_empty_or_mismatch() -> None:
    assert _cosine([], [1.0]) == 0.0
    assert _cosine([1.0, 2.0], [3.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero-norm guard


def test_mean_vector_empty() -> None:
    assert _mean_vector([]) == []


def test_mean_vector_basic() -> None:
    out = _mean_vector([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    assert out == pytest.approx([3.0, 4.0], rel=1e-9)


# ─── Router behavior tests ───────────────────────────────────────────


def _install_fake(fake: FakeEngine) -> None:
    """Patch the lazy import inside TrainedRouter.warmup()."""
    import src.pdf_framework.embeddings as embmod

    embmod.get_embedding_engine = lambda: fake  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_warmup_caches_per_level_means() -> None:
    router = TrainedRouter()
    fake = FakeEngine()
    _install_fake(fake)
    await router.warmup()

    assert set(router._level_means.keys()) == set(EXEMPLARS.keys())
    # one embed_batch call per non-empty level
    assert fake.embed_batch_calls == len([lv for lv in EXEMPLARS if EXEMPLARS[lv]])


@pytest.mark.asyncio
async def test_warmup_idempotent() -> None:
    router = TrainedRouter()
    fake = FakeEngine()
    _install_fake(fake)
    await router.warmup()
    first_calls = fake.embed_batch_calls
    await router.warmup()
    assert fake.embed_batch_calls == first_calls  # no re-embedding


@pytest.mark.asyncio
async def test_classify_empty_prompt_abstains() -> None:
    router = TrainedRouter()
    fake = FakeEngine()
    _install_fake(fake)
    res = await router.classify_async("")
    assert res.abstained is True
    assert res.level == DEFAULT_LEVEL
    assert res.score == 0.0


@pytest.mark.asyncio
async def test_classify_exact_exemplar_match_wins() -> None:
    """Prompt identical to a single exemplar must route to that level."""
    custom = {
        "Soft": ["A"],
        "Medium": ["B"],
        "Hard": ["UNIQUE_HARD_PROMPT"],
        "Never": ["D"],
    }
    router = TrainedRouter(exemplars=custom)
    fake = FakeEngine()
    _install_fake(fake)
    await router.warmup()

    res = await router.classify_async("UNIQUE_HARD_PROMPT")
    assert res.level == "Hard"
    assert res.score == pytest.approx(1.0, abs=1e-6)
    assert res.abstained is False


@pytest.mark.asyncio
async def test_classify_engine_failure_abstains() -> None:
    router = TrainedRouter()
    fake = FakeEngine(force_fail=True)
    _install_fake(fake)
    # warmup fails silently → level_means stays empty
    res = await router.classify_async("test prompt")
    assert res.abstained is True
    assert res.level == DEFAULT_LEVEL


@pytest.mark.asyncio
async def test_classify_returns_full_score_dict() -> None:
    """ClassificationResult.scores must expose per-level explanations."""
    router = TrainedRouter()
    fake = FakeEngine()
    _install_fake(fake)
    await router.warmup()

    res = await router.classify_async("write some code")
    assert set(res.scores.keys()) == set(EXEMPLARS.keys())
    assert all(-1.0 <= s <= 1.0 for s in res.scores.values())


# ─── Sync wrapper ────────────────────────────────────────────────────


def test_classify_sync_inside_running_loop_raises() -> None:
    """classify_sync must refuse to nest inside an event loop."""
    import asyncio

    from src.shared.llm_rotation.router.trained import classify_sync

    async def runner() -> None:
        with pytest.raises(RuntimeError, match="running event loop"):
            classify_sync("test")

    asyncio.run(runner())
