#!/usr/bin/env python3
"""Load BSL call graph from SQLite to Neo4j (Phase 3 GraphRAG roadmap)."""
from __future__ import annotations
import argparse
import sqlite3
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import make_tracker  # noqa: E402
from neo4j import GraphDatabase

DEFAULT_DB = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "bsl-graph-2026")

SCHEMA = [
    "CREATE CONSTRAINT module_id IF NOT EXISTS FOR (n:Module) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (n:Symbol) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT object_id IF NOT EXISTS FOR (n:Object) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX symbol_name IF NOT EXISTS FOR (n:Symbol) ON (n.name)",
    "CREATE INDEX module_path IF NOT EXISTS FOR (n:Module) ON (n.path)",
    "CREATE INDEX object_name IF NOT EXISTS FOR (n:Object) ON (n.name)",
]


def chunked(items, size):
    buf = []
    for x in items:
        buf.append(x)
        if len(buf) >= size:
            yield buf; buf = []
    if buf: yield buf


def load_modules_and_objects(session, conn, tracker=None):
    c = conn.cursor()
    c.execute("SELECT path, module_type, subsystem, object_type, object_name FROM module_metadata")
    rows = c.fetchall()
    print(f"  Modules: {len(rows)}")
    if tracker:
        tracker.set_state(modules_total=len(rows), modules_done=0)
    batch_idx = 0
    for batch in chunked(rows, 1000):
        session.run("""
            UNWIND $rows AS row
            MERGE (m:Module {id: row.path})
            SET m.path = row.path, m.module_type = row.module_type,
                m.subsystem = row.subsystem, m.object_type = row.object_type,
                m.object_name = row.object_name
        """, rows=[{"path": r[0], "module_type": r[1] or "", "subsystem": r[2] or "",
                    "object_type": r[3] or "", "object_name": r[4] or ""} for r in batch])
        batch_idx += 1
        if tracker:
            tracker.set_state(modules_done=min(batch_idx * 1000, len(rows)))
            tracker.event("modules_batch", batch=batch_idx, rows=len(batch))
    objects = {(r[3], r[4]) for r in rows if r[3] and r[4]}
    print(f"  Objects: {len(objects)}")
    obj_rows = [{"id": f"{ot}/{on}", "object_type": ot, "name": on} for ot, on in objects]
    if obj_rows:
        session.run("""
            UNWIND $rows AS row
            MERGE (o:Object {id: row.id})
            SET o.object_type = row.object_type, o.name = row.name
        """, rows=obj_rows)
    if obj_rows:
        session.run("""
            MATCH (m:Module), (o:Object {id: m.object_type + '/' + m.object_name})
            MERGE (o)-[:CONTAINS]->(m)
        """)


def load_symbols(session, conn, tracker=None):
    c = conn.cursor()
    c.execute("SELECT id, name, type, module_path, line_start, line_end, is_export FROM symbols")
    rows = c.fetchall()
    print(f"  Symbols: {len(rows)}")
    if tracker:
        tracker.set_state(symbols_total=len(rows), symbols_done=0)
    batch_idx = 0
    for batch in chunked(rows, 2000):
        session.run("""
            UNWIND $rows AS row
            MERGE (s:Symbol {id: row.id})
            SET s.name = row.name, s.symbol_type = row.symbol_type,
                s.module_path = row.module_path, s.line_start = row.line_start,
                s.line_end = row.line_end, s.is_export = row.is_export
        """, rows=[{"id": r[0], "name": r[1], "symbol_type": r[2], "module_path": r[3],
                    "line_start": r[4] or 0, "line_end": r[5] or 0, "is_export": bool(r[6])} for r in batch])
        batch_idx += 1
        if tracker:
            tracker.set_state(symbols_done=min(batch_idx * 2000, len(rows)))
            tracker.event("symbols_batch", batch=batch_idx, rows=len(batch))
    session.run("""
        MATCH (s:Symbol), (m:Module {id: s.module_path})
        MERGE (m)-[:DECLARES]->(s)
    """)


def load_calls(session, conn, tracker=None):
    c = conn.cursor()
    c.execute("SELECT caller_id, callee_name, callee_module, line_number, call_type FROM calls")
    rows = c.fetchall()
    print(f"  Calls: {len(rows)}")
    if tracker:
        tracker.set_state(calls_total=len(rows), calls_done=0)
    batch_idx = 0
    for batch in chunked(rows, 5000):
        import time as _t
        t_b = _t.perf_counter()
        session.run("""
            UNWIND $rows AS row
            MATCH (caller:Symbol {id: row.caller_id})
            OPTIONAL MATCH (callee:Symbol {name: row.callee_name})
            FOREACH (_ IN CASE WHEN callee IS NOT NULL THEN [1] ELSE [] END |
                MERGE (caller)-[r:CALLS]->(callee)
                ON CREATE SET r.call_type = row.call_type, r.line = row.line_number)
        """, rows=[{"caller_id": r[0], "callee_name": r[1], "callee_module": r[2] or "",
                    "line_number": r[3] or 0, "call_type": r[4]} for r in batch])
        batch_idx += 1
        if tracker:
            done = min(batch_idx * 5000, len(rows))
            tracker.set_state(calls_done=done)
            tracker.event(
                "calls_batch",
                batch=batch_idx,
                rows=len(batch),
                done=done,
                total=len(rows),
                batch_s=round(_t.perf_counter() - t_b, 3),
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    if not args.db.exists():
        print(f"ERROR: {args.db} missing"); sys.exit(1)
    tracker = make_tracker("load_graph_to_neo4j").start()
    tracker.event("startup", db=str(args.db), neo4j_uri=NEO4J_URI, clear=bool(args.clear))
    t0 = time.time()
    conn = sqlite3.connect(str(args.db))
    with tracker.stage("neo4j_connect", uri=NEO4J_URI):
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    print(f"=== Connected to {NEO4J_URI} ===")
    stats: dict[str, int] = {}
    with driver.session() as session:
        if args.clear:
            with tracker.stage("clear_graph"):
                print("Clearing graph...")
                session.run("MATCH (n) DETACH DELETE n")
        with tracker.stage("schema"):
            print("Setting up schema...")
            for cypher in SCHEMA: session.run(cypher)
        print("\n=== Loading modules + objects ===")
        with tracker.stage("load_modules_objects"):
            load_modules_and_objects(session, conn, tracker=tracker)
        print("\n=== Loading symbols + DECLARES edges ===")
        with tracker.stage("load_symbols"):
            load_symbols(session, conn, tracker=tracker)
        print("\n=== Loading CALLS edges (this is the long part) ===")
        with tracker.stage("load_calls"):
            load_calls(session, conn, tracker=tracker)
        print("\n=== Final stats ===")
        with tracker.stage("final_stats"):
            for label in ("Module", "Symbol", "Object"):
                r = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
                print(f"  {label}: {r['c']}")
                stats[label] = int(r["c"])
            for rel in ("CONTAINS", "DECLARES", "CALLS"):
                r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()
                print(f"  {rel}: {r['c']}")
                stats[rel] = int(r["c"])
    driver.close()
    conn.close()
    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    tracker.stop(summary={**stats, "elapsed_s": round(elapsed, 1)})


if __name__ == "__main__":
    main()
