#!/usr/bin/env python3
"""
BSL Reindex — Phase 60 + Phase 8.8 (Qwen3-Embedding-8B via sentence-transformers)

Parse BSL files → chunk by symbols → embed → store in Qdrant.

Embedder options:
  e5        — intfloat/multilingual-e5-large (1024d, CPU OK, default)
  qwen3     — Qwen3-Embedding via Ollama (4096d, slow)
  qwen3-st  — Qwen/Qwen3-Embedding-8B via sentence-transformers (4096d, GPU bf16 b=32; Phase 8.4b)

Phase 8.10: qwen3-st uses length-bucketed dynamic batching to handle the
long-tail chunk distribution measured on real BSL data (p50=332, p99=3588,
max=16854 tokens). Without bucketing, padding to the longest chunk in a
random batch dominates wall-clock; bucketing isolates long chunks into
smaller batches and restores throughput on short chunks.

Usage:
    python scripts/reindex_bsl_qwen3.py --project path/to/1c/project
    python scripts/reindex_bsl_qwen3.py --project path --embedder qwen3-st \
        --collection bsl_code_v4 --batch-size 32 --buffer-size 512 --recreate
"""

import argparse
import logging
import os
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Phase 8.12 C4 + roadmap 260518 Phase 2 fix: на Windows WDDM
# `expandable_segments:True` позволяет аллокатору расти за пределы физ. VRAM
# в shared system memory (наблюдалось reserved=49 GB на RTX 3090 24 GB →
# illegal memory access → driver crash → BSOD/reboot). Profile
# `garbage_collection_threshold:0.6,max_split_size_mb:512` форсит ранний
# GC при росте occupancy и ограничивает размер сегмента — оставляет работу
# в пределах физ. VRAM или поднимает явный CUDA OOM до драйвер-краша.
# Must precede `import torch` (CUDA caching allocator reads env once).
os.environ.setdefault(
    "PYTORCH_CUDA_ALLOC_CONF",
    "garbage_collection_threshold:0.6,max_split_size_mb:512",
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
# Make scripts/_progress.py importable when running from any CWD.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import ProgressTracker, make_tracker  # noqa: E402
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.bsl.parser import BSLASTParser, BSLChunker, BSLContextEnricher
from src.bsl.parser.bsl_chunker import BSLChunk

SKIP_PATTERNS = ["node_modules", "bin/", "build/"]
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# Roadmap 260518 follow-up — module-level progress tracker. main() replaces
# this with a real `ProgressTracker` after CLI parsing; embedder/flush_batch
# reach for it via the `_tracker` global. Default None means "no-op" so
# importing this module from tests/REPL doesn't spawn heartbeat threads or
# touch the filesystem.
_tracker: ProgressTracker | None = None


def _evt(name: str, **payload: Any) -> None:
    """Emit a tracker event if a tracker is initialized; else no-op."""
    if _tracker is not None:
        _tracker.event(name, **payload)


def _state(**kw: Any) -> None:
    """Update tracker heartbeat state if a tracker is initialized; else no-op."""
    if _tracker is not None:
        _tracker.set_state(**kw)


@contextmanager
def _stage(name: str, **start_payload: Any) -> Iterator[None]:
    """Open a tracker stage if a tracker is initialized; else pass-through."""
    if _tracker is not None:
        with _tracker.stage(name, **start_payload):
            yield
    else:
        yield


# Cap each Qdrant upsert payload. 4096-dim float32 vectors × 64 points ≈ 1 MB —
# well under proxy/keepalive limits and survives WinError 10053 mid-stream resets.
# Embedding bucket pool (--buffer-size) stays large for throughput; only the
# network call is sub-batched.
UPSERT_SUB_BATCH = 64

_upsert_log = logging.getLogger("reindex_bsl_qwen3.upsert")
if not _upsert_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _upsert_log.addHandler(_h)
    _upsert_log.setLevel(logging.WARNING)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1.0, max=30.0, jitter=2.0),
    retry=retry_if_exception_type((OSError, ConnectionError, TimeoutError, UnexpectedResponse)),
    before_sleep=before_sleep_log(_upsert_log, logging.WARNING),
    reraise=True,
)
def _upsert_with_retry(client: QdrantClient, collection: str, points: list) -> None:
    client.upsert(collection_name=collection, points=points)


def should_skip(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(p in path_str for p in SKIP_PATTERNS)


def detect_collection_layout(client: QdrantClient, name: str) -> str:
    """Return existing collection layout, or 'absent' if not found.

    Layouts: 'hybrid' (named {dense} + sparse {bm25:IDF}), 'dual_vector'
    (named {content, module_path}), 'dense_only' (single-vector), 'absent'.
    Recovered 2026-06-02 (merge/autofix regression deleted it; call sites used noqa).
    """
    try:
        info = client.get_collection(collection_name=name)
    except (UnexpectedResponse, Exception):
        return "absent"
    vec_cfg = info.config.params.vectors
    sparse_cfg = info.config.params.sparse_vectors
    has_sparse_bm25 = bool(sparse_cfg and "bm25" in sparse_cfg)
    if isinstance(vec_cfg, dict):
        if "dense" in vec_cfg and has_sparse_bm25:
            return "hybrid"
        if "content" in vec_cfg and "module_path" in vec_cfg:
            return "dual_vector"
    return "dense_only"


def _looks_like_cyrillic_project(project: Path) -> bool:
    """Heuristic: project root path contains Cyrillic (signals Cyrillic BSL inside).

    Used by the late-chunking-requires-FA2 guard. Recovered 2026-06-02 (regression).
    """
    return any("Ѐ" <= ch <= "ӿ" for ch in str(project))


def create_collection(
    client: QdrantClient,
    name: str,
    dims: int,
    recreate: bool = False,
    dual_vector: bool = False,
    enable_sparse: bool = False,
) -> None:
    if recreate:
        try:
            client.delete_collection(collection_name=name)
            print(f"Deleted existing collection: {name}")
        except (UnexpectedResponse, Exception):
            pass

    layout = detect_collection_layout(client, name)  # noqa: F821
    if layout != "absent":
        info = client.get_collection(collection_name=name)
        print(f"Collection '{name}' exists: {info.points_count} points (layout={layout})")
        return layout

    if enable_sparse:  # noqa: F821
        client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(size=dims, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
            },
        )
        print(f"Created hybrid collection: {name} (dense={dims}d cosine, bm25 sparse IDF)")
        return "hybrid"
    if dual_vector:
        client.create_collection(
            collection_name=name,
            vectors_config={
                "content": models.VectorParams(size=dims, distance=models.Distance.COSINE),
                "module_path": models.VectorParams(size=dims, distance=models.Distance.COSINE),
            },
        )
        print(f"Created dual-vector collection: {name} (content+module_path, {dims}d, cosine)")
        return "dual_vector"
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=dims,
            distance=models.Distance.COSINE,
        ),
    )
    print(f"Created collection: {name} (dims={dims}, cosine)")
    return "dense_only"


def point_id(collection: str, chunk_id: str) -> str:
    # Namespace by collection so v3 and v4 produce distinct UUIDs for the same chunk_id.
    return str(uuid.uuid5(UUID_NAMESPACE, f"{collection}-{chunk_id}"))


def _char_span_to_token_span(
    offset_mapping: list[tuple[int, int]],
    char_start: int,
    char_end: int,
) -> tuple[int, int] | None:
    """Phase 8.12.9 helper — map a [char_start, char_end) span in source text
    to a [tok_start, tok_end) range in a tokenizer's offset_mapping.

    Skips special tokens (offset (0,0) — CLS/SEP/PAD). Assumes monotonic
    offsets, breaks early once tokens pass the span. Returns None when the
    span has no overlap with any real token (typical: the span fell entirely
    past the model's truncation cap, or zero-width input).
    """
    tok_start: int | None = None
    tok_end: int | None = None
    for i, (s, e) in enumerate(offset_mapping):
        if s == 0 and e == 0:
            continue
        if e <= char_start:
            continue
        if s >= char_end:
            break
        if tok_start is None:
            tok_start = i
        tok_end = i + 1
    if tok_start is None or tok_end is None:
        return None
    return tok_start, tok_end


def chunk_payload(chunk: BSLChunk) -> dict[str, Any]:
    m = chunk.metadata
    calls = m.get("calls", [])
    return {
        "chunk_id": chunk.chunk_id,
        "content": chunk.content[:500],
        "name": m.get("name", ""),
        "chunk_type": m.get("chunk_type", ""),
        "symbol_type": m.get("symbol_type", ""),
        "is_export": m.get("is_export", False),
        "module_path": m.get("module_path", ""),
        "module_name": m.get("module_name", ""),
        "module_type": m.get("module_type", ""),
        "params": m.get("params", ""),
        "calls": calls[:20] if isinstance(calls, list) else [],
        "signature": m.get("signature", ""),
        "region": m.get("region", ""),
        "line_start": m.get("line_start", 0),
        "line_end": m.get("line_end", 0),
        "object_type": m.get("object_type", ""),
        "object_name": m.get("object_name", ""),
        "caller_count": m.get("caller_count", 0),
    }


class E5Embedder:
    """E5-large embedder via sentence-transformers (1024d, fast on CPU)."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("intfloat/multilingual-e5-large")
        self.dims = 1024

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        prefix = "query: " if is_query else "passage: "
        prefixed = [prefix + t[:8000] for t in texts]
        embeddings = self.model.encode(prefixed, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def close(self) -> None:
        pass


class Qwen3STEmbedder:
    """Qwen3-Embedding-8B via sentence-transformers (4096d native, GPU).

    Phase 8.4b: bf16 + batch=32 is the throughput plateau on RTX 3090 for
    short chunks (~200 tokens, ~18 ch/s).

    Phase 8.10 (length-bucketed batching): Real BSL data has a long-tail
    length distribution (p50=332, p99=3588, max=16854 tokens). Mixing a
    single long chunk with short ones in a fixed batch=32 forces padding
    to the longest, blowing wall-clock 5–25× and risking OOM. Solution:
    bucket chunks by token count and pick batch_size per bucket. The
    `batch_size` ctor arg sets the SHORT-chunk batch (S bucket); other
    buckets scale down per BUCKETS table.

    Bucket table (token_len_max → batch_size), tuned for RTX 3090 (24 GB):
        ≤512    → 32   (S, 69% of chunks)
        ≤1024   → 16   (M, 19.5%)
        ≤2048   → 8    (L, 7.9%)
        ≤4096   → 4    (XL, 2.6%)
        ≤8192   → 2    (XXL_8K, ~1% — Phase 1 of roadmap 260518; activations ~1.5 GB)
        8193+   → 1    (XXXL, 0.3% — outliers up to 16854 tokens; truncated at max_seq_length)

    Phase 1 of roadmap 260518 (BSL Late Chunking improvements):
        - `max_seq_length` default bumped 4096 → 8192 to cut single-pass fallback%.
        - VRAM math on RTX 3090 24GB: model 16 GB FP16 + 8192-token activations
          ~1.5 GB (no FA2) → ~17.5 GB peak, 6.5 GB headroom. Safe by ~2 GB margin
          required in §3.4 success criteria.
    """

    MODEL_ID = "Qwen/Qwen3-Embedding-8B"

    # (token_upper_bound or None for "unbounded", batch_size). Order matters
    # — first match wins, so list shortest→longest.
    DEFAULT_BUCKETS: tuple[tuple[int | None, int], ...] = (
        (512, 32),
        (1024, 16),
        (2048, 8),
        (4096, 4),
        (8192, 2),
        (None, 1),
    )

    def __init__(
        self,
        dtype: str = "bfloat16",
        batch_size: int = 32,
        buckets: tuple[tuple[int | None, int], ...] | None = None,
        enable_fa2: bool = False,
        max_seq_length: int = 8192,
    ) -> None:
        # Phase 8.12 C4 + roadmap 260518 Phase 2 fix (defense-in-depth — also
        # set at module top in case this class is imported and instantiated
        # from a context that imported torch before our module). See module
        # top for full rationale on switch away from expandable_segments.
        os.environ.setdefault(
            "PYTORCH_CUDA_ALLOC_CONF",
            "garbage_collection_threshold:0.6,max_split_size_mb:512",
        )

        import torch
        from sentence_transformers import SentenceTransformer

        if not torch.cuda.is_available():
            raise RuntimeError(
                "qwen3-st requires CUDA. Run Phase 8.2 to install cu128 wheels first."
            )

        torch_dtype = {"float16": torch.float16, "bfloat16": torch.bfloat16}.get(dtype)
        if torch_dtype is None:
            raise ValueError(f"dtype must be 'float16' or 'bfloat16', got {dtype!r}")

        model_kwargs: dict[str, Any] = {"torch_dtype": torch_dtype}
        tokenizer_kwargs: dict[str, Any] = {}
        if enable_fa2:
            # Phase 8.12 A1: FA2 — O(n²) attention → ~linear, ×1.5–2 on long chunks.
            model_kwargs["attn_implementation"] = "flash_attention_2"
            # Phase 8.12 C6 (CORRECTNESS, not optimization): FA2 + last-token
            # pooling reads the final position from each row in the batch. With
            # default right-padding, short rows in a mixed batch end with [PAD]
            # — embedding becomes garbage. Left-padding keeps the actual final
            # token at the rightmost position. Required when FA2 is enabled.
            # Source: Qwen3-Embedding-8B HF model card.
            tokenizer_kwargs["padding_side"] = "left"

        self.model = SentenceTransformer(
            self.MODEL_ID,
            device="cuda",
            model_kwargs=model_kwargs,
            tokenizer_kwargs=tokenizer_kwargs or None,
        )
        self.dims = 4096
        self.batch_size = batch_size
        self.enable_fa2 = enable_fa2
        self.max_seq_length = max_seq_length

        # Phase 8.12 C5: cap forward-pass token length at the model level. ST's
        # encode() truncates with this limit, so XXL chunks (97k chars / ~30k
        # tokens for translation dictionaries) no longer blow VRAM budget.
        # The bucketer below also tokenizes with the same max_length so its
        # per-chunk token count matches what the model actually sees.
        self.model.max_seq_length = max_seq_length

        # Phase 8.12 C7: Qwen3-Embedding ships a "query" prompt in
        # config_sentence_transformers.json (task instruction prepended for
        # retrieval queries — +1-5% recall per HF model card). Feature-detect
        # so the embedder degrades gracefully if the model ever drops it.
        prompts = getattr(self.model, "prompts", None) or {}
        self._has_query_prompt = "query" in prompts

        # Use caller-provided buckets if given. Otherwise treat batch_size as
        # a per-bucket ceiling: each bucket gets min(default_for_bucket,
        # batch_size). Rationale — a caller passing --batch-size 8 wants a
        # safety cap; without min(), long-chunk buckets keep their default
        # 16/8/4 which can OOM under tight VRAM. The defaults assume a 32-card
        # ceiling; any tighter cap should propagate down the bucket chain.
        if buckets is not None:
            self.buckets = buckets
        else:
            self.buckets = tuple(
                (upper, min(default_bs, batch_size)) for upper, default_bs in self.DEFAULT_BUCKETS
            )

    def _bucket_batch(self, token_len: int) -> int:
        for upper, bs in self.buckets:
            if upper is None or token_len <= upper:
                return bs
        return 1

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        # Phase 8.12 C1+C5: token-level cap via tokenizer(truncation=True,
        # max_length=self.max_seq_length). The previous char-level slice
        # (t[:32000]) was wrong for Cyrillic — 32k chars ≈ 12-16k tokens, well
        # past safe VRAM for an 8B model on 24GB. ST's encode() will also
        # apply max_seq_length internally; bucketing with the same cap keeps
        # token_lens aligned with what the forward pass sees.
        tokenizer = self.model.tokenizer
        token_lens = [
            len(
                tokenizer(
                    t,
                    add_special_tokens=True,
                    truncation=True,
                    max_length=self.max_seq_length,
                    return_tensors=None,
                )["input_ids"]
            )
            for t in texts
        ]

        # Group indices by per-bucket batch_size. ST's encode() sorts internally
        # by length, so within a bucket padding stays bounded by the bucket's
        # token ceiling.
        groups: dict[int, list[int]] = {}
        for idx, tl in enumerate(token_lens):
            bs = self._bucket_batch(tl)
            groups.setdefault(bs, []).append(idx)

        # Telemetry: emit bucket distribution per flush. Validates the
        # predicted weighted-throughput model against actual data and flags
        # XXL-bucket presence (potential VRAM pressure on 24 GB cards).
        if groups and len(texts) >= 32:
            tally = " ".join(
                f"b{bs}={len(idxs)}" for bs, idxs in sorted(groups.items(), reverse=True)
            )
            max_len = max(token_lens) if token_lens else 0
            print(f"  [bucket] flush={len(texts)} {tally} max_tok={max_len}")

        results: list[list[float] | None] = [None] * len(texts)
        for bs, indices in groups.items():
            group_texts = [texts[i] for i in indices]
            encode_kwargs: dict[str, Any] = {
                "batch_size": bs,
                "show_progress_bar": False,
                "convert_to_numpy": True,
            }
            # Phase 8.12 C7: prepend Qwen3 retrieval-query instruction for
            # query-side encoding. Asymmetric retrieval — passages encode raw.
            if is_query and self._has_query_prompt:
                encode_kwargs["prompt_name"] = "query"
            embeddings = self.model.encode(group_texts, **encode_kwargs)
            for orig_idx, emb in zip(indices, embeddings):
                results[orig_idx] = emb.tolist()

        # All slots filled — _bucket_batch always returns a batch_size for
        # any token_len, so every index from 0..len-1 lands in some group.
        # Filtering None silently would shrink the result and break the
        # 1-to-1 correspondence flush_batch relies on; assert instead.
        assert all(r is not None for r in results), "bucket grouping missed an index"
        return results  # type: ignore[return-value]

    # Phase 2 of roadmap 260518: sliding window overlap fraction. 15% keeps
    # border chunks covered by ≥1 adjacent window — overlap of full
    # `max_seq_length=8192` ≈ 1230 tokens ≈ 3-4 KB BSL code, more than
    # enough for a single BSL symbol body (capped to ~2K tokens by
    # `BSLChunker.split_threshold_chars`). Raise to 0.25 if cross-window
    # symbol bodies start showing recall regression.
    DEFAULT_SLIDING_OVERLAP_RATIO = 0.15

    # roadmap 260518 follow-up — only emit `single_pass` events for forward
    # passes >= 2s. Small regions are sub-second and would flood the JSONL.
    SINGLE_PASS_LOG_THRESHOLD_S: float = 2.0

    def embed_late_chunked(
        self,
        parent_text: str,
        chunk_char_spans: list[tuple[int, int]],
    ) -> list[list[float] | None]:
        """Phase 8.12.9 (A2-alt) — Late Chunking pooling.

        ONE forward pass over `parent_text` (or N forward passes over
        overlapping windows for oversized `parent_text` — Phase 2 of
        roadmap 260518) → mean-pool the contextualized token embeddings
        within each chunk's [char_start, char_end) span → L2-normalize.
        Each chunk vector retains document-level context (Jina,
        arXiv:2409.04701).

        Returns one vector per `chunk_char_spans` entry; `None` when the
        span maps to no real tokens (e.g. zero-width input, or chunk
        that straddles every window boundary). Caller falls back to
        `embed_batch` for `None` slots.

        Passages only — query-side prompt-prepending shifts char offsets,
        so route queries through `embed_batch(..., is_query=True)`.

        Reference impl: github.com/jina-ai/late-chunking.
        """
        tokenizer = self.model.tokenizer
        if not getattr(tokenizer, "is_fast", False):
            raise RuntimeError(
                "embed_late_chunked requires a fast tokenizer "
                "(needs return_offsets_mapping). Got slow tokenizer."
            )

        # Phase 2 of roadmap 260518 — probe untruncated token count to
        # decide single-pass vs sliding window. Probe is CPU-only
        # tokenization (no GPU/VRAM cost) so it's cheap even on 1 MB
        # god-object modules. Without this probe, oversized modules
        # silently lose context past max_seq_length → up to 99% chunks
        # fall back to `embed_batch` (std pooling, no Late Chunking
        # benefit). See roadmap §1.2 empirics.
        probe = tokenizer(
            parent_text,
            add_special_tokens=True,
            truncation=False,
            return_offsets_mapping=False,
            return_tensors=None,
        )
        total_tokens = len(probe["input_ids"])
        if total_tokens <= self.max_seq_length:
            t_sp = time.perf_counter()
            result = self._embed_late_chunked_single_pass(parent_text, chunk_char_spans)
            forward_s = time.perf_counter() - t_sp
            if forward_s >= self.SINGLE_PASS_LOG_THRESHOLD_S:
                _evt(
                    "single_pass",
                    tokens=total_tokens,
                    parent_chars=len(parent_text),
                    chunks=len(chunk_char_spans),
                    forward_s=round(forward_s, 3),
                )
            return result
        return self._embed_late_chunked_sliding(parent_text, chunk_char_spans, total_tokens)

    def _embed_late_chunked_single_pass(
        self,
        parent_text: str,
        chunk_char_spans: list[tuple[int, int]],
    ) -> list[list[float] | None]:
        """Single-pass Late Chunking — assumes parent fits in max_seq_length.

        Extracted from `embed_late_chunked` to enable reuse by the sliding
        path (Phase 2 of roadmap 260518). Truncation=True is kept as a
        safety net: the caller probes total token count and routes here
        only when it fits, but if a window construction is ever off-by-one
        we'd rather drop the tail tokens than blow VRAM.
        """
        import torch

        tokenizer = self.model.tokenizer
        enc = tokenizer(
            parent_text,
            return_tensors="pt",
            return_offsets_mapping=True,
            truncation=True,
            max_length=self.max_seq_length,
            add_special_tokens=True,
        )
        offsets = [tuple(p) for p in enc.pop("offset_mapping")[0].tolist()]
        device = next(self.model[0].auto_model.parameters()).device
        features = {k: v.to(device) for k, v in enc.items()}

        # Skip ST's pooling head; run only the transformer to get raw
        # contextualized hidden states.
        with torch.inference_mode():
            features = self.model[0](features)
        token_embeddings = features["token_embeddings"][0]

        out: list[list[float] | None] = []
        for char_start, char_end in chunk_char_spans:
            span = _char_span_to_token_span(offsets, char_start, char_end)
            if span is None:
                out.append(None)
                continue
            tok_start, tok_end = span
            pooled = token_embeddings[tok_start:tok_end].mean(dim=0)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=0)
            out.append(pooled.float().cpu().tolist())
        # roadmap 260518 Phase 2 fix: освободить GPU-resident tensor'ы до выхода
        # из метода. Без явного del аллокатор PyTorch держит full token_embeddings
        # (≈18K tok × 4096 dim × bf16 ≈ 150 MB) и features в reserved-сегменте
        # пока caller (sliding loop) не вернётся в Python. На 39 окнах накопление
        # выталкивало reserved за 24 GB физ. VRAM → BSOD/reboot.
        del token_embeddings, features
        return out

    @staticmethod
    def _make_char_windows(
        text: str,
        window_chars: int,
        overlap_chars: int,
    ) -> list[tuple[int, str]]:
        """Phase 2 of roadmap 260518 — split `text` into overlapping char
        windows of approximately `window_chars` length, snapping breaks to
        newline boundaries when possible.

        Returns `[(char_offset, window_text), ...]`. Last window may be
        shorter than `window_chars`. If `text` fits in one window, returns
        a single tuple `[(0, text)]`.

        Line-snapping rationale: BSL is line-oriented, so cutting mid-token
        loses readability inside the window AND may split an identifier
        across the boundary (the tokenizer would then produce different
        subword boundaries on either side, breaking offset alignment).
        Snap to the nearest preceding `\\n` within `window_chars // 10` of
        the ideal cut so the snap doesn't shrink windows too aggressively.
        """
        n = len(text)
        if n <= window_chars:
            return [(0, text)]
        if overlap_chars >= window_chars:
            raise ValueError(
                f"overlap_chars ({overlap_chars}) must be < window_chars "
                f"({window_chars}) — sliding would loop forever otherwise."
            )

        windows: list[tuple[int, str]] = []
        step = window_chars - overlap_chars
        snap_zone = max(1, window_chars // 10)
        start = 0
        while start < n:
            ideal_end = min(start + window_chars, n)
            if ideal_end < n:
                # Snap backward to nearest \n within snap_zone for line
                # alignment. rfind() returns -1 if absent → fall back to
                # ideal_end (mid-line cut).
                snap_min = max(start + 1, ideal_end - snap_zone)
                nl = text.rfind("\n", snap_min, ideal_end)
                end = nl + 1 if nl != -1 else ideal_end
            else:
                end = ideal_end
            windows.append((start, text[start:end]))
            if end >= n:
                break
            # Next window starts `step` chars before previous end, but
            # also snap to \n so the start is a clean line boundary.
            next_start = max(start + 1, end - overlap_chars)
            if next_start < n:
                snap_max = min(n, next_start + snap_zone)
                nl = text.find("\n", next_start, snap_max)
                if nl != -1:
                    next_start = nl + 1
            start = next_start
        return windows

    def _embed_late_chunked_sliding(
        self,
        parent_text: str,
        chunk_char_spans: list[tuple[int, int]],
        total_tokens: int,
        overlap_ratio: float | None = None,
    ) -> list[list[float] | None]:
        """Phase 2 of roadmap 260518 — sliding-window Late Chunking for
        modules that exceed `max_seq_length` in token count.

        Approach:
          1. Estimate chars-per-token from the untruncated probe.
          2. Build overlapping char windows whose token count fits
             `max_seq_length - special_tokens_budget`.
          3. For each window, embed via `_embed_late_chunked_single_pass`
             with chunk spans re-based to window coordinates.
          4. Each chunk is embedded by the FIRST window that fully
             contains it (deterministic, avoids merging vectors from
             two windows which would skew L2 norm).
          5. Chunks crossing every window boundary stay `None` →
             caller falls back to `embed_batch`. With 15% overlap of
             8192 tokens (~1200 tokens / ~3.5 KB), this only triggers
             for chunks longer than the overlap — well above
             `BSLChunker.window_chars` (3000 chars).

        Trade-off vs single forward over all tokens:
          - Quality: chunks near window edges lose context from "the
            other side". Mitigated by overlap (15% default).
          - Wall-clock: O(N_windows × forward_pass) per module instead
            of one. For a 30K-token module ≈ 4 windows ≈ +4s/module.

        Why char windows rather than token windows: re-tokenizing a
        char slice keeps offset_mapping in the slice's own coordinate
        system, so we can reuse `_char_span_to_token_span` and the
        single-pass code path without a special "global token index"
        machinery. Cost of re-tokenization on CPU is negligible vs
        the forward pass.
        """
        if overlap_ratio is None:
            overlap_ratio = self.DEFAULT_SLIDING_OVERLAP_RATIO

        # Reserve 4 tokens for BOS/EOS/padding budget (Qwen3 adds 1-2,
        # safety margin). 0.95 multiplier accounts for char-to-token
        # ratio variance across windows — same module may have BSL code
        # (4 chars/token) mixed with comment paragraphs (3 chars/token).
        chars_per_token = max(1.0, len(parent_text) / total_tokens)
        safe_window_tokens = max(64, self.max_seq_length - 4)
        window_chars = max(64, int(safe_window_tokens * chars_per_token * 0.95))
        overlap_chars = max(1, int(window_chars * overlap_ratio))

        char_windows = self._make_char_windows(parent_text, window_chars, overlap_chars)

        # Telemetry — observability on sliding behaviour. Helps tune
        # overlap_ratio if benchmark shows recall drop at boundaries.
        print(
            f"  [late-chunking sliding] {total_tokens} tokens / {len(parent_text)} chars "
            f"-> {len(char_windows)} windows x ~{window_chars} chars "
            f"(overlap {overlap_chars} chars, ratio {overlap_ratio:.0%})"
        )
        # roadmap 260518 follow-up — emit structured event + push window
        # progress into heartbeat state. Critical for god-object modules
        # where GPU forward on a 30+-window sequence runs ~5-15s/window
        # with no other stdout output between windows.
        _evt(
            "sliding_start",
            total_tokens=total_tokens,
            parent_chars=len(parent_text),
            windows=len(char_windows),
            window_chars=window_chars,
            overlap_chars=overlap_chars,
            chunks=len(chunk_char_spans),
        )
        _state(windows_total=len(char_windows), windows_done=0)

        # roadmap 260518 Phase 2 fix: import здесь, чтобы не зависеть от
        # порядка инициализации модуля; gc нужен для дробления generational
        # ссылок на token_embeddings, которые иначе живут до возврата метода.
        import gc

        import torch

        results: list[list[float] | None] = [None] * len(chunk_char_spans)
        for win_idx, (win_char_start, win_text) in enumerate(char_windows, 1):
            win_char_end = win_char_start + len(win_text)
            # Collect chunks fully contained in this window that haven't
            # been embedded yet. "Fully contained" avoids vector merging
            # across windows — partial chunks fall through to next window
            # where overlap should cover them.
            relevant: list[int] = []
            for i, (cs, ce) in enumerate(chunk_char_spans):
                if results[i] is not None:
                    continue
                if cs >= win_char_start and ce <= win_char_end:
                    relevant.append(i)
            if not relevant:
                continue
            local_spans = [
                (
                    chunk_char_spans[i][0] - win_char_start,
                    chunk_char_spans[i][1] - win_char_start,
                )
                for i in relevant
            ]
            t_win = time.perf_counter()
            win_vectors = self._embed_late_chunked_single_pass(win_text, local_spans)
            forward_s = time.perf_counter() - t_win
            for orig_idx, vec in zip(relevant, win_vectors):
                if vec is not None:
                    results[orig_idx] = vec
            # roadmap 260518 follow-up — emit per-window event AFTER forward.
            # Heartbeat state already updated above with the window index so
            # `[hb]` lines show progress even if forward stalls > 10s.
            _state(windows_done=win_idx)
            _evt(
                "sliding_window",
                win=win_idx,
                of=len(char_windows),
                relevant=len(relevant),
                forward_s=round(forward_s, 3),
            )
            # roadmap 260518 Phase 2 fix: между окнами явно дробим reserved-
            # сегменты PyTorch'а. Без этого на 39 окнах × ~150 MB token
            # embeddings reserved уходил до 49 GB (RTX 3090 24 GB) и драйвер
            # падал в shared system memory → BSOD/reboot. gc.collect()
            # подбирает Python-уровень ссылки на features dict, empty_cache()
            # возвращает аллокаторные сегменты обратно в CUDA driver.
            gc.collect()
            torch.cuda.empty_cache()
        # Clear sliding-specific heartbeat keys so the next file's hb line
        # doesn't show stale windows_done from the previous god-object.
        _state(windows_total=None, windows_done=None)
        return results

    def close(self) -> None:
        import gc

        import torch

        if getattr(self, "model", None) is None:
            return
        self.model = None
        gc.collect()
        torch.cuda.empty_cache()


class Qwen3TEIEmbedder:
    """Qwen3-Embedding-8B via text-embeddings-inference HTTP backend (Phase 8.12.6 A3).

    TEI is a Rust-native embedding runtime: continuous batching + token-based
    dynamic batching + FlashAttention 2 are built into the server, so the
    Python-side bucketing/OOM-recovery machinery in `Qwen3STEmbedder` is
    unnecessary here — the server fans the request across its internal queue.
    Expected ×3-5 vs sentence-transformers per roadmap §21.4.

    Endpoint: POST `/embed` (TEI-native, lighter than the `/v1/embeddings`
    OpenAI-compatible variant). Server-side `truncate=true` honors
    `--max-input-length` from compose, matching `Qwen3STEmbedder.max_seq_length`
    (Phase 8.12 C5) so the same forward-pass token cap applies on either backend.

    Query-side instruction (Phase 8.12 C7): Qwen3-Embedding ships a "query"
    prompt in `config_sentence_transformers.json`. TEI may or may not honor
    sentence-transformers prompt config across versions, so we prepend the
    canonical instruction client-side. The string is reproduced verbatim from
    the Qwen3-Embedding-8B HF model card (`prompts.query`); changing it would
    desync queries from passages indexed via `Qwen3STEmbedder` (which loads
    the same prompt via the model's own config).

    Late chunking (8.12.9 A2-alt): NOT supported. TEI returns pooled vectors
    only — no token-level hidden states, so the per-span mean-pool path can't
    run here. Use `--embedder qwen3-st --pooling-mode late-chunking` for that
    A/B arm. The CLI guard at main() enforces this — guard-message also lists
    `qwen3-tei` so users know it's intentional.
    """

    DEFAULT_BASE_URL = "http://localhost:8080"

    # Qwen3-Embedding-8B query-side instruction. Source: HF model card,
    # `config_sentence_transformers.json` -> prompts.query. Must match exactly
    # what `Qwen3STEmbedder` prepends via `prompt_name="query"` so queries
    # land in the same instruction-conditioned subspace as the passages
    # indexed by either backend.
    QUERY_INSTRUCTION = (
        "Instruct: Given a web search query, retrieve relevant passages "
        "that answer the query\nQuery: "
    )

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
        max_chars: int = 32000,
        client_batch_size: int = 32,
        verify_health: bool = True,
    ) -> None:
        import httpx

        self.base_url = base_url.rstrip("/")
        # Single Client reused across calls so HTTP/keep-alive + connection
        # pool amortize across batches. TEI runs on localhost so the timeout
        # mainly guards against deadlocks during cold model load.
        self._client = httpx.Client(timeout=timeout, base_url=self.base_url)
        self.dims = 4096
        # max_chars is a defensive client-side cap. Server-side `truncate=true`
        # is the source of truth (token-aware), but a 16 MB request body still
        # costs network/parse time even if server discards the tail. 32k chars
        # ≈ 12-16k tokens worst case (Cyrillic) — still gives the server room
        # to truncate to MAX_INPUT_LENGTH=4096 without our help.
        self.max_chars = max_chars
        # TEI MAX_CLIENT_BATCH_SIZE default = 32. Caller's flush buffer can be
        # larger (512) for upsert efficiency, so slice client-side per request.
        self.client_batch_size = max(1, int(client_batch_size))

        if verify_health:
            self._verify_health()

    def _verify_health(self) -> None:
        """Smoke-check that TEI is up and serving the expected model.

        Fails fast if the user forgot to start the `tei` profile, or if the
        compose override pinned a different MODEL_ID. Late discovery via a
        500 from `/embed` mid-reindex would lose the buffered batch.
        """
        import httpx

        try:
            r = self._client.get("/health")
            r.raise_for_status()
        except (httpx.HTTPError, OSError) as e:
            raise RuntimeError(
                f"TEI not reachable at {self.base_url}/health. Start it with: "
                f"`docker compose -f docker/docker-compose.yml "
                f"-f docker/docker-compose.gpu.yml --profile tei up -d tei`. "
                f"Underlying error: {e}"
            ) from e

        # Best-effort model-id check. /info is a TEI extension; some image
        # variants may omit it — treat absence as soft-pass rather than fail.
        try:
            info = self._client.get("/info").json()
            model_id = info.get("model_id")
            if model_id and "Qwen3-Embedding" not in model_id:
                print(
                    f"  [TEI] WARNING: server is serving model_id={model_id!r}, "
                    f"expected Qwen/Qwen3-Embedding-8B. Vectors will not match "
                    f"those indexed by qwen3-st."
                )
        except Exception:  # noqa: BLE001 — /info is optional
            pass

    def _post_embed_sub(self, sub: list[str]) -> list[list[float]]:
        resp = self._client.post(
            "/embed",
            json={
                "inputs": sub,
                "normalize": True,
                "truncate": True,
                "truncation_direction": "Right",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "embeddings" in data:
            data = data["embeddings"]
        if not isinstance(data, list) or len(data) != len(sub):
            raise RuntimeError(
                f"TEI shape: {len(data) if isinstance(data, list) else '?'} vs {len(sub)}"
            )
        return data

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        prefix = self.QUERY_INSTRUCTION if is_query else ""
        inputs = [prefix + t[: self.max_chars] for t in texts]
        out: list[list[float]] = []
        bs = self.client_batch_size
        for s in range(0, len(inputs), bs):
            out.extend(self._post_embed_sub(inputs[s : s + bs]))
        if len(out) != len(texts):
            raise RuntimeError(f"TEI concat: {len(out)} vs {len(texts)}")
        return out

    def embed_late_chunked(
        self,
        parent_text: str,  # noqa: ARG002
        chunk_char_spans: list[tuple[int, int]],  # noqa: ARG002
    ) -> list[list[float] | None]:
        # TEI exposes pooled vectors only; token-level hidden states required
        # for Late Chunking are not in the API surface. Caller (CLI) already
        # guards against this combo — surface a clear error if reached anyway.
        raise NotImplementedError(
            "Late Chunking (Phase 8.12.9) is not supported on TEI backend — "
            "the server returns pooled vectors only. Use --embedder qwen3-st."
        )

    def close(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            client.close()
            self._client = None  # type: ignore[assignment]


def make_embedder(
    name: str,
    batch_size: int = 32,
    enable_fa2: bool = False,
    tei_base_url: str = Qwen3TEIEmbedder.DEFAULT_BASE_URL,
) -> Any:
    """Create embedder by name."""
    if name == "e5":
        return E5Embedder()
    if name == "qwen3":
        from src.bsl.semantic_search.services.qwen3_embedding import Qwen3EmbeddingService

        return Qwen3EmbeddingService()  # type: ignore[return-value]
    if name == "qwen3-st":
        return Qwen3STEmbedder(dtype="bfloat16", batch_size=batch_size, enable_fa2=enable_fa2)
    if name == "qwen3-tei":
        return Qwen3TEIEmbedder(base_url=tei_base_url, client_batch_size=batch_size)
    raise ValueError(f"Unknown embedder: {name}. Use 'e5', 'qwen3', 'qwen3-st', or 'qwen3-tei'")


_LATE_CHUNK_SEP = "\n\n"


def _group_chunks_for_late(
    chunks: list[BSLChunk],
    region_aware: bool,
) -> list[list[int]]:
    """Phase 3 of roadmap 260518 — group chunk indices for Late Chunking.

    `region_aware=False` (Phase 8.12.9 original behaviour): one group per
    `module_path`. Whole module forwards through the embedder in one pass
    (or sliding windows if oversized — Phase 2 of roadmap 260518).

    `region_aware=True` (Phase 3 of roadmap 260518): one group per
    `(module_path, region)`. BSL's `#Область … #КонецОбласти` markers
    are natural semantic boundaries (typically `ОбработчикиСобытийФормы`
    vs `ПрограммныйИнтерфейс` vs `СлужебныеПроцедуры`) — splitting on
    them keeps each forward pass scoped to one semantic concern, which
    matters more than cross-region context. Chunks with empty `region`
    metadata (legacy modules without `#Область`, or symbols outside any
    region) form a separate "<no region>" group per module so they stay
    together and still receive Late Chunking — they just don't share
    context with annotated regions in the same file.

    Group ordering preserves chunk order via `dict` insertion order so
    that the synthesized parent text per group concatenates symbols in
    source order, matching the original Phase 8.12.9 behaviour.
    """
    groups: dict[tuple[str, str], list[int]] = {}
    for idx, c in enumerate(chunks):
        module_path = c.metadata.get("module_path", "")
        region = c.metadata.get("region", "") if region_aware else ""
        groups.setdefault((module_path, region), []).append(idx)
    return list(groups.values())


def _embed_chunks_late(
    embedder: Any,
    chunks: list[BSLChunk],
    region_aware: bool = True,
) -> list[list[float]]:
    """Phase 8.12.9 (A2-alt) — Late Chunking orchestrator.

    Group chunks by `module_path` (Phase 8.12.9) or by
    `(module_path, region)` (Phase 3 of roadmap 260518, `region_aware=True`,
    default), build one parent text per group with a fixed separator, run
    `embed_late_chunked` once per group, then fall back to `embed_batch`
    for any spans that landed past truncation.

    Two-tier fallback chain (after Phase 2 + 3 of roadmap 260518):
      1. Region-aware grouping shrinks parent text → fewer regions hit
         `max_seq_length` at all.
      2. Oversize regions cascade into `embed_late_chunked_sliding`
         (Phase 2) inside the embedder.
      3. Spans that still come back `None` (e.g. chunk longer than one
         window — unusual after Phase 8.12.5 chunk splitting at 6000 chars)
         fall back to `embed_batch` standard pooling.
    """
    groups = _group_chunks_for_late(chunks, region_aware=region_aware)

    out: list[list[float] | None] = [None] * len(chunks)
    for indices in groups:
        spans: list[tuple[int, int]] = []
        parts: list[str] = []
        cursor = 0
        for j, idx in enumerate(indices):
            if j > 0:
                parts.append(_LATE_CHUNK_SEP)
                cursor += len(_LATE_CHUNK_SEP)
            body = chunks[idx].content
            parts.append(body)
            spans.append((cursor, cursor + len(body)))
            cursor += len(body)
        parent_text = "".join(parts)

        vectors = embedder.embed_late_chunked(parent_text, spans)

        fallback_local = [j for j, v in enumerate(vectors) if v is None]
        if fallback_local:
            # 8.12.8 observability: warn when ≥ half of a group's chunks
            # missed Late Chunking (overflowed max_seq_length even after
            # Phase 2 sliding windows + Phase 3 region grouping) — they
            # fall back to standard pooling and lose document context.
            first_path = chunks[indices[0]].metadata.get("module_path", "?")
            first_region = chunks[indices[0]].metadata.get("region", "") or "<no region>"
            if len(fallback_local) * 2 >= len(indices):
                print(
                    f"  [late-chunking] fallback {len(fallback_local)}/{len(indices)} "
                    f"chunks (parent {len(parent_text)} chars) — "
                    f"module_path={first_path} region={first_region}"
                )
            # roadmap 260518 follow-up — always record fallback events
            # (not just severe ones) so post-mortem can compute average
            # fallback% across the full run without scraping noisy stdout.
            _evt(
                "late_chunk_fallback",
                fallback=len(fallback_local),
                group=len(indices),
                parent_chars=len(parent_text),
                module_path=first_path,
                region=first_region,
            )
            fb_texts = [chunks[indices[j]].content for j in fallback_local]
            fb_vecs = embedder.embed_batch(fb_texts, is_query=False)
            for j, fv in zip(fallback_local, fb_vecs):
                vectors[j] = fv

        for j, idx in enumerate(indices):
            out[idx] = vectors[j]

    assert all(v is not None for v in out), "late-chunking missed an index"
    return out  # type: ignore[return-value]


def _is_cuda_oom(exc: BaseException) -> bool:
    """Detect CUDA OOM across torch versions.

    Newer torch raises `torch.cuda.OutOfMemoryError`, older raises plain
    `RuntimeError("CUDA out of memory. ...")`. Match by type name and message
    so we don't have to import torch at module top.
    """
    msg = str(exc).lower()
    name = type(exc).__name__
    return name == "OutOfMemoryError" or "out of memory" in msg or "cuda oom" in msg


from src.bsl.semantic_search.services.bm25_tokenizer import (  # noqa: E402
    normalize_camelcase as _normalize_camelcase_for_bm25,
)


def flush_batch(
    client: QdrantClient,
    embedder: Any,
    collection: str,
    chunks: list[BSLChunk],
    dual_vector: bool = False,
    pooling_mode: str = "standard",
    region_aware: bool = True,
    sparse_encoder: Any = None,
) -> int:
    """Embed and upsert a batch. Returns count of successfully upserted points.

    Phase 8.12 C2: catches CUDA OOM from `embedder.embed_batch`, drops the
    cache, logs the likely culprit (largest chunk by content length), and
    returns 0 so the caller can clear its buffer and continue. Without this,
    a single XXL chunk would crash the entire reindex.

    Phase 8.12.9 A2-alt: when `pooling_mode == "late-chunking"`, route
    passage embedding through `_embed_chunks_late` (full-document forward
    + per-chunk mean-pool). Module-path embeddings stay on `embed_batch`
    because they're standalone strings without a parent context.

    Phase 3 of roadmap 260518: `region_aware` toggles `(module_path, region)`
    grouping vs the legacy `module_path` grouping in `_embed_chunks_late`.
    """
    texts = [c.content for c in chunks]
    try:
        if pooling_mode == "late-chunking":
            vectors = _embed_chunks_late(embedder, chunks, region_aware=region_aware)
        else:
            vectors = embedder.embed_batch(texts, is_query=False)

        # Generate module_path embeddings if dual-vector mode
        mp_vectors = None
        if dual_vector:
            mp_texts = [c.metadata.get("module_path", "") or "" for c in chunks]
            mp_vectors = embedder.embed_batch(mp_texts, is_query=False)

        # Compute BM25 sparse vectors when sparse_encoder is provided.
        # Mirrors smoke + migration: CamelCase-normalize chunk.content, embed
        # via fastembed `Qdrant/bm25`, attach as `bm25` named sparse vector.
        # Empty content -> no sparse entry on the point (dense-only).
        sparse_vectors: list[Any] | None = None
        if sparse_encoder is not None:
            norm_texts = [_normalize_camelcase_for_bm25(t) if t else "" for t in texts]
            sparse_vectors = list(sparse_encoder.embed(norm_texts))
    except Exception as e:  # noqa: BLE001 — we re-raise non-OOM
        if not _is_cuda_oom(e):
            raise
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass
        if chunks:
            largest = max(chunks, key=lambda c: len(c.content))
            name = largest.metadata.get("name", "?")
            print(
                f"  [OOM] flush_batch: dropped batch of {len(chunks)} chunks; "
                f"largest='{name}' ({len(largest.content)} chars). "
                f"Continuing past OOM."
            )
            _evt(
                "oom_recovery",
                batch=len(chunks),
                largest_chars=len(largest.content),
                largest_name=name,
            )
        else:
            print("  [OOM] flush_batch: dropped empty batch (should not happen).")
            _evt("oom_recovery", batch=0)
        return 0

    # Fix #3 (2026-05-21): collect None vectors for retry instead of silent skip.
    # TEI HTTP can race-fail on large batches (returns None for some chunks
    # without raising), causing coverage gap on incremental reindexes.
    points = []
    none_chunks: list[tuple[int, BSLChunk]] = []  # (idx, chunk) for retry

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        if vec is None:
            none_chunks.append((i, chunk))
            continue
        vec_list = vec if isinstance(vec, list) else vec.tolist()

        if sparse_vectors is not None:
            # Hybrid layout: named `dense` + optional `bm25` sparse.
            # Mutually exclusive with dual_vector — refused in main().
            vector_data: Any = {"dense": vec_list}
            sp = sparse_vectors[i]
            if len(sp.indices) > 0:
                vector_data["bm25"] = models.SparseVector(
                    indices=sp.indices.tolist(),
                    values=sp.values.tolist(),
                )
        elif dual_vector and mp_vectors and mp_vectors[i] is not None:
            mp_vec = mp_vectors[i] if isinstance(mp_vectors[i], list) else mp_vectors[i].tolist()
            vector_data = {"content": vec_list, "module_path": mp_vec}
        else:
            vector_data = vec_list

        points.append(
            models.PointStruct(
                id=point_id(collection, chunk.chunk_id),
                vector=vector_data,
                payload=chunk_payload(chunk),
            )
        )

    # Retry None chunks one-by-one (single-element batches typically don't race)
    permanent_drops = 0
    if none_chunks:
        recovered = 0
        for idx, chunk in none_chunks:
            try:
                retry_vecs = embedder.embed_batch([chunk.content], is_query=False)
                if retry_vecs and retry_vecs[0] is not None:
                    vec = retry_vecs[0]
                    vec_list = vec if isinstance(vec, list) else vec.tolist()

                    if sparse_vectors is not None:
                        vector_data = {"dense": vec_list}
                        sp = sparse_vectors[idx]
                        if len(sp.indices) > 0:
                            vector_data["bm25"] = models.SparseVector(
                                indices=sp.indices.tolist(),
                                values=sp.values.tolist(),
                            )
                    elif dual_vector and mp_vectors and mp_vectors[idx] is not None:
                        mp_vec = (
                            mp_vectors[idx]
                            if isinstance(mp_vectors[idx], list)
                            else mp_vectors[idx].tolist()
                        )
                        vector_data = {"content": vec_list, "module_path": mp_vec}
                    else:
                        vector_data = vec_list

                    points.append(
                        models.PointStruct(
                            id=point_id(collection, chunk.chunk_id),
                            vector=vector_data,
                            payload=chunk_payload(chunk),
                        )
                    )
                    recovered += 1
                else:
                    permanent_drops += 1
                    module_path_tail = chunk.module_path[-50:] if chunk.module_path else "unknown"
                    print(f"[DROP] {chunk.chunk_id} @ {module_path_tail}")
                    _evt(
                        "chunk_dropped",
                        reason="retry_returned_none",
                        name=chunk.chunk_id,
                        module_path=chunk.module_path,
                    )
            except Exception as e:
                permanent_drops += 1
                module_path_tail = chunk.module_path[-50:] if chunk.module_path else "unknown"
                print(f"[DROP] {chunk.chunk_id} @ {module_path_tail} (error: {type(e).__name__})")
                _evt(
                    "chunk_dropped",
                    reason="retry_exception",
                    name=chunk.chunk_id,
                    module_path=chunk.module_path,
                    error=str(e),
                )

        print(
            f"[RETRY] flush_batch: {len(none_chunks)} None vectors, recovered={recovered}, dropped={permanent_drops}"
        )

    for start in range(0, len(points), UPSERT_SUB_BATCH):
        _upsert_with_retry(client, collection, points[start : start + UPSERT_SUB_BATCH])
    return len(points)


def _detect_bsl_project(bsl_path: Path) -> Path | None:
    """Walk UP from a .bsl file path to find the nearest BSL project root.

    A BSL project root is any directory containing `.bsl-language-server.json`
    (the standard 1c-syntax/bsl-language-server config). Used by --paths mode
    to auto-derive --project for context enrichment when only file paths are
    passed (e.g. from git hooks).

    Returns the absolute project root, or None if no marker found above.
    """
    # Lazy import to avoid circular dependencies at module load.
    import sys

    repo_root_local = Path(__file__).resolve().parent.parent
    if str(repo_root_local) not in sys.path:
        sys.path.insert(0, str(repo_root_local))
    from src.bsl.project_discovery import find_project_for_path

    return find_project_for_path(bsl_path, repo_root_local)


def _delete_stale_for_paths(
    client: QdrantClient,
    collection: str,
    file_paths: list[str],
    upserted_ids_per_file: dict[str, set[str]],
) -> int:
    """Delete chunks whose module_path matches a reindexed file but whose
    point_id is NOT among the upserted set (= stale chunks from removed
    or renamed BSL symbols).

    Per-file MatchValue filter (exact match) — keyword field semantics
    expected on `module_path` payload key in Qdrant.
    """
    total_deleted = 0
    for fp in file_paths:
        keep = list(upserted_ids_per_file.get(fp, set()))
        flt = models.Filter(
            must=[
                models.FieldCondition(
                    key="module_path",
                    match=models.MatchValue(value=fp),
                ),
            ],
            must_not=[models.HasIdCondition(has_id=keep)] if keep else None,
        )
        try:
            client.delete(
                collection_name=collection,
                points_selector=models.FilterSelector(filter=flt),
                wait=True,
            )
            total_deleted += 1
        except Exception as e:
            print(f"[WARN] delete-stale {fp}: {e}")
    return total_deleted


def main() -> None:
    ap = argparse.ArgumentParser(description="Reindex BSL with embeddings")
    ap.add_argument("--project", type=Path, required=True, help="Project root with BSL files")
    ap.add_argument(
        "--embedder", choices=["e5", "qwen3"], default="e5", help="Embedding model (default: e5)"
    )
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument(
        "--buffer-size",
        type=int,
        default=0,
        help="Chunks to accumulate before flush (0=auto: 512 for qwen3-st, "
        "else --batch-size). Larger buffers give the qwen3-st length "
        "bucketer a fuller pool, increasing throughput.",
    )
    ap.add_argument(
        "--collection",
        default="bsl_code_v4_late",
        help="Default: bsl_code_v4_late (Qwen3+Late, production). "
        "Legacy bsl_code_v3 dropped 2026-04-30 (§27).",
    )
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    ap.add_argument(
        "--enable-sparse",
        action="store_true",
        help="When creating a new collection, use hybrid layout "
        "(named `dense` + sparse `bm25` IDF). Existing collections "
        "with hybrid layout are auto-detected regardless of this "
        "flag — the production alias bsl_code_v4_late (hybrid since "
        "2026-05-22 migration) makes incremental git post-commit "
        "reindexes hybrid automatically.",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max chunks to index (0=all)")
    ap.add_argument("--no-context", action="store_true", help="Skip context enrichment")
    ap.add_argument(
        "--dual-vector", action="store_true", help="Use dual named vectors (content + module_path)"
    )
    # Recovered 2026-06-02: these 6 args were dropped by a merge/autofix regression
    # (existed at b5ff6e9d3) while the code below still references them — restored verbatim.
    ap.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Incremental mode: list of .bsl files to reindex (instead of walking "
        "--project). Used by git post-commit hooks for per-file updates.",
    )
    ap.add_argument(
        "--tei-url",
        default=Qwen3TEIEmbedder.DEFAULT_BASE_URL,
        help=f"qwen3-tei only: base URL of the TEI HTTP server (default: "
        f"{Qwen3TEIEmbedder.DEFAULT_BASE_URL})",
    )
    ap.add_argument(
        "--enable-fa2",
        action="store_true",
        help="qwen3-st only: enable FlashAttention 2 (1.5-2x on long chunks).",
    )
    ap.add_argument(
        "--pooling-mode",
        choices=["standard", "late-chunking"],
        default="standard",
        help="qwen3-st only. 'standard' (default): each chunk embedded independently. "
        "'late-chunking': one forward pass per module, mean-pool per chunk span.",
    )
    ap.add_argument(
        "--sliding-overlap",
        type=float,
        default=None,
        help="Override sliding-window overlap ratio (default 0.15). roadmap 260518 §4.5.",
    )
    ap.add_argument(
        "--no-region-aware",
        action="store_true",
        help="late-chunking only: disable (module_path, region) grouping, revert to "
        "module_path grouping (roadmap 260518 Phase 3). Region-aware is ON by default.",
    )
    args = ap.parse_args()

    # Validate --project / --paths combination.
    if not args.project and not args.paths:
        print("ERROR: either --project or --paths must be provided")
        sys.exit(1)
    if args.paths and args.recreate:
        # Incremental mode must NOT drop the collection — that would remove
        # all other projects' chunks too. Refuse the combination explicitly.
        print("ERROR: --recreate is incompatible with --paths (incremental mode)")
        sys.exit(1)

    if args.paths:
        # --paths mode: auto-derive project root from first valid file.
        path_objs = []
        for p in args.paths:
            pp = Path(p).resolve()
            if pp.suffix.lower() == ".bsl" and pp.is_file() and not should_skip(pp):
                path_objs.append(pp)
        if not path_objs:
            print("[--paths] no valid .bsl files after filtering; nothing to do")
            sys.exit(0)
        if args.project:
            project = args.project.resolve()
        else:
            project = _detect_bsl_project(path_objs[0])
            if project is None:
                print(
                    f"ERROR: cannot auto-detect project root from {path_objs[0]} "
                    f"(expected layout: configuration/<X>/...)"
                )
                sys.exit(1)
            print(f"[--paths] auto-detected project: {project}")
        # Sanity-check: all files must be under the same project root.
        outside = [
            p for p in path_objs if project.resolve() not in p.parents and p != project.resolve()
        ]
        if outside:
            print(f"ERROR: --paths spans multiple projects; outside {project}:")
            for p in outside[:5]:
                print(f"  - {p}")
            sys.exit(1)
    else:
        project = args.project.resolve()

    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    if args.dual_vector and args.embedder in ("qwen3-st", "qwen3-tei"):
        # Qwen3 runs on GPU at ~18 ch/s (ST) or via TEI server-side batching.
        # Embedding the (often empty) module_path field as a second pass
        # doubles wall-clock cost and produces a near-degenerate vector for
        # empty strings. Refuse the combination — Phase 8.8 explicitly chose
        # single-vector for v4; same constraint applies to TEI backend.
        print(f"ERROR: --dual-vector is incompatible with --embedder {args.embedder}")
        print("       (Phase 8.8 uses single-vector 4096d for bsl_code_v4)")
        sys.exit(1)

    t0 = time.time()
    # roadmap 260518 follow-up — initialize module-level tracker so embedder
    # methods (_embed_chunks_late, _embed_late_chunked_sliding, flush_batch)
    # can emit events via the `_evt`/`_state` helpers without threading a
    # tracker handle through every signature. start() launches the daemon
    # heartbeat thread; atexit guarantees run_end on uncaught exception.
    global _tracker
    _tracker = make_tracker("reindex_bsl_qwen3").start()
    _evt(
        "startup",
        embedder=args.embedder,
        project=str(project),
        paths_mode=bool(args.paths),
        pooling_mode=args.pooling_mode,
        region_aware=(not args.no_region_aware),
        collection=args.collection,
        batch_size=args.batch_size,
        recreate=bool(args.recreate),
    )
    parser = BSLASTParser()
    chunker = BSLChunker()
    if args.enable_fa2 and args.embedder != "qwen3-st":
        # FA2 is a sentence-transformers model_kwarg. TEI bakes FA2 into the
        # Rust runtime, so the flag is meaningless on qwen3-tei.
        print(
            f"ERROR: --enable-fa2 requires --embedder qwen3-st (got {args.embedder!r}). "
            f"For qwen3-tei, FlashAttention 2 is built into the TEI runtime."
        )
        sys.exit(1)
    if args.pooling_mode == "late-chunking" and args.embedder != "qwen3-st":
        # TEI returns pooled vectors only — no token-level hidden states.
        # The hook lives on Qwen3STEmbedder.embed_late_chunked.
        print(
            f"ERROR: --pooling-mode late-chunking requires --embedder qwen3-st "
            f"(got {args.embedder!r}). Phase 8.12.9 hook lives on "
            f"Qwen3STEmbedder; qwen3-tei exposes pooled vectors only."
        )
        sys.exit(1)
    if args.pooling_mode == "late-chunking" and args.dual_vector:
        # Late chunking pools transformer hidden states per chunk. Re-running it
        # for the standalone `module_path` strings is meaningless (no parent
        # context) and the current orchestrator only handles the content side.
        print("ERROR: --pooling-mode late-chunking is incompatible with --dual-vector")
        sys.exit(1)
    if args.no_region_aware and args.pooling_mode != "late-chunking":
        # Phase 3 of roadmap 260518 — region grouping only affects the
        # late-chunking orchestrator. Silently ignoring the flag would
        # mislead callers into thinking they had opted out of something
        # that was never on. Refuse the combination explicitly.
        print(
            "ERROR: --no-region-aware requires --pooling-mode late-chunking "
            "(region-aware grouping only applies to the late-chunking "
            "orchestrator — Phase 3 of roadmap 260518)."
        )
        sys.exit(1)
    if (
        args.pooling_mode == "late-chunking"
        and args.embedder == "qwen3-st"
        and not args.enable_fa2
        and _looks_like_cyrillic_project(project)  # noqa: F821
    ):
        # roadmap 260518 §1.2.2 A/B (2026-05-19) showed Phase 2 sliding
        # forward_s is 191-437s without FA2 vs 2.1s with FA2 on Cyrillic
        # BSL — ~91-208× slower, with per-window degradation. Production
        # rollout requires FA2; without it, reindex never finishes in a
        # reasonable wall-clock. Allow override via env to keep a debug
        # escape hatch for benchmarking the no-FA2 path itself.
        if not os.environ.get("BSL_ALLOW_LATE_CHUNKING_WITHOUT_FA2"):
            # Note: keep message strictly ASCII — Windows cp1251 console
            # cannot encode `x` (multiplication sign) nor many Cyrillic
            # path glyphs, and `print()` raises UnicodeEncodeError before
            # sys.exit() can fire. Numbers come from roadmap 260518 §1.2.2.
            print(
                "ERROR: --pooling-mode late-chunking on Cyrillic project "
                "requires --enable-fa2 (see roadmap 260518 section 1.2.2). "
                "Without FA2, per-window forward is 191-437s vs 2.1s with FA2 "
                "(91-208 times slower) and degrades between windows due to "
                "VRAM pressure. Either add --enable-fa2 OR set "
                "BSL_ALLOW_LATE_CHUNKING_WITHOUT_FA2=1 for benchmark mode."
            )
            sys.exit(1)
    if args.sliding_overlap is not None:
        # Override class-level default before instantiation so the new ratio
        # propagates to `_embed_late_chunked_sliding`'s None-fallback. Emit
        # an event so post-mortem analysis can correlate fallback% with the
        # ratio active during the run. Range guard mirrors the ValueError
        # in `_make_char_windows` (overlap must be < window).
        if not 0.0 <= args.sliding_overlap < 1.0:
            print(f"ERROR: --sliding-overlap must be in [0.0, 1.0), got {args.sliding_overlap}")
            sys.exit(1)
        Qwen3STEmbedder.DEFAULT_SLIDING_OVERLAP_RATIO = args.sliding_overlap
        _evt("sliding_overlap_override", ratio=args.sliding_overlap)

    with _stage("model_load", embedder=args.embedder, fa2=bool(args.enable_fa2)):
        embedder = make_embedder(
            args.embedder,
            batch_size=args.batch_size,
            enable_fa2=args.enable_fa2,
            tei_base_url=args.tei_url,
        )
    vector_dims = embedder.dims

    # Auto-pick buffer for length bucketing: qwen3-st benefits from a fuller
    # pool (each bucket gets a meaningful sample); qwen3-tei benefits from a
    # large pool too (TEI's continuous batching merges across requests). Other
    # embedders flush at batch_size like before.
    buffer_size = args.buffer_size
    if buffer_size <= 0:
        if args.embedder in ("qwen3-st", "qwen3-tei"):
            buffer_size = 512
        else:
            buffer_size = args.batch_size

    print(
        f"Embedder: {args.embedder} ({vector_dims}d, batch={args.batch_size}, "
        f"flush every {buffer_size} chunks)"
    )
    if args.pooling_mode != "standard":
        # Phases 1-3 of roadmap 260518 apply only to late-chunking on qwen3-st.
        # Surface them in the run banner so log readers can correlate
        # fallback-rate changes with which phases were active.
        msl = getattr(embedder, "max_seq_length", "?")
        region_state = "off" if args.no_region_aware else "on"
        print(
            f"Pooling mode: {args.pooling_mode} (Phase 8.12.9 A2-alt + "
            f"roadmap 260518 P1 max_seq={msl} + P2 sliding-on-overflow + "
            f"P3 region-aware={region_state})"
        )

    # Phase 63: Context enrichment
    enricher = None
    if not args.no_context:
        try:
            from src.bsl.call_graph.store import CallGraphStore
            from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor

            extractor = MetadataExtractor(project)
            cg_db = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
            cg = CallGraphStore(cg_db) if cg_db.exists() else None
            enricher = BSLContextEnricher(metadata_extractor=extractor, call_graph=cg)
            obj_stats = extractor.stats()
            print(
                f"Context enrichment ON: {obj_stats['total']} objects"
                f"{', call graph loaded' if cg else ''}"
            )
        except Exception as e:
            print(f"Context enrichment unavailable: {e}")
            enricher = None

    qdrant = QdrantClient(host="localhost", port=6333, timeout=30)
    layout = create_collection(
        qdrant,
        args.collection,
        vector_dims,
        args.recreate,
        dual_vector=args.dual_vector,
        enable_sparse=args.enable_sparse,
    )
    if args.dual_vector:
        print("Dual-vector mode: content + module_path named vectors")

    # Auto-init sparse encoder when collection layout is hybrid (covers both
    # explicit --enable-sparse on a fresh collection and the incremental
    # case of reindexing into an existing hybrid collection like the
    # production alias bsl_code_v4_late).
    sparse_encoder = None
    if layout == "hybrid":  # noqa: F821
        from fastembed import SparseTextEmbedding

        sparse_encoder = SparseTextEmbedding(model_name="Qdrant/bm25")
        print("Hybrid layout: BM25 sparse vectors via fastembed Qdrant/bm25")

    with _stage("file_scan", project=str(project), paths_mode=bool(args.paths)):
        if args.paths:
            bsl_files = sorted(path_objs)
            print(f"[--paths] processing {len(bsl_files)} file(s)")
        else:
            bsl_files = sorted(f for f in project.rglob("*.bsl") if not should_skip(f))
            print(f"Found {len(bsl_files)} BSL files")
    _evt("file_scan_done", count=len(bsl_files))
    _state(total_files=len(bsl_files), file_idx=0, chunks_done=0)

    # Track point_ids upserted per file → enables delete-stale at end of run.
    # Stale = chunks at the same module_path that we did NOT touch this run
    # (= removed/renamed BSL symbols, or duplicates from prior runs with
    # different chunk_id schema, e.g. switching pooling mode).
    # Fix #6 (2026-05-21): enable delete-stale in --project mode too — previously
    # only --paths mode cleaned stale chunks, allowing 30k+ duplicates to
    # accumulate across pooling-mode changes (Late Chunking → Standard).
    upserted_ids_per_file: dict[str, set[str]] = {}
    paths_to_clean: list[str] = [str(p) for p in bsl_files]

    total_symbols = 0
    total_chunks = 0
    errors = 0
    batch: list[BSLChunk] = []

    for i, fp in enumerate(bsl_files, 1):
        # roadmap 260518 follow-up — push per-file state so heartbeat
        # (10s daemon thread) prints `current=<file>` even when the
        # current file's flush_batch sits in a multi-window GPU forward.
        _state(file_idx=i, current=fp.name, chunks_done=total_chunks)
        try:
            module = parser.parse_file(str(fp))
            chunks = chunker.chunk_module(module)
            if enricher:
                enricher.enrich(chunks)
            total_symbols += len(module.symbols)

            # Pre-record point_ids for every chunk produced for this file so
            # we can compute the keep-set for delete-stale (always, not just
            # --paths mode — see Fix #6 above).
            fp_str = str(fp)
            ids = upserted_ids_per_file.setdefault(fp_str, set())
            for ch in chunks:
                ids.add(point_id(args.collection, ch.chunk_id))

            for chunk in chunks:
                batch.append(chunk)
                if len(batch) >= args.batch_size:
                    n = flush_batch(
                        qdrant, embedder, args.collection, batch, dual_vector=args.dual_vector
                    )
                    total_chunks += n
                    batch.clear()
                    if args.limit and total_chunks >= args.limit:
                        break

            if args.limit and total_chunks >= args.limit:
                break

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"[ERROR] {fp.name}: {e}")

        if i % 100 == 0:
            elapsed = time.time() - t0
            print(
                f"[{i}/{len(bsl_files)}] {total_symbols} symbols, {total_chunks} chunks, {elapsed:.0f}s"
            )

    # Flush remaining
    if batch:
        n = flush_batch(
            qdrant,
            embedder,
            args.collection,
            batch,
            dual_vector=args.dual_vector,
            pooling_mode=args.pooling_mode,
            region_aware=not args.no_region_aware,
            sparse_encoder=sparse_encoder,
        )
        total_chunks += n

    # Delete stale chunks for files we just reindexed (--paths AND --project).
    # Any chunk at the same module_path whose point_id we did NOT upsert
    # is from a removed/renamed BSL symbol OR a previous run with different
    # chunk_id schema (e.g. pooling-mode change) and must go.
    # Fix #6 (2026-05-21): unconditional on paths_to_clean — was previously
    # `args.paths and paths_to_clean`, which left --project mode accumulating
    # 30k+ duplicates.
    if paths_to_clean:
        cleaned = _delete_stale_for_paths(
            qdrant,
            args.collection,
            paths_to_clean,
            upserted_ids_per_file,
        )
        mode = "--paths" if args.paths else "--project"
        print(f"[{mode}] delete-stale: {cleaned} files cleaned")

    elapsed = time.time() - t0
    print(f"\n{'=' * 50}")
    print("REINDEX COMPLETE")
    print(f"{'=' * 50}")
    print(f"  Files:    {len(bsl_files)}")
    print(f"  Symbols:  {total_symbols}")
    print(f"  Chunks:   {total_chunks}")
    print(f"  Errors:   {errors}")
    print(f"  Time:     {elapsed:.1f}s ({elapsed / max(len(bsl_files), 1):.2f}s/file)")
    print(f"  Collection: {args.collection}")
    print(f"{'=' * 50}")

    embedder.close()
    # roadmap 260518 follow-up — final summary lands in JSONL run_end record;
    # makes it possible to script "compare last 3 runs" without parsing
    # the per-line `[evt]` stdout.
    _tracker.stop(
        summary={
            "files": len(bsl_files),
            "symbols": total_symbols,
            "chunks": total_chunks,
            "errors": errors,
            "elapsed_s": round(elapsed, 1),
            "collection": args.collection,
        }
    )


if __name__ == "__main__":
    main()
