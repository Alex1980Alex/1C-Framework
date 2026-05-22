#!/usr/bin/env python3
"""
scripts/bench_qwen3_embedding.py

Benchmark Qwen3-Embedding-8B inference (via sentence-transformers) on GPU RTX 3090 fp16.
Fetches 1000 BSL chunks from a local Qdrant (collection bsl_code_v4), runs them through
the model in 3 different sequence-length/batch-size modes, measures throughput and VRAM peak.

Usage:
    python scripts/bench_qwen3_embedding.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "bsl_code_v4"
MODEL_ID = "Qwen/Qwen3-Embedding-8B"

BENCH_MODES: list[dict[str, Any]] = [
    {"label": "seq~512  b=8", "batch_size": 8, "n_chunks": 1000, "char_cap": 1800},
    {"label": "seq~2048 b=4", "batch_size": 4, "n_chunks": 400, "char_cap": 7000},
    {"label": "seq~8192 b=2", "batch_size": 2, "n_chunks": 100, "char_cap": 28000},
]

ACCEPTANCE_RATE = 30.0  # chunks/sec for the first mode (b=8)


def fetch_chunks(n: int) -> list[str]:
    """Scroll Qdrant for up to n payload['content'] strings."""
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll"
    chunks: list[str] = []
    offset: Any = None

    while len(chunks) < n:
        payload: dict[str, Any] = {
            "limit": min(100, n - len(chunks)),
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            payload["offset"] = offset

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))

        points = data.get("result", {}).get("points", [])
        if not points:
            break

        for point in points:
            content = point.get("payload", {}).get("content")
            if content is not None:
                chunks.append(str(content))

        offset = data.get("result", {}).get("next_page_offset")
        if offset is None:
            break

    return chunks[:n]


def bench(
    model: SentenceTransformer, texts: list[str], batch_size: int, label: str
) -> dict[str, Any]:
    """Run a single benchmark mode, returning stats or error status."""
    print(f"\n--- Running benchmark: {label} ---", flush=True)
    print(f"    Chunks: {len(texts)}, Batch size: {batch_size}", flush=True)

    result: dict[str, Any] = {
        "label": label,
        "batch_size": batch_size,
        "n_chunks": len(texts),
        "status": "FAIL",
        "error": None,
        "rate_chunks_sec": 0.0,
        "vram_peak_gb": 0.0,
        "time_sec": 0.0,
    }

    try:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats(device="cuda")

        t0 = time.perf_counter()

        _ = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )

        torch.cuda.synchronize()
        t1 = time.perf_counter()

        elapsed = t1 - t0
        vram_peak = torch.cuda.max_memory_allocated(device="cuda") / (1024**3)

        result["status"] = "OK"
        result["time_sec"] = round(elapsed, 4)
        result["vram_peak_gb"] = round(vram_peak, 3)
        result["rate_chunks_sec"] = round(len(texts) / elapsed, 2)

        print("    Status: OK", flush=True)
        print(f"    Time:   {result['time_sec']} sec", flush=True)
        print(f"    Rate:   {result['rate_chunks_sec']} chunks/sec", flush=True)
        print(f"    VRAM:   {result['vram_peak_gb']} GB", flush=True)

    except torch.cuda.OutOfMemoryError:
        result["error"] = "CUDA OutOfMemoryError"
        print("    Status: FAILED (CUDA OutOfMemoryError)", flush=True)
        torch.cuda.empty_cache()
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
        print(f"    Status: FAILED ({type(e).__name__})", flush=True)

    return result


def main() -> int:
    print("=" * 60, flush=True)
    print("PDF Vector Framework - Phase 8.4: Qwen3-Embedding-8B Benchmark", flush=True)
    print("=" * 60, flush=True)

    if not torch.cuda.is_available():
        print("FAIL: CUDA is not available. An NVIDIA GPU is required.", flush=True)
        return 2

    print(f"\nDevice: {torch.cuda.get_device_name(0)}", flush=True)

    print(f"\nLoading model: {MODEL_ID} ...", flush=True)
    t_load_start = time.perf_counter()
    try:
        model = SentenceTransformer(
            MODEL_ID,
            device="cuda",
            model_kwargs={"torch_dtype": torch.float16},
        )
    except Exception as e:
        print(f"FAIL: Error loading model: {e}", flush=True)
        return 2

    t_load_end = time.perf_counter()
    print(f"Model loaded in {round(t_load_end - t_load_start, 2)} sec.", flush=True)

    max_chunks_needed = max(mode["n_chunks"] for mode in BENCH_MODES)
    print(f"\nFetching {max_chunks_needed} chunks from Qdrant ({COLLECTION_NAME})...", flush=True)

    chunks = fetch_chunks(max_chunks_needed)
    print(f"Fetched {len(chunks)} chunks.", flush=True)

    if len(chunks) < max_chunks_needed:
        print(
            f"FAIL: Not enough chunks. Needed {max_chunks_needed}, got {len(chunks)}.", flush=True
        )
        return 3

    results: list[dict[str, Any]] = []
    for mode in BENCH_MODES:
        n = mode["n_chunks"]
        cap = mode["char_cap"]
        texts = [c[:cap] for c in chunks[:n]]
        res = bench(
            model=model,
            texts=texts,
            batch_size=mode["batch_size"],
            label=mode["label"],
        )
        results.append(res)

    print("\n" + "=" * 60, flush=True)
    print("ACCEPTANCE CHECK", flush=True)
    print("=" * 60, flush=True)

    primary_run = results[0]
    is_pass = primary_run["status"] == "OK" and primary_run["rate_chunks_sec"] >= ACCEPTANCE_RATE

    status_str = "PASS" if is_pass else "FAIL"
    print(f"Mode: {primary_run['label']}", flush=True)
    print(
        f"Rate: {primary_run['rate_chunks_sec']} chunks/sec (Target: >= {ACCEPTANCE_RATE})",
        flush=True,
    )
    print(f"Result: {status_str}", flush=True)

    final_output = {
        "model": MODEL_ID,
        "results": results,
        "acceptance": {
            "target_rate": ACCEPTANCE_RATE,
            "actual_rate": primary_run["rate_chunks_sec"],
            "status": status_str,
        },
    }

    print("\nFinal JSON Output:", flush=True)
    print(json.dumps(final_output, indent=2, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
