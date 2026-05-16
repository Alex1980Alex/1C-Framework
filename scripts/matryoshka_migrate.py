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
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models  # noqa: E402

logger = logging.getLogger("matryoshka_migrate")

TARGET_DIMS = (4096, 1024, 512)
TOP_K = 10
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = PROJECT_ROOT / "data" / "eval" / "golden_v1.json"
DEFAULT_QDRANT = os.environ.get("QDRANT_URL", "http://localhost:6333")
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
QUERY_PREFIX = (
    "Instruct: Given a web search query, retrieve relevant passages that "
    "answer the query\nQuery: "
)

THRESH_MIGRATE = -0.05
THRESH_OPT_IN = -0.10


def target_name(source: str, dim: int) -> str:
    return f"{source}_mrl_{dim}"


def truncate_and_normalize(vec, target_dim: int):
    arr = np.asarray(list(vec)[:target_dim], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr.tolist()
    return (arr / norm).tolist()


def truncate_all(client, source: str, batch_size: int = 256):
    coll_info = client.get_collection(source)
    vector_size = coll_info.config.params.vectors.size
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
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
    counts = {d: 0 for d in TARGET_DIMS if d != 4096}
    offset = None
    total = 0
    t0 = time.time()
    while True:
        pts, next_offset = client.scroll(
            collection_name=source, limit=batch_size,
            with_payload=True, with_vectors=True, offset=offset,
        )
        for dim in TARGET_DIMS:
            if dim == 4096:
                continue
            points = []
            for pt in pts:
                v = pt.vector
                if isinstance(v, dict):
                    v = next(iter(v.values()))
                if not v:
                    continue
                truncated = truncate_and_normalize(v, dim)
                points.append(models.PointStruct(id=pt.id, vector=truncated, payload=pt.payload))
            if points:
                client.upsert(
                    collection_name=target_name(source, dim),
                    points=points, wait=False,
                )
                counts[dim] += len(points)
        total += len(pts)
        if total % 1024 == 0 or next_offset is None:
            logger.info("  scrolled %d points, %.1fs", total, time.time() - t0)
        if next_offset is None:
            break
        offset = next_offset
    logger.info("Truncate done in %.1fs. Per-dim upserts: %s", time.time() - t0, counts)
    return counts


def embed_query(query, http_client):
    payload = {"inputs": [QUERY_PREFIX + query]}
    resp = http_client.post(TEI_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()[0]


def load_grounded_items(target_collection):
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) and "items" in raw else raw
    return [it for it in items
            if it.get("target_collection") == target_collection
            and it.get("expected_chunk_ids")]


def ndcg_at_k(retrieved_ids, expected_ids, k):
    dcg = 0.0
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in expected_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def percentile(values, p):
    if not values:
        return 0.0
    sv = sorted(values)
    idx = max(0, min(len(sv) - 1, int(round(p / 100 * (len(sv) - 1)))))
    return sv[idx]


def evaluate(client, http_client, items, source, dim):
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
    mean_ndcg = sum(scores) / len(scores) if scores else 0.0
    return {
        "dim": dim, "collection": coll,
        "n_items": len(items), "n_scored": len(scores),
        "mean_ndcg": mean_ndcg,
        "p50_ms": percentile(latencies_ms, 50),
        "p95_ms": percentile(latencies_ms, 95),
    }


def classify_verdict(delta_rel):
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
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    client = QdrantClient(url=args.qdrant_url)
    report = {"source": args.source, "stages": {}}
    if not args.no_truncate:
        logger.info("=== Phase 1: Truncate %s -> MRL ===", args.source)
        counts = truncate_all(client, args.source)
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
                    r = evaluate(client, http, items, args.source, dim)
                    results[str(dim)] = r
                    logger.info(
                        "  %dd: ndcg=%.4f n_scored=%d p95=%.1fms",
                        dim, r.get("mean_ndcg", 0), r.get("n_scored", 0),
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
                    "delta_rel": delta_rel, "verdict": verdict,
                    "ndcg": ndcg, "baseline": baseline,
                }
                logger.info("  -> %dd: delta_rel=%+.1f%% verdict=%s", dim, delta_rel * 100, verdict)
            report["verdicts"] = verdicts
    if args.report:
        report_path = Path(args.report)
    else:
        report_path = PROJECT_ROOT / "data" / "eval" / ("matryoshka_migrate_" + args.source + ".json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Report saved to %s", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())