#!/usr/bin/env python3
"""Nightly archival: hook-invocations.jsonl → Parquet cold tier (§15 P1 P5).

DuckDB `COPY ... TO 'X.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)` produces
columnar archive ~10-30× smaller than JSONL для same content. Compressed
parquets remain query-able by DuckDB via `read_parquet()`.

Workflow:
1. Pre-filter malformed JSON lines (same logic as audit_query._build_relation).
2. DuckDB reads cleaned JSONL via `read_json_auto(..., union_by_name=true)`.
3. `COPY (SELECT * FROM logs) TO 'data/archive/hook-events-<YYYYMMDD>.parquet'
   (FORMAT PARQUET, COMPRESSION ZSTD)`.
4. Optional: --rotate moves source jsonl → .jsonl.archived-<YYYYMMDD>.
5. Optional: --retention N delets parquets older than N days.

Usage:
    # Daily archive (most common — preserve source as-is)
    python scripts/archive_jsonl_to_parquet.py

    # Archive + rotate source (start fresh jsonl tomorrow)
    python scripts/archive_jsonl_to_parquet.py --rotate

    # GC archives older than 365 days
    python scripts/archive_jsonl_to_parquet.py --retention 365

    # Dry run (show what would happen, no writes)
    python scripts/archive_jsonl_to_parquet.py --dry-run

Per roadmap 260523 §15.4 P0 cold-tier foundation (decouple instrumentation).
Successor steps (§15 P1 P6): PyIceberg snapshot append + S3/MinIO retention.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
ROTATED_PATH = PROJECT_ROOT / "data" / "hook-invocations.1.jsonl"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"


def _check_duckdb() -> bool:
    try:
        import duckdb  # noqa: F401
        return True
    except ImportError:
        print("ERROR: duckdb not installed. pip install duckdb", file=sys.stderr)
        return False


def _pre_clean(paths: list[Path]) -> tuple[str, int, int]:
    """Stream-filter JSONL lines into temp file. Returns (temp_path, kept, bad)."""
    kept = 0
    bad = 0
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    try:
        for src in paths:
            if not src.exists():
                continue
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
                    kept += 1
    finally:
        tmp.close()
    return tmp.name, kept, bad


def cmd_archive(rotate: bool, dry_run: bool) -> int:
    """Produce one Parquet from current JSONL state."""
    if not _check_duckdb():
        return 2
    paths = [JSONL_PATH]
    if ROTATED_PATH.exists():
        paths.append(ROTATED_PATH)
    if not any(p.exists() for p in paths):
        print(f"No JSONL source at {JSONL_PATH}")
        return 1

    date_tag = dt.date.today().strftime("%Y%m%d")
    archive_path = ARCHIVE_DIR / f"hook-events-{date_tag}.parquet"

    print(f"Source: {[str(p) for p in paths if p.exists()]}")
    print(f"Target: {archive_path}")
    if dry_run:
        print("(dry-run — no writes)")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    tmp_path, kept, bad = _pre_clean(paths)
    print(f"Pre-clean: {kept} valid, {bad} malformed lines skipped")

    try:
        import duckdb

        con = duckdb.connect(":memory:")
        con.execute(
            f"CREATE VIEW logs AS SELECT * FROM read_json_auto('{tmp_path}', "
            f"format='newline_delimited', union_by_name=true)"
        )
        # COMPRESSION ZSTD — best ratio/speed для cold tier per duckdb docs.
        con.execute(
            f"COPY (SELECT * FROM logs) TO '{archive_path}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        size = archive_path.stat().st_size
        print(f"Archive written: {size:,} bytes")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if rotate:
        if JSONL_PATH.exists():
            rotated_to = JSONL_PATH.with_name(f"hook-invocations.jsonl.archived-{date_tag}")
            shutil.move(str(JSONL_PATH), str(rotated_to))
            print(f"Rotated source: {JSONL_PATH.name} → {rotated_to.name}")

    return 0


def cmd_retention(days: int, dry_run: bool) -> int:
    """Delete Parquet archives older than `days`."""
    if days <= 0:
        print("ERROR: --retention requires positive integer", file=sys.stderr)
        return 1
    if not ARCHIVE_DIR.exists():
        print(f"No archive dir at {ARCHIVE_DIR}")
        return 0
    cutoff_ts = dt.datetime.now().timestamp() - days * 86400
    deleted = 0
    for path in ARCHIVE_DIR.iterdir():
        if not path.is_file() or path.suffix != ".parquet":
            continue
        try:
            if path.stat().st_mtime < cutoff_ts:
                if dry_run:
                    print(f"would delete: {path.name}")
                else:
                    path.unlink()
                    print(f"deleted: {path.name}")
                deleted += 1
        except OSError:
            continue
    verb = "would delete" if dry_run else "deleted"
    print(f"\n{verb}: {deleted} archives older than {days} days")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rotate", action="store_true",
                        help="After archive, move source jsonl → .archived-<date>")
    parser.add_argument("--retention", type=int, metavar="DAYS",
                        help="Delete archives older than N days (separate run mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done, no writes")
    args = parser.parse_args()

    if args.retention is not None:
        return cmd_retention(args.retention, dry_run=args.dry_run)
    return cmd_archive(rotate=args.rotate, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
