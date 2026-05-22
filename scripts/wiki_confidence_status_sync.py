"""Report wiki frontmatter inconsistencies between confidence and status.

Per docs/wiki/SCHEMA.md — promotion rule confidence>=0.8 to remain `active`.
Reports two violation classes:
  - DEMOTE: status=active but confidence<0.8 -> should move to drafts/ or downgrade
  - PROMOTE: status=draft but confidence>=0.8 -> ready for promotion

Read-only by default. With --apply only DEMOTE class is auto-fixed
(status=active -> status=draft). PROMOTE class is always reported, never
auto-moved (requires human review per SCHEMA.md).

Usage:
    python scripts/wiki_confidence_status_sync.py
    python scripts/wiki_confidence_status_sync.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
CONFIDENCE_RE = re.compile(r"^confidence:\s*([0-9.]+)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^status:\s*(\w+)\s*$", re.MULTILINE)
THRESHOLD = 0.8


def scan(wiki_dir: Path) -> tuple[list[tuple[Path, float]], list[tuple[Path, float]]]:
    demote: list[tuple[Path, float]] = []
    promote: list[tuple[Path, float]] = []
    for p in wiki_dir.rglob("*.md"):
        if "archive" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        fm_match = FM_RE.match(text)
        if not fm_match:
            continue
        fm = fm_match.group(1)
        c_match = CONFIDENCE_RE.search(fm)
        s_match = STATUS_RE.search(fm)
        if not c_match or not s_match:
            continue
        try:
            conf = float(c_match.group(1))
        except ValueError:
            continue
        status = s_match.group(1).lower()
        if status == "active" and conf < THRESHOLD:
            demote.append((p, conf))
        elif status == "draft" and conf >= THRESHOLD:
            promote.append((p, conf))
    return demote, promote


def apply_demote(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new_text, n = STATUS_RE.subn("status: draft", text, count=1)
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", type=Path, default=Path("docs/wiki"))
    parser.add_argument("--apply", action="store_true", help="Auto-demote active+lowconf")
    args = parser.parse_args()

    repo_root = Path.cwd()
    wiki_dir = args.wiki_dir if args.wiki_dir.is_absolute() else repo_root / args.wiki_dir
    if not wiki_dir.is_dir():
        print(f"Not a directory: {wiki_dir}", file=sys.stderr)
        return 1

    demote, promote = scan(wiki_dir)

    print(f"DEMOTE (status=active, confidence<{THRESHOLD}): {len(demote)}")
    for p, c in demote[:20]:
        print(f"  {c:.2f}  {p.relative_to(repo_root)}")
    if len(demote) > 20:
        print(f"  ... and {len(demote) - 20} more")

    print(f"\nPROMOTE (status=draft, confidence>={THRESHOLD}): {len(promote)}")
    for p, c in promote[:20]:
        print(f"  {c:.2f}  {p.relative_to(repo_root)}")
    if len(promote) > 20:
        print(f"  ... and {len(promote) - 20} more")

    if args.apply and demote:
        fixed = 0
        for p, _c in demote:
            if apply_demote(p):
                fixed += 1
        print(f"\n[APPLIED] demoted {fixed} files (status: active -> draft)")
    elif demote:
        print("\nRun with --apply to demote them")

    return 0


if __name__ == "__main__":
    sys.exit(main())
