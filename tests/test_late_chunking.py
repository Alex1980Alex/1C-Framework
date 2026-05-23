"""Phase 8.12.9 (A2-alt Late Chunking) — pure-python unit tests.

Validates the two pieces that don't need GPU / real model:
- `_char_span_to_token_span`: char-span -> token-span mapping over a
  tokenizer-style offset_mapping list.
- `_embed_chunks_late`: orchestrator that groups BSLChunks by module_path,
  builds parent_text + spans, dispatches to `embed_late_chunked`, and falls
  back to `embed_batch` for spans that ran past truncation.

The actual transformer forward + mean-pool path lives behind
`Qwen3STEmbedder.embed_late_chunked` and requires CUDA / real Qwen3 weights;
runtime validation happens in 8.12.8 quality regression on golden set.
"""
from __future__ import annotations

import pytest

from scripts.reindex_bsl_qwen3 import (
    _LATE_CHUNK_SEP,
    _char_span_to_token_span,
    _embed_chunks_late,
)
from src.bsl.parser.bsl_chunker import BSLChunk


# ---------------------------------------------------------------------------
# _char_span_to_token_span
# ---------------------------------------------------------------------------


def test_full_span_maps_all_real_tokens():
    # CLS, "Hello"(0,5), " world"(5,11), SEP — 4 tokens total.
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 0, 11) == (1, 3)


def test_partial_prefix_span():
    # span [0,5) covers only "Hello".
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 0, 5) == (1, 2)


def test_partial_suffix_span():
    # span [5,11) covers " world" (token 2). Note: token 1 ends at 5, so
    # "e <= char_start" excludes it.
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 5, 11) == (2, 3)


def test_span_inside_single_token():
    # span [2,4) lies inside "Hello"(0,5) — should claim that one token.
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 2, 4) == (1, 2)


def test_span_past_truncation_returns_none():
    # offset_mapping ends at char 11 (model truncated past). Span [20,30) has
    # no real-token overlap.
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 20, 30) is None


def test_zero_width_span_returns_none():
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 5, 5) is None


def test_span_skips_special_tokens_in_middle():
    # Synthetic: [CLS] "ab"(0,2) [SEP-mid]=(0,0) "cd"(2,4) [SEP].
    # span [0,4) should yield tokens 1..3 (skipping the (0,0) at index 2).
    offsets = [(0, 0), (0, 2), (0, 0), (2, 4), (0, 0)]
    assert _char_span_to_token_span(offsets, 0, 4) == (1, 4)


def test_span_with_multi_subtoken_word():
    # "interesting" tokenized as "inter"(0,5) "esting"(5,11).
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 0, 11) == (1, 3)


def test_span_starts_mid_token():
    # span [3,11) starts inside "Hello"(0,5) — should still claim token 1
    # because token 1's e=5 > char_start=3.
    offsets = [(0, 0), (0, 5), (5, 11), (0, 0)]
    assert _char_span_to_token_span(offsets, 3, 11) == (1, 3)


def test_empty_offset_mapping():
    assert _char_span_to_token_span([], 0, 10) is None


def test_only_special_tokens():
    # Pathological input that produced just [CLS][SEP].
    offsets = [(0, 0), (0, 0)]
    assert _char_span_to_token_span(offsets, 0, 5) is None


# ---------------------------------------------------------------------------
# _embed_chunks_late orchestrator
# ---------------------------------------------------------------------------


class _FakeEmbedder:
    """Records calls; produces deterministic vectors so we can assert
    grouping/dispatch behavior without loading a real model."""

    def __init__(self, fail_indices=None):
        # fail_indices: set of (parent_text_len, local_chunk_index). Each
        # entry forces embed_late_chunked to return None for that slot,
        # exercising the fallback path. parent_text_len identifies which
        # group is targeted (each test crafts unique total lengths).
        self.fail_indices = fail_indices or set()
        self.late_calls: list[tuple[str, list[tuple[int, int]]]] = []
        self.batch_calls: list[list[str]] = []

    def embed_late_chunked(self, parent_text, chunk_char_spans):
        self.late_calls.append((parent_text, list(chunk_char_spans)))
        sig = len(parent_text)
        out: list[list[float] | None] = []
        for i, (start, end) in enumerate(chunk_char_spans):
            if (sig, i) in self.fail_indices:
                out.append(None)
                continue
            out.append([float(end - start), float(start), float(end)])
        return out

    def embed_batch(self, texts, is_query=False):
        assert is_query is False
        self.batch_calls.append(list(texts))
        return [[-1.0, float(len(t)), 0.0] for t in texts]


def _chunk(chunk_id, content, module_path):
    return BSLChunk(
        chunk_id=chunk_id,
        content=content,
        metadata={"module_path": module_path, "name": chunk_id},
    )


def test_late_groups_by_module_path():
    e = _FakeEmbedder()
    chunks = [
        _chunk("a1", "alpha", "modA"),
        _chunk("b1", "BBB", "modB"),
        _chunk("a2", "gamma", "modA"),
    ]
    out = _embed_chunks_late(e, chunks)

    assert len(out) == 3
    # Two groups -> two embed_late_chunked calls.
    assert len(e.late_calls) == 2
    assert e.batch_calls == []

    parents = {pt for pt, _ in e.late_calls}
    assert ("alpha" + _LATE_CHUNK_SEP + "gamma") in parents
    assert "BBB" in parents


def test_late_char_spans_are_contiguous_and_correct():
    e = _FakeEmbedder()
    chunks = [
        _chunk("a1", "alpha", "modA"),  # 5 chars
        _chunk("a2", "beta", "modA"),   # 4 chars
    ]
    _embed_chunks_late(e, chunks)

    [(parent, spans)] = e.late_calls
    sep = _LATE_CHUNK_SEP
    assert parent == "alpha" + sep + "beta"
    assert spans == [(0, 5), (5 + len(sep), 5 + len(sep) + 4)]
    for (s, e_), expected in zip(spans, ["alpha", "beta"]):
        assert parent[s:e_] == expected


def test_late_preserves_input_order_after_grouping():
    e = _FakeEmbedder()
    chunks = [
        _chunk("a1", "AAA", "modA"),
        _chunk("b1", "BBBBB", "modB"),
        _chunk("a2", "AA", "modA"),
        _chunk("b2", "B", "modB"),
    ]
    out = _embed_chunks_late(e, chunks)

    # Each fake vector encodes [len, start, end] of the chunk's span. The
    # length-of-content (slot 0) is unique per chunk in this fixture, so
    # we can assert input-order preservation by it.
    expected_lens = [3.0, 5.0, 2.0, 1.0]
    actual_lens = [v[0] for v in out]
    assert actual_lens == expected_lens


def test_late_falls_back_to_embed_batch_on_none():
    # Group "modA" has 2 chunks; the second is forced to None -> fallback
    # produces a vector via embed_batch for that chunk only.
    chunks = [
        _chunk("a1", "alpha", "modA"),  # 5 chars
        _chunk("a2", "beta", "modA"),   # 4 chars
    ]
    parent_len = 5 + len(_LATE_CHUNK_SEP) + 4
    e = _FakeEmbedder(fail_indices={(parent_len, 1)})
    out = _embed_chunks_late(e, chunks)

    assert out[0][0] == 5.0       # late path: span len 5
    assert out[1][0] == -1.0      # fallback marker
    assert e.batch_calls == [["beta"]]


def test_late_module_path_missing_falls_into_empty_group():
    # Chunks without module_path still group (empty-string key).
    e = _FakeEmbedder()
    c = BSLChunk(chunk_id="x", content="solo", metadata={})
    out = _embed_chunks_late(e, [c])

    assert len(out) == 1
    assert out[0] is not None
    assert len(e.late_calls) == 1


def test_late_returns_no_none_in_output():
    # Even when underlying late path returns None for every chunk, fallback
    # must fill them all.
    chunks = [_chunk("a1", "x", "modA"), _chunk("a2", "y", "modA")]
    parent_len = 1 + len(_LATE_CHUNK_SEP) + 1
    e = _FakeEmbedder(fail_indices={(parent_len, 0), (parent_len, 1)})
    out = _embed_chunks_late(e, chunks)

    assert all(v is not None for v in out)
    assert e.batch_calls == [["x", "y"]]


def test_late_empty_input_returns_empty_output():
    e = _FakeEmbedder()
    assert _embed_chunks_late(e, []) == []
    assert e.late_calls == []
    assert e.batch_calls == []
