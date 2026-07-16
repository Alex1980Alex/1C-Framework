#!/usr/bin/env python3
"""Re-stamp drifted ``pattern_type`` values onto the canonical enum (roadmap 260716 P0.4).

Context: 8+ producers write ``learned_patterns``, but until P0.3 only ``save_pattern``
validated the type. Free-form values ('requirements', 'error-fix', '1c-bsl', ...) and
even missing keys accumulated; a strict reader then choked on them and took down whole
search responses (incident 2026-07-16). P0.1/P0.2 made readers coerce and P0.3 made
writers normalize — this script cleans the tail so stored data matches the contract.

Scope is deliberately narrow — ONE field, in two stores:
  * Qdrant ``learned_patterns`` — payload ``pattern_type`` (+ provenance in
    ``metadata.original_pattern_type``);
  * skill-learning silos (``patterns.jsonl``, ``pending_patterns.jsonl``) — the same
    field, because the Stop-harvest lifts these records into Qdrant.
Neighbouring data defects have their own vetted tools — do NOT reimplement them here:
  * missing ``content_hash``  → ``scripts/backfill_content_hash.py``
  * byte-identical duplicates → ``scripts/dedupe_learned_patterns.py``

SAFETY:
  - **dry-run by default** — prints the plan; ``--apply`` is required to mutate.
  - **backup first** — every changed point's previous ``pattern_type``/``metadata`` is
    written to ``data/memory/backups/pattern_types_<ts>.json`` (a precise inverse of
    what this script writes). Restore with ``--restore <file> --apply``.
  - JSONL silos are rewritten atomically (tmp + os.replace) after a ``.bak`` copy.
  - Coercion goes through the ONE alias table (``vector_memory.models``): this script
    can never invent a mapping the readers/writers do not share.

Usage:
  python scripts/migrate_pattern_types.py                    # dry-run plan
  python scripts/migrate_pattern_types.py --apply
  python scripts/migrate_pattern_types.py --apply --qdrant-only
  python scripts/migrate_pattern_types.py --restore data/memory/backups/pattern_types_<ts>.json --apply
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = os.environ.get("LEARNING_COLLECTION_NAME", "learned_patterns")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
BACKUP_DIR = PROJECT_ROOT / "data" / "memory" / "backups"
SILOS = (
    PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl",
    PROJECT_ROOT / "data" / "skill_learning" / "pending_patterns.jsonl",
)

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from memory.vector_memory.models import normalize_pattern_type


def _client() -> Any:
    from qdrant_client import QdrantClient

    return QdrantClient(url=QDRANT_URL, timeout=60)


def plan_point(payload: dict[str, Any]) -> tuple[str, str | None] | None:
    """Return (canonical, original) when the stored value needs re-stamping, else None.

    A point already carrying a canonical value is untouched — the migration is
    idempotent, so re-running it is a no-op.
    """
    stored = payload.get("pattern_type")
    canonical, original = normalize_pattern_type(stored)
    return (canonical, original) if stored != canonical else None


def scan_qdrant(client: Any) -> list[dict[str, Any]]:
    """Collect the migration plan for every drifted point in the collection."""
    changes: list[dict[str, Any]] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            planned = plan_point(payload)
            if planned is None:
                continue
            canonical, original = planned
            changes.append(
                {
                    "id": str(p.id),
                    "old_pattern_type": payload.get("pattern_type"),
                    "new_pattern_type": canonical,
                    "original": original,
                    "old_metadata": payload.get("metadata") or {},
                    "name": (payload.get("name") or "")[:60],
                }
            )
        if offset is None:
            break
    return changes


def apply_qdrant(client: Any, changes: list[dict[str, Any]]) -> int:
    """Write the canonical type + provenance. set_payload replaces named keys only."""
    for ch in changes:
        metadata = dict(ch["old_metadata"])
        if ch["original"]:
            metadata["original_pattern_type"] = ch["original"]
        client.set_payload(
            collection_name=COLLECTION,
            payload={"pattern_type": ch["new_pattern_type"], "metadata": metadata},
            points=[ch["id"]],
        )
    return len(changes)


def scan_silo(path: Path) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return (entries, changes) for a JSONL silo.

    `entries` holds EVERY line: parsed dicts plus, verbatim, anything this script
    does not understand (unparsable JSON, or valid JSON that is not an object).
    `write_silo` echoes those back untouched — a type migration must never be a
    silent line-dropper. Non-dict entries are also skipped before `plan_point`,
    which would otherwise raise on `.get` outside the caller's try.
    """
    entries: list[Any] = []
    changes: list[dict[str, Any]] = []
    if not path.exists():
        return entries, changes
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            entries.append(line)  # opaque: preserved verbatim
            continue
        if not isinstance(rec, dict):
            entries.append(line)
            continue
        entries.append(rec)
        planned = plan_point(rec)
        if planned is None:
            continue
        canonical, original = planned
        changes.append(
            {
                "pattern_id": rec.get("pattern_id"),
                "old_pattern_type": rec.get("pattern_type"),
                "new_pattern_type": canonical,
                "original": original,
            }
        )
        rec["pattern_type"] = canonical
        if original:
            meta = dict(rec.get("metadata") or {})
            meta["original_pattern_type"] = original
            rec["metadata"] = meta
    return entries, changes


def write_silo(path: Path, entries: list[Any]) -> None:
    """Atomic rewrite (tmp + os.replace) after a .bak snapshot — kill-safe.

    ⚠ Read-modify-write of the WHOLE file: a concurrent append (Stop-harvest,
    capture_pattern, route_and_save) landing between scan_silo and here is lost —
    run this without live sessions. `.bak` is the recovery path for the silos;
    `--restore` covers Qdrant only.
    """
    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for entry in entries:
            # str = a line we did not parse; echo it byte-for-byte.
            f.write(
                (entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)) + "\n"
            )
    os.replace(tmp, path)


def restore(path: Path, apply: bool) -> int:
    """Put back the pattern_type/metadata captured in a backup file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("qdrant", [])
    print(f"restore: {len(entries)} point(s) from {path}")
    if not apply:
        print("dry-run — pass --apply to write")
        return 0
    client = _client()
    for ch in entries:
        client.set_payload(
            collection_name=COLLECTION,
            payload={"pattern_type": ch["old_pattern_type"], "metadata": ch["old_metadata"]},
            points=[ch["id"]],
        )
    print(f"restored {len(entries)} point(s)")
    return len(entries)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--qdrant-only", action="store_true")
    ap.add_argument("--silo-only", action="store_true")
    ap.add_argument("--restore", metavar="FILE", help="restore pattern_type from a backup file")
    args = ap.parse_args()

    if args.restore:
        restore(Path(args.restore), args.apply)
        return 0

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    qdrant_changes: list[dict[str, Any]] = []
    silo_plans: list[tuple[Path, list[Any], list[dict[str, Any]]]] = []

    if not args.silo_only:
        client = _client()
        qdrant_changes = scan_qdrant(client)
        print(f"\n=== Qdrant {COLLECTION}: {len(qdrant_changes)} point(s) to re-stamp ===")
        for ch in qdrant_changes:
            print(
                f"  {ch['id'][:8]}  {ch['old_pattern_type']!r:28} -> {ch['new_pattern_type']:24} {ch['name']}"
            )

    if not args.qdrant_only:
        for silo in SILOS:
            entries, changes = scan_silo(silo)
            silo_plans.append((silo, entries, changes))
            print(f"\n=== {silo.name}: {len(changes)} of {len(entries)} record(s) to re-stamp ===")
            for ch in changes:
                print(f"  {ch['old_pattern_type']!r:28} -> {ch['new_pattern_type']}")

    total = len(qdrant_changes) + sum(len(c) for _, _, c in silo_plans)
    if total == 0:
        print("\nNothing to migrate — stored types already canonical.")
        return 0
    if not args.apply:
        print(f"\nDRY-RUN: {total} change(s) planned. Re-run with --apply to write.")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f"pattern_types_{ts}.json"
    backup.write_text(
        json.dumps(
            {"qdrant": qdrant_changes, "collection": COLLECTION}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    print(f"\nbackup -> {backup}")

    if qdrant_changes:
        print(f"qdrant: re-stamped {apply_qdrant(_client(), qdrant_changes)} point(s)")
    for silo, entries, changes in silo_plans:
        if changes:
            write_silo(silo, entries)
            print(f"{silo.name}: re-stamped {len(changes)} record(s) (.bak kept)")

    print("\nDone. Reminder: surfacing cache keys off the confidence epoch — patterns")
    print("re-rank on the next read; no /mcp reconnect needed for DATA changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
