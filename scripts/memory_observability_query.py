#!/usr/bin/env python3
"""DuckDB SQL query layer over ALL memory observability sinks (§27 P3 / D3.2).

Mirrors ``scripts/audit_query.py`` (§15) but spans the full §27 sink set —
confidence-lifecycle, surfacing, ingestion, routing, read, propagation, circuit,
metrics, maintenance, audit — projected through the canonical reader-adapter
(``src/memory/infrastructure/event_envelope.normalize``) so one DuckDB ``events``
view answers cross-process questions, including the end-to-end **fact trace**
(D3.2: one ``content_hash`` threaded save → ingest → reinforce → forget).

Per roadmap Q3 the legacy sinks are NOT migrated on disk — each line is
normalized at read time, written to one pre-cleaned temp JSONL, then read with
``read_json_auto(..., union_by_name=true)`` (schema drift across sinks harmless).

Usage:
    python scripts/memory_observability_query.py --view recent
    python scripts/memory_observability_query.py --view by-source
    python scripts/memory_observability_query.py --view error-rate
    python scripts/memory_observability_query.py --view latency
    python scripts/memory_observability_query.py --view freshness
    python scripts/memory_observability_query.py --view fact-trace --content-hash <hash>
    python scripts/memory_observability_query.py --sql "SELECT ..."   # raw SQL over `events`

Requires DuckDB: ``pip install duckdb`` (or ``uv pip install duckdb``).

Roadmap: docs/roadmap/260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md (§27 P3).
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.infrastructure.event_envelope import known_sinks, normalize

# Root the sink registry is read from. Overridable via --root / MEMORY_OBS_ROOT
# (mirrors the loggers' CLAUDE_CACHE_DIR override) for tests / relocated trees.
SINK_ROOT = Path(os.environ.get("MEMORY_OBS_ROOT") or PROJECT_ROOT)

VIEWS: dict[str, str] = {
    "recent": """
        SELECT ts, source, type, content_hash, store, action, outcome, latency_ms
        FROM events
        ORDER BY ts DESC
        LIMIT 40
    """,
    "by-source": """
        SELECT source,
               COUNT(*) AS events,
               COUNT(DISTINCT type) AS event_types,
               MIN(ts) AS first_seen, MAX(ts) AS last_seen
        FROM events
        GROUP BY source
        ORDER BY events DESC
    """,
    "error-rate": """
        SELECT source,
               COUNT(*) AS total,
               SUM(CASE WHEN type IN ('error', 'reinforce_error', 'session_error')
                        OR success = FALSE THEN 1 ELSE 0 END) AS errors,
               ROUND(100.0 * SUM(CASE WHEN type IN ('error', 'reinforce_error', 'session_error')
                        OR success = FALSE THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_pct
        FROM events
        GROUP BY source
        HAVING errors > 0
        ORDER BY error_pct DESC
    """,
    "latency": """
        SELECT source, type,
               COUNT(*) AS samples,
               ROUND(AVG(latency_ms), 1) AS avg_ms,
               approx_quantile(latency_ms, 0.5) AS p50_ms,
               approx_quantile(latency_ms, 0.95) AS p95_ms
        FROM events
        WHERE latency_ms IS NOT NULL
        GROUP BY source, type
        ORDER BY p95_ms DESC
    """,
    "freshness": """
        SELECT source, COUNT(*) AS events, MAX(ts) AS last_seen
        FROM events
        GROUP BY source
        ORDER BY last_seen DESC
    """,
}


def _check_duckdb() -> bool:
    try:
        import duckdb

        return bool(duckdb)
    except ImportError:
        print("ERROR: duckdb not installed. Run: pip install duckdb", file=sys.stderr)
        return False


def _build_relation(con) -> str:
    """Create the normalized `events` view across every existing memory sink.

    Streams each sink, decodes per-line (skipping malformed JSON), projects via
    the canonical reader-adapter, and writes one pre-cleaned temp JSONL that
    DuckDB reads with full schema inference. Returns the temp path for cleanup.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    bad = 0
    written = 0
    try:
        for label, path in known_sinks(SINK_ROOT):
            if not path.exists():
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    try:
                        raw = json.loads(line_s)
                    except (ValueError, json.JSONDecodeError):
                        bad += 1
                        continue
                    rec = normalize(label, raw)
                    tmp.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    written += 1
    finally:
        tmp.close()

    def _cleanup(p: str = tmp.name) -> None:
        try:
            os.unlink(p)
        except OSError:
            pass

    atexit.register(_cleanup)

    if bad:
        print(f"(skipped {bad} malformed lines)", file=sys.stderr)
    if not written:
        # Empty events still produce a valid (empty) view so queries don't crash.
        tmp_empty = tmp.name
        con.execute(
            "CREATE OR REPLACE VIEW events AS "
            "SELECT NULL::VARCHAR AS ts, NULL::VARCHAR AS source, NULL::VARCHAR AS type, "
            "NULL::VARCHAR AS content_hash, NULL::VARCHAR AS store, NULL::VARCHAR AS action, "
            "NULL::VARCHAR AS outcome, NULL::DOUBLE AS latency_ms, NULL::BOOLEAN AS success "
            "WHERE 1=0"
        )
        return tmp_empty

    con.execute(
        "CREATE OR REPLACE VIEW events AS "
        f"SELECT * FROM read_json_auto('{tmp.name}', "
        "format='newline_delimited', union_by_name=true)"
    )
    return tmp.name


def _fact_trace(con, key: str) -> None:
    """Show every event sharing one fact key across all sinks (D3.2).

    ``key`` matches either ``content_hash`` (ingestion sink) OR ``pattern_id``
    (= ``UUID5(content_hash)`` — the confidence-lifecycle sink's key). Passing a
    ``pattern_id`` threads ingestion(saved/dup) → lifecycle(save/apply/reinforce/
    forget) for the same fact.
    """
    rows = con.execute(
        """
        SELECT ts, source, type, store, action, outcome
        FROM events
        WHERE content_hash = ? OR pattern_id = ?
        ORDER BY ts ASC
        """,
        [key, key],
    ).fetchall()
    if not rows:
        print(f"No events found for fact key={key}")
        return
    print(f"Fact trace ({len(rows)} events) for key={key[:20]}…:")
    print("-" * 92)
    print(f"{'ts':<28} {'source':<14} {'type':<18} {'store':<16} action/outcome")
    print("-" * 92)
    for ts, source, type_, store, action, outcome in rows:
        tail = action or outcome or ""
        print(
            f"{str(ts):<28} {str(source or ''):<14} {str(type_ or ''):<18} "
            f"{str(store or ''):<16} {tail or ''}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--view", choices=list(VIEWS.keys()) + ["fact-trace"], help="Predefined view"
    )
    parser.add_argument("--sql", help="Raw SQL (uses `events` as table name)")
    parser.add_argument("--content-hash", help="For --view fact-trace: content_hash or pattern_id")
    parser.add_argument("--key", help="Alias of --content-hash (content_hash OR pattern_id)")
    parser.add_argument("--limit", type=int, default=0, help="Append LIMIT (0=no limit)")
    parser.add_argument("--root", help="Project root to read sinks from (default: this repo)")
    args = parser.parse_args()

    if not args.view and not args.sql:
        parser.error("specify --view or --sql")
    if args.root:
        global SINK_ROOT
        SINK_ROOT = Path(args.root)
    if not _check_duckdb():
        return 2

    import duckdb

    con = duckdb.connect(":memory:")
    tmp_path = _build_relation(con)
    try:
        return _main_inner(con, args, parser)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _main_inner(con, args, parser) -> int:
    if args.view == "fact-trace":
        key = args.key or args.content_hash
        if not key:
            parser.error("--view fact-trace requires --key (or --content-hash)")
        _fact_trace(con, key)
        return 0

    sql = VIEWS[args.view] if args.view else args.sql
    if args.limit and "LIMIT" not in sql.upper():
        sql = f"{sql.rstrip().rstrip(';')} LIMIT {args.limit}"

    try:
        result = con.execute(sql)
    except Exception as exc:
        print(f"SQL error: {exc}", file=sys.stderr)
        return 1

    cols = [d[0] for d in result.description]
    print("\t".join(cols))
    for row in result.fetchall():
        print("\t".join(str(v) if v is not None else "" for v in row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
