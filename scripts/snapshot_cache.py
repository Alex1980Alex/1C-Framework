#!/usr/bin/env python3
"""RocksDB-style hard-link snapshots для .claude/cache/ (§15 P2 P11).

Per roadmap 260523 §15.2 item 14 + §15.6 P2 item 11. Implements
RocksDB's `CreateCheckpoint(dir)` pattern in Python: hard-links create
near-instant point-in-time snapshots без copy overhead, providing
rollback safety net против accidental cache corruption / NTFS recovery
incidents (memory `feedback_post_merge_baseline_resync_protocol` —
2026-04-26 lost 18 memory files).

Why hard links (vs copy):
- Same-filesystem: O(1) per file (just adds dentry, no block copy)
- Storage: shared inodes — N snapshots ≈ 1× size on disk
- Read-only-ish: editing source file does NOT propagate to snapshot
  (most editors write new inode via "save as temp + atomic rename")
- Editing through truncate-in-place WOULD affect both — common editors
  (vscode, vim, edit, write) use temp-file pattern → safe in practice

Fallback: `shutil.copy2` если `os.link` fails (cross-volume / ACL issues).

Storage layout:
    .claude/cache/                   ← source
    .claude/cache/snapshots/
        2026-05-25T11-30-00/         ← snapshot id (ISO8601-safe)
            <mirror of cache/ minus snapshots/>

CLI:
    python scripts/snapshot_cache.py --snapshot         # create new
    python scripts/snapshot_cache.py --list             # show all
    python scripts/snapshot_cache.py --restore <id>     # rollback
    python scripts/snapshot_cache.py --gc 30 [--dry-run]
    python scripts/snapshot_cache.py --diff <id>        # vs current
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
SNAPSHOTS_DIR = CACHE_DIR / "snapshots"

# Exclude patterns — files/dirs we don't snapshot.
EXCLUDE_NAMES = {"snapshots"}  # never recurse into our own snapshots dir
EXCLUDE_SUFFIXES = {".lock", ".tmp"}  # transient files


def _iter_source_files() -> list[Path]:
    """Walk CACHE_DIR, return all regular files to snapshot.

    Excludes:
    - snapshots/ directory (don't recurse into our own output)
    - *.lock / *.tmp transient files
    - symlinks (security: avoid following potentially-rogue links)
    """
    out: list[Path] = []
    if not CACHE_DIR.exists():
        return out
    for root, dirs, files in os.walk(CACHE_DIR):
        # Mutate dirs in place to skip recursion into excluded dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
        for name in files:
            p = Path(root) / name
            if p.suffix in EXCLUDE_SUFFIXES:
                continue
            if p.is_symlink():
                continue
            if not p.is_file():
                continue
            out.append(p)
    return out


def _make_snapshot_id() -> str:
    """Generate ISO8601-derived snapshot id safe for filesystem.

    Format: `YYYY-MM-DDTHH-MM-SS` (replaces `:` with `-` for Windows compat).
    """
    return dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _link_or_copy(src: Path, dst: Path) -> str:
    """Hard-link src→dst. Fallback to copy2 if cross-volume. Returns mode."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "link"
    except OSError:
        # Cross-volume or filesystem doesn't support hard-link
        try:
            shutil.copy2(src, dst)
            return "copy"
        except OSError:
            return "fail"


def cmd_snapshot(dry_run: bool) -> int:
    """Create one snapshot."""
    if not CACHE_DIR.exists():
        print(f"No cache dir at {CACHE_DIR}", file=sys.stderr)
        return 1

    snap_id = _make_snapshot_id()
    target = SNAPSHOTS_DIR / snap_id
    if target.exists():
        print(f"Snapshot id collision: {snap_id} exists. Wait 1s and retry.", file=sys.stderr)
        return 1

    files = _iter_source_files()
    print(f"Snapshot id: {snap_id}")
    print(f"Source files: {len(files)}")
    print(f"Target: {target}")
    if dry_run:
        print("(dry-run — no writes)")
        return 0

    counts = {"link": 0, "copy": 0, "fail": 0}
    for src in files:
        rel = src.relative_to(CACHE_DIR)
        dst = target / rel
        mode = _link_or_copy(src, dst)
        counts[mode] += 1

    print(f"Snapshot complete: {counts['link']} hard-link, "
          f"{counts['copy']} copy fallback, {counts['fail']} failed")
    return 0 if counts["fail"] == 0 else 1


def _dir_size(path: Path) -> int:
    """Recursive bytes total. Hard-links count multiple times here
    (showing logical size), но on-disk usage значительно меньше."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def cmd_list() -> int:
    """List all snapshots."""
    if not SNAPSHOTS_DIR.exists():
        print("No snapshots stored.")
        return 0
    snaps = sorted(p for p in SNAPSHOTS_DIR.iterdir() if p.is_dir())
    if not snaps:
        print("No snapshots stored.")
        return 0

    now = dt.datetime.now()
    print(f"{'snapshot_id':<24} {'age':>10}  {'size_bytes':>12}  files")
    print("-" * 75)
    for snap in snaps:
        try:
            mtime = dt.datetime.fromtimestamp(snap.stat().st_mtime)
            age = now - mtime
            age_str = f"{age.days}d {age.seconds // 3600}h"
        except OSError:
            age_str = "?"
        size = _dir_size(snap)
        nfiles = sum(1 for _ in snap.rglob("*") if _.is_file())
        print(f"{snap.name:<24} {age_str:>10}  {size:>12,}  {nfiles}")
    print(f"\nTotal: {len(snaps)} snapshots")
    return 0


def cmd_restore(snap_id: str, dry_run: bool) -> int:
    """Restore cache state from snapshot (overwrites current)."""
    src = SNAPSHOTS_DIR / snap_id
    if not src.exists() or not src.is_dir():
        print(f"Snapshot not found: {snap_id}", file=sys.stderr)
        print(f"List available via: --list", file=sys.stderr)
        return 1

    files = []
    for root, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
        for n in names:
            files.append(Path(root) / n)

    print(f"Snapshot: {snap_id}")
    print(f"Files to restore: {len(files)}")
    if dry_run:
        for f in files[:10]:
            print(f"  {f.relative_to(src)}")
        if len(files) > 10:
            print(f"  ... +{len(files) - 10} more")
        print("(dry-run — no writes)")
        return 0

    # Before restore — create rescue snapshot of current state.
    print("Creating rescue snapshot of current state first...")
    rescue_rc = cmd_snapshot(dry_run=False)
    if rescue_rc != 0:
        print("Rescue snapshot failed — aborting restore for safety.", file=sys.stderr)
        return 2

    counts = {"link": 0, "copy": 0, "fail": 0}
    for f in files:
        rel = f.relative_to(src)
        target = CACHE_DIR / rel
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        mode = _link_or_copy(f, target)
        counts[mode] += 1

    print(f"Restore complete: {counts['link']} hard-link, "
          f"{counts['copy']} copy fallback, {counts['fail']} failed")
    return 0 if counts["fail"] == 0 else 1


def cmd_gc(days: int, dry_run: bool) -> int:
    """Delete snapshots older than `days`."""
    if days <= 0:
        print("ERROR: --gc requires positive integer", file=sys.stderr)
        return 1
    if not SNAPSHOTS_DIR.exists():
        print("No snapshots dir.")
        return 0

    cutoff = dt.datetime.now().timestamp() - days * 86400
    deleted = 0
    for snap in SNAPSHOTS_DIR.iterdir():
        if not snap.is_dir():
            continue
        try:
            mtime = snap.stat().st_mtime
            if mtime < cutoff:
                if dry_run:
                    print(f"would delete: {snap.name}")
                else:
                    shutil.rmtree(snap, ignore_errors=True)
                    print(f"deleted: {snap.name}")
                deleted += 1
        except OSError:
            continue
    verb = "would delete" if dry_run else "deleted"
    print(f"\n{verb}: {deleted} snapshots older than {days} days")
    return 0


def cmd_diff(snap_id: str) -> int:
    """Show file-count diff between snapshot and current cache."""
    src = SNAPSHOTS_DIR / snap_id
    if not src.exists():
        print(f"Snapshot not found: {snap_id}", file=sys.stderr)
        return 1

    def _rel_set(root: Path) -> set[str]:
        seen: set[str] = set()
        for r, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
            for n in files:
                p = Path(r) / n
                if p.suffix in EXCLUDE_SUFFIXES:
                    continue
                if p.is_symlink():
                    continue
                seen.add(str(p.relative_to(root)).replace("\\", "/"))
        return seen

    snap_files = _rel_set(src)
    cur_files = _rel_set(CACHE_DIR)
    added = cur_files - snap_files
    removed = snap_files - cur_files
    common = snap_files & cur_files

    print(f"Snapshot:  {len(snap_files)} files")
    print(f"Current:   {len(cur_files)} files")
    print(f"Added:     {len(added)} (in current, not snap)")
    print(f"Removed:   {len(removed)} (in snap, not current)")
    print(f"Common:    {len(common)} (potentially modified — see hashes)")
    if added:
        print("\nAdded (top 5):")
        for f in sorted(added)[:5]:
            print(f"  + {f}")
    if removed:
        print("\nRemoved (top 5):")
        for f in sorted(removed)[:5]:
            print(f"  - {f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot", action="store_true",
                       help="Create new snapshot of .claude/cache/")
    group.add_argument("--list", action="store_true",
                       help="List all snapshots")
    group.add_argument("--restore", metavar="ID",
                       help="Restore cache from snapshot id")
    group.add_argument("--gc", type=int, metavar="DAYS",
                       help="Delete snapshots older than N days")
    group.add_argument("--diff", metavar="ID",
                       help="Show file-set diff (snap vs current)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview, no writes")
    args = parser.parse_args()

    if args.snapshot:
        return cmd_snapshot(dry_run=args.dry_run)
    if args.list:
        return cmd_list()
    if args.restore:
        return cmd_restore(args.restore, dry_run=args.dry_run)
    if args.gc is not None:
        return cmd_gc(args.gc, dry_run=args.dry_run)
    if args.diff:
        return cmd_diff(args.diff)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
