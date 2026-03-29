#!/usr/bin/env python3
"""
Migrate hook-invocations.jsonl and hook-latency.jsonl to SQLite.

Usage:
    python scripts/migrate-invocations-to-sqlite.py --dry-run
    python scripts/migrate-invocations-to-sqlite.py --input data/hook-invocations.jsonl
    python scripts/migrate-invocations-to-sqlite.py --input data/hook-latency.jsonl

Creates data/hooks.db with tables:
    - hook_invocations (from hook-invocations.jsonl)
    - hook_latency (from hook-latency.jsonl)
"""

import argparse
import json
import os
import sqlite3
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(PROJECT_ROOT, "data", "hooks.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS hook_invocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT,
    hook_name TEXT NOT NULL,
    hook_type TEXT NOT NULL,
    tool_name TEXT,
    latency_ms REAL,
    status TEXT DEFAULT 'ok',
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS hook_latency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hook TEXT NOT NULL,
    tool TEXT,
    latency_ms REAL NOT NULL,
    over_budget INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_invocations_hook
    ON hook_invocations(hook_name);
CREATE INDEX IF NOT EXISTS idx_invocations_ts
    ON hook_invocations(timestamp);
CREATE INDEX IF NOT EXISTS idx_latency_hook
    ON hook_latency(hook);
CREATE INDEX IF NOT EXISTS idx_latency_ts
    ON hook_latency(ts);
"""


def migrate_jsonl(jsonl_path: str, db_path: str, dry_run: bool = False) -> int:
    """Migrate a JSONL file to SQLite. Returns count of migrated rows."""
    table_name = "hook_latency" if "latency" in jsonl_path else "hook_invocations"

    if not os.path.isfile(jsonl_path):
        print(f"File not found: {jsonl_path}")
        return 0

    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"Read {len(rows)} rows from {jsonl_path}")

    if dry_run:
        print(f"[DRY RUN] Would insert {len(rows)} rows "
              f"into {table_name} at {db_path}")
        return len(rows)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    count = 0
    if table_name == "hook_latency":
        for row in rows:
            try:
                conn.execute(
                    "INSERT INTO hook_latency "
                    "(ts, hook, tool, latency_ms, over_budget) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        row.get("ts", ""),
                        row.get("hook", ""),
                        row.get("tool", ""),
                        float(row.get("latency_ms", 0)),
                        1 if row.get("over_budget") else 0,
                    ),
                )
                count += 1
            except (KeyError, ValueError, TypeError):
                continue
    else:
        for row in rows:
            try:
                conn.execute(
                    "INSERT INTO hook_invocations "
                    "(timestamp, session_id, hook_name, hook_type, "
                    "tool_name, latency_ms, status, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.get("timestamp", ""),
                        row.get("session_id", ""),
                        row.get("hook_name", ""),
                        row.get("hook_type", ""),
                        row.get("tool_name", ""),
                        float(row.get("latency_ms", 0)),
                        row.get("status", "ok"),
                        json.dumps(
                            row.get("metadata", {}),
                            ensure_ascii=False,
                        ),
                    ),
                )
                count += 1
            except (KeyError, ValueError, TypeError):
                continue

    conn.commit()
    conn.close()
    print(f"Migrated {count}/{len(rows)} rows "
          f"into {table_name} at {db_path}")
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate hook JSONL files to SQLite"
    )
    parser.add_argument(
        "--input",
        help="Path to JSONL file "
             "(default: both invocations + latency)",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="Path to SQLite database",
        default=DEFAULT_DB,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing",
    )
    args = parser.parse_args()

    if args.input:
        migrate_jsonl(args.input, args.output, args.dry_run)
    else:
        for name in [
            "hook-invocations.jsonl",
            "hook-latency.jsonl",
        ]:
            path = os.path.join(PROJECT_ROOT, "data", name)
            if os.path.isfile(path):
                t0 = time.time()
                count = migrate_jsonl(
                    path, args.output, args.dry_run
                )
                elapsed = (time.time() - t0) * 1000
                print(f"  Migration time: {elapsed:.0f}ms")


if __name__ == "__main__":
    main()
