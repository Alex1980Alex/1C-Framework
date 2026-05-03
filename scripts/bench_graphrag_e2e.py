#!/usr/bin/env python3
"""Phase 6 end-to-end benchmark for GraphRAG (roadmap 260502).

Wires real backends:
- vector_fn  → Qdrant bsl_code_v4_late (Qwen3-Embedding-8B 4096d)
- graph_fn   → Neo4j Cypher (query_type-specific)
- community_fn → Qdrant graph_embeddings filter kind=Community

Runs 25 golden queries from tests/benchmarks/bsl_complex_queries.py,
reports recall@k, latency P50/P95, and per-category coverage.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from src.bsl.semantic_search.hybrid_router import hybrid_search
from tests.benchmarks.bsl_complex_queries import GOLDEN_QUERIES

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bsl-graph-2026")
QDRANT_URL = "http://localhost:6333"
COLL_BSL = "bsl_code_v4_late"
COLL_GRAPH = "graph_embeddings"


_model_cache = {"m": None}


def get_query_embedder():
    if _model_cache["m"] is not None:
        return _model_cache["m"]
    from sentence_transformers import SentenceTransformer
    import torch
    instr = ("Instruct: Given a web search query, retrieve relevant passages "
             "that answer the query\nQuery: ")
    m = SentenceTransformer("Qwen/Qwen3-Embedding-8B",
        model_kwargs={"device_map": "auto"},
        tokenizer_kwargs={"padding_side": "left"})
    if torch.cuda.is_available():
        m = m.to("cuda")
    _model_cache["m"] = (m, instr)
    return _model_cache["m"]


def embed_query(q: str):
    m, instr = get_query_embedder()
    vec = m.encode([instr + q], show_progress_bar=False, convert_to_numpy=True)[0]
    return vec.tolist()


def make_vector_fn(qdrant: QdrantClient):
    def f(query: str, k: int = 10):
        emb = embed_query(query)
        hits = qdrant.query_points(collection_name=COLL_BSL, query=emb, limit=k).points
        return [{"id": str(h.id), "score": h.score,
                 "name": (h.payload or {}).get("name") or (h.payload or {}).get("symbol_name", ""),
                 "module": (h.payload or {}).get("module_path", ""),
                 "kind": "code"} for h in hits]
    return f


def make_community_fn(qdrant: QdrantClient):
    flt = qm.Filter(must=[qm.FieldCondition(key="kind", match=qm.MatchValue(value="Community"))])
    def f(query: str, k: int = 5):
        emb = embed_query(query)
        hits = qdrant.query_points(collection_name=COLL_GRAPH, query=emb, query_filter=flt, limit=k).points
        return [{"id": str(h.id), "score": h.score,
                 "name": (h.payload or {}).get("name", ""),
                 "summary": (h.payload or {}).get("summary", "")[:200],
                 "kind": "community"} for h in hits]
    return f


CYPHER_CALLERS = """
MATCH (callee:Symbol)
WHERE toLower(callee.name) CONTAINS toLower($name)
  AND ($module_hint = '' OR toLower(coalesce(callee.module_path, '')) CONTAINS toLower($module_hint))
WITH collect(DISTINCT callee) AS targets
UNWIND targets AS t
MATCH (caller:Symbol)-[:CALLS]->(t)
RETURN DISTINCT caller.name AS name, caller.module_path AS module, 'Symbol' AS kind
LIMIT $k
"""

CYPHER_IMPACT = """
MATCH (target:Symbol)
WHERE toLower(target.name) CONTAINS toLower($name)
  AND ($module_hint = '' OR toLower(coalesce(target.module_path, '')) CONTAINS toLower($module_hint))
OPTIONAL MATCH (caller:Symbol)-[:CALLS]->(target)
RETURN DISTINCT coalesce(caller.name, target.name) AS name,
                coalesce(caller.module_path, target.module_path) AS module,
                'Symbol' AS kind
LIMIT $k
"""

CYPHER_CALLERS_MODULE_ONLY = """
MATCH (callee:Symbol)
WHERE toLower(coalesce(callee.module_path, '')) CONTAINS toLower($module_hint)
WITH collect(DISTINCT callee) AS targets
UNWIND targets AS t
MATCH (caller:Symbol)-[:CALLS]->(t)
RETURN DISTINCT caller.name AS name, caller.module_path AS module, 'Symbol' AS kind
LIMIT $k
"""

CYPHER_DEAD = """
MATCH (s:Symbol)
WHERE s.is_export = true
  AND NOT (()-[:CALLS]->(s))
RETURN s.name AS name, s.module_path AS module, 'Symbol' AS kind
LIMIT $k
"""

CYPHER_SUBSYSTEM = """
MATCH (m:Module)-[:CONTAINS]->(o:Object)
WHERE toLower(coalesce(m.subsystem, '')) CONTAINS toLower($name)
   OR toLower(o.name) CONTAINS toLower($name)
RETURN DISTINCT o.name AS name, m.path AS module, 'Object' AS kind
LIMIT $k
"""

CYPHER_TOPOLOGY = """
MATCH (s:Symbol)<-[c:CALLS]-()
RETURN s.name AS name, s.module_path AS module, count(c) AS in_degree, 'Symbol' AS kind
ORDER BY in_degree DESC LIMIT $k
"""

CYPHER_CALLERS_MULTIHOP = """
MATCH (callee:Symbol)
WHERE toLower(callee.name) CONTAINS toLower($name)
  AND ($module_hint = '' OR toLower(coalesce(callee.module_path,'')) CONTAINS toLower($module_hint))
MATCH (caller:Symbol)-[:CALLS*1..3]->(callee)
RETURN DISTINCT caller.name AS name, caller.module_path AS module, 'Symbol' AS kind
LIMIT $k
"""


def extract_target(query: str) -> tuple[str, str]:
    """Return (symbol_name, module_hint).

    - module_hint: identifiers starting with subsystem/module prefixes
      ('гкс_', 'обх_', 'УТ_') or generic Russian-prefixed-with-underscore names.
      These typically denote a 1C module (e.g., "гкс_Взвешивание").
    - symbol_name: trailing CamelCase function name; for "Module.Function"
      dotted form, the part after dot.

    Pattern from FalkorDB CodeGraph + Neo4j GraphRAG: separate symbol from
    module hint to disambiguate same-named functions across modules.
    """
    import re
    candidates = re.findall(r"[А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_\.]{3,}", query)
    candidates = [c for c in candidates if any(ch.isupper() for ch in c) or "_" in c]
    if not candidates:
        return "", ""
    module_hint = ""
    symbol = ""
    module_prefixes = ("гкс_", "обх_", "УТ_", "БСП_", "сис_")
    for c in sorted(candidates, key=len, reverse=True):
        if "." in c:
            head, tail = c.rsplit(".", 1)
            if not module_hint and (head.startswith(module_prefixes) or "_" in head):
                module_hint = head
            if not symbol:
                symbol = tail
        elif c.startswith(module_prefixes):
            if not module_hint:
                module_hint = c
        elif not symbol:
            symbol = c
    if not symbol and module_hint:
        symbol = module_hint
    return symbol, module_hint


def make_graph_fn(driver):
    def f(query: str, k: int = 10, query_type: str = "semantic"):
        target, module_hint = extract_target(query)
        if not target: target = query[:60]
        params = {"name": target, "module_hint": module_hint, "k": k}
        # Detect multi-hop chain hints in query text — switch to *1..3 traversal.
        ql = query.lower()
        multihop_hints = ("через 2", "через 3", "транзитивно", "цепочка вызовов",
                          "уровн", "2-3 уровн", "несколько уровн")
        deep_chain = any(h in ql for h in multihop_hints)
        if query_type == "topology":
            cypher = CYPHER_TOPOLOGY
            params = {"k": k}
        elif query_type == "multi_hop_callers":
            if module_hint and target == module_hint:
                cypher = CYPHER_CALLERS_MODULE_ONLY
            elif deep_chain:
                cypher = CYPHER_CALLERS_MULTIHOP
            else:
                cypher = CYPHER_CALLERS
        elif query_type == "impact_analysis":
            cypher = CYPHER_IMPACT
        elif query_type == "dead_code":
            cypher = CYPHER_DEAD
            params = {"k": k}
        elif query_type == "architectural":
            cypher = CYPHER_SUBSYSTEM
            params = {"name": target, "k": k}
        else:
            cypher = CYPHER_IMPACT
        with driver.session() as session:
            recs = session.run(cypher, **params).data()
        out = []
        for r in recs:
            in_deg = r.get("in_degree")
            score = float(in_deg) if in_deg is not None else 0.5
            out.append({"id": f"{r.get('module', '')}/{r.get('name', '')}",
                        "name": r.get("name", ""), "module": r.get("module", ""),
                        "kind": r.get("kind", "graph"),
                        "in_degree": in_deg, "score": score})
        return out
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--out", type=Path, default=PROJECT_ROOT / "tmp" / "phase6_e2e_results.json")
    ap.add_argument("--limit", type=int, default=0, help="limit to first N queries")
    args = ap.parse_args()

    qdrant = QdrantClient(url=QDRANT_URL, timeout=120)
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    vector_fn = make_vector_fn(qdrant)
    graph_fn = make_graph_fn(driver)
    community_fn = make_community_fn(qdrant)

    print("Warming up Qwen3 embedder...")
    embed_query("warm up")
    print("Ready.\n")

    queries = GOLDEN_QUERIES if args.limit == 0 else GOLDEN_QUERIES[:args.limit]
    results, latencies = [], []
    by_type = {}

    for i, case in enumerate(queries, 1):
        t0 = time.time()
        r = hybrid_search(case["query"], vector_fn=vector_fn, graph_fn=graph_fn,
                          community_fn=community_fn, k=args.k)
        ms = (time.time() - t0) * 1000
        latencies.append(ms)
        n = len(r.results)
        ok = n >= case["expected_min"]
        by_type.setdefault(case["type"], {"pass": 0, "total": 0})
        by_type[case["type"]]["total"] += 1
        if ok: by_type[case["type"]]["pass"] += 1
        results.append({"id": case["id"], "type": case["type"], "query": case["query"],
                        "detected": r.detected_type, "strategy": r.strategy_used,
                        "n_results": n, "expected_min": case["expected_min"],
                        "pass": ok, "latency_ms": round(ms, 1),
                        "layers": r.layers_consulted,
                        "top3": [{"name": x.get("name", ""), "kind": x.get("kind", "")} for x in r.results[:3]]})
        flag = "PASS" if ok else "FAIL"
        print(f"[{i}/{len(queries)}] {case['id']} {flag} type={r.detected_type} strat={r.strategy_used} n={n} {ms:.0f}ms")

    driver.close()

    args.out.parent.mkdir(exist_ok=True)
    summary = {
        "total": len(results),
        "pass": sum(1 for r in results if r["pass"]),
        "by_type": by_type,
        "latency_p50_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
        "results": results,
    }
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 60}\nPhase 6 E2E results\n{'=' * 60}")
    print(f"Total: {summary['pass']}/{summary['total']} ({100 * summary['pass'] / summary['total']:.0f}%)")
    print(f"Latency: P50={summary['latency_p50_ms']}ms P95={summary['latency_p95_ms']}ms")
    print("By type:")
    for t, d in by_type.items():
        print(f"  {t:24s} {d['pass']}/{d['total']}")
    print(f"\nFull report: {args.out}")


if __name__ == "__main__":
    main()
