"""
Optimization sweep for Qwen3-Embedding-8B on RTX 3090.
Tests combinations of dtype x batch_size at seq~512 and reports best throughput.

Run command:
    .venv/Scripts/python.exe tmp/phase8/8.4b_optimize.py
"""

from __future__ import annotations

import gc
import json
import time
import urllib.request
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "bsl_code_v4"
MODEL_ID = "Qwen/Qwen3-Embedding-8B"
N_CHUNKS = 1000
CHAR_CAP = 1800

DTYPES = {
    "fp16": torch.float16,
    "bf16": torch.bfloat16,
}
BATCH_SIZES = [8, 16, 32]
BASELINE_RATE = 17.84


def fetch_chunks(n: int) -> list[str]:
    chunks: list[str] = []
    offset = None
    while len(chunks) < n:
        url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll"
        payload: dict[str, Any] = {"limit": min(100, n - len(chunks)), "with_payload": True}
        if offset is not None:
            payload["offset"] = offset
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        points = data.get("result", {}).get("points", [])
        if not points:
            break
        for p in points:
            content = (p.get("payload") or {}).get("content", "")
            if content:
                chunks.append(content[:CHAR_CAP])
        offset = data.get("result", {}).get("next_page_offset")
        if offset is None:
            break
    return chunks[:n]


def main() -> int:
    if not torch.cuda.is_available():
        print("No CUDA available", flush=True)
        return 2

    print(f"Device: {torch.cuda.get_device_name(0)}", flush=True)
    total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"Total VRAM: {round(total_vram, 2)} GB", flush=True)

    print(f"\nFetching {N_CHUNKS} chunks...", flush=True)
    texts = fetch_chunks(N_CHUNKS)
    if len(texts) < N_CHUNKS:
        print(f"Not enough chunks: got {len(texts)}, need {N_CHUNKS}", flush=True)
        return 3
    print(f"Fetched {len(texts)} chunks", flush=True)

    results: list[dict[str, Any]] = []

    for dtype_name, dtype_val in DTYPES.items():
        print(f"\n--- Loading model with dtype={dtype_name} ---", flush=True)
        t_load = time.perf_counter()
        model: SentenceTransformer | None = None
        try:
            model = SentenceTransformer(
                MODEL_ID,
                device="cuda",
                model_kwargs={"torch_dtype": dtype_val},
            )
        except Exception as e:
            err = f"Model load failed: {type(e).__name__}: {e}"
            print(err, flush=True)
            for bs in BATCH_SIZES:
                results.append({
                    "dtype": dtype_name,
                    "batch_size": bs,
                    "n_chunks": N_CHUNKS,
                    "status": "FAIL",
                    "error": err,
                    "rate_chunks_sec": 0.0,
                    "vram_peak_gb": 0.0,
                    "time_sec": 0.0,
                })
            continue
        print(f"  loaded in {round(time.perf_counter() - t_load, 1)}s", flush=True)

        for bs in BATCH_SIZES:
            print(f"  dtype={dtype_name} batch_size={bs} ...", end=" ", flush=True)
            row: dict[str, Any] = {
                "dtype": dtype_name,
                "batch_size": bs,
                "n_chunks": N_CHUNKS,
                "status": "FAIL",
                "error": None,
                "rate_chunks_sec": 0.0,
                "vram_peak_gb": 0.0,
                "time_sec": 0.0,
            }
            try:
                _ = model.encode(
                    texts[:bs],
                    batch_size=bs,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=False,
                )
                torch.cuda.synchronize()

                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()

                t0 = time.perf_counter()
                with torch.inference_mode():
                    _ = model.encode(
                        texts,
                        batch_size=bs,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                        normalize_embeddings=False,
                    )
                torch.cuda.synchronize()
                t1 = time.perf_counter()

                elapsed = t1 - t0
                vram_gb = torch.cuda.max_memory_allocated() / (1024**3)
                rate = len(texts) / elapsed

                row["status"] = "OK"
                row["rate_chunks_sec"] = round(rate, 2)
                row["vram_peak_gb"] = round(vram_gb, 3)
                row["time_sec"] = round(elapsed, 4)

                print(
                    f"OK  rate={row['rate_chunks_sec']:.2f} ch/s  "
                    f"vram={row['vram_peak_gb']:.3f} GB  time={row['time_sec']:.4f}s",
                    flush=True,
                )

            except torch.cuda.OutOfMemoryError as e:
                row["error"] = f"OOM: {e}"
                print("OOM", flush=True)
                torch.cuda.empty_cache()

            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"
                print(f"ERROR: {row['error']}", flush=True)

            results.append(row)

        if model is not None:
            del model
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    print("\n" + "=" * 80, flush=True)
    print("SUMMARY", flush=True)
    print("=" * 80, flush=True)
    print(f"{'dtype':<6} {'batch':<8} {'rate ch/s':<12} {'vram GB':<10} {'status':<6}", flush=True)
    print("-" * 50, flush=True)
    for r in results:
        print(
            f"{r['dtype']:<6} {r['batch_size']:<8} "
            f"{r['rate_chunks_sec']:<12.2f} {r['vram_peak_gb']:<10.3f} {r['status']:<6}",
            flush=True,
        )

    ok_rows = [r for r in results if r["status"] == "OK"]
    if ok_rows:
        best = max(ok_rows, key=lambda r: r["rate_chunks_sec"])
        speedup = best["rate_chunks_sec"] / BASELINE_RATE
        print(
            f"\nBEST: dtype={best['dtype']} batch_size={best['batch_size']} "
            f"rate={best['rate_chunks_sec']:.2f} ch/s  vram={best['vram_peak_gb']:.3f} GB",
            flush=True,
        )
        print(f"Speedup vs baseline ({BASELINE_RATE} ch/s): {speedup:.2f}x", flush=True)
    else:
        print("\nNo successful runs.", flush=True)

    output = {"model": MODEL_ID, "results": results}
    print("\n" + json.dumps(output, indent=2, ensure_ascii=False), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
