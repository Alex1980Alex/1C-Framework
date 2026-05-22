"""Production anchor MRR bench on bsl_code_v4_late alias (post-2026-05-22 swap).

Same methodology as scripts/bench_bsl_sparse_smoke.py, but targets the
production alias which now resolves to bsl_code_v4_late_hybrid (named
{dense, bm25} layout). Verifies the +73pp Hit@10 jump observed on the
smoke side-collection holds on production.

Modes:
  - dense (using="dense")
  - bm25 (using="bm25")
  - hybrid (Prefetch dense + bm25 -> FusionQuery RRF)

Run:
    .venv\\Scripts\\python.exe scripts\\bench_bsl_sparse_production.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

import httpx
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

QWEN3_QUERY_INSTRUCT = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.bsl.semantic_search.services.bm25_tokenizer import normalize_camelcase  # noqa: E402


def derive_query_fragment(content: str, seed: int) -> str:
    rng = random.Random(seed)
    text = content.strip()
    if len(text) < 60:
        return text
    start = rng.randint(20, max(20, len(text) - 80))
    length = rng.randint(50, min(120, len(text) - start))
    return text[start: start + length].strip()


def embed_query_tei(text: str, base_url: str) -> list[float]:
    prefixed = QWEN3_QUERY_INSTRUCT + text[:8000]
    r = httpx.post(f"{base_url}/embed", json={"inputs": prefixed}, timeout=60.0)
    r.raise_for_status()
    return r.json()[0]


def compute_rank_metrics(target: str, results: list[str]) -> dict[str, float]:
    try:
        rank = results.index(target) + 1
    except ValueError:
        rank = 0
    return {
        "rank": rank,
        "hit_1": 1.0 if rank == 1 else 0.0,
        "hit_3": 1.0 if 0 < rank <= 3 else 0.0,
        "hit_10": 1.0 if 0 < rank <= 10 else 0.0,
        "rr": (1.0 / rank) if rank > 0 else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--tei-url", default="http://localhost:8080")
    parser.add_argument("--collection", default="bsl_code_v4_late")
    parser.add_argument("--num-queries", type=int, default=30)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data/reports/bsl_sparse_production_bench.json")
    args = parser.parse_args()

    client = QdrantClient(url=args.qdrant_url, timeout=120)
    rng = random.Random(args.seed)

    print("[load] FastEmbed Qdrant/bm25...")
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")

    info = client.get_collection(args.collection)
    print(f"[sample] {args.collection}: {info.points_count} pts")

    all_pts = []
    offset = None
    while True:
        page, next_offset = client.scroll(
            collection_name=args.collection,
            limit=1000,
            offset=offset,
            with_vectors=False,
            with_payload=True,
        )
        all_pts.extend(page)
        if next_offset is None:
            break
        offset = next_offset
    print(f"[sample] scrolled {len(all_pts)} pts, picking {args.num_queries}")

    candidates = [p for p in all_pts if p.payload and p.payload.get("content")]
    sample = rng.sample(candidates, min(args.num_queries, len(candidates)))

    modes = ["dense", "bm25", "hybrid_rrf"]
    metrics: dict[str, list[dict[str, float]]] = {m: [] for m in modes}
    query_log = []

    for i, anchor in enumerate(sample):
        target_id = str(anchor.id)
        content = anchor.payload["content"]
        fragment = derive_query_fragment(content, seed=args.seed + i)
        if len(fragment) < 20:
            continue

        t0 = time.time()
        dense_vec = embed_query_tei(fragment, base_url=args.tei_url)
        dense_ms = (time.time() - t0) * 1000

        sparse_emb = next(iter(bm25.embed([normalize_camelcase(fragment)])))
        sparse_indices = sparse_emb.indices.tolist()
        sparse_values = sparse_emb.values.tolist()

        r_dense = [
            str(p.id) for p in client.query_points(
                collection_name=args.collection,
                query=dense_vec,
                using="dense",
                limit=args.k,
                with_payload=False,
            ).points
        ]
        r_bm25 = [
            str(p.id) for p in client.query_points(
                collection_name=args.collection,
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using="bm25",
                limit=args.k,
                with_payload=False,
            ).points
        ]
        r_hybrid = [
            str(p.id) for p in client.query_points(
                collection_name=args.collection,
                prefetch=[
                    models.Prefetch(query=dense_vec, using="dense", limit=50),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_indices, values=sparse_values,
                        ),
                        using="bm25",
                        limit=50,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=args.k,
                with_payload=False,
            ).points
        ]

        m_dense = compute_rank_metrics(target_id, r_dense)
        m_bm25 = compute_rank_metrics(target_id, r_bm25)
        m_hybrid = compute_rank_metrics(target_id, r_hybrid)
        metrics["dense"].append(m_dense)
        metrics["bm25"].append(m_bm25)
        metrics["hybrid_rrf"].append(m_hybrid)

        query_log.append({
            "query_idx": i,
            "target_id": target_id,
            "fragment_len": len(fragment),
            "dense_ms": round(dense_ms, 1),
            "dense_rank": m_dense["rank"],
            "bm25_rank": m_bm25["rank"],
            "hybrid_rank": m_hybrid["rank"],
        })

        if (i + 1) % 5 == 0:
            print(
                f"[bench] {i+1}/{args.num_queries} "
                f"dense={m_dense['rank']} bm25={m_bm25['rank']} hybrid={m_hybrid['rank']}"
            )

    def agg(rows):
        n = len(rows)
        if n == 0:
            return {"n": 0}
        return {
            "n": n,
            "mrr_at_10": sum(r["rr"] for r in rows) / n,
            "hit_at_1": sum(r["hit_1"] for r in rows) / n,
            "hit_at_3": sum(r["hit_3"] for r in rows) / n,
            "hit_at_10": sum(r["hit_10"] for r in rows) / n,
            "found_in_top10": sum(1 for r in rows if r["rank"] > 0),
        }

    summary = {mode: agg(rows) for mode, rows in metrics.items()}

    print("\n" + "=" * 70)
    print(f"{'Mode':<16} {'MRR@10':>8} {'Hit@1':>7} {'Hit@3':>7} {'Hit@10':>8} {'Found/N':>10}")
    print("-" * 70)
    for mode in modes:
        s = summary[mode]
        if s.get("n", 0) == 0:
            continue
        print(
            f"{mode:<16} "
            f"{s['mrr_at_10']:>8.3f} "
            f"{s['hit_at_1']:>7.2%} "
            f"{s['hit_at_3']:>7.2%} "
            f"{s['hit_at_10']:>8.2%} "
            f"{s['found_in_top10']:>5}/{s['n']:<4}"
        )
    print("=" * 70)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "config": {
                    "collection": args.collection,
                    "num_queries": args.num_queries,
                    "k": args.k,
                    "seed": args.seed,
                },
                "summary": summary,
                "queries": query_log,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
