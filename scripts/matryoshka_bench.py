"""Matryoshka A/B bench — roadmap 260509 §4.1.

Re-embed `pdf_documents` text on the local GPU at 3 dims (4096 / 1024 / 512)
using Qwen3-Embedding-8B with truncate-and-renormalize, then run keyword
recall@10 against `data/eval/golden_v1.json`.

Why local GPU instead of TEI:
    TEI returns only the pooled 4096d vector — truncation needs client-side
    `vec[:dim]` + renormalize (L2). Both happen here in one place.

Why keyword recall@10 instead of NDCG@10:
    `expected_chunk_ids` is empty in current golden_v1 (40 templated items
    pending v2.0 grounding pass per roadmap §7.5). `expected_keywords` is
    populated for all 40 items. Keyword recall is a recognized retrieval
    proxy when click-through / judgement data is unavailable.

Acceptance per §4.1.3:
    delta_rel < 5%   → recommend production migration (MIGRATE)
    5%-10%           → keep 4096d primary, MRL as opt-in (OPT_IN)
    >10%             → reject MRL, close experiment with measured loss (REJECT)

Usage:
    python scripts/matryoshka_bench.py --reembed
    python scripts/matryoshka_bench.py --evaluate
    python scripts/matryoshka_bench.py --full --report data/eval/matryoshka_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# Reuse production Qwen3 ST embedder from the BSL reindex pipeline.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reindex_bsl_qwen3 import Qwen3STEmbedder  # noqa: E402

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models  # noqa: E402

logger = logging.getLogger("matryoshka_bench")

SOURCE_COLLECTION = "pdf_documents"
SOURCE_TEXT_FIELD = "content"  # pdf_documents uses `content`, not `text`
TARGET_DIMS = (4096, 1024, 512)
TOP_K = 10
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = PROJECT_ROOT / "data" / "eval" / "golden_v1.json"
DEFAULT_QDRANT = "http://localhost:6333"


def target_collection_name(dim: int) -> str:
    """Stable naming: pdf_documents_mrl_<dim>."""
    return f"pdf_documents_mrl_{dim}"


def truncate_and_normalize(vec: list[float], target_dim: int) -> list[float]:
    """First `target_dim` components, L2-renormalized.

    Matryoshka models store coarse-to-fine info from low to high indices,
    so prefix truncation yields a usable shorter vector. Cosine distance
    on Qdrant requires unit-normalized inputs — without renormalize,
    truncated vectors have norm < 1 and similarity scores drift.
    """
    arr = np.asarray(vec[:target_dim], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr.tolist()  # degenerate — preserve zero
    return (arr / norm).tolist()


# ─── Re-embed phase ─────────────────────────────────────────────────────────


def scroll_source_chunks(client: QdrantClient) -> list[dict[str, Any]]:
    """Pull every chunk from pdf_documents with id + content + full payload."""
    rows: list[dict[str, Any]] = []
    offset: Any = None
    while True:
        pts, next_offset = client.scroll(
            collection_name=SOURCE_COLLECTION,
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for p in pts:
            text = (p.payload or {}).get(SOURCE_TEXT_FIELD, "")
            if not text:
                continue
            rows.append({"id": p.id, "text": text, "payload": p.payload or {}})
        if next_offset is None:
            break
        offset = next_offset
    return rows


def reembed_all(
    client: QdrantClient,
    embedder: Qwen3STEmbedder,
    batch_size: int = 8,
) -> None:
    """Re-embed source once at 4096d, derive 1024d/512d locally, upsert all 3."""
    logger.info("Scrolling source %s...", SOURCE_COLLECTION)
    rows = scroll_source_chunks(client)
    if not rows:
        raise RuntimeError(f"No rows with `{SOURCE_TEXT_FIELD}` in {SOURCE_COLLECTION}")
    logger.info("Total chunks to re-embed: %d", len(rows))

    for dim in TARGET_DIMS:
        name = target_collection_name(dim)
        if client.collection_exists(name):
            logger.info("Dropping existing %s", name)
            client.delete_collection(name)
        logger.info("Creating %s (%dd cosine)", name, dim)
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=dim, distance=models.Distance.COSINE
            ),
        )

    logger.info("Embedding %d chunks at 4096d on local GPU...", len(rows))
    t0 = time.time()
    upserted: dict[int, int] = {d: 0 for d in TARGET_DIMS}
    for s in range(0, len(rows), batch_size):
        batch = rows[s : s + batch_size]
        texts = [r["text"] for r in batch]
        vectors_4096 = embedder.embed_batch(texts, is_query=False)

        for dim in TARGET_DIMS:
            points: list[models.PointStruct] = []
            for r, v_full in zip(batch, vectors_4096, strict=True):
                v = (
                    truncate_and_normalize(v_full, dim)
                    if dim < 4096
                    else list(v_full)  # 4096d already unit-normalized by Qwen3 ST
                )
                points.append(
                    models.PointStruct(id=r["id"], vector=v, payload=r["payload"])
                )
            client.upsert(
                collection_name=target_collection_name(dim),
                points=points,
                wait=True,
            )
            upserted[dim] += len(points)

        if (s // batch_size) % 4 == 0 or s + batch_size >= len(rows):
            logger.info(
                "Progress: %d/%d chunks (%.1fs elapsed)",
                min(s + batch_size, len(rows)),
                len(rows),
                time.time() - t0,
            )

    logger.info(
        "Re-embed done in %.1fs. Per-dim upserts: %s",
        time.time() - t0,
        upserted,
    )


# ─── Evaluate phase ─────────────────────────────────────────────────────────


def load_golden() -> list[dict[str, Any]]:
    """Load golden_v1 items that have both query and expected_keywords."""
    if not GOLDEN_PATH.is_file():
        raise FileNotFoundError(f"golden_v1 dataset not at {GOLDEN_PATH}")
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return [
        it for it in raw["items"]
        if it.get("expected_keywords") and it.get("query")
    ]


def keyword_recall(retrieved_texts: list[str], keywords: list[str]) -> float:
    """Fraction of expected keywords found via case-insensitive substring."""
    if not keywords:
        return 0.0
    blob = "\n".join(retrieved_texts).lower()
    hits = sum(1 for kw in keywords if kw.lower() in blob)
    return hits / len(keywords)


def percentile(values: list[float], p: int) -> float:
    """Inclusive percentile via sorted-index pick."""
    if not values:
        return 0.0
    s = sorted(values)
    k = int(len(s) * p / 100)
    return s[min(k, len(s) - 1)]


def evaluate_collection(
    client: QdrantClient,
    embedder: Qwen3STEmbedder,
    dim: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keyword recall@10 across all golden_v1 items at target dim."""
    name = target_collection_name(dim)
    if not client.collection_exists(name):
        raise RuntimeError(f"collection {name} missing — run --reembed first")

    recalls: list[float] = []
    latencies_ms: list[float] = []
    per_difficulty: dict[str, list[float]] = {}

    for item in items:
        # Embed query at 4096d (Qwen3 prepends retrieval prompt via
        # prompt_name="query"), then truncate+renormalize to target dim
        # with the same transform as the indexed chunks.
        q_vec_full = embedder.embed_batch([item["query"]], is_query=True)[0]
        q_vec = (
            truncate_and_normalize(q_vec_full, dim)
            if dim < 4096
            else list(q_vec_full)
        )

        t0 = time.perf_counter()
        hits = client.query_points(
            collection_name=name,
            query=q_vec,
            limit=TOP_K,
            with_payload=True,
        ).points
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        retrieved_texts = [
            (h.payload or {}).get(SOURCE_TEXT_FIELD, "") for h in hits
        ]
        rec = keyword_recall(retrieved_texts, item["expected_keywords"])
        recalls.append(rec)
        diff = item.get("difficulty", "medium")
        per_difficulty.setdefault(diff, []).append(rec)

    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0
    return {
        "dim": dim,
        "collection": name,
        "n_queries": len(items),
        "mean_keyword_recall": round(mean_recall, 4),
        "per_difficulty": {
            d: round(sum(v) / len(v), 4) if v else 0.0
            for d, v in per_difficulty.items()
        },
        "latency_ms": {
            "mean": round(sum(latencies_ms) / len(latencies_ms), 2),
            "p50": round(percentile(latencies_ms, 50), 2),
            "p95": round(percentile(latencies_ms, 95), 2),
        },
    }


def compare_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """A/B summary vs 4096d baseline with per-variant recommendation."""
    baseline = next(r for r in results if r["dim"] == 4096)
    comparisons: list[dict[str, Any]] = []
    for r in results:
        if r["dim"] == 4096:
            continue
        delta = r["mean_keyword_recall"] - baseline["mean_keyword_recall"]
        delta_rel = (
            delta / baseline["mean_keyword_recall"]
            if baseline["mean_keyword_recall"] > 0
            else 0.0
        )
        # Asymmetric thresholds — only DEGRADATION counts against MRL. An
        # improvement at smaller dim is suspect (likely noise at small N)
        # but does not block migration: the swap is still safe to ship.
        if delta_rel >= -0.05:
            recommendation = "MIGRATE"
        elif delta_rel >= -0.10:
            recommendation = "OPT_IN"
        else:
            recommendation = "REJECT"
        comparisons.append({
            "dim": r["dim"],
            "keyword_recall": r["mean_keyword_recall"],
            "delta_abs": round(delta, 4),
            "delta_rel_pct": round(delta_rel * 100, 2),
            "latency_speedup_p95": (
                round(baseline["latency_ms"]["p95"] / r["latency_ms"]["p95"], 2)
                if r["latency_ms"]["p95"] > 0
                else None
            ),
            "storage_factor": round(4096 / r["dim"], 2),
            "recommendation": recommendation,
        })
    return {
        "baseline_dim": 4096,
        "baseline_keyword_recall": baseline["mean_keyword_recall"],
        "comparisons": comparisons,
    }


# ─── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Matryoshka A/B bench (roadmap §4.1)"
    )
    ap.add_argument("--reembed", action="store_true",
                    help="Re-embed pdf_documents at 4096/1024/512d")
    ap.add_argument("--evaluate", action="store_true",
                    help="Run keyword recall@10 on existing MRL collections")
    ap.add_argument("--full", action="store_true",
                    help="--reembed then --evaluate")
    ap.add_argument("--qdrant-url", default=DEFAULT_QDRANT)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--report", type=Path, default=None,
                    help="Save JSON report to this path")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not (args.reembed or args.evaluate or args.full):
        ap.error("specify one of --reembed / --evaluate / --full")

    client = QdrantClient(url=args.qdrant_url)
    embedder: Qwen3STEmbedder | None = None

    def _get_embedder() -> Qwen3STEmbedder:
        nonlocal embedder
        if embedder is None:
            logger.info("Loading Qwen3-Embedding-8B (local GPU, bf16)...")
            embedder = Qwen3STEmbedder(
                dtype="bfloat16",
                batch_size=args.batch_size,
                enable_fa2=False,
            )
            logger.info("Embedder ready (dim=%d)", embedder.dims)
        return embedder

    if args.reembed or args.full:
        reembed_all(client, _get_embedder(), batch_size=args.batch_size)

    if args.evaluate or args.full:
        items = load_golden()
        logger.info("golden_v1 items with keywords + query: %d", len(items))
        results = []
        for dim in TARGET_DIMS:
            logger.info("Evaluating %dd...", dim)
            r = evaluate_collection(client, _get_embedder(), dim, items)
            results.append(r)
            logger.info(
                "%dd recall=%.3f  p50=%.1fms  p95=%.1fms",
                dim, r["mean_keyword_recall"],
                r["latency_ms"]["p50"], r["latency_ms"]["p95"],
            )

        summary = compare_results(results)
        report = {
            "schema_version": 1,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_collection": SOURCE_COLLECTION,
            "metric": "keyword_recall_at_10",
            "model": Qwen3STEmbedder.MODEL_ID,
            "results": results,
            "summary": summary,
        }
        out = json.dumps(report, indent=2, ensure_ascii=False)
        sys.stdout.write("\n" + out + "\n")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(out, encoding="utf-8")
            logger.info("Report saved to %s", args.report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
