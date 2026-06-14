#!/usr/bin/env python3
"""DuckDB analytics over memory-ingestion.log -- per-day / per-store event counts.

Sources cited (per task requirements):
  1. Official DuckDB JSON docs:
     https://duckdb.org/docs/stable/data/json/loading_json
     -- read_json_auto, format='newline_delimited', union_by_name, ignore_errors semantics.
  2. GitHub duckdb/duckdb issue #14259
     -- DuckDB >=1.1.x can misinfer mixed-type fields as MAP(VARCHAR, DATE);
        ignore_errors=true DROPS non-conforming columns (silent data loss).
        Robust fix: pre-filter malformed lines in Python, then read clean temp file.
  3. scripts/audit_query.py (this repo, trusted internal pattern)
     -- pre-clean pattern: stream-filter into temp JSONL, read with
        union_by_name=true (no ignore_errors), atexit + finally cleanup,
        duckdb.connect(":memory:"), TSV output.

Usage:
    python scripts/skill_ingest_trend.py
    python scripts/skill_ingest_trend.py --store skill_library
    python scripts/skill_ingest_trend.py --since 2026-06-08
    python scripts/skill_ingest_trend.py --sql "SELECT event, COUNT(*) FROM logs GROUP BY event"
    python scripts/skill_ingest_trend.py --log /path/to/other.log
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
DEFAULT_LOG = PROJECT_ROOT / ".claude" / "cache" / "memory-ingestion.log"


def _check_duckdb() -> bool:
    # Source: scripts/audit_query.py -- identical ImportError guard pattern
    try:
        import duckdb

        return True
    except ImportError:
        print(
            "ERROR: duckdb not installed. Run: pip install duckdb",
            file=sys.stderr,
        )
        return False


def _build_view(con: object, log_path: Path) -> str:
    """Pre-clean JSONL and create a `logs` DuckDB view over it.

    Source: scripts/audit_query.py -- pre-clean pattern.
    Rationale: DuckDB issue #14259 -- ignore_errors=true collapses schema to a
    single `json` column when malformed lines exist; pre-filtering in Python is
    safer.  union_by_name=true handles schema drift (early lines lack
    content_hash/pattern_id; store_size lines lack action/harvester).

    Source: official docs -- format='newline_delimited' for JSONL;
    union_by_name parameter; CREATE OR REPLACE VIEW.
    """
    if not log_path.exists():
        print(f"ERROR: log not found: {log_path}", file=sys.stderr)
        sys.exit(2)

    # Pre-clean: write only valid JSON lines into a temp file.
    # Source: scripts/audit_query.py -- pre-clean pattern (stream-filter).
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    bad = 0
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line_s = line.strip()
                if not line_s:
                    continue
                try:
                    json.loads(line_s)
                except (ValueError, json.JSONDecodeError):
                    bad += 1
                    continue
                tmp.write(line_s + "\n")
    finally:
        tmp.close()

    # Belt-and-suspenders cleanup at interpreter exit.
    # Source: scripts/audit_query.py -- atexit.register pattern.
    def _cleanup(path: str = tmp.name) -> None:
        # Source: scripts/audit_query.py -- _cleanup helper (near-verbatim copy)
        try:
            os.unlink(path)
        except OSError:
            pass

    atexit.register(_cleanup)

    if bad:
        print(f"(skipped {bad} malformed lines)", file=sys.stderr)

    # Build DuckDB view over clean temp file.
    # Source: official DuckDB docs -- read_json_auto + format='newline_delimited'.
    # Source: official DuckDB docs -- union_by_name=true for schema drift across lines.
    # Note: NO ignore_errors -- temp file is already clean (avoids issue #14259).
    read_expr = (
        f"SELECT * FROM read_json_auto('{tmp.name}', "
        "format='newline_delimited', union_by_name=true)"
    )
    # Source: official DuckDB docs -- CREATE OR REPLACE VIEW pattern.
    con.execute(f"CREATE OR REPLACE VIEW logs AS {read_expr}")  # type: ignore[union-attr]
    return tmp.name


def _default_query(store: str | None, since: str | None) -> tuple[str, list[str]]:
    """Build the default per-day / per-store count query with optional filters.

    Source: official DuckDB docs -- date_trunc('day', CAST(ts AS TIMESTAMP)).
    Source: [own] -- parameterised WHERE clauses to avoid SQL injection.
    """
    conditions: list[str] = []
    params: list[str] = []

    if store:
        conditions.append("store = ?")
        params.append(store)
    if since:
        conditions.append("CAST(ts AS TIMESTAMP) >= CAST(? AS TIMESTAMP)")
        params.append(since)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Source: official DuckDB docs -- date_trunc + GROUP BY aggregation pattern.
    sql = f"""
        SELECT
            date_trunc('day', CAST(ts AS TIMESTAMP)) AS day,
            store,
            COUNT(*) AS events
        FROM logs
        {where}
        GROUP BY day, store
        ORDER BY day DESC, events DESC
    """
    return sql, params


def _run_query(con: object, sql: str, params: list[str]) -> None:
    """Execute SQL and print TSV (header + rows), UTF-8 safe.

    Source: scripts/audit_query.py -- TSV output pattern (description + fetchall).
    Source: [own] -- sys.stdout.buffer.write for UTF-8 safety on Windows cp1251 pipes.
    """
    try:
        result = con.execute(sql, params)  # type: ignore[union-attr]
    except Exception as exc:
        print(f"SQL error: {exc}", file=sys.stderr)
        sys.exit(1)

    cols = [d[0] for d in result.description]
    # Source: [own] -- write UTF-8 bytes directly to avoid cp1251 encoding errors
    # on Windows (project feedback: windows-hook-stdout-cp1251).
    out = sys.stdout.buffer
    out.write(("\t".join(cols) + "\n").encode("utf-8"))
    for row in result.fetchall():
        out.write(("\t".join("" if v is None else str(v) for v in row) + "\n").encode("utf-8"))
    out.flush()


def main() -> int:
    # Source: scripts/audit_query.py -- argparse structure.
    parser = argparse.ArgumentParser(
        description="Per-day / per-store memory-ingestion event counts (DuckDB over JSONL)."
    )
    parser.add_argument(
        "--store",
        metavar="NAME",
        help="Filter to one store (e.g. skill_library, learned_patterns)",
    )
    parser.add_argument(
        "--since",
        metavar="ISO_DATE",
        help="Lower bound on ts (e.g. 2026-06-08 or 2026-06-08T00:00:00)",
    )
    parser.add_argument(
        "--sql",
        metavar="SQL",
        help="Raw SQL executed against the `logs` view (overrides default query)",
    )
    parser.add_argument(
        "--log",
        metavar="PATH",
        default=str(DEFAULT_LOG),
        help=f"Path to JSONL ingestion log (default: {DEFAULT_LOG})",
    )
    args = parser.parse_args()

    if not _check_duckdb():
        return 2

    import duckdb

    # Source: scripts/audit_query.py -- in-memory connection.
    # Source: official DuckDB docs -- duckdb.connect(":memory:").
    con = duckdb.connect(":memory:")
    log_path = Path(args.log)
    tmp_path = _build_view(con, log_path)

    try:
        if args.sql:
            # Source: scripts/audit_query.py -- raw --sql passthrough.
            _run_query(con, args.sql, [])
        else:
            sql, params = _default_query(args.store, args.since)
            _run_query(con, sql, params)
    finally:
        # Source: scripts/audit_query.py -- explicit unlink in finally block.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
