"""Apply wiki entity merge candidates produced by wiki_entity_normalize.py.

Reads JSONL from stdin (one group per line, as emitted by
wiki_entity_normalize.py --json).  For each group:

1. Picks the canonical file (shortest stem, then lexicographically first).
2. Moves non-canonical files to the archive directory via git mv (tracked)
   or os.rename (untracked).
3. Rewrites [[old-stem]] wikilinks in all .md files under docs/wiki/
   (excluding archive/) to point at the canonical stem.

Usage:

    python scripts/wiki_entity_merge_apply.py --help
    python scripts/wiki_entity_merge_apply.py < tmp/merge-candidates.jsonl
    python scripts/wiki_entity_merge_apply.py --apply < tmp/merge-candidates.jsonl
    python scripts/wiki_entity_merge_apply.py --apply --limit 5 < tmp/merge-candidates.jsonl
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTITIES_DIR = PROJECT_ROOT / "docs" / "wiki" / "entities"
WIKI_DIR = PROJECT_ROOT / "docs" / "wiki"
ARCHIVE_DIR = ENTITIES_DIR / "archive" / "2026-05" / "merged-entities"


def _git_is_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def _git_mv(src: Path, dst: Path) -> None:
    result = subprocess.run(
        ["git", "mv", str(src), str(dst)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git mv failed: {result.stderr.strip()}")


def pick_canonical(paths: list[Path]) -> Path:
    return min(paths, key=lambda p: (len(p.stem), p.stem))


def _wiki_md_files() -> list[Path]:
    result = []
    for p in WIKI_DIR.rglob("*.md"):
        if "archive" in p.parts:
            continue
        result.append(p)
    return result


def rewrite_backlinks(old_stem: str, new_stem: str, dry_run: bool) -> int:
    old_link = f"[[{old_stem}]]"
    new_link = f"[[{new_stem}]]"
    count = 0
    for md_file in _wiki_md_files():
        try:
            raw = md_file.read_bytes()
            text = raw.decode("utf-8-sig")
        except Exception as exc:
            print(f"  WARN: cannot read {md_file}: {exc}", file=sys.stderr)
            continue
        if old_link not in text:
            continue
        new_text = text.replace(old_link, new_link)
        if new_text != text:
            if not dry_run:
                md_file.write_text(new_text, encoding="utf-8", newline="\n")
            count += 1
    return count


def process_group(group: dict, dry_run: bool) -> dict:
    raw_files: list[str] = group["files"]
    paths = [PROJECT_ROOT / f for f in raw_files]
    existing = [p for p in paths if p.exists()]
    if not existing:
        return {"status": "skip_all_missing", "files_archived": 0, "backlinks": 0}
    canonical = pick_canonical(existing)
    non_canonical = [p for p in existing if p != canonical]
    print(f"  canonical : {canonical.name}")
    files_archived = 0
    total_backlinks = 0
    for src in non_canonical:
        dst = ARCHIVE_DIR / src.name
        if dst.exists():
            print(f"  SKIP (already archived): {src.name}")
            continue
        bl_count = rewrite_backlinks(src.stem, canonical.stem, dry_run)
        if bl_count:
            print(f"    backlinks rewritten ({src.stem} -> {canonical.stem}): {bl_count} file(s)")
        total_backlinks += bl_count
        print(f"  archive   : {src.name} -> archive/2026-05/merged-entities/")
        if not dry_run:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            if _git_is_tracked(src):
                _git_mv(src, dst)
            else:
                os.rename(src, dst)
            files_archived += 1
        else:
            files_archived += 1
    return {"status": "ok", "canonical": canonical.name, "files_archived": files_archived, "backlinks": total_backlinks}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--apply", action="store_true", default=False,
        help="Actually mutate files. Without this flag the script runs in dry-run mode.")
    parser.add_argument("--dry-run", action="store_true", default=False,
        help="Explicit dry-run flag (default behaviour; alias for omitting --apply).")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
        help="Process at most N groups.")
    parser.add_argument("--archive-dir", type=Path, default=None, metavar="PATH",
        help="Override archive directory.")
    args = parser.parse_args()

    dry_run = not args.apply

    global ARCHIVE_DIR
    if args.archive_dir:
        if args.archive_dir.is_absolute():
            ARCHIVE_DIR = args.archive_dir
        else:
            ARCHIVE_DIR = PROJECT_ROOT / args.archive_dir

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.stdin.encoding and sys.stdin.encoding.lower() != "utf-8":
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

    mode_label = "DRY-RUN" if dry_run else "APPLY"
    print(f"wiki_entity_merge_apply -- mode: {mode_label}")
    if args.limit:
        print(f"  limit: {args.limit} group(s)")
    print("")

    groups_processed = 0
    files_archived = 0
    backlinks_total = 0
    skipped = 0

    for lineno, line in enumerate(sys.stdin, 1):
        line = line.strip()
        if not line:
            continue
        if args.limit is not None and groups_processed >= args.limit:
            break
        try:
            group = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"WARN: line {lineno} not valid JSON, skipping: {exc}", file=sys.stderr)
            continue

        lk = group.get("lemma_key")
        nf = len(group["files"])
        print(f"[Group {lineno}] lemma={lk}  files={nf}")
        result = process_group(group, dry_run=dry_run)

        if result["status"].startswith("skip"):
            skipped += 1
            print(f"  -> skipped ({result['status']})")
        else:
            groups_processed += 1
            files_archived += result["files_archived"]
            backlinks_total += result["backlinks"]
        print("")

    summary = {
        "mode": mode_label,
        "groups_processed": groups_processed,
        "groups_skipped": skipped,
        "files_archived": files_archived,
        "backlink_rewrites_count": backlinks_total,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
