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
            if ns and nt:
                key = f"{ns['name']}->{nt['name']}"
                if key not in seen:
                    seen.add(key); elines.append(key)
                    if len(elines) >= 20: break
    return "\n".join(nlines), "; ".join(elines) if elines else "(no internal calls)"


def call_llm(prompt: str, model: str = "zai/glm-5", max_tokens: int = 500):
    """Call LLM rotation MCP. Falls back to stub if rotation unavailable."""
    try:
        from src.shared.llm_rotation import client
        return client.complete(prompt=prompt, model=model, max_tokens=max_tokens)
    except Exception as e:
        print(f"    [LLM stub] {e}")
        return f"(Stub summary: {len(prompt)} char prompt; LLM rotation unavailable)"


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
    model = SentenceTransformer("Qwen/Qwen3-Embedding-8B",
        model_kwargs={"device_map": "auto"},
        tokenizer_kwargs={"padding_side": "left"})
    if torch.cuda.is_available(): model = model.to("cuda")
    texts = [p["payload"]["summary"] or p["payload"]["name"] for p in points]
    embs = model.encode(texts, batch_size=20, show_progress_bar=False, convert_to_numpy=True)
    qpoints = [qm.PointStruct(id=p["id"], vector=e.tolist(), payload=p["payload"])
               for p, e in zip(points, embs)]
    qdrant.upsert(collection_name=COLLECTION, points=qpoints, wait=True)
    return len(qpoints)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit communities for smoke test")
    ap.add_argument("--no-llm", action="store_true", help="Use stub summaries instead of LLM")
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
        # Generate summaries
        print(f"\nGenerating LLM summaries ({len(communities)} communities)...")
        summaries = {}
        for i, (cid, nids) in enumerate(communities.items(), 1):
            nlines, elines = build_summary_input(nids, nodes, edges)
            prompt = SUMMARY_PROMPT.format(nodes_listing=nlines, edges_listing=elines)
            if args.no_llm:
                summaries[cid] = f"Stub: {len(nids)} nodes, top labels in community"
            else:
                summaries[cid] = call_llm(prompt)
            if i % 10 == 0:
                print(f"  [{i}/{len(communities)}] summaries done")
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
