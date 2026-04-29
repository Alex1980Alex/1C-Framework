"""Phase 8.12.8 Step 4: multi-positive labeling via call_graph 1-hop neighbors.

KL-divergence validation skipped for pilot — TODO next iteration:
compute KL between query↔positive cosine sim distribution vs noise baseline.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "cache" / "bsl_call_graph.db"


def load_symbols_index(db_path: Path) -> tuple[dict[tuple[str, str], str], dict[str, list[str]]]:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, module_path FROM symbols")
    idx_full: dict[tuple[str, str], str] = {}
    idx_name: dict[str, list[str]] = {}
    for sym_id, name, mod in cursor.fetchall():
        idx_full[(name, mod or "")] = sym_id
        idx_name.setdefault(name, []).append(sym_id)
    conn.close()
    return idx_full, idx_name


def neighbors_of(conn: sqlite3.Connection, symbol_id: str, name: str, module_path: str,
                 idx_full: dict[tuple[str, str], str],
                 idx_name: dict[str, list[str]]) -> set[str]:
    neighbors: set[str] = set()
    cur = conn.cursor()
    cur.execute(
        "SELECT caller_id FROM calls WHERE callee_name = ? "
        "AND (callee_module = ? OR callee_module = '' OR callee_module IS NULL)",
        (name, module_path),
    )
    for (caller,) in cur.fetchall():
        if caller and caller != symbol_id:
            neighbors.add(caller)

    cur.execute("SELECT callee_name, callee_module FROM calls WHERE caller_id = ?", (symbol_id,))
    for callee_name, callee_mod in cur.fetchall():
        if not callee_name:
            continue
        resolved = idx_full.get((callee_name, callee_mod or ""))
        if not resolved:
            cands = idx_name.get(callee_name, [])
            if len(cands) == 1:
                resolved = cands[0]
        if resolved and resolved != symbol_id:
            neighbors.add(resolved)

    return neighbors


def fetch_chunk_id(client: QdrantClient, name: str, module_path: str,
                   collection: str) -> str | None:
    flt = Filter(must=[
        FieldCondition(key="name", match=MatchValue(value=name)),
        FieldCondition(key="module_path", match=MatchValue(value=module_path)),
    ])
    points, _ = client.scroll(
        collection_name=collection, scroll_filter=flt,
        limit=1, with_payload=False, with_vectors=False,
    )
    return str(points[0].id) if points else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=Path, default=config.QUERIES_PILOT)
    p.add_argument("--output", type=Path, default=config.GOLDEN_SET)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--max-neighbors", type=int, default=20)
    args = p.parse_args()

    print(f"[label] loading symbols index from {args.db}")
    idx_full, idx_name = load_symbols_index(args.db)
    conn = sqlite3.connect(str(args.db))

    queries: list[dict] = []
    with open(args.queries, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    print(f"[label] {len(queries)} queries loaded")

    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT, timeout=30)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    total_positives = 0
    processed = 0
    with open(args.output, "w", encoding="utf-8") as out:
        for q in queries:
            sid = q["anchor_symbol_id"]
            name = q["anchor_name"]
            module_path = q["anchor_module_path"]
            anchor_chunk_id = q["anchor_chunk_id"]

            neighbors = neighbors_of(conn, sid, name, module_path, idx_full, idx_name)
            neighbors = set(list(neighbors)[: args.max_neighbors])

            secondary_chunk_ids: list[str] = []
            for nsid in neighbors:
                if "::" not in nsid:
                    continue
                n_module, n_name = nsid.rsplit("::", 1)
                cid = fetch_chunk_id(client, n_name, n_module, config.COLL_QWEN3)
                if cid and cid != anchor_chunk_id:
                    secondary_chunk_ids.append(cid)

            graded = {anchor_chunk_id: 3}
            for cid in secondary_chunk_ids:
                graded[cid] = 2

            out.write(json.dumps({
                "query": q["query"], "primary_positive": anchor_chunk_id,
                "secondary_positives": secondary_chunk_ids, "graded": graded,
                "anchor_symbol_id": sid, "anchor_chunk_id": anchor_chunk_id,
                "n_neighbors": len(secondary_chunk_ids),
            }, ensure_ascii=False) + "\n")
            total_positives += 1 + len(secondary_chunk_ids)
            processed += 1

    conn.close()
    avg = total_positives / processed if processed else 0.0
    print(f"Done: {processed} queries labeled, avg {avg:.2f} positives -> {args.output}")


if __name__ == "__main__":
    main()
