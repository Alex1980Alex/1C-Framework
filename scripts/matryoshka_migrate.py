"""Roadmap 260509 §4.1.5 - production Matryoshka migration verdict.

Pure-truncate path: scrolls SOURCE collection with stored 4096d vectors,
truncates to target dim, L2-renormalizes, uploads to new <source>_mrl_<dim>
collection. Then runs NDCG@10 on grounded golden_v1 items.

Usage:
    python scripts/matryoshka_migrate.py                # framework_code_v1 default
    python scripts/matryoshka_migrate.py --source X
    python scripts/matryoshka_migrate.py --no-truncate  # bench only
    python scripts/matryoshka_migrate.py --no-bench     # truncate only
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger("matryoshka_migrate")

TARGET_DIMS = (4096, 1024, 512)
TOP_K = 10
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = PROJECT_ROOT / "data" / "eval" / "golden_v1.json"
# Shared constants (TEI_URL, QUERY_PREFIX, embed_query) — see scripts/_eval_common.py
from _eval_common import QDRANT_URL as DEFAULT_QDRANT
from _eval_common import embed_query

THRESH_MIGRATE = -0.05
THRESH_OPT_IN = -0.10


def target_name(source: str, dim: int) -> str:
    return f"{source}_mrl_{dim}"


def truncate_and_normalize(vec: list[float], target_dim: int) -> list[float]:
    arr = np.asarray(list(vec)[:target_dim], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr.tolist()
    return (arr / norm).tolist()


def detect_vector_config(coll_info: Any, vector_name: str | None = None) -> tuple[int, str | None]:
    """Detect vector size + optional name for single- and multi-vector collections.

    `vectors_config` is either a single VectorParams (unnamed/legacy) or a dict
    of named VectorParams (multi-vector). Need to handle both for portability
    across framework_code_v1 (single-vector) and bsl_code_v4_late (multi).

    Returns:
        (vector_size, vector_name) — vector_name is None for unnamed, else the
        resolved named vector key (deterministic across runs).
    """
    vectors = coll_info.config.params.vectors
    if vectors is None:
        raise RuntimeError("Collection has no vectors_config (None)")
    if isinstance(vectors, dict):
        if vector_name:
            if vector_name not in vectors:
                raise RuntimeError(f"--vector-name '{vector_name}' not in {sorted(vectors.keys())}")
            cfg = vectors[vector_name]
            return cfg.size, vector_name
        first_name = sorted(vectors.keys())[0]
        cfg = vectors[first_name]
        logger.warning(
            "Multi-vector collection (%d named vectors); using '%s' "
            "(alphabetical first). Override with --vector-name.",
            len(vectors),
            first_name,
        )
        return cfg.size, first_name
    return vectors.size, None


def truncate_all(
    client: QdrantClient,
    source: str,
    batch_size: int = 256,
    vector_name: str | None = None,
) -> dict[int, int]:
    coll_info = client.get_collection(source)
    vector_size, resolved_name = detect_vector_config(coll_info, vector_name)
    if vector_size != 4096:
        raise RuntimeError(f"Source {source} has {vector_size}d; expected 4096")
    for dim in TARGET_DIMS:
        if dim == 4096:
            continue
        name = target_name(source, dim)
        if client.collection_exists(name):
            logger.info("Dropping existing %s", name)
            client.delete_collection(name)
        logger.info("Creating %s (%dd cosine)", name, dim)
        # Preserve named-vector shape on target if source was multi-vector
        if resolved_name:
            vectors_cfg: Any = {
                resolved_name: models.VectorParams(size=dim, distance=models.Distance.COSINE)
            }
        else:
            vectors_cfg = models.VectorParams(size=dim, distance=models.Distance.COSINE)
        client.create_collection(collection_name=name, vectors_config=vectors_cfg)
    counts: dict[int, int] = {d: 0 for d in TARGET_DIMS if d != 4096}
    offset = None
    total = 0
    batch_idx = 0
    t0 = time.time()
    while True:
        pts, next_offset = client.scroll(
            collection_name=source,
            limit=batch_size,
            with_payload=True,
            with_vectors=True,
            offset=offset,
        )
        for dim in TARGET_DIMS:
            if dim == 4096:
                continue
            points = []
            for pt in pts:
                v = pt.vector
                if isinstance(v, dict):
                    # Multi-vector: select by resolved name (deterministic)
                    if resolved_name and resolved_name in v:
                        v = v[resolved_name]
                    elif v:
                        v = v[sorted(v.keys())[0]]
                    else:
                        continue
                if not v:
                    continue
                truncated = truncate_and_normalize(list(v), dim)
                # Preserve named-vector shape in target if source was multi-vector
                if resolved_name:
                    point_vec: Any = {resolved_name: truncated}
                else:
                    point_vec = truncated
                points.append(models.PointStruct(id=pt.id, vector=point_vec, payload=pt.payload))
            if points:
                client.upsert(
                    collection_name=target_name(source, dim),
                    points=points,
                    wait=False,
                )
                counts[dim] += len(points)
        total += len(pts)
        batch_idx += 1
        # Robust log cadence: every 4 batches OR final batch (decoupled from batch_size)
        if batch_idx % 4 == 0 or next_offset is None:
            logger.info(
                "  scrolled %d points (%d batches), %.1fs", total, batch_idx, time.time() - t0
            )
        if next_offset is None:
            break
        offset = next_offset
    logger.info("Truncate done in %.1fs. Per-dim upserts: %s", time.time() - t0, counts)
    return counts


def load_grounded_items(target_collection: str) -> list[dict[str, Any]]:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) and "items" in raw else raw
    return [
        it
        for it in items
        if it.get("target_collection") == target_collection and it.get("expected_chunk_ids")
    ]


def ndcg_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    dcg = 0.0
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in expected_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    sv = sorted(values)
    idx = max(0, min(len(sv) - 1, int(round(p / 100 * (len(sv) - 1)))))
    return sv[idx]


# Failure-ratio gate: abort if too many items error out (prevents publishing
# verdict on degraded sample, e.g. TEI 5xx storm).
MIN_SUCCESS_RATIO: float = 0.8


def evaluate(
    client: QdrantClient,
    http_client: httpx.Client,
    items: list[dict[str, Any]],
    source: str,
    dim: int,
    vector_name: str | None = None,
) -> dict[str, Any]:
    coll = source if dim == 4096 else target_name(source, dim)
    if not client.collection_exists(coll):
        return {"dim": dim, "collection": coll, "error": "missing collection"}
    scores = []
    latencies_ms = []
    for item in items:
        try:
            t0 = time.perf_counter()
            vec_4096 = embed_query(item["query"], http_client)
            vec = vec_4096 if dim == 4096 else truncate_and_normalize(vec_4096, dim)
            hits = client.query_points(collection_name=coll, query=vec, limit=TOP_K).points
            latencies_ms.append((time.perf_counter() - t0) * 1000)
            retrieved = [str(h.id) for h in hits]
            expected = {str(x) for x in item["expected_chunk_ids"]}
            scores.append(ndcg_at_k(retrieved, expected, TOP_K))
        except Exception as e:
            logger.warning("[BENCH] %s: %s", item["id"], e)
            continue
    success_ratio = (len(scores) / len(items)) if items else 0.0
    failure_gate_passed = success_ratio >= MIN_SUCCESS_RATIO
    mean_ndcg = sum(scores) / len(scores) if scores else 0.0
    result: dict[str, Any] = {
        "dim": dim,
        "collection": coll,
        "n_items": len(items),
        "n_scored": len(scores),
        "success_ratio": success_ratio,
        "mean_ndcg": mean_ndcg,
        "p50_ms": percentile(latencies_ms, 50),
        "p95_ms": percentile(latencies_ms, 95),
    }
    if not failure_gate_passed:
        result["error"] = (
            f"failure_ratio_gate: success_ratio={success_ratio:.2f} < "
            f"{MIN_SUCCESS_RATIO} (n_scored={len(scores)}/{len(items)}); "
            f"verdict suppressed on degraded sample"
        )
        logger.error("[BENCH] %s", result["error"])
    return result


def classify_verdict(delta_rel: float) -> str:
    if delta_rel >= THRESH_MIGRATE:
        return "MIGRATE"
    if delta_rel >= THRESH_OPT_IN:
        return "OPT_IN"
    return "REJECT"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="framework_code_v1")
    p.add_argument("--qdrant-url", default=DEFAULT_QDRANT)
    p.add_argument("--no-truncate", action="store_true")
    p.add_argument("--no-bench", action="store_true")
    p.add_argument("--report", default=None)
    p.add_argument(
        "--vector-name",
        default=None,
        help="For multi-vector collections (e.g. bsl_code_v4_late): "
        "name of the vector to truncate. Default: alphabetically-first.",
    )
    args = p.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"
    )
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    client = QdrantClient(url=args.qdrant_url)
    report = {"source": args.source, "stages": {}}
    if not args.no_truncate:
        logger.info("=== Phase 1: Truncate %s -> MRL ===", args.source)
        counts = truncate_all(client, args.source, vector_name=args.vector_name)
        report["stages"]["truncate"] = counts
    else:
        logger.info("Skipping truncate (--no-truncate)")
    if not args.no_bench:
        logger.info("=== Phase 2: NDCG bench on grounded items ===")
        items = load_grounded_items(args.source)
        if not items:
            logger.warning("No grounded golden_v1 items for %s", args.source)
        else:
            logger.info("%d grounded items target %s", len(items), args.source)
            results = {}
            with httpx.Client() as http:
                for dim in TARGET_DIMS:
                    r = evaluate(
                        client, http, items, args.source, dim, vector_name=args.vector_name
                    )
                    results[str(dim)] = r
                    logger.info(
                        "  %dd: ndcg=%.4f n_scored=%d p95=%.1fms",
                        dim,
                        r.get("mean_ndcg", 0),
                        r.get("n_scored", 0),
                        r.get("p95_ms", 0),
                    )
            report["stages"]["evaluate"] = results
            baseline = results.get("4096", {}).get("mean_ndcg", 0.0)
            verdicts = {}
            for dim_str, r in results.items():
                dim = int(dim_str)
                if dim == 4096 or "error" in r:
                    continue
                ndcg = r["mean_ndcg"]
                delta_rel = (ndcg - baseline) / baseline if baseline > 0 else 0.0
                verdict = classify_verdict(delta_rel)
                verdicts[dim_str] = {
                    "delta_rel": delta_rel,
                    "verdict": verdict,
                    "ndcg": ndcg,
                    "baseline": baseline,
                }
                logger.info("  -> %dd: delta_rel=%+.1f%% verdict=%s", dim, delta_rel * 100, verdict)
            report["verdicts"] = verdicts
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = (
            PROJECT_ROOT / "data" / "eval" / ("matryoshka_migrate_" + args.source + ".json")
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Report saved to %s", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
