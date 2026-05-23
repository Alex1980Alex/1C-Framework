"""Identify wiki entities that share a normalized lemma key.

Scans docs/wiki/entities/*.md, lemmatizes each stem-word via pymorphy3,
groups by lemma key, and reports candidates for merge. Read-only — does
not modify any files.

Usage:
    pip install pymorphy3>=2.0
    python scripts/wiki_entity_normalize.py
    python scripts/wiki_entity_normalize.py --json > merge-candidates.jsonl
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymorphy3

WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


def lemma_key(stem: str, morph: pymorphy3.MorphAnalyzer) -> tuple[str, ...]:
    """Tuple of sorted lemmas — order-insensitive identity for entity stem."""
    words = WORD_RE.findall(stem.lower())
    lemmas = [morph.parse(w)[0].normal_form for w in words]
    return tuple(sorted(lemmas))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entities-dir", type=Path, default=Path("docs/wiki/entities"))
    parser.add_argument("--json", action="store_true", help="JSONL output (one group per line)")
    args = parser.parse_args()

    # Force UTF-8 on Windows console where default is cp1251.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    entities_dir = (
        args.entities_dir if args.entities_dir.is_absolute() else Path.cwd() / args.entities_dir
    )
    if not entities_dir.is_dir():
        print(f"Not a directory: {entities_dir}", file=sys.stderr)
        return 1

    morph = pymorphy3.MorphAnalyzer()

    groups: dict[tuple[str, ...], list[Path]] = defaultdict(list)
    for p in entities_dir.rglob("*.md"):
        if "archive" in p.parts:
            continue
        groups[lemma_key(p.stem, morph)].append(p)

    merge_candidates = {k: v for k, v in groups.items() if len(v) > 1}

    if args.json:
        for key, paths in merge_candidates.items():
            print(
                json.dumps(
                    {
                        "lemma_key": list(key),
                        "files": [str(p.relative_to(Path.cwd())) for p in paths],
                    },
                    ensure_ascii=False,
                )
            )
        return 0

    print(f"Entities scanned: {sum(len(v) for v in groups.values())}")
    print(f"Unique lemma keys: {len(groups)}")
    print(f"Merge candidates: {len(merge_candidates)} groups")
    print("")
    for key, paths in sorted(merge_candidates.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{' '.join(key)}]  ×{len(paths)}")
        for p in paths:
            print(f"    - {p.relative_to(Path.cwd())}")
        print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
