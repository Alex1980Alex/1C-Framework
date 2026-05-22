"""Realistic framework_code_v1 retrieval eval on 67 queries from golden_v1.json.

Generalization probe (2026-05-22): does BSL pure-BM25 win generalize to
framework_code_v1 (Python+MD, English ids, 1024d MRL)? Bench uses parallel
framework_code_v1_hybrid_bench. Point-id matching against expected_chunk_ids.
Query embedding truncated 4096d->1024d MRL to match collection dim.

Modes: dense, bm25, hybrid_rrf. Metrics: Recall@10, NDCG@10, MRR, P@5.

Run:
    .venv\\Scripts\\python.exe scripts\\bench_framework_realistic_eval.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

QWEN3_QUERY_INSTRUCT = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)
CAMELCASE_RE = re.compile(r"[А-ЯЁ][а-яё]*|[A-Z][a-z]*|[а-яё]+|[a-z]+|\d+")


def normalize_camelcase(text: str) -> str:
    parts = CAMELCASE_RE.findall(text)
    return " ".join(parts).lower() if parts else text.lower()


def embed_query_tei(text: str, base_url: str) -> list[float]:
    r = httpx.post(
        f"{base_url}/embed",
        json={"inputs": QWEN3_QUERY_INSTRUCT + text[:8000]},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()[0]


def _id_from_point(p: Any) -> str:
    # golden_v1.expected_chunk_ids = list[str(UUID)]; Qdrant point.id is UUID too.
    return str(p.id)


def _mrl_truncate(vec: list[float], target_dim: int) -> list[float]:
    """MRL truncation + L2 renorm for query vectors going into 1024d collection."""
    import math
    v = vec[:target_dim]
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def recall_at_k(retr: list[str], exp: list[str], k: int = 10) -> float:
    if not exp:
        return 0.0
    return sum(1 for e in exp if e in retr[:k]) / len(exp)


def precision_at_k(retr: list[str], exp: list[str], k: int = 5) -> float:
    if k == 0:
        return 0.0
    return sum(1 for r in retr[:k] if r in exp) / k


def mrr(retr: list[str], exp: list[str]) -> float:
    for rank, r in enumerate(retr, 1):
        if r in exp:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retr: list[str], exp: list[str], k: int = 10) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, r in enumerate(retr[:k], 1)
        if r in exp
    )
    ideal = min(len(exp), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal + 1))
    return dcg / idcg if idcg > 0 else 0.0


def search_dense(client, coll, dvec, k, filt):
    res = client.query_points(
        collection_name=coll, query=dvec, using="dense",
        limit=k, with_payload=True, query_filter=filt,
    ).points
    return [_id_from_point(p) for p in res]


def search_bm25(client, coll, sp, k, filt):
    res = client.query_points(
        collection_name=coll,
        query=models.SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist()),
        using="bm25", limit=k, with_payload=True, query_filter=filt,
    ).points
    return [_id_from_point(p) for p in res]


def search_hybrid(client, coll, dvec, sp, k, filt):
    # Prefetch uses `filter=` (positional via models.Prefetch field); top-level
    # FusionQuery has no query_filter — filter must be inside each Prefetch.
    res = client.query_points(
        collection_name=coll,
        prefetch=[
            models.Prefetch(query=dvec, using="dense", limit=50, filter=filt),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sp.indices.tolist(), values=sp.values.tolist(),
                ),
                using="bm25", limit=50, filter=filt,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=k, with_payload=True,
    ).points
    return [_id_from_point(p) for p in res]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--tei-url", default="http://localhost:8080")
    ap.add_argument("--collection", default="bsl_code_v4_late")
    ap.add_argument("--golden", default="data/bsl_golden_set.json")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", default="data/reports/bsl_realistic_eval.json")
    ap.add_argument("--no-scope-filter", action="store_true")
    args = ap.parse_args()

    golden_path = Path(args.golden)
    items = json.loads(golden_path.read_text(encoding="utf-8"))
    print(f"[load] {golden_path}: {len(items)} queries")

    client = QdrantClient(url=args.qdrant_url, timeout=120)
    print("[load] FastEmbed Qdrant/bm25...")
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")

    scope_filter = None
    if not args.no_scope_filter:
        scope_filter = models.Filter(
            must=[models.FieldCondition(
                key="module_path",
                match=models.MatchText(text="CommonModules"),
            )]
        )

    modes = ["dense", "bm25", "hybrid_rrf"]
    raw: dict[str, dict[str, dict[str, list[float]]]] = {
        m: defaultdict(lambda: defaultdict(list)) for m in modes
    }
    overall: dict[str, dict[str, list[float]]] = {m: defaultdict(list) for m in modes}
    query_log = []
    t0 = time.time()

    for i, item in enumerate(items):
        query = item["query"]
        slc = item.get("slice", "overall")
        expected_ids = [_id_from_expected(e) for e in item["expected"]]
        if not expected_ids:
            continue

        try:
            dvec = embed_query_tei(query, args.tei_url)
        except Exception as e:
            print(f"[skip] {item.get('id','?')} embed failed: {e}")
            continue
        sparse = next(iter(bm25.embed([normalize_camelcase(query)])))

        retrievals = {
            "dense": search_dense(client, args.collection, dvec, args.k, scope_filter),
            "bm25": search_bm25(client, args.collection, sparse, args.k, scope_filter),
            "hybrid_rrf": search_hybrid(client, args.collection, dvec, sparse, args.k, scope_filter),
        }
        qmetrics = {}
        for mode, retrieved in retrievals.items():
            m = {
                "recall@10": recall_at_k(retrieved, expected_ids, 10),
                "ndcg@10": ndcg_at_k(retrieved, expected_ids, 10),
                "mrr": mrr(retrieved, expected_ids),
                "p@5": precision_at_k(retrieved, expected_ids, 5),
            }
            qmetrics[mode] = m
            for metric, val in m.items():
                raw[mode][slc][metric].append(val)
                overall[mode][metric].append(val)

        query_log.append({
            "id": item.get("id", f"q{i}"),
            "slice": slc,
            "query": query,
            "expected_count": len(expected_ids),
            "metrics": qmetrics,
        })

        if (i + 1) % 10 == 0:
            print(
                f"[bench] {i+1}/{len(items)} "
                f"dense_mrr={qmetrics['dense']['mrr']:.2f} "
                f"bm25_mrr={qmetrics['bm25']['mrr']:.2f} "
                f"hybrid_mrr={qmetrics['hybrid_rrf']['mrr']:.2f}"
            )

    elapsed = time.time() - t0

    averaged: dict[str, dict[str, dict[str, float]]] = {}
    for mode in modes:
        per_slice = {
            slc: {m: sum(vs) / max(1, len(vs)) for m, vs in metrics.items()}
            for slc, metrics in raw[mode].items()
        }
        per_slice["overall"] = {
            m: sum(vs) / max(1, len(vs)) for m, vs in overall[mode].items()
        }
        averaged[mode] = per_slice

    all_slices = ["small", "medium", "god_object", "overall"]
    print(f"\n=== Realistic BSL eval -- {len(items)} queries, {elapsed:.1f}s ===\n")
    print("| mode        | slice       | recall@10 | NDCG@10 | MRR    | p@5   |")
    print("|-------------|-------------|-----------|---------|--------|-------|")
    for mode in modes:
        for slc in all_slices:
            m = averaged[mode].get(slc, {})
            if not m:
                continue
            print(
                f"| {mode:<11} | {slc:<11} | "
                f"{m.get('recall@10', 0):>9.3f} | "
                f"{m.get('ndcg@10', 0):>7.3f} | "
                f"{m.get('mrr', 0):>6.3f} | "
                f"{m.get('p@5', 0):>5.3f} |"
            )
        print("|-------------|-------------|-----------|---------|--------|-------|")

    bm25_o = averaged["bm25"]["overall"]
    hyb_o = averaged["hybrid_rrf"]["overall"]
    dense_o = averaged["dense"]["overall"]
    d_mrr = bm25_o["mrr"] - hyb_o["mrr"]
    d_recall = bm25_o["recall@10"] - hyb_o["recall@10"]
    print("\n=== Decision support ===")
    print(
        f"  BM25 vs Hybrid: dMRR={d_mrr*100:+.1f}pp, "
        f"dRecall@10={d_recall*100:+.1f}pp"
    )
    print(
        f"  Hybrid vs Dense: dMRR={(hyb_o['mrr']-dense_o['mrr'])*100:+.1f}pp, "
        f"dRecall@10={(hyb_o['recall@10']-dense_o['recall@10'])*100:+.1f}pp"
    )
    if d_mrr >= 0.05 and (hyb_o["recall@10"] - bm25_o["recall@10"]) <= 0.03:
        recommendation = "SWITCH_DEFAULT_TO_BM25"
    else:
        recommendation = "KEEP_RRF_DEFAULT"
    print(f"  -> Recommendation: {recommendation}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "config": {
                "collection": args.collection,
                "golden_path": str(golden_path),
                "k": args.k,
                "scope_filter": ("CommonModules" if scope_filter else None),
            },
            "averaged": averaged,
            "queries": query_log,
            "recommendation": recommendation,
            "elapsed_s": round(elapsed, 1),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[out] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
