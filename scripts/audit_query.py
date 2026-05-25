#!/usr/bin/env python3
"""DuckDB SQL query layer over data/hook-invocations.jsonl (§15 P0 P2.9).

Zero-migration analytics: DuckDB reads JSONL directly via `read_json_auto`.
~2200× faster than raw grep/jq scans on large logs.

Usage:
    python scripts/audit_query.py --view hooks-per-session
    python scripts/audit_query.py --view latency-p95
    python scripts/audit_query.py --view error-rate
    python scripts/audit_query.py --view causation-chain --correlation-id <uuid>
    python scripts/audit_query.py --sql "SELECT ..."  # raw SQL

Views (predefined queries):
- hooks-per-session: count hook invocations per session_id
- latency-p95: p50/p95/p99 latency per hook
- error-rate: error count + rate per hook
- causation-chain: trace event DAG for one correlation_id
- top-tools: most-invoked tools (PreToolUse/PostToolUse)
- recent: last N events

Requires DuckDB: `pip install duckdb` (or `uv pip install duckdb`).

Per roadmap 260523 §15.3 Option C + §15.4 P0 item 3.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
ROTATED_PATH = PROJECT_ROOT / "data" / "hook-invocations.1.jsonl"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"  # §15 P1 — Parquet cold tier

# §15 P0 P0.4 — optional decrypt of crypto-shredded error envelopes.
_HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"
sys.path.insert(0, str(_HOOKS_DIR))
try:
    from shared.crypto_shred import decrypt as _crypto_decrypt
    from shared.crypto_shred import is_encrypted as _is_encrypted
    from shared.session_keys import get_or_create_key as _get_key

    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

    def _is_encrypted(_v: object) -> bool:  # type: ignore[misc]
        return False

    def _crypto_decrypt(_b: str, _k: bytes) -> str | None:  # type: ignore[misc]
        return None

    def _get_key(_s: str) -> bytes | None:  # type: ignore[misc]
        return None


def _maybe_decrypt(value: object, session_id: object) -> str:
    """Return plaintext if value is encrypted envelope AND session key available.

    Otherwise returns value as-is, or `<shredded>` if envelope present but key
    gone (crypto-shredding semantics — §15.2 item 7).
    """
    if not isinstance(value, str) or not _is_encrypted(value):
        return str(value) if value is not None else ""
    sid = str(session_id) if session_id else ""
    if not sid:
        return "<encrypted>"
    key = _get_key(sid)
    if not key:
        return "<shredded>"
    pt = _crypto_decrypt(value, key)
    if pt is None:
        return "<shredded>"
    return pt


VIEWS: dict[str, str] = {
    "hooks-per-session": """
        SELECT session, COUNT(*) AS events,
               COUNT(DISTINCT hook) AS unique_hooks,
               MIN(ts) AS first_seen, MAX(ts) AS last_seen
        FROM logs
        WHERE session != ''
        GROUP BY session
        ORDER BY events DESC
        LIMIT 20
    """,
    "latency-p95": """
        SELECT hook,
               COUNT(*) AS calls,
               ROUND(AVG(elapsed_ms), 1) AS avg_ms,
               approx_quantile(elapsed_ms, 0.5) AS p50_ms,
               approx_quantile(elapsed_ms, 0.95) AS p95_ms,
               approx_quantile(elapsed_ms, 0.99) AS p99_ms
        FROM logs
        WHERE elapsed_ms > 0
        GROUP BY hook
        ORDER BY p95_ms DESC
        LIMIT 30
    """,
    "error-rate": """
        SELECT hook,
               COUNT(*) AS total,
               SUM(CASE WHEN outcome = 'error' OR error IS NOT NULL THEN 1 ELSE 0 END) AS errors,
               ROUND(100.0 * SUM(CASE WHEN outcome = 'error' OR error IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_pct
        FROM logs
        GROUP BY hook
        HAVING errors > 0
        ORDER BY error_pct DESC
    """,
    "top-tools": """
        SELECT tool, COUNT(*) AS calls
        FROM logs
        WHERE tool IS NOT NULL AND tool != ''
        GROUP BY tool
        ORDER BY calls DESC
        LIMIT 20
    """,
    "recent": """
        SELECT ts, hook, event, tool, outcome, elapsed_ms
        FROM logs
        ORDER BY ts DESC
        LIMIT 30
    """,
}


def _check_duckdb():
    try:
        import duckdb  # noqa: F401

        return True
    except ImportError:
        print(
            "ERROR: duckdb not installed. Run: pip install duckdb",
            file=sys.stderr,
        )
        return False


def _build_relation(con, include_rotated: bool, include_archive: bool = False) -> str:
    """Create `logs` view spanning current JSONL + optional rotated + Parquet archive.

    Pre-filters malformed lines via Python (DuckDB `ignore_errors=true` collapses
    schema to single `json` column when corrupted lines present — see git
    history of this file). Pre-cleaned content written to one temp JSONL,
    которое DuckDB читает с полноценным schema inference.

    With `include_archive=True`, UNIONs all `data/archive/*.parquet` files via
    DuckDB `read_parquet()` (§15 P1 — cold tier). Both branches use
    `union_by_name=True` так что schema drift между JSONL и Parquet harmless.

    Returns the temp JSONL file path so caller can delete it after query.
    """
    import atexit
    import json
    import os
    import tempfile

    if not JSONL_PATH.exists() and not include_archive:
        print(f"ERROR: {JSONL_PATH} not found", file=sys.stderr)
        sys.exit(2)

    paths = []
    if JSONL_PATH.exists():
        paths.append(JSONL_PATH)
    if include_rotated and ROTATED_PATH.exists():
        paths.append(ROTATED_PATH)

    # Pre-clean: stream-filter valid JSON lines into a single temp file.
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    bad = 0
    try:
        for src in paths:
            with open(src, encoding="utf-8", errors="replace") as f:
                for line in f:
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

    # Belt-and-suspenders: register cleanup at interpreter shutdown
    # in case caller forgets explicit unlink (e.g. exception в SQL).
    def _cleanup(path: str = tmp.name) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    atexit.register(_cleanup)

    if bad:
        print(f"(skipped {bad} malformed lines)", file=sys.stderr)

    # union_by_name=True handles schema drift (Phase 7→8→9 added fields).
    # No ignore_errors — temp file is pre-cleaned.
    parts = [
        f"SELECT * FROM read_json_auto('{tmp.name}', "
        f"format='newline_delimited', union_by_name=true)"
    ]

    if include_archive and ARCHIVE_DIR.exists():
        parquets = sorted(ARCHIVE_DIR.glob("*.parquet"))
        if parquets:
            files = "[" + ", ".join(f"'{p}'" for p in parquets) + "]"
            # union_by_name=true reconciles schema drift Parquet ↔ JSONL.
            parts.append(f"SELECT * FROM read_parquet({files}, union_by_name=true)")
            print(f"(merging {len(parquets)} archive parquet(s))", file=sys.stderr)

    if len(parts) == 1:
        union_sql = parts[0]
    else:
        union_sql = " UNION ALL BY NAME ".join(f"({p})" for p in parts)

    con.execute(f"CREATE OR REPLACE VIEW logs AS {union_sql}")
    return tmp.name


def _causation_chain(con, correlation_id: str) -> None:
    """Show DAG of events sharing one correlation_id, ordered by causation."""
    query = """
        SELECT ts, id, causationid, hook, event, tool, outcome
        FROM logs
        WHERE correlationid = ?
        ORDER BY ts ASC
    """
    rows = con.execute(query, [correlation_id]).fetchall()
    if not rows:
        print(f"No events found for correlationid={correlation_id}")
        return

    print(f"Correlation chain ({len(rows)} events):")
    print("-" * 100)
    print(f"{'ts':<28} {'id':<8} {'caused_by':<8} {'hook':<25} {'event':<18} outcome")
    print("-" * 100)
    for row in rows:
        ts, eid, caused, hook, event, _tool, outcome = row
        eid_short = str(eid or "")[:8]
        caused_short = str(caused or "")[:8] if caused else "—"
        hook_str = str(hook or "")[:25]
        event_str = str(event or "")[:18]
        print(
            f"{str(ts):<28} {eid_short:<8} {caused_short:<8} "
            f"{hook_str:<25} {event_str:<18} {outcome or ''}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--view", choices=list(VIEWS.keys()) + ["causation-chain"], help="Predefined view"
    )
    parser.add_argument("--sql", help="Raw SQL (uses `logs` as table name)")
    parser.add_argument("--correlation-id", help="For --view causation-chain")
    parser.add_argument(
        "--include-rotated",
        action="store_true",
        help="Also scan hook-invocations.1.jsonl (rotated)",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Also scan data/archive/*.parquet cold tier (§15 P1)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Append LIMIT to result (0=no limit)")
    parser.add_argument(
        "--decrypt-errors",
        action="store_true",
        help="Decrypt `error` envelopes when session key available",
    )
    args = parser.parse_args()

    if not args.view and not args.sql:
        parser.error("specify --view or --sql")

    if not _check_duckdb():
        return 2

    import duckdb

    con = duckdb.connect(":memory:")
    tmp_path = _build_relation(
        con,
        include_rotated=args.include_rotated,
        include_archive=args.include_archive,
    )
    # Best-effort cleanup в normal exit path; atexit handles abnormal exits.
    try:
        return _main_inner(con, args, parser)
    finally:
        try:
            import os as _os

            _os.unlink(tmp_path)
        except OSError:
            pass


def _main_inner(con, args, parser) -> int:
    if args.view == "causation-chain":
        if not args.correlation_id:
            parser.error("--view causation-chain requires --correlation-id")
        _causation_chain(con, args.correlation_id)
        return 0

    if args.view:
        sql = VIEWS[args.view]
    else:
        sql = args.sql

    if args.limit and "LIMIT" not in sql.upper():
        sql = f"{sql.rstrip().rstrip(';')} LIMIT {args.limit}"

    try:
        result = con.execute(sql)
    except Exception as exc:
        print(f"SQL error: {exc}", file=sys.stderr)
        return 1

    # Print column names + rows; optional decrypt of `error` field per row.
    cols = [d[0] for d in result.description]
    err_idx = cols.index("error") if "error" in cols else -1
    sess_idx = cols.index("session") if "session" in cols else -1
    print("\t".join(cols))
    for row in result.fetchall():
        row_list = list(row)
        if args.decrypt_errors and err_idx >= 0 and sess_idx >= 0:
            row_list[err_idx] = _maybe_decrypt(row_list[err_idx], row_list[sess_idx])
        print("\t".join(str(v) if v is not None else "" for v in row_list))

    return 0


if __name__ == "__main__":
    sys.exit(main())
