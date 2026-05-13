"""Walk docs/wiki/, ensure bidirectional backlinks in frontmatter.

For each [[wikilink]] in a page A, ensures the target page T has [[A]] in its
related: frontmatter list. Idempotent — running twice does NOT duplicate.

Usage:
    python scripts/wiki_backlink_walker.py --dry-run
    python scripts/wiki_backlink_walker.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FM_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:\|[^\]]*)?\]\]")
RELATED_BLOCK_RE = re.compile(
    r"(^related:[ \t]*)\n((?:[ \t]+-[ \t]+.*\n)*)",
    re.MULTILINE,
)
RELATED_EMPTY_RE = re.compile(r"^related:[ \t]*\[\][ \t]*$", re.MULTILINE)


def find_targets(wiki_dir: Path) -> dict[str, Path]:
    """Map stem (lowercase) -> file path. First match wins on collision."""
    index: dict[str, Path] = {}
    for p in wiki_dir.rglob("*.md"):
        if "archive" in p.parts:
            continue
        index.setdefault(p.stem.lower(), p)
    return index


def extract_wikilinks(body: str) -> set[str]:
    body_no_code = CODE_FENCE_RE.sub("", body)
    return {m.lower() for m in WIKILINK_RE.findall(body_no_code)}


def has_backlink(frontmatter: str, source_stem: str) -> bool:
    """True if related: already contains [[source_stem]] in any common quoting."""
    needle = f"[[{source_stem}]]"
    block = RELATED_BLOCK_RE.search(frontmatter)
    if not block:
        return False
    return needle in block.group(2)


def add_backlink(frontmatter: str, source_stem: str) -> str:
    new_line = f"  - '[[{source_stem}]]'\n"
    empty_match = RELATED_EMPTY_RE.search(frontmatter)
    if empty_match:
        return RELATED_EMPTY_RE.sub("related:\n" + new_line.rstrip("\n"), frontmatter, count=1)
    block_match = RELATED_BLOCK_RE.search(frontmatter)
    if block_match:
        existing = block_match.group(2)
        replacement = block_match.group(1) + "\n" + new_line + existing
        return frontmatter[:block_match.start()] + replacement + frontmatter[block_match.end():]
    return frontmatter.rstrip() + "\nrelated:\n" + new_line.rstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-dir", type=Path, default=Path("docs/wiki"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd()
    wiki_dir = args.wiki_dir if args.wiki_dir.is_absolute() else repo_root / args.wiki_dir
    if not wiki_dir.is_dir():
        print(f"Not a directory: {wiki_dir}", file=sys.stderr)
        return 1

    targets = find_targets(wiki_dir)

    files_scanned = 0
    wikilinks_total = 0
    backlinks_added = 0
    orphans: dict[str, int] = {}
    pending_writes: dict[Path, str] = {}

    for src in wiki_dir.rglob("*.md"):
        if "archive" in src.parts:
            continue
        text = src.read_text(encoding="utf-8")
        fm_match = FM_RE.match(text)
        if not fm_match:
            continue
        files_scanned += 1
        body = fm_match.group(2)
        stems = extract_wikilinks(body)
        wikilinks_total += len(stems)

        for stem in stems:
            target = targets.get(stem)
            if target is None:
                orphans[stem] = orphans.get(stem, 0) + 1
                continue
            if target == src:
                continue

            current = pending_writes.get(target)
            if current is None:
                current = target.read_text(encoding="utf-8")
            t_match = FM_RE.match(current)
            if not t_match:
                continue
            t_fm, t_body = t_match.group(1), t_match.group(2)
            if has_backlink(t_fm, src.stem):
                continue
            new_fm = add_backlink(t_fm, src.stem)
            pending_writes[target] = f"---\n{new_fm}\n---\n{t_body}"
            backlinks_added += 1

    if not args.dry_run:
        for path, content in pending_writes.items():
            path.write_text(content, encoding="utf-8")

    print(f"Files scanned: {files_scanned}")
    print(f"Wikilinks total: {wikilinks_total}")
    print(f"Backlinks {'would be added' if args.dry_run else 'added'}: {backlinks_added}")
    print(f"Files {'would be updated' if args.dry_run else 'updated'}: {len(pending_writes)}")
    if orphans:
        print(f"Orphan targets: {len(orphans)} unique")
        for stem in list(orphans.keys())[:10]:
            print(f"  - {stem}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
