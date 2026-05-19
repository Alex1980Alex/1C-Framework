#!/usr/bin/env python3
"""Build BSL graph_embeddings - Phase 1 GraphRAG roadmap (260502)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import make_tracker  # noqa: E402
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

DEFAULT_DB = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
COLLECTION = "graph_embeddings"
QDRANT_URL = "http://localhost:6333"
EMBED_DIM = 4096
NODE_NS = uuid.UUID("c3d4e5f6-a7b8-9012-cdef-123456789abc")


def make_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NODE_NS, f"{kind}:{key}"))


def iter_module_nodes(conn):
    c = conn.cursor()
    c.execute("SELECT path, module_type, subsystem, object_type, object_name FROM module_metadata")
    for path, mtype, subsystem, obj_type, obj_name in c.fetchall():
        parts = [f"Module: {path}"]
        if mtype: parts.append(f"type={mtype}")
        if obj_type and obj_name: parts.append(f"object={obj_type}.{obj_name}")
        if subsystem: parts.append(f"subsystem={subsystem}")
        yield {
            "id": make_id("Module", path), "kind": "Module",
            "name": Path(path).stem if path else "Module",
            "module_path": path, "module_type": mtype or "",
            "object_type": obj_type or "", "object_name": obj_name or "",
            "subsystem": subsystem or "", "text": " | ".join(parts),
        }


def iter_symbol_nodes(conn):
    c = conn.cursor()
    c.execute("SELECT s.id, s.name, s.type, s.module_path, s.is_export, s.params, s.doc_comment, m.object_type, m.object_name FROM symbols s LEFT JOIN module_metadata m ON s.module_path = m.path")
    for sid, name, stype, mpath, is_export, params, doc, obj_type, obj_name in c.fetchall():
        parts = [f"{stype}: {name}"]
        if is_export: parts.append("Export")
        if obj_type and obj_name: parts.append(f"in {obj_type}.{obj_name}")
        if params: parts.append(f"params={params}")
        if doc: parts.append(f"doc={doc[:200]}")
        yield {
            "id": make_id("Symbol", sid), "kind": "Symbol", "name": name,
            "symbol_type": stype, "module_path": mpath, "is_export": bool(is_export),
            "object_type": obj_type or "", "object_name": obj_name or "",
            "text": " | ".join(parts),
        }


def iter_object_nodes(conn):
    c = conn.cursor()
    c.execute("SELECT DISTINCT object_type, object_name, subsystem FROM module_metadata WHERE object_type != ''  AND object_name != ''")
    for obj_type, obj_name, subsystem in c.fetchall():
        parts = [f"{obj_type}: {obj_name}"]
        if subsystem: parts.append(f"subsystem={subsystem}")
        yield {
            "id": make_id("Object", f"{obj_type}/{obj_name}"),
            "kind": "Object", "name": obj_name,
            "object_type": obj_type, "object_name": obj_name,
            "subsystem": subsystem or "", "text": " | ".join(parts),
        }


def collect_nodes(db_path, limit=None):
    conn = sqlite3.connect(str(db_path))
    nodes = []
    for it in (iter_module_nodes, iter_object_nodes, iter_symbol_nodes):
        for n in it(conn):
            nodes.append(n)
            if limit and len(nodes) >= limit:
                conn.close(); return nodes
    conn.close()
    return nodes


def ensure_collection(qdrant, recreate):
    exists = qdrant.collection_exists(COLLECTION)
    if exists and recreate:
        print(f"Recreating {COLLECTION}..."); qdrant.delete_collection(COLLECTION); exists = False
    if not exists:
        qdrant.create_collection(collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=EMBED_DIM, distance=qm.Distance.COSINE))
        print(f"Created {COLLECTION} ({EMBED_DIM}d, cosine)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--enable-fa2", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not args.db.exists():
        print(f"ERROR: {args.db} missing"); sys.exit(1)
    tracker = make_tracker("build_graph_embeddings").start()
    tracker.event("startup", db=str(args.db), recreate=bool(args.recreate),
                  fa2=bool(args.enable_fa2), batch_size=args.batch_size, limit=int(args.limit))
    t0 = time.time()
    print(f"=== Reading nodes from {args.db} ===")
    with tracker.stage("collect_nodes", db=str(args.db)):
        nodes = collect_nodes(args.db, limit=args.limit or None)
    print(f"Collected {len(nodes)} nodes")
    by_kind = {}
    for n in nodes: by_kind[n["kind"]] = by_kind.get(n["kind"], 0) + 1
    print(f"  By kind: {by_kind}")
    tracker.event("nodes_collected", count=len(nodes), by_kind=by_kind)
    if not nodes:
        tracker.stop(summary={"nodes": 0, "abort": "empty"}); sys.exit(1)
    print(f"\n=== Loading Qwen3-Embedding-8B {'+ FA2' if args.enable_fa2 else '(no FA2)'} ===")
    with tracker.stage("model_load", fa2=bool(args.enable_fa2)):
        from sentence_transformers import SentenceTransformer
        import torch
        model_kwargs = {"device_map": "auto"}
        tokenizer_kwargs = {"padding_side": "left"}
        if args.enable_fa2:
            try:
                import flash_attn  # noqa
                model_kwargs["attn_implementation"] = "flash_attention_2"
                print("  FA2 import OK")
            except ImportError:
                print("  WARN: flash_attn missing")
                tracker.event("fa2_missing")
        model = SentenceTransformer("Qwen/Qwen3-Embedding-8B",
            model_kwargs=model_kwargs, tokenizer_kwargs=tokenizer_kwargs)
        if torch.cuda.is_available(): model = model.to("cuda")
    print(f"Model loaded ({time.time() - t0:.1f}s)")
    qdrant = QdrantClient(host="localhost", port=6333, grpc_port=6334, prefer_grpc=True, timeout=300)
    with tracker.stage("ensure_collection", recreate=bool(args.recreate)):
        ensure_collection(qdrant, recreate=args.recreate)
    print(f"\n=== Embedding+upsert {len(nodes)} nodes ===")
    BATCH = max(1, args.batch_size); UPSERT_CHUNK = 200
    buf = []; total = 0
    tracker.set_state(total_nodes=len(nodes), nodes_done=0)
    with tracker.stage("embed_upsert", batch=BATCH, upsert_chunk=UPSERT_CHUNK):
        for i in range(0, len(nodes), BATCH):
            batch = nodes[i:i+BATCH]
            texts = [n["text"] for n in batch]
            t_enc = time.perf_counter()
            embs = model.encode(texts, batch_size=BATCH, show_progress_bar=False, convert_to_numpy=True)
            encode_s = time.perf_counter() - t_enc
            for n, emb in zip(batch, embs):
                payload = {k: v for k, v in n.items() if k not in ("id", "text")}
                payload["text"] = n["text"][:2000]
                buf.append(qm.PointStruct(id=n["id"], vector=emb.tolist(), payload=payload))
            tracker.set_state(nodes_done=min(i + BATCH, len(nodes)),
                              buf=len(buf), batch_idx=i // BATCH + 1)
            tracker.event("encode_batch", i=i, n=len(batch), encode_s=round(encode_s, 3))
            if len(buf) >= UPSERT_CHUNK:
                t_up = time.perf_counter()
                qdrant.upsert(collection_name=COLLECTION, points=buf, wait=False)
                upsert_s = time.perf_counter() - t_up
                total += len(buf); buf.clear()
                print(f"  [{total}/{len(nodes)}] upserted, {time.time()-t0:.0f}s")
                tracker.event("upsert_chunk", total=total, of=len(nodes), upsert_s=round(upsert_s, 3))
        if buf:
            t_up = time.perf_counter()
            qdrant.upsert(collection_name=COLLECTION, points=buf, wait=True)
            upsert_s = time.perf_counter() - t_up
            total += len(buf); buf.clear()
            tracker.event("upsert_tail", total=total, upsert_s=round(upsert_s, 3))
    elapsed = time.time() - t0
    final = qdrant.get_collection(COLLECTION)
    print(f"\n{'=' * 50}\nGRAPH EMBEDDINGS BUILD COMPLETE\n{'=' * 50}")
    print(f"  Nodes:   {len(nodes)}")
    print(f"  Points:  {final.points_count}")
    print(f"  Time:    {elapsed:.1f}s ({elapsed/max(1,len(nodes)):.2f}s/node)")
    tracker.stop(summary={
        "nodes": len(nodes),
        "points": final.points_count,
        "elapsed_s": round(elapsed, 1),
        "by_kind": by_kind,
    })


if __name__ == "__main__":
    main()
