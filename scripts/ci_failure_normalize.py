#!/usr/bin/env python3
"""Re-normalize ci-failures.jsonl with updated _hash (Phase 1 fix)."""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL = PROJECT_ROOT / ".claude" / "cache" / "ci-failures.jsonl"
BACKUP = JSONL.with_suffix(".jsonl.bak")


def _load_cfc():
    spec = importlib.util.spec_from_file_location(
        "cfc", str(PROJECT_ROOT / "scripts" / "ci_failure_cache.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rehash_entries(entries: list[dict], cfc) -> int:
    rehashed = 0
    for e in entries:
        if e.get("event_type"):
            continue
        new_hash = cfc._hash(e.get("error_first_line", ""))
        if new_hash != e.get("error_hash"):
            e["error_hash"] = new_hash
            rehashed += 1
    return rehashed


def _print_top(entries: list[dict], counter, label: str, n: int = 5) -> None:
    print(f"\nTop {n} {label}:")
    for h, count in counter.most_common(n):
        sample = next((e for e in entries if e.get("error_hash") == h), {})
        line = (sample.get("error_first_line") or "")[:100]
        print(f"  [{count}x] {h}  {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not JSONL.exists():
        print(f"ERROR: {JSONL} not found", file=sys.stderr)
        return 1

    cfc = _load_cfc()
    entries = []
    for ln in JSONL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            parsed = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    print(f"Loaded {len(entries)} entries")

    old = collections.Counter(e.get("error_hash", "?") for e in entries)
    rehashed = _rehash_entries(entries, cfc)
    new = collections.Counter(e.get("error_hash", "?") for e in entries)

    print(f"Rehashed: {rehashed}/{len(entries)}")
    print(f"Unique hashes: {len(old)} -> {len(new)}")
    _print_top(entries, new, "NEW recurring hashes")

    if args.dry_run:
        print("\n[dry-run] no changes written")
        return 0

    shutil.copy2(JSONL, BACKUP)
    print(f"\nBackup saved: {BACKUP}")
    tmp = JSONL.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(JSONL)  # atomic on POSIX, near-atomic on Windows NTFS
    print(f"Rewrote: {JSONL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
