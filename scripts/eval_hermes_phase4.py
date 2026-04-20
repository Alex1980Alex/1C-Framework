"""Hermes Phase 4 Eval: GraphRAG Baseline vs Wiki-Augmented Retrieval.

Compares baseline retrieval (Qdrant vector search on graph_embeddings)
against wiki-augmented retrieval (RRF fusion with wiki_pages_v1).

Usage:
    python scripts/eval_hermes_phase4.py smoke
    python scripts/eval_hermes_phase4.py baseline --queries data/eval/hermes/phase4_queries.jsonl --output data/eval/hermes/graphrag_baseline.json
    python scripts/eval_hermes_phase4.py index-wiki --wiki-dir docs/wiki/entities/
    python scripts/eval_hermes_phase4.py wiki-eval --queries data/eval/hermes/phase4_queries.jsonl --wiki-dir docs/wiki/entities/ --output data/eval/hermes/wiki_augmented.json
    python scripts/eval_hermes_phase4.py export-wiki --output docs/wiki/entities/
    python scripts/eval_hermes_phase4.py report --baseline data/eval/hermes/graphrag_baseline.json --augmented data/eval/hermes/wiki_augmented.json --output data/eval/hermes/phase4_report.md
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient

GRAPH_COLLECTION = "graph_embeddings"
PDF_COLLECTION = "pdf_documents"
TOP_K = 10


# ── Embedding ──────────────────────────────────────────────────────────────────

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name="intfloat/multilingual-e5-large")
    return _model


def embed_query(text: str) -> list[float]:
    model = _get_model()
    vecs = list(model.embed([text]))
    return vecs[0].tolist()


# ── Metrics ────────────────────────────────────────────────────────────────────


def _fuzzy_match(name: str, relevant: set[str]) -> bool:
    n = name.lower().strip()
    for r in relevant:
        rl = r.lower().strip()
        if n == rl or n in rl or rl in n:
            return True
    return False


def precision_at_k(results: list[dict], relevant: set[str], k: int = TOP_K) -> float:
    if not relevant or not results:
        return 0.0
    top = results[:k]
    hits = sum(1 for r in top if _fuzzy_match(r["name"], relevant))
    return hits / len(top)


def recall_at_k(results: list[dict], relevant: set[str], k: int = TOP_K) -> float:
    if not relevant:
        return 0.0
    top = results[:k]
    found = sum(1 for rel in relevant if any(_fuzzy_match(r["name"], {rel}) for r in top))
    return found / len(relevant)


def ndcg_at_k(results: list[dict], relevant: set[str], k: int = TOP_K) -> float:
    if not relevant:
        return 0.0
    dcg = 0.0
    for i, r in enumerate(results[:k]):
        if _fuzzy_match(r["name"], relevant):
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg <= 0:
        return 0.0
    return min(dcg / idcg, 1.0)


def compute_latency_metrics(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0}
    s = sorted(latencies)
    n = len(s)
    return {
        "p50": s[int(n * 0.5)],
        "p95": s[min(int(n * 0.95), n - 1)],
        "mean": statistics.mean(s),
    }


def bootstrap_ci(values: list[float], n_boot: int = 1000, ci: float = 0.95) -> dict[str, float]:
    if not values:
        return {"lo": 0.0, "hi": 0.0, "mean": 0.0}
    rng = random.Random(42)
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(statistics.mean(sample))
    means.sort()
    alpha = (1 - ci) / 2
    return {"lo": means[int(n_boot * alpha)], "hi": means[int(n_boot * (1 - alpha))], "mean": statistics.mean(values)}


# ── Retrieval eval ─────────────────────────────────────────────────────────────


def _search(client: QdrantClient, query_vec: list[float], k: int = TOP_K) -> list[dict]:
    resp = client.query_points(GRAPH_COLLECTION, query=query_vec, limit=k, with_payload=True)
    return [
        {"name": p.payload.get("name", ""), "score": p.score, "entity_type": p.payload.get("entity_type", "")}
        for p in resp.points
    ]


def _search_with_wiki(
    client: QdrantClient,
    query_vec: list[float],
    wiki_dir: Path,
    k: int = TOP_K,
) -> list[dict]:
    results = _search(client, query_vec, k=k * 2)

    if not wiki_dir.exists():
        return results[:k]

    wiki_pages = set()
    for wp in wiki_dir.glob("*.md"):
        wiki_pages.add(wp.stem)

    boosted = []
    normal = []
    for r in results:
        name = r["name"].lower().strip()
        name = "".join(c if c.isalnum() or c in "- " else "" for c in name)
        name = name.replace(" ", "-").strip("-")
        # Naive uniform boost — proved harmful in eval (-15.7% precision).
        # Next iteration: content-based RRF fusion instead.
        if name in wiki_pages:
            r["score"] += 0.1
            boosted.append(r)
        else:
            normal.append(r)

    merged = boosted + normal
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:k]


def run_eval(
    queries: list[dict],
    client: QdrantClient,
    wiki_dir: Path | None = None,
    k: int = TOP_K,
) -> dict[str, Any]:
    per_query = []
    precisions, recalls, ndcgs, latencies = [], [], [], []

    for q in queries:
        relevant = set(q.get("relevant_entity_names", []))
        t0 = time.perf_counter()
        vec = embed_query(q["query"])
        if wiki_dir:
            results = _search_with_wiki(client, vec, wiki_dir, k=k)
        else:
            results = _search(client, vec, k=k)
        latency = time.perf_counter() - t0

        p = precision_at_k(results, relevant, k)
        r = recall_at_k(results, relevant, k)
        n = ndcg_at_k(results, relevant, k)
        precisions.append(p)
        recalls.append(r)
        ndcgs.append(n)
        latencies.append(latency)

        per_query.append({
            "id": q["id"],
            "query": q["query"],
            "precision": p,
            "recall": r,
            "ndcg": n,
            "latency": latency,
            "top_results": [{"name": x["name"], "score": round(x["score"], 3)} for x in results[:5]],
        })

    metrics = {
        "precision@10": statistics.mean(precisions) if precisions else 0,
        "recall@10": statistics.mean(recalls) if recalls else 0,
        "ndcg@10": statistics.mean(ndcgs) if ndcgs else 0,
        "latency": compute_latency_metrics(latencies),
        "num_queries": len(queries),
    }
    ci = {
        "precision@10": bootstrap_ci(precisions),
        "recall@10": bootstrap_ci(recalls),
        "ndcg@10": bootstrap_ci(ndcgs),
    }
    return {"metrics": metrics, "ci": ci, "per_query": per_query}


# ── Subcommands ────────────────────────────────────────────────────────────────


def cmd_smoke(_args: argparse.Namespace) -> None:
    print("[SMOKE] Starting...")
    t0 = time.perf_counter()
    client = QdrantClient("localhost", port=6333)

    colls = [c.name for c in client.get_collections().collections]
    assert GRAPH_COLLECTION in colls, f"{GRAPH_COLLECTION} not found"
    info = client.get_collection(GRAPH_COLLECTION)
    print(f"[SMOKE] {GRAPH_COLLECTION}: {info.points_count} points")

    test_queries = [
        {"id": "s1", "query": "справочник метаданных", "relevant_entity_names": ["СправочникМетаданные", "справочник"]},
        {"id": "s2", "query": "ресурс регистра сведений", "relevant_entity_names": ["ресурс регистра сведений", "регистр"]},
        {"id": "s3", "query": "расписание фоновых заданий", "relevant_entity_names": ["расписание фоновых заданий"]},
    ]

    results = run_eval(test_queries, client)
    elapsed = time.perf_counter() - t0
    m = results["metrics"]

    print(f"[SMOKE] P@10={m['precision@10']:.3f}, R@10={m['recall@10']:.3f}, NDCG@10={m['ndcg@10']:.3f}")
    for pq in results["per_query"]:
        print(f"  {pq['id']}: P={pq['precision']:.2f} top={pq['top_results'][:3]}")
    print(f"[SMOKE] {elapsed:.1f}s — {'PASS' if elapsed < 60 else 'SLOW'}")


def cmd_baseline(args: argparse.Namespace) -> None:
    queries = _load_queries(args.queries)
    client = QdrantClient("localhost", port=6333)
    print(f"[BASELINE] Running on {len(queries)} queries...")
    results = run_eval(queries, client)
    _save_json(results, args.output)
    m = results["metrics"]
    print(f"[BASELINE] P@10={m['precision@10']:.3f}, R@10={m['recall@10']:.3f}, NDCG@10={m['ndcg@10']:.3f}")


def cmd_export_wiki(args: argparse.Namespace) -> None:
    import asyncio

    from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
    from src.pdf_framework.indexing.wiki_exporter import WikiExportConfig, WikiExporter
    from src.pdf_framework.schemas.entities import Entity

    client = QdrantClient("localhost", port=6333)

    async def _export():
        store = NetworkXGraphStore()
        await store.initialize()

        pts, _ = client.scroll(GRAPH_COLLECTION, limit=10000, with_payload=True)
        count = 0
        for pt in pts:
            if not pt.payload.get("name"):
                continue
            entity = Entity(
                id=str(pt.id),
                name=pt.payload["name"],
                entity_type=pt.payload.get("entity_type", "CONCEPT"),
                properties={"text": pt.payload.get("text", "")},
                source_document_id=pt.payload.get("source_document_id", ""),
                source_chunk_ids=pt.payload.get("source_chunk_ids", []),
            )
            await store.add_entity(entity)
            count += 1

        store.flush()
        print(f"[EXPORT] Loaded {count} entities into graph store")

        config = WikiExportConfig(output_dir=Path(args.output), overwrite_existing=True)
        exporter = WikiExporter(store, config)
        result = await exporter.export_all()
        print(f"[EXPORT] {result.summary()}")

    asyncio.run(_export())


def cmd_wiki_eval(args: argparse.Namespace) -> None:
    queries = _load_queries(args.queries)
    client = QdrantClient("localhost", port=6333)
    wiki_dir = Path(args.wiki_dir)
    print(f"[WIKI-EVAL] Running on {len(queries)} queries with wiki_dir={wiki_dir}...")
    results = run_eval(queries, client, wiki_dir=wiki_dir)
    _save_json(results, args.output)
    m = results["metrics"]
    print(f"[WIKI-EVAL] P@10={m['precision@10']:.3f}, R@10={m['recall@10']:.3f}, NDCG@10={m['ndcg@10']:.3f}")


def cmd_report(args: argparse.Namespace) -> None:
    baseline = _load_json(args.baseline)
    augmented = _load_json(args.augmented)
    bm = baseline["metrics"]
    am = augmented["metrics"]

    lines = ["# Hermes Phase 4 — Wiki-Augmented Retrieval Eval Report\n"]
    lines.append(f"- Baseline: GraphRAG vector search ({bm['num_queries']} queries)")
    lines.append(f"- Augmented: Wiki-boosted retrieval ({am['num_queries']} queries)")
    lines.append(f"- Collection: {GRAPH_COLLECTION}")
    lines.append("")

    lines.append("## Retrieval Metrics\n")
    lines.append("| Metric | Baseline | Wiki-Augmented | Delta | CI (augmented) |")
    lines.append("|--------|----------|----------------|-------|----------------|")

    for metric in ["precision@10", "recall@10", "ndcg@10"]:
        bv = bm[metric]
        av = am[metric]
        delta = av - bv
        sign = "+" if delta >= 0 else ""
        ci = augmented["ci"].get(metric, {})
        ci_str = f"[{ci.get('lo', 0):.3f}, {ci.get('hi', 0):.3f}]" if ci else "—"
        lines.append(f"| {metric} | {bv:.4f} | {av:.4f} | {sign}{delta:.4f} | {ci_str} |")
    lines.append("")

    lines.append("## Latency\n")
    lines.append("| Metric | Baseline | Wiki-Augmented |")
    lines.append("|--------|----------|----------------|")
    for sub in ["p50", "p95", "mean"]:
        bv = bm["latency"].get(sub, 0)
        av = am["latency"].get(sub, 0)
        lines.append(f"| {sub} | {bv:.3f}s | {av:.3f}s |")
    lines.append("")

    delta_p = am["precision@10"] - bm["precision@10"]
    if delta_p >= 0.10:
        verdict = "IMPROVEMENT"
    elif delta_p < -0.05:
        verdict = "REGRESSION"
    else:
        verdict = "NO_CHANGE"
    lines.append(f"## Verdict: **{verdict}**\n")
    lines.append(f"Delta precision@10: {delta_p:+.4f}")
    if verdict == "IMPROVEMENT":
        lines.append(f"Target met: >=10% improvement ({delta_p:+.1%})")
    elif verdict == "REGRESSION":
        lines.append(f"Regression detected: >5% drop ({delta_p:+.1%})")
    else:
        lines.append(f"No significant change ({delta_p:+.1%})")
    lines.append("")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[REPORT] Written to {out} — Verdict: {verdict}")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _load_queries(path: str) -> list[dict]:
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(data: dict, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"[SAVED] {out}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes Phase 4 Eval")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("smoke", help="Smoke test: 3 queries, <60s")

    p_base = sub.add_parser("baseline", help="Run baseline eval")
    p_base.add_argument("--queries", required=True)
    p_base.add_argument("--output", required=True)

    p_wiki = sub.add_parser("export-wiki", help="Export graph entities to wiki pages")
    p_wiki.add_argument("--output", default="docs/wiki/entities")

    p_weval = sub.add_parser("wiki-eval", help="Run wiki-augmented eval")
    p_weval.add_argument("--queries", required=True)
    p_weval.add_argument("--wiki-dir", required=True)
    p_weval.add_argument("--output", required=True)

    p_rep = sub.add_parser("report", help="Generate comparison report")
    p_rep.add_argument("--baseline", required=True)
    p_rep.add_argument("--augmented", required=True)
    p_rep.add_argument("--output", required=True)

    args = parser.parse_args()
    commands = {
        "smoke": cmd_smoke,
        "baseline": cmd_baseline,
        "export-wiki": cmd_export_wiki,
        "wiki-eval": cmd_wiki_eval,
        "report": cmd_report,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
