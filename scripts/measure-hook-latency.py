#!/usr/bin/env python3
"""
Measure Write|Edit hook latency from data/hooks.db and data/hook-latency.jsonl.
Reports p50/p95/p99/max, per-hook breakdown, and KPI check (<100ms p95).

Usage:
    python scripts/measure-hook-latency.py [--last N] [--hook HOOK] [--tool TOOL]
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "hooks.db"
JSONL_PATH = PROJECT_ROOT / "data" / "hook-latency.jsonl"
KPI_P95_MS = 100


def load_from_sqlite(last_n: int, hook: str = "", tool: str = "") -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM latency"
        params = []
        conditions = []
        if hook:
            conditions.append("hook LIKE ?")
            params.append(f"%{hook}%")
        if tool:
            conditions.append("tool LIKE ?")
            params.append(f"%{tool}%")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY id DESC LIMIT {last_n}"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"SQLite error: {e}", file=sys.stderr)
        return []


def load_from_jsonl(last_n: int, hook: str = "", tool: str = "") -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    entries = []
    try:
        with open(JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if hook and hook.lower() not in entry.get("hook", "").lower():
                        continue
                    if tool and tool.lower() not in entry.get("tool", "").lower():
                        continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries[-last_n:]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0
    idx = min(int(len(values) * p / 100), len(values) - 1)
    return values[idx]


def print_stats(entries: list[dict], label: str = "All") -> dict:
    latencies = sorted(e.get("latency_ms", 0) for e in entries)
    if not latencies:
        print(f"  {label}: no data")
        return {}

    n = len(latencies)
    stats = {
        "count": n,
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "max": latencies[-1],
        "avg": sum(latencies) / n,
        "over_kpi": sum(1 for lat in latencies if lat > KPI_P95_MS),
    }

    kpi_status = "PASS" if stats["p95"] <= KPI_P95_MS else "FAIL"
    print(f"  {label} (n={n}):")
    print(f"    p50={stats['p50']:.1f}ms  p95={stats['p95']:.1f}ms  "
          f"p99={stats['p99']:.1f}ms  max={stats['max']:.1f}ms  avg={stats['avg']:.1f}ms")
    print(f"    KPI p95 <{KPI_P95_MS}ms: [{kpi_status}]  "
          f"(over KPI: {stats['over_kpi']}/{n})")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Hook latency measurement")
    parser.add_argument("--last", type=int, default=500, help="Last N records")
    parser.add_argument("--hook", type=str, default="", help="Filter by hook name")
    parser.add_argument("--tool", type=str, default="", help="Filter by tool (Write|Edit)")
    args = parser.parse_args()

    sqlite_entries = load_from_sqlite(args.last, args.hook, args.tool)
    jsonl_entries = load_from_jsonl(args.last, args.hook, args.tool)

    entries = sqlite_entries if sqlite_entries else jsonl_entries
    if not entries:
        print("No latency data found.")
        print(f"  Checked: {DB_PATH}")
        print(f"  Checked: {JSONL_PATH}")
        sys.exit(1)

    source = "SQLite" if sqlite_entries else "JSONL"
    print(f"=== Hook Latency Report ({source}, {len(entries)} records) ===\n")

    print_stats(entries, "Overall")
    print()

    write_edit = [e for e in entries if e.get("tool", "") in ("Write", "Edit")]
    if write_edit:
        print_stats(write_edit, "Write|Edit only")
        print()

    hooks = {}
    for e in entries:
        h = e.get("hook", "unknown")
        hooks.setdefault(h, []).append(e)

    if len(hooks) > 1:
        print("--- Per-hook breakdown ---")
        for hook_name in sorted(hooks.keys()):
            print_stats(hooks[hook_name], hook_name)
        print()

    if write_edit:
        we_stats = print_stats(write_edit, "KPI CHECK: Write|Edit")
        p95 = we_stats.get("p95", 999)
        if p95 <= KPI_P95_MS:
            print(f"\n  KPI ACHIEVED: Write|Edit p95={p95:.1f}ms <= {KPI_P95_MS}ms")
        else:
            print(f"\n  KPI NOT MET: Write|Edit p95={p95:.1f}ms > {KPI_P95_MS}ms")
            print(f"  Gap: {p95 - KPI_P95_MS:.1f}ms over target")


if __name__ == "__main__":
    main()
