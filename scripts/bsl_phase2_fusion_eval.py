"""Phase 2 (query-adaptive fusion) measurement: сравнить стратегии fusion на BSL golden.

Read-only. Для каждого запроса L (lexical) и S (semantic vocab-mismatch) golden измеряет recall@10
под: dense_only, bm25_only, RRF (native), DBSF (native, score-distribution), weighted-RRF (dense-heavy
70/30 и 60/40 — ранговые веса). Цель: найти fusion, который ловит семантику (S) без регресса лексики (L).

Запуск: .venv\\Scripts\\python.exe scripts\\bsl_phase2_fusion_eval.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.bsl.semantic_search.services.bm25_tokenizer import normalize_camelcase

QWEN3_QUERY_INSTRUCT = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)
QDRANT = "http://localhost:6333"
TEI = "http://localhost:8080"
COLL = "bsl_code_v4_late"
RRF_K = 60
POOL = 50


def embed_query(text: str) -> list[float]:
    r = httpx.post(
        f"{TEI}/embed", json={"inputs": QWEN3_QUERY_INSTRUCT + text[:8000]}, timeout=60.0
    )
    r.raise_for_status()
    return r.json()[0]


def _eid(e: dict) -> str:
    return f"{e['module_path']}:{e['line_start']}"


def _pid(p) -> str:
    pl = getattr(p, "payload", {}) or {}
    return f"{pl.get('module_path', '?')}:{pl.get('line_start', 0)}"


def recall_at_10(retr: list[str], exp: list[str]) -> float:
    return sum(1 for e in exp if e in retr[:10]) / len(exp) if exp else 0.0


def weighted_rrf(dense_pts, bm25_pts, w_d: float, w_b: float, limit: int = 10) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for rank, p in enumerate(dense_pts):
        scores[_pid(p)] += w_d / (RRF_K + rank + 1)
    for rank, p in enumerate(bm25_pts):
        scores[_pid(p)] += w_b / (RRF_K + rank + 1)
    return [i for i, _ in sorted(scores.items(), key=lambda x: -x[1])][:limit]


def eval_golden(path: str, client, bm25, filt) -> dict[str, float]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    agg: dict[str, list[float]] = defaultdict(list)
    for it in items:
        exp = [_eid(e) for e in it["expected"]]
        if not exp:
            continue
        dvec = embed_query(it["query"])
        sp = next(iter(bm25.embed([normalize_camelcase(it["query"])])))
        spv = models.SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist())
        dense_pts = client.query_points(
            collection_name=COLL,
            query=dvec,
            using="dense",
            limit=POOL,
            with_payload=True,
            query_filter=filt,
        ).points
        bm25_pts = client.query_points(
            collection_name=COLL,
            query=spv,
            using="bm25",
            limit=POOL,
            with_payload=True,
            query_filter=filt,
        ).points

        def native(fusion):
            return client.query_points(
                collection_name=COLL,
                prefetch=[
                    models.Prefetch(query=dvec, using="dense", limit=POOL, filter=filt),
                    models.Prefetch(query=spv, using="bm25", limit=POOL, filter=filt),
                ],
                query=models.FusionQuery(fusion=fusion),
                limit=10,
                with_payload=True,
            ).points

        variants = {
            "dense_only": [_pid(p) for p in dense_pts[:10]],
            "bm25_only": [_pid(p) for p in bm25_pts[:10]],
            "rrf": [_pid(p) for p in native(models.Fusion.RRF)],
            "wrrf_70_30": weighted_rrf(dense_pts, bm25_pts, 0.7, 0.3),
            "wrrf_60_40": weighted_rrf(dense_pts, bm25_pts, 0.6, 0.4),
        }
        try:
            variants["dbsf"] = [_pid(p) for p in native(models.Fusion.DBSF)]
        except Exception as e:
            variants["dbsf"] = []
            if not hasattr(eval_golden, "_dbsf_warned"):
                print(f"[warn] DBSF unavailable: {e}")
                eval_golden._dbsf_warned = True
        for name, ids in variants.items():
            agg[name].append(recall_at_10(ids, exp))
    return {n: round(sum(v) / len(v), 3) for n, v in agg.items() if v}


def main() -> int:
    client = QdrantClient(url=QDRANT, timeout=120)
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
    filt = models.Filter(
        must=[
            models.FieldCondition(key="module_path", match=models.MatchText(text="CommonModules"))
        ]
    )
    sets = {
        "L_lexical": "data/bsl_golden_set.json",
        "S_semantic": "data/eval/bsl/bsl_semantic_golden.json",
    }
    results = {}
    order = ["dense_only", "bm25_only", "rrf", "dbsf", "wrrf_70_30", "wrrf_60_40"]
    for name, path in sets.items():
        print(f"[eval] {name}: {path}")
        results[name] = eval_golden(path, client, bm25, filt)
    print("\n=== recall@10 by fusion variant ===")
    hdr = "| split      | " + " | ".join(f"{v:<10}" for v in order) + " |"
    print(hdr)
    print("|" + "-" * (len(hdr) - 2) + "|")
    for name in sets:
        row = results[name]
        print(f"| {name:<10} | " + " | ".join(f"{row.get(v, 0):<10.3f}" for v in order) + " |")
    Path("data/reports").mkdir(parents=True, exist_ok=True)
    Path("data/reports/bsl_phase2_fusion_eval.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n[out] data/reports/bsl_phase2_fusion_eval.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
