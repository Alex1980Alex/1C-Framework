"""A/B benchmark: dense-only vs sparse-only vs hybrid RRF on bsl_code_v4_sparse_smoke.

Strategy — synthetic anchor MRR (no manual ground truth needed):
  1. Scroll N random points from smoke collection.
  2. For each: derive query fragment from payload.content (middle slice, normalized).
  3. Search 4 modes on smoke:
       - dense (Qwen3 vec via TEI 4096d)
       - bm25 (FastEmbed Qdrant/bm25 sparse + CamelCase normalize)
       - hybrid RRF (Prefetch dense + bm25 → FusionQuery RRF)
       - dense on production bsl_code_v4_late (full 37k pts, context only)
  4. Compute MRR@10, hit@1, hit@3, hit@10 — target = original point.

Run:
  .venv\\Scripts\\python.exe scripts\\bench_bsl_sparse_smoke.py --num-queries 30
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

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
    """Pick a 50-120 char fragment from content. Deterministic per seed.

    Avoid first 20 chars (often noise: '// region', 'Function FooBar('),
    avoid last 20 (usually '; End').
    """
    rng = random.Random(seed)
    text = content.strip()
    if len(text) < 60:
        return text
    start = rng.randint(20, max(20, len(text) - 80))
    length = rng.randint(50, min(120, len(text) - start))
    return text[start : start + length].strip()


def embed_query_tei(text: str, base_url: str = "http://localhost:8080") -> list[float]:
    prefixed = QWEN3_QUERY_INSTRUCT + text[:8000]
    r = httpx.post(f"{base_url}/embed", json={"inputs": prefixed}, timeout=60.0)
    r.raise_for_status()
    return r.json()[0]


def search_dense(
    client: QdrantClient,
    collection: str,
    dense_vec: list[float],
    k: int = 10,
    using: str | None = None,
) -> list[str]:
    kwargs: dict[str, Any] = {
        "collection_name": collection,
        "query": dense_vec,
        "limit": k,
        "with_payload": False,
    }
    if using is not None:
        kwargs["using"] = using
    res = client.query_points(**kwargs)
    return [str(p.id) for p in res.points]


def search_bm25(
    client: QdrantClient,
    collection: str,
    sparse_indices: list[int],
    sparse_values: list[float],
    k: int = 10,
    using: str = "bm25",
) -> list[str]:
    res = client.query_points(
        collection_name=collection,
        query=models.SparseVector(indices=sparse_indices, values=sparse_values),
        using=using,
        limit=k,
        with_payload=False,
    )
    return [str(p.id) for p in res.points]


def search_hybrid_rrf(
    client: QdrantClient,
    collection: str,
    dense_vec: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    k: int = 10,
    prefetch_limit: int = 50,
) -> list[str]:
    res = client.query_points(
        collection_name=collection,
        prefetch=[
            models.Prefetch(query=dense_vec, using="dense", limit=prefetch_limit),
            models.Prefetch(
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using="bm25",
                limit=prefetch_limit,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=k,
        with_payload=False,
    )
    return [str(p.id) for p in res.points]


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
    parser.add_argument("--smoke", default="bsl_code_v4_sparse_smoke")
    parser.add_argument("--prod", default="bsl_code_v4_late")
    parser.add_argument("--num-queries", type=int, default=30)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="data/reports/bsl_sparse_smoke_bench.json")
    args = parser.parse_args()

    client = QdrantClient(url=args.qdrant_url, timeout=120)
    rng = random.Random(args.seed)

    print("[load] FastEmbed Qdrant/bm25...")
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")

    smoke_info = client.get_collection(args.smoke)
    print(f"[sample] {args.smoke}: {smoke_info.points_count} pts")

    all_pts = []
    offset = None
    while True:
        page, next_offset = client.scroll(
            collection_name=args.smoke,
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

    modes = ["dense_smoke", "bm25_smoke", "hybrid_rrf_smoke", "dense_prod_full"]
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

        sparse_emb = list(bm25.embed([normalize_camelcase(fragment)]))[0]
        sparse_indices = sparse_emb.indices.tolist()
        sparse_values = sparse_emb.values.tolist()

        r_dense_smoke = search_dense(client, args.smoke, dense_vec, k=args.k, using="dense")
        r_bm25_smoke = search_bm25(client, args.smoke, sparse_indices, sparse_values, k=args.k)
        r_hybrid_smoke = search_hybrid_rrf(
            client, args.smoke, dense_vec, sparse_indices, sparse_values, k=args.k
        )
        r_dense_prod = search_dense(client, args.prod, dense_vec, k=args.k, using=None)

        m_dense_smoke = compute_rank_metrics(target_id, r_dense_smoke)
        m_bm25_smoke = compute_rank_metrics(target_id, r_bm25_smoke)
        m_hybrid_smoke = compute_rank_metrics(target_id, r_hybrid_smoke)
        m_dense_prod = compute_rank_metrics(target_id, r_dense_prod)

        metrics["dense_smoke"].append(m_dense_smoke)
        metrics["bm25_smoke"].append(m_bm25_smoke)
        metrics["hybrid_rrf_smoke"].append(m_hybrid_smoke)
        metrics["dense_prod_full"].append(m_dense_prod)

        query_log.append(
            {
                "query_idx": i,
                "target_id": target_id,
                "fragment_len": len(fragment),
                "dense_ms": round(dense_ms, 1),
                "dense_smoke_rank": m_dense_smoke["rank"],
                "bm25_smoke_rank": m_bm25_smoke["rank"],
                "hybrid_smoke_rank": m_hybrid_smoke["rank"],
                "dense_prod_rank": m_dense_prod["rank"],
            }
        )

        if (i + 1) % 5 == 0:
            print(
                f"[bench] {i+1}/{args.num_queries} "
                f"dense_smoke={m_dense_smoke['rank']} "
                f"bm25={m_bm25_smoke['rank']} "
                f"hybrid={m_hybrid_smoke['rank']} "
                f"dense_prod={m_dense_prod['rank']}"
            )

    def agg(rows: list[dict[str, float]]) -> dict[str, float]:
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

    print("\n" + "=" * 75)
    print(f"{'Mode':<22} {'MRR@10':>8} {'Hit@1':>7} {'Hit@3':>7} {'Hit@10':>8} {'Found/N':>10}")
    print("-" * 75)
    for mode in modes:
        s = summary[mode]
        if s.get("n", 0) == 0:
            continue
        print(
            f"{mode:<22} "
            f"{s['mrr_at_10']:>8.3f} "
            f"{s['hit_at_1']:>7.2%} "
            f"{s['hit_at_3']:>7.2%} "
            f"{s['hit_at_10']:>8.2%} "
            f"{s['found_in_top10']:>5}/{s['n']:<4}"
        )
    print("=" * 75)

    if summary["dense_smoke"].get("n", 0) > 0 and summary["hybrid_rrf_smoke"].get("n", 0) > 0:
        d_mrr = summary["hybrid_rrf_smoke"]["mrr_at_10"] - summary["dense_smoke"]["mrr_at_10"]
        d_hit10 = summary["hybrid_rrf_smoke"]["hit_at_10"] - summary["dense_smoke"]["hit_at_10"]
        print(f"\n[delta] Hybrid_RRF vs Dense (smoke): MRR@10 {d_mrr:+.3f}, Hit@10 {d_hit10:+.2%}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "config": {
                    "smoke": args.smoke,
                    "prod": args.prod,
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
    print(f"\n[out] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
