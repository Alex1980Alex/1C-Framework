"""Phase 3 measurement: bm25-confidence-gated fusion vs DBSF on L/S/I golden (read-only).

Гипотеза: на vocab-mismatch (S) bm25 проваливается -> его top1-скор НИЗКИЙ; на in-vocab (L) и
identifier (I) -> ВЫСОКИЙ. Если распределения bm25_top1 разделимы, gated-правило «bm25_top1 < θ ->
dense-only, иначе DBSF» поднимет S к dense-ceiling (0.42) БЕЗ регресса L/I. Иначе — остаток не закрыть
дёшево (DBSF остаётся). Свип θ; identifier-golden строится из semantic-golden (query = _meta.name).

Запуск: .venv\\Scripts\\python.exe scripts\\bsl_phase3_adaptive_eval.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.bsl.semantic_search.services.bm25_tokenizer import normalize_camelcase

QWEN3 = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)
QDRANT, TEI, COLL, POOL = "http://localhost:6333", "http://localhost:8080", "bsl_code_v4_late", 50


def embed(text):
    r = httpx.post(f"{TEI}/embed", json={"inputs": QWEN3 + text[:8000]}, timeout=60.0)
    r.raise_for_status()
    return r.json()[0]


def eid(e):
    return f"{e['module_path']}:{e['line_start']}"


def pid(p):
    pl = getattr(p, "payload", {}) or {}
    return f"{pl.get('module_path', '?')}:{pl.get('line_start', 0)}"


def recall10(retr, exp):
    return sum(1 for e in exp if e in retr[:10]) / len(exp) if exp else 0.0


def build_identifier_golden(sem_path):
    """I-golden из semantic-golden: query = имя символа (identifier), expected тот же."""
    items = json.loads(Path(sem_path).read_text(encoding="utf-8"))
    out = []
    for it in items:
        name = (it.get("_meta") or {}).get("name")
        if name and it.get("expected"):
            out.append(
                {"id": it["id"].replace("SEM", "ID"), "query": name, "expected": it["expected"]}
            )
    return out


def collect(items, client, bm25, filt):
    """Для каждого запроса: dense top10 ids, bm25 top1 score, DBSF top10 ids, expected."""
    rows = []
    for it in items:
        exp = [eid(e) for e in it["expected"]]
        if not exp:
            continue
        dvec = embed(it["query"])
        sp = next(iter(bm25.embed([normalize_camelcase(it["query"])])))
        spv = models.SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist())
        dpts = client.query_points(
            collection_name=COLL,
            query=dvec,
            using="dense",
            limit=POOL,
            with_payload=True,
            query_filter=filt,
        ).points
        bpts = client.query_points(
            collection_name=COLL,
            query=spv,
            using="bm25",
            limit=POOL,
            with_payload=True,
            query_filter=filt,
        ).points
        dbsf = client.query_points(
            collection_name=COLL,
            prefetch=[
                models.Prefetch(query=dvec, using="dense", limit=POOL, filter=filt),
                models.Prefetch(query=spv, using="bm25", limit=POOL, filter=filt),
            ],
            query=models.FusionQuery(fusion=models.Fusion.DBSF),
            limit=10,
            with_payload=True,
        ).points
        rows.append(
            {
                "exp": exp,
                "dense10": [pid(p) for p in dpts[:10]],
                "dbsf10": [pid(p) for p in dbsf],
                "bm25_top1": float(bpts[0].score) if bpts else 0.0,
            }
        )
    return rows


def main():
    client = QdrantClient(url=QDRANT, timeout=120)
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
    filt = models.Filter(
        must=[
            models.FieldCondition(key="module_path", match=models.MatchText(text="CommonModules"))
        ]
    )
    sem_path = "data/eval/bsl/bsl_semantic_golden.json"
    id_golden = build_identifier_golden(sem_path)
    Path("data/eval/bsl/bsl_identifier_golden.json").write_text(
        json.dumps(id_golden, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sets = {
        "L": json.loads(Path("data/bsl_golden_set.json").read_text(encoding="utf-8")),
        "S": json.loads(Path(sem_path).read_text(encoding="utf-8")),
        "I": id_golden,
    }
    data = {}
    for name, items in sets.items():
        print(f"[collect] {name}: {len(items)}")
        data[name] = collect(items, client, bm25, filt)

    # bm25_top1 distribution
    print("\n=== bm25_top1 distribution (in-vocab L/I должны быть ВЫШЕ out-vocab S) ===")
    for name in ("L", "S", "I"):
        vals = sorted(r["bm25_top1"] for r in data[name])
        if vals:
            print(
                f"  {name}: min={vals[0]:.2f} p25={vals[len(vals) // 4]:.2f} "
                f"median={statistics.median(vals):.2f} p75={vals[3 * len(vals) // 4]:.2f} max={vals[-1]:.2f}"
            )

    # baseline DBSF + dense-only
    print("\n=== baseline recall@10 ===")
    base = {}
    for name in ("L", "S", "I"):
        dbsf = sum(recall10(r["dbsf10"], r["exp"]) for r in data[name]) / len(data[name])
        dense = sum(recall10(r["dense10"], r["exp"]) for r in data[name]) / len(data[name])
        base[name] = (dbsf, dense)
        print(f"  {name}: DBSF={dbsf:.3f}  dense_only={dense:.3f}")

    # gated sweep: bm25_top1 < theta -> dense_only else DBSF
    all_top1 = sorted(r["bm25_top1"] for n in sets for r in data[n])
    grid = sorted(
        {round(all_top1[int(q * (len(all_top1) - 1))], 2) for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)}
    )
    print("\n=== gated recall@10 (bm25_top1<θ -> dense_only, else DBSF) ===")
    print("| θ     | L     | S     | I     |")
    for theta in grid:
        row = {}
        for name in ("L", "S", "I"):
            rec = [
                recall10(r["dense10"] if r["bm25_top1"] < theta else r["dbsf10"], r["exp"])
                for r in data[name]
            ]
            row[name] = sum(rec) / len(rec)
        print(f"| {theta:<5.2f} | {row['L']:.3f} | {row['S']:.3f} | {row['I']:.3f} |")

    Path("data/reports").mkdir(parents=True, exist_ok=True)
    Path("data/reports/bsl_phase3_adaptive_eval.json").write_text(
        json.dumps(
            {
                "baseline": {k: {"dbsf": v[0], "dense_only": v[1]} for k, v in base.items()},
                "bm25_top1": {n: sorted(r["bm25_top1"] for r in data[n]) for n in ("L", "S", "I")},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        "\n[out] data/reports/bsl_phase3_adaptive_eval.json  + data/eval/bsl/bsl_identifier_golden.json"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
