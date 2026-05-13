"""Cleanup wiki/entities/: archive or delete noise-entity stub files.

Closes false-positive NER output (dates, numbers, hashes, single chars, versions).
Companion to _is_noise_entity_name() in src/pdf_framework/indexing/wiki_exporter.py.

Usage:
    python scripts/wiki_cleanup_noise_entities.py --dry-run
    python scripts/wiki_cleanup_noise_entities.py --archive
    python scripts/wiki_cleanup_noise_entities.py --delete   (irreversible)
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WIKI_DIR = Path("docs/wiki/entities")

# Sync with src/pdf_framework/indexing/wiki_exporter.py:_NOISE_RE
# Version strings (8.3.27, v1.2.3) NOT included — valid domain entities.
_NOISE_RE = re.compile(
    r"^(?:\d{8}|\d{6,8}-\d{4,6}|\d{1,4}|[a-zа-я]|[0-9a-f]{16,}|(?:20|19)\d{2})$"
)


def stem_is_noise(stem: str) -> bool:
    return bool(_NOISE_RE.match(stem.strip().lower()))


def collect_noise(wiki_dir: Path) -> list[Path]:
    if not wiki_dir.is_dir():
        return []
    return sorted(p for p in wiki_dir.glob("*.md") if stem_is_noise(p.stem))


def archive_path(repo_root: Path) -> Path:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    target = repo_root / "docs" / "wiki" / "archive" / month / "noise-entities"
    target.mkdir(parents=True, exist_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--archive", action="store_true")
    group.add_argument("--delete", action="store_true")
    parser.add_argument("--wiki-dir", type=Path, default=WIKI_DIR)
    args = parser.parse_args()

    repo_root = Path.cwd()
    wiki_dir = args.wiki_dir if args.wiki_dir.is_absolute() else repo_root / args.wiki_dir

    matches = collect_noise(wiki_dir)
    if not matches:
        print(f"No noise entities found in {wiki_dir}", file=sys.stderr)
        return 0

    print(f"Found {len(matches)} noise entities in {wiki_dir}")
    for p in matches[:10]:
        print(f"  - {p.name}")
    if len(matches) > 10:
        print(f"  ... and {len(matches) - 10} more")

    if args.dry_run:
        print("\n[DRY-RUN] no changes made")
        return 0

    if args.archive:
        target = archive_path(repo_root)
        for p in matches:
            shutil.move(str(p), target / p.name)
        print(f"\n[ARCHIVED] {len(matches)} files -> {target}")
        return 0

    if args.delete:
        for p in matches:
            p.unlink()
        print(f"\n[DELETED] {len(matches)} files")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
