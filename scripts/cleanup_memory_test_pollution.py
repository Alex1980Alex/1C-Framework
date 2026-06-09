#!/usr/bin/env python3
"""Cleanup of test-fixture pollution in production memory sinks (roadmap 260609 P0.3).

Before the P0.2 isolation landed (tests/conftest.py: CLAUDE_CACHE_DIR +
LINK_REGISTRY_PATH overrides), pytest runs wrote fixture data into the real
observability sinks and the real link graph:

  - .claude/cache/confidence-lifecycle.log — fixture events with synthetic ids
    (session_id: s1/s-cap/s2/idem-ses/cool-ses; pattern_id: pid-1/pid-err/...)
  - data/link_registry.db — edges with fixture entity ids
    (test-source-001, orphan-src, verify-src-42, only-in-links, ...)

This script removes both kinds of pollution. DRY-RUN by default; pass --apply
to write. The lifecycle log is backed up next to itself before rewrite.

Detection rules (production shapes, see 27.12.7):
  - real `session` events carry an 8-hex session_id prefix (uuid[:8]);
  - real `reinforce*` events carry a full-UUID pattern_id.
Anything else in those event families is fixture residue.

Usage:
    .venv/Scripts/python.exe scripts/cleanup_memory_test_pollution.py [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIFECYCLE_LOG = PROJECT_ROOT / ".claude" / "cache" / "confidence-lifecycle.log"
LINK_REGISTRY = PROJECT_ROOT / "data" / "link_registry.db"

_HEX8 = re.compile(r"^[0-9a-f]{8}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Fixture entity-id shapes observed in data/link_registry.db (tests created
# these via LinkRegistry() with the default production path).
_FIXTURE_ID_SQL = (
    "source_id LIKE 'test-%' OR target_id LIKE 'test-%' "
    "OR source_id LIKE 'orphan-%' OR target_id LIKE 'orphan-%' "
    "OR source_id LIKE 'verify-%' OR target_id LIKE 'verify-%' "
    "OR source_id IN ('only-in-links', 'also-in-links') "
    "OR target_id IN ('only-in-links', 'also-in-links')"
)


def _is_fixture_event(d: dict) -> bool:
    event = d.get("event", "")
    if event in ("session", "session_error"):
        return not _HEX8.match(str(d.get("session_id", "")))
    if event in ("reinforce", "reinforce_miss", "reinforce_error"):
        return not _UUID.match(str(d.get("pattern_id", "")))
    return False


def clean_lifecycle_log(apply: bool) -> tuple[int, int]:
    """Return (kept, dropped). Rewrites the log atomically when *apply*."""
    if not LIFECYCLE_LOG.exists():
        print(f"  {LIFECYCLE_LOG} — missing, skip")
        return (0, 0)

    kept_lines: list[str] = []
    dropped = 0
    for line in LIFECYCLE_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            kept_lines.append(line)  # never drop what we can't parse
            continue
        if _is_fixture_event(d):
            dropped += 1
        else:
            kept_lines.append(line)

    if apply and dropped:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = LIFECYCLE_LOG.with_suffix(f".log.bak-{stamp}")
        shutil.copy2(LIFECYCLE_LOG, backup)
        tmp = LIFECYCLE_LOG.with_suffix(".log.tmp")
        tmp.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")
        tmp.replace(LIFECYCLE_LOG)
        print(f"  backup: {backup.name}")
    return (len(kept_lines), dropped)


def clean_link_registry(apply: bool) -> int:
    """Return number of fixture edges (deleted when *apply*)."""
    if not LINK_REGISTRY.exists():
        print(f"  {LINK_REGISTRY} — missing, skip")
        return 0

    conn = sqlite3.connect(str(LINK_REGISTRY))
    try:
        rows = conn.execute(
            f"SELECT link_id, source_id, target_id, link_type FROM entity_links WHERE {_FIXTURE_ID_SQL}"
        ).fetchall()
        for _lid, src, tgt, lt in rows:
            print(f"  edge: {lt}  {src} -> {tgt}")
        if apply and rows:
            link_ids = [r[0] for r in rows]
            qmarks = ",".join("?" * len(link_ids))
            conn.execute(f"DELETE FROM link_history WHERE link_id IN ({qmarks})", link_ids)
            conn.execute(f"DELETE FROM entity_links WHERE {_FIXTURE_ID_SQL}")
            # link_stats rows for fixture entities are orphans now — drop them.
            conn.execute(
                "DELETE FROM link_stats WHERE entity_id LIKE 'test-%' "
                "OR entity_id LIKE 'orphan-%' OR entity_id LIKE 'verify-%' "
                "OR entity_id IN ('only-in-links', 'also-in-links')"
            )
            conn.commit()
        return len(rows)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[cleanup_memory_test_pollution] mode={mode}")

    print("lifecycle log:")
    kept, dropped = clean_lifecycle_log(args.apply)
    print(f"  kept={kept} dropped={dropped}")

    print("link registry:")
    n_edges = clean_link_registry(args.apply)
    print(f"  fixture edges: {n_edges}")

    if not args.apply and (dropped or n_edges):
        print("re-run with --apply to write")
    return 0


if __name__ == "__main__":
    main()
    sys.exit(0)
