#!/usr/bin/env python3
"""Backfill the canonical ``content_hash`` onto existing learned_patterns (§26 P0, D0.4).

The §26 cross-store sync uses ``content_hash`` (= ``sha256(content)[:16]``) as the
join key. New writes get it from ``MemoryCube.__post_init__``; pre-existing points
predate the field. This script stamps it onto every point in ``learned_patterns``.

SAFETY (Qdrant payload mutation):
  - **dry-run by default** — prints the plan; ``--apply`` is required to mutate.
  - **backup first** — full snapshot (id + payload + vector) to
    ``data/memory/backups/learned_patterns_<ts>.json`` before any write
    (reuses the dedupe script's backup/restore helpers). ``--no-backup`` opts out.
  - **idempotent** — a point whose stored ``content_hash`` already equals the
    derived key is skipped; re-running is a no-op.
  - **payload-only** — sets a single field; never deletes points or touches vectors.

Usage:
  python scripts/backfill_content_hash.py                # dry-run plan
  python scripts/backfill_content_hash.py --apply        # stamp content_hash
  python scripts/backfill_content_hash.py --apply --no-backup
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = "learned_patterns"

# Reuse the canonical hash + the dedupe script's I/O helpers (single source).
# PROJECT_ROOT makes `scripts.*` importable when run as a CLI; src/ for `memory.*`.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.orchestrator.content_hash import content_key
from scripts.dedupe_learned_patterns import _client, fetch_points, write_backup


def build_plan(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure planner: which points need a content_hash set / corrected."""
    updates: list[dict[str, str]] = []
    already_ok = 0
    empty_content = 0
    for pt in points:
        payload = pt["payload"]
        derived = content_key(payload)
        if not (payload.get("content") or payload.get("description")):
            empty_content += 1
        if payload.get("content_hash") == derived:
            already_ok += 1
            continue
        updates.append({"id": pt["id"], "content_hash": derived})
    return {
        "total": len(points),
        "already_ok": already_ok,
        "to_update": updates,
        "empty_content": empty_content,
    }


def apply_plan(client, plan: dict[str, Any]) -> None:
    for upd in plan["to_update"]:
        client.set_payload(
            collection_name=COLLECTION,
            payload={"content_hash": upd["content_hash"]},
            points=[upd["id"]],
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="backfill content_hash on learned_patterns")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    ap.add_argument("--no-backup", action="store_true", help="skip backup (not recommended)")
    ap.add_argument("--stamp", default=None, help="override backup timestamp (tests)")
    args = ap.parse_args()

    try:
        client = _client()
    except Exception as exc:
        print(f"Qdrant unavailable: {exc}", file=sys.stderr)
        return 1

    points = fetch_points(client)
    plan = build_plan(points)

    print(f"# learned_patterns content_hash backfill (apply={args.apply})")
    print(
        f"total={plan['total']} already_stamped={plan['already_ok']} "
        f"to_update={len(plan['to_update'])} empty_content={plan['empty_content']}"
    )

    if not plan["to_update"]:
        print("-> nothing to do (all points already carry the correct content_hash).")
        return 0

    if not args.apply:
        print("\n-> dry-run; re-run with --apply to execute.")
        return 0

    if not args.no_backup:
        stamp = args.stamp or _timestamp()
        path = write_backup(client, stamp)
        print(f"backup written: {path}")

    apply_plan(client, plan)
    print(f"stamped content_hash on {len(plan['to_update'])} points.")
    return 0


def _timestamp() -> str:
    # Local import keeps the module import-time free of clock reads (test-friendly).
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    raise SystemExit(main())
