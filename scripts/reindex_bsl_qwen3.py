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
from pathlib import Path
from typing import Any

# Phase 8.12 C4: enable expandable_segments to fight VRAM fragmentation
# from mixed-length BSL chunks (p99/max can be 50× p50). Must precede
# `import torch` to take effect (CUDA caching allocator reads it once).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

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


def create_collection(client: QdrantClient, name: str, dims: int, recreate: bool = False, dual_vector: bool = False) -> None:
    if recreate:
        try:
            client.delete_collection(collection_name=name)
            print(f"Deleted existing collection: {name}")
        except (UnexpectedResponse, Exception):
            pass

    try:
        info = client.get_collection(collection_name=name)
        print(f"Collection '{name}' exists: {info.points_count} points")
    except (UnexpectedResponse, Exception):
        if dual_vector:
            client.create_collection(
                collection_name=name,
                vectors_config={
                    "content": models.VectorParams(size=dims, distance=models.Distance.COSINE),
                    "module_path": models.VectorParams(size=dims, distance=models.Distance.COSINE),
                },
            )
            print(f"Created dual-vector collection: {name} (content+module_path, {dims}d, cosine)")
        else:
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=dims,
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"Created collection: {name} (dims={dims}, cosine)")


def point_id(collection: str, chunk_id: str) -> str:
    # Namespace by collection so v3 and v4 produce distinct UUIDs for the same chunk_id.
    return str(uuid.uuid5(UUID_NAMESPACE, f"{collection}-{chunk_id}"))


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
        4097+   → 1    (XXL, 0.7% — includes outliers up to 16854 tokens)
    """

    MODEL_ID = "Qwen/Qwen3-Embedding-8B"

    # (token_upper_bound or None for "unbounded", batch_size). Order matters
    # — first match wins, so list shortest→longest.
    DEFAULT_BUCKETS: tuple[tuple[int | None, int], ...] = (
        (512, 32),
        (1024, 16),
        (2048, 8),
        (4096, 4),
        (None, 1),
    )

    def __init__(
        self,
        dtype: str = "bfloat16",
        batch_size: int = 32,
        buckets: tuple[tuple[int | None, int], ...] | None = None,
        enable_fa2: bool = False,
        max_seq_length: int = 4096,
    ) -> None:
        # Phase 8.12 C4 (defense-in-depth — also set at module top in case
        # this class is imported and instantiated from a context that
        # imported torch before our module).
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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
                (upper, min(default_bs, batch_size))
                for upper, default_bs in self.DEFAULT_BUCKETS
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
            len(tokenizer(
                t,
                add_special_tokens=True,
                truncation=True,
                max_length=self.max_seq_length,
                return_tensors=None,
            )["input_ids"])
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
                f"b{bs}={len(idxs)}"
                for bs, idxs in sorted(groups.items(), reverse=True)
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

    def close(self) -> None:
        import gc

        import torch

        if getattr(self, "model", None) is None:
            return
        self.model = None
        gc.collect()
        torch.cuda.empty_cache()


def make_embedder(name: str, batch_size: int = 32, enable_fa2: bool = False) -> Any:
    """Create embedder by name."""
    if name == "e5":
        return E5Embedder()
    if name == "qwen3":
        from src.bsl.semantic_search.services.qwen3_embedding import Qwen3EmbeddingService
        return Qwen3EmbeddingService()  # type: ignore[return-value]
    if name == "qwen3-st":
        return Qwen3STEmbedder(dtype="bfloat16", batch_size=batch_size, enable_fa2=enable_fa2)
    raise ValueError(f"Unknown embedder: {name}. Use 'e5', 'qwen3', or 'qwen3-st'")


def _is_cuda_oom(exc: BaseException) -> bool:
    """Detect CUDA OOM across torch versions.

    Newer torch raises `torch.cuda.OutOfMemoryError`, older raises plain
    `RuntimeError("CUDA out of memory. ...")`. Match by type name and message
    so we don't have to import torch at module top.
    """
    msg = str(exc).lower()
    name = type(exc).__name__
    return name == "OutOfMemoryError" or "out of memory" in msg or "cuda oom" in msg


def flush_batch(
    client: QdrantClient,
    embedder: Any,
    collection: str,
    chunks: list[BSLChunk],
    dual_vector: bool = False,
) -> int:
    """Embed and upsert a batch. Returns count of successfully upserted points.

    Phase 8.12 C2: catches CUDA OOM from `embedder.embed_batch`, drops the
    cache, logs the likely culprit (largest chunk by content length), and
    returns 0 so the caller can clear its buffer and continue. Without this,
    a single XXL chunk would crash the entire reindex.
    """
    texts = [c.content for c in chunks]
    try:
        vectors = embedder.embed_batch(texts, is_query=False)

        # Generate module_path embeddings if dual-vector mode
        mp_vectors = None
        if dual_vector:
            mp_texts = [c.metadata.get("module_path", "") or "" for c in chunks]
            mp_vectors = embedder.embed_batch(mp_texts, is_query=False)
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
        else:
            print("  [OOM] flush_batch: dropped empty batch (should not happen).")
        return 0

    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        if vec is None:
            continue
        vec_list = vec if isinstance(vec, list) else vec.tolist()

        if dual_vector and mp_vectors and mp_vectors[i] is not None:
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

    for start in range(0, len(points), UPSERT_SUB_BATCH):
        _upsert_with_retry(client, collection, points[start:start + UPSERT_SUB_BATCH])
    return len(points)


def main() -> None:
    ap = argparse.ArgumentParser(description="Reindex BSL with embeddings")
    ap.add_argument("--project", type=Path, required=True, help="Project root with BSL files")
    ap.add_argument(
        "--embedder",
        choices=["e5", "qwen3", "qwen3-st"],
        default="e5",
        help="Embedding model (default: e5; Phase 8.8 uses qwen3-st)",
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
    ap.add_argument("--collection", default="bsl_code_v3")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    ap.add_argument("--limit", type=int, default=0, help="Max chunks to index (0=all)")
    ap.add_argument("--no-context", action="store_true", help="Skip context enrichment")
    ap.add_argument("--dual-vector", action="store_true", help="Use dual named vectors (content + module_path)")
    ap.add_argument(
        "--enable-fa2",
        action="store_true",
        help="qwen3-st only: enable FlashAttention 2 (1.5-2x on long chunks). "
             "Requires `pip install flash-attn` and CUDA 12.x toolkit + MSVC on Windows. "
             "Auto-applies left-padding (Phase 8.12 C6) - required for FA2 + last-token pooling.",
    )
    args = ap.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    if args.dual_vector and args.embedder == "qwen3-st":
        # Qwen3-ST runs on GPU at ~18 ch/s. Embedding the (often empty)
        # module_path field as a second pass doubles wall-clock cost and
        # produces a near-degenerate vector for empty strings. Refuse the
        # combination — Phase 8.8 explicitly chose single-vector for v4.
        print("ERROR: --dual-vector is incompatible with --embedder qwen3-st")
        print("       (Phase 8.8 uses single-vector 4096d for bsl_code_v4)")
        sys.exit(1)

    t0 = time.time()
    parser = BSLASTParser()
    chunker = BSLChunker()
    if args.enable_fa2 and args.embedder != "qwen3-st":
        print(f"ERROR: --enable-fa2 requires --embedder qwen3-st (got {args.embedder!r})")
        sys.exit(1)
    embedder = make_embedder(args.embedder, batch_size=args.batch_size, enable_fa2=args.enable_fa2)
    vector_dims = embedder.dims

    # Auto-pick buffer for length bucketing: qwen3-st benefits from a fuller
    # pool (each bucket gets a meaningful sample); other embedders flush at
    # batch_size like before.
    buffer_size = args.buffer_size
    if buffer_size <= 0:
        buffer_size = 512 if args.embedder == "qwen3-st" else args.batch_size

    print(f"Embedder: {args.embedder} ({vector_dims}d, batch={args.batch_size}, "
          f"flush every {buffer_size} chunks)")

    # Phase 63: Context enrichment
    enricher = None
    if not args.no_context:
        try:
            from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor
            from src.bsl.call_graph.store import CallGraphStore

            extractor = MetadataExtractor(project)
            cg_db = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
            cg = CallGraphStore(cg_db) if cg_db.exists() else None
            enricher = BSLContextEnricher(metadata_extractor=extractor, call_graph=cg)
            obj_stats = extractor.stats()
            print(f"Context enrichment ON: {obj_stats['total']} objects"
                  f"{', call graph loaded' if cg else ''}")
        except Exception as e:
            print(f"Context enrichment unavailable: {e}")
            enricher = None

    qdrant = QdrantClient(host="localhost", port=6333, timeout=120)
    create_collection(qdrant, args.collection, vector_dims, args.recreate, dual_vector=args.dual_vector)
    if args.dual_vector:
        print("Dual-vector mode: content + module_path named vectors")

    bsl_files = sorted(f for f in project.rglob("*.bsl") if not should_skip(f))
    print(f"Found {len(bsl_files)} BSL files")

    total_symbols = 0
    total_chunks = 0
    errors = 0
    batch: list[BSLChunk] = []

    for i, fp in enumerate(bsl_files, 1):
        try:
            module = parser.parse_file(str(fp))
            chunks = chunker.chunk_module(module)
            if enricher:
                enricher.enrich(chunks)
            total_symbols += len(module.symbols)

            for chunk in chunks:
                batch.append(chunk)
                if len(batch) >= buffer_size:
                    # Phase 8.12 C3: clear the buffer in `finally` so a
                    # mid-flush OOM (or any other exception) cannot leave
                    # the previous batch around to grow unbounded — the
                    # zombie-loop bug that ate ~75% of the 28.04 reindex.
                    try:
                        n = flush_batch(qdrant, embedder, args.collection, batch, dual_vector=args.dual_vector)
                        total_chunks += n
                    finally:
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
            print(f"[{i}/{len(bsl_files)}] {total_symbols} symbols, {total_chunks} chunks, {elapsed:.0f}s")

    # Flush remaining
    if batch:
        n = flush_batch(qdrant, embedder, args.collection, batch, dual_vector=args.dual_vector)
        total_chunks += n

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"REINDEX COMPLETE")
    print(f"{'='*50}")
    print(f"  Files:    {len(bsl_files)}")
    print(f"  Symbols:  {total_symbols}")
    print(f"  Chunks:   {total_chunks}")
    print(f"  Errors:   {errors}")
    print(f"  Time:     {elapsed:.1f}s ({elapsed/max(len(bsl_files),1):.2f}s/file)")
    print(f"  Collection: {args.collection}")
    print(f"{'='*50}")

    embedder.close()


if __name__ == "__main__":
    main()
