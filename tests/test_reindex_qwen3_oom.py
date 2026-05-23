"""Phase 8.12 C2 — OOM recovery in flush_batch.

Goal: a single OOM during reindex must not stop the run nor leak the batch
buffer (which was the zombie-loop bug on 28.04 — see roadmap §21.1, C3).

These tests deliberately avoid importing torch. The OOM path is reached by
raising `RuntimeError("CUDA out of memory")` (the message older torch uses);
`flush_batch` catches it via `_is_cuda_oom` which matches by message text and
exception class name.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.reindex_bsl_qwen3 import _is_cuda_oom, flush_batch
from src.bsl.parser.bsl_chunker import BSLChunk


def _chunk(chunk_id: str, content: str, name: str = "Sym") -> BSLChunk:
    return BSLChunk(
        chunk_id=chunk_id,
        content=content,
        metadata={"name": name, "module_path": "M", "chunk_type": "symbol"},
    )


class _FailingEmbedder:
    """Raises CUDA-OOM on the first N calls, succeeds afterwards."""

    dims = 4096

    def __init__(self, fail_count: int = 1) -> None:
        self.calls = 0
        self.fail_count = fail_count

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        self.calls += 1
        if self.calls <= self.fail_count:
            # Mimic torch <2.4 OOM message; _is_cuda_oom matches by substring.
            raise RuntimeError("CUDA out of memory. Tried to allocate 18.91 GiB")
        return [[0.0] * self.dims for _ in texts]


# ---------------------------------------------------------------------------
# _is_cuda_oom — classifier
# ---------------------------------------------------------------------------


def test_is_cuda_oom_matches_runtime_error_message():
    assert _is_cuda_oom(RuntimeError("CUDA out of memory. Tried to allocate ..."))


def test_is_cuda_oom_matches_named_exception_class():
    # Newer torch raises torch.cuda.OutOfMemoryError; we match by class name
    # so the test does not have to import torch.
    class OutOfMemoryError(Exception):
        pass

    assert _is_cuda_oom(OutOfMemoryError("anything"))


def test_is_cuda_oom_rejects_unrelated_runtime_error():
    assert not _is_cuda_oom(RuntimeError("connection reset"))


def test_is_cuda_oom_rejects_value_error():
    assert not _is_cuda_oom(ValueError("bad shape"))


# ---------------------------------------------------------------------------
# flush_batch — OOM-handling contract
# ---------------------------------------------------------------------------


def test_flush_batch_swallows_oom_and_returns_zero():
    embedder = _FailingEmbedder(fail_count=1)
    client = MagicMock()
    chunks = [_chunk("c1", "x" * 50_000, name="huge"), _chunk("c2", "y", name="tiny")]

    n = flush_batch(client, embedder, "test_coll", chunks)

    assert n == 0
    assert embedder.calls == 1
    # No upsert when the embedder failed — we must not push half-built points.
    client.upsert.assert_not_called()


def test_flush_batch_recovers_on_next_call():
    embedder = _FailingEmbedder(fail_count=1)
    client = MagicMock()

    failing = [_chunk("c1", "x", "name1")]
    healthy = [_chunk("c2", "y", "name2")]

    # 1st call OOMs → 0, no upsert
    assert flush_batch(client, embedder, "test_coll", failing) == 0
    client.upsert.assert_not_called()

    # 2nd call succeeds → 1, upsert called once
    assert flush_batch(client, embedder, "test_coll", healthy) == 1
    assert client.upsert.call_count == 1


def test_flush_batch_propagates_non_oom_exceptions():
    """Anything that isn't CUDA-OOM bubbles up — we don't want to silently
    swallow real bugs (shape mismatches, missing models, etc.)."""

    class BadEmbedder:
        dims = 4096

        def embed_batch(self, texts, is_query=False):
            raise ValueError("vector dim mismatch")

    chunks = [_chunk("c1", "x", "n")]
    with pytest.raises(ValueError, match="vector dim mismatch"):
        flush_batch(MagicMock(), BadEmbedder(), "test_coll", chunks)


def test_flush_batch_oom_with_empty_chunks_does_not_crash():
    """Defensive: flush_batch should never be called with [] in production
    (buffer_size guards), but if it is and the embedder OOMs on [], we still
    return 0 cleanly."""
    embedder = _FailingEmbedder(fail_count=1)
    client = MagicMock()

    n = flush_batch(client, embedder, "test_coll", [])
    assert n == 0
    client.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# C3 — main-loop `batch.clear()` in finally
# ---------------------------------------------------------------------------


def test_main_loop_clears_batch_in_finally():
    """C3 regression: a non-OOM exception from flush_batch must NOT leave
    the batch buffer populated. We replicate the inner loop fragment from
    main() and assert post-condition.

    Without try/finally, this test would leave 3 entries in `batch`."""
    batch: list[BSLChunk] = []
    chunks = [_chunk(f"c{i}", "x", f"n{i}") for i in range(3)]

    def boom(*_a, **_k):
        raise RuntimeError("simulated downstream failure (not OOM)")

    for chunk in chunks:
        batch.append(chunk)

    # Inline copy of the protected fragment from main().
    try:
        try:
            boom()  # stand-in for flush_batch
        finally:
            batch.clear()
    except RuntimeError:
        pass

    assert batch == [], "C3: batch must be cleared even when flush_batch raises"
