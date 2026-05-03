#!/usr/bin/env python3
"""Phase 2: Leiden communities + LLM summaries (GraphRAG roadmap 260502)."""
from __future__ import annotations
import argparse
import os
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import igraph as ig
import leidenalg
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bsl-graph-2026")
QDRANT_URL = "http://localhost:6333"
COLLECTION = "graph_embeddings"
COMMUNITY_NS = uuid.UUID("d4e5f6a7-b8c9-0123-defa-2345678901bc")
EMBED_DIM = 4096
MIN_COMMUNITY_SIZE = 5

SUMMARY_PROMPT = """You are a 1C:Enterprise architect with 10+ years of experience.
Below is a list of objects and connections from one configuration subsystem.

Describe briefly (4-6 sentences in Russian):
1. Business function (what processes it serves)
2. 2-3 key documents/catalogs
3. Registers - what they write (movements), what they read
4. Connections to other subsystems via shared objects or FO

Nodes (kind: name): {nodes_listing}
Top calls: {edges_listing}

Style: plain markdown, no headers, exact object names from the list, no fabricated connections.
Reply (Russian):"""


def fetch_subgraph(session):
    print("Fetching graph from Neo4j...")
    nodes_q = session.run("""
        MATCH (n) WHERE n:Module OR n:Symbol OR n:Object
        RETURN id(n) AS nid, labels(n)[0] AS label, n.name AS name,
               coalesce(n.object_type, '') AS object_type,
               coalesce(n.module_path, n.path, '') AS path
    """)
    nodes = {r["nid"]: dict(r) for r in nodes_q}
    edges_q = session.run("""
        MATCH (a)-[r:CALLS|REFERENCES|DECLARES|CONTAINS]->(b)
        RETURN id(a) AS source, id(b) AS target, type(r) AS rel
    """)
    edges = [(r["source"], r["target"], r["rel"]) for r in edges_q]
    print(f"  {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


def run_leiden(nodes, edges, seed=42):
    print("Running Leiden...")
    nid_to_idx = {nid: i for i, nid in enumerate(nodes.keys())}
    edge_list = [(nid_to_idx[s], nid_to_idx[t]) for s, t, _ in edges if s in nid_to_idx and t in nid_to_idx]
    g = ig.Graph(n=len(nodes), edges=edge_list, directed=False)
    g.simplify(combine_edges=None)
    partition = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition, seed=seed)
    communities = defaultdict(list)
    nids = list(nodes.keys())
    for idx, comm_id in enumerate(partition.membership):
        communities[comm_id].append(nids[idx])
    print(f"  Detected {len(communities)} raw communities")
    nontrivial = {cid: ns for cid, ns in communities.items() if len(ns) >= MIN_COMMUNITY_SIZE}
    coverage = sum(len(ns) for ns in nontrivial.values()) / max(1, len(nodes))
    print(f"  Nontrivial (>={MIN_COMMUNITY_SIZE} nodes): {len(nontrivial)} ({coverage*100:.1f}% coverage)")
    return nontrivial


def build_summary_input(community_nids, nodes, edges, max_nodes=40):
    cset = set(community_nids)
    nlines = []
    by_label = defaultdict(list)
    for nid in community_nids:
        n = nodes[nid]
        name = n.get("name") or n.get("path") or f"node-{nid}"
        by_label[n["label"]].append(str(name))
    for label in ("Object", "Module", "Symbol"):
        items = [x for x in by_label.get(label, []) if x][:max_nodes // 3]
        if items: nlines.append(f"{label}: " + ", ".join(items))
    elines = []
    seen = set()
    for s, t, rel in edges:
        if s in cset and t in cset and rel == "CALLS":
            ns, nt = nodes.get(s), nodes.get(t)
            if ns and nt and ns.get("name") and nt.get("name"):
                key = f"{ns['name']}->{nt['name']}"
                if key not in seen:
                    seen.add(key); elines.append(key)
                    if len(elines) >= 20: break
    return "\n".join(nlines), "; ".join(elines) if elines else "(no internal calls)"


def build_deterministic_summary(community_nids, nodes, edges, top_n: int = 5) -> str:
    """Structured Russian summary from graph data — no LLM dependency.

    Pattern from FalkorDB CodeGraph + Neo4j GraphRAG field guide: instead of
    LLM narrative (lossy, non-deterministic, fails on rate-limit), compose
    a telegraphic summary from concrete graph features. Maximum accuracy,
    100% reproducibility, microseconds per community.
    """
    from collections import Counter
    cset = set(community_nids)
    objects, modules, symbols = [], [], []
    for nid in community_nids:
        n = nodes[nid]
        lab = n.get("label")
        if lab == "Object": objects.append(n)
        elif lab == "Module": modules.append(n)
        elif lab == "Symbol": symbols.append(n)

    subs = Counter(n.get("subsystem", "") for n in modules + objects if n.get("subsystem"))
    obj_types = Counter(o.get("object_type", "") for o in objects if o.get("object_type"))

    in_deg = Counter()
    internal_calls = 0
    for s, t, rel in edges:
        if rel != "CALLS": continue
        if t in cset: in_deg[t] += 1
        if s in cset and t in cset: internal_calls += 1
    top_syms = [(nodes[nid]["name"], deg) for nid, deg in in_deg.most_common(top_n)
                if nid in cset and nodes[nid].get("name")]

    parts = []
    if subs:
        parts.append("Подсистемы: " + ", ".join(s for s, _ in subs.most_common(3)) + ".")
    if obj_types:
        parts.append("Объекты: " + ", ".join(f"{t} ({n})" for t, n in obj_types.most_common(5)) + ".")
    parts.append(f"Модулей: {len(modules)}, символов: {len(symbols)}, объектов: {len(objects)}.")
    parts.append(f"Внутренних вызовов CALLS: {internal_calls}.")
    if top_syms:
        parts.append("Ключевые функции (по числу вызывающих): "
                     + ", ".join(f"{name}({deg})" for name, deg in top_syms) + ".")
    if objects:
        obj_names = [o.get("name", "") for o in objects if o.get("name")][:5]
        if obj_names:
            parts.append("Примеры объектов: " + ", ".join(obj_names) + ".")
    return " ".join(parts)


def save_communities(session, qdrant, communities, nodes, summaries):
    print(f"Saving {len(communities)} communities to Neo4j + Qdrant...")
    points = []
    for cid, nids in communities.items():
        community_uuid = str(uuid.uuid5(COMMUNITY_NS, str(cid)))
        summary = summaries.get(cid, "")
        names = [nodes[nid]["name"] for nid in nids[:50]]
        # Neo4j Community node
        session.run("""
            MERGE (c:Community {id: $cid})
            SET c.name = $name, c.summary = $summary, c.size = $size, c.detected_by = "leiden"
        """, cid=community_uuid, name=f"Community-{cid}",
             summary=summary, size=len(nids))
        # Link nodes
        for nid in nids:
            n = nodes[nid]
            label = n["label"]
            session.run(f"""
                MATCH (c:Community {{id: $cid}})
                MATCH (n:{label}) WHERE id(n) = $nid
                MERGE (n)-[:BELONGS_TO]->(c)
            """, cid=community_uuid, nid=nid)
        # Qdrant point (will get embedding later)
        points.append({
            "id": community_uuid,
            "payload": {"kind": "Community", "name": f"Community-{cid}",
                        "summary": summary[:2000], "size": len(nids),
                        "node_names": names},
        })
    return points


def embed_and_upsert(qdrant, points, summaries):
    """Embed summaries via Qwen3-st and upsert to graph_embeddings."""
    if not points: return 0
    print(f"Embedding {len(points)} community summaries...")
    from sentence_transformers import SentenceTransformer
    import torch
    # device_map="auto" + .to() triggers "Cannot copy out of meta tensor".
    # Pick device upfront and let SentenceTransformer load weights there.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("Qwen/Qwen3-Embedding-8B",
        device=device,
        tokenizer_kwargs={"padding_side": "left"})
    texts = [p["payload"]["summary"] or p["payload"]["name"] for p in points]
    embs = model.encode(texts, batch_size=20, show_progress_bar=False, convert_to_numpy=True)
    qpoints = [qm.PointStruct(id=p["id"], vector=e.tolist(), payload=p["payload"])
               for p, e in zip(points, embs)]
    qdrant.upsert(collection_name=COLLECTION, points=qpoints, wait=True)
    return len(qpoints)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit communities for smoke test")
    args = ap.parse_args()

    t0 = time.time()
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    qdrant = QdrantClient(url=QDRANT_URL, timeout=120)

    with driver.session() as session:
        nodes, edges = fetch_subgraph(session)
        communities = run_leiden(nodes, edges)
        if args.limit > 0:
            communities = dict(list(communities.items())[:args.limit])
            print(f"  Limited to {len(communities)} communities for smoke test")
        # Deterministic summaries — no LLM dependency, 100% reproducible.
        print(f"\nGenerating deterministic summaries ({len(communities)} communities)...")
        summaries = {cid: build_deterministic_summary(nids, nodes, edges)
                     for cid, nids in communities.items()}
        # Save
        points = save_communities(session, qdrant, communities, nodes, summaries)
        # Embed + upsert (only if not --no-llm to save time on stubs)
        upserted = embed_and_upsert(qdrant, points, summaries)
        print(f"\nUpserted {upserted} community embeddings to {COLLECTION}")

    driver.close()
    elapsed = time.time() - t0
    print(f"\nTotal: {elapsed:.1f}s, {len(communities)} communities")


if __name__ == "__main__":
    main()
