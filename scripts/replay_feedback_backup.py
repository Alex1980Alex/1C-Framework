"""Replay feedback JSONL backup → SQLite recovery (roadmap 260509 §3.5).

Reads `data/feedback/backups/backup_*.jsonl` produced by
`FeedbackCollector._write_jsonl_backup`, reconstructs `FeedbackEntry`
objects, and inserts them into a target SQLite database.

Use cases:
  - Primary SQLite (`data/feedback.db`) corrupted → restore from JSONL.
  - Migrate feedback to a new instance (copy backup dir, replay).
  - Build a clean dataset from selected dates only (`--since` / `--until`).

The script intentionally re-uses `FeedbackCollector.add_feedback` so the
target DB schema stays in sync with whatever the collector currently
defines. Backup IDs are NOT preserved — target DB assigns fresh
auto-increment IDs. Original backup ID is captured in the new entry's
`metadata.backup_origin_id` for traceability.

Idempotency: by default re-running replays everything (creates duplicates).
Pass `--dedupe` to skip entries whose `(query, timestamp)` pair already
exists in the target DB — sufficient for typical replay use.

Exit codes:
  0 — replay finished, summary printed
  1 — IO/parse failure
  2 — invalid arguments

Usage:
    python scripts/replay_feedback_backup.py --target-db data/feedback_restored.db
    python scripts/replay_feedback_backup.py --since 2026-05-01 --until 2026-05-09
    python scripts/replay_feedback_backup.py --dedupe
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_iso_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _enumerate_backup_files(
    backup_dir: Path,
    since: date | None,
    until: date | None,
) -> list[Path]:
    """Return sorted list of backup_YYYY-MM-DD.jsonl files within range."""
    if not backup_dir.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(backup_dir.glob("backup_*.jsonl")):
        stem = path.stem  # "backup_YYYY-MM-DD"
        try:
            file_date = _parse_iso_date(stem.replace("backup_", ""))
        except ValueError:
            logger.warning(f"Skipping unparseable backup filename: {path.name}")
            continue
        if since and file_date < since:
            continue
        if until and file_date > until:
            continue
        files.append(path)
    return files


def _existing_keys(target_db: Path) -> set[tuple[str, float]]:
    """Return set of (query, timestamp) pairs already in target DB."""
    if not target_db.is_file():
        return set()
    try:
        with sqlite3.connect(target_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT query, timestamp FROM feedback")
            return {(q, ts) for q, ts in cur.fetchall()}
    except sqlite3.DatabaseError as e:
        logger.warning(f"Could not read existing keys (treating as empty): {e}")
        return set()


def replay(
    backup_dir: Path,
    target_db: Path,
    since: date | None = None,
    until: date | None = None,
    dedupe: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Replay JSONL backups into target SQLite.

    Returns:
        (records_seen, records_inserted, records_skipped)
    """
    files = _enumerate_backup_files(backup_dir, since, until)
    if not files:
        logger.warning(f"No backup files matched in {backup_dir} (since={since} until={until})")
        return 0, 0, 0

    seen_keys = _existing_keys(target_db) if dedupe else set()

    # Lazy import — avoid pulling settings when only doing dry-run inspection
    if not dry_run:
        from src.pdf_framework.feedback.collector import FeedbackCollector, FeedbackEntry

        collector = FeedbackCollector(db_path=target_db, backup_enabled=False)

    seen = inserted = skipped = 0
    for path in files:
        with path.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                seen += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"{path.name}:{line_no} bad JSON: {e}")
                    skipped += 1
                    continue

                entry_data = record.get("entry") or {}
                if dedupe:
                    key = (entry_data.get("query", ""), entry_data.get("timestamp", 0.0))
                    if key in seen_keys:
                        skipped += 1
                        continue
                    seen_keys.add(key)

                if dry_run:
                    inserted += 1
                    continue

                # Tag origin so replays can be traced
                meta = dict(entry_data.get("metadata", {}))
                origin_id = record.get("id")
                if origin_id is not None:
                    meta["backup_origin_id"] = origin_id
                meta["backup_source_file"] = path.name
                entry_data["metadata"] = meta

                try:
                    entry = FeedbackEntry(**entry_data)
                except Exception as e:
                    logger.warning(f"{path.name}:{line_no} invalid entry: {e}")
                    skipped += 1
                    continue

                collector.add_feedback(entry)
                inserted += 1

    return seen, inserted, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("data/feedback/backups"),
        help="Directory holding backup_*.jsonl files",
    )
    parser.add_argument(
        "--target-db",
        type=Path,
        default=Path("data/feedback_restored.db"),
        help="SQLite DB to populate (created if missing)",
    )
    parser.add_argument("--since", type=_parse_iso_date, default=None, help="YYYY-MM-DD inclusive")
    parser.add_argument("--until", type=_parse_iso_date, default=None, help="YYYY-MM-DD inclusive")
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Skip entries whose (query, timestamp) already exist in target DB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only, don't insert (count what would be replayed)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.backup_dir.is_dir():
        print(f"ERROR: backup dir not found: {args.backup_dir}", file=sys.stderr)
        return 2

    seen, inserted, skipped = replay(
        backup_dir=args.backup_dir,
        target_db=args.target_db,
        since=args.since,
        until=args.until,
        dedupe=args.dedupe,
        dry_run=args.dry_run,
    )

    mode = "DRY-RUN" if args.dry_run else "REPLAY"
    print(f"[{mode}] target={args.target_db}")
    print(f"[{mode}] seen={seen} inserted={inserted} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
