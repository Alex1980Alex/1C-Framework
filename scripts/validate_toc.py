"""Validate framework documentation TOC vs filesystem.

Парсит `00_СОДЕРЖАНИЕ.md`, извлекает все `[link](path)` ссылающиеся на `.md` файлы,
сравнивает с реальным glob `**/*.md` в docs root. Выводит diff:

- declared_missing: декларированы в TOC, но отсутствуют на диске
- orphan_fs:        существуют на диске, но не упомянуты в TOC

Exit codes:
- 0: TOC == filesystem (no diff)
- 1: any diff present
- 2: TOC file or docs root not found

Usage:
    python scripts/validate_toc.py
    python scripts/validate_toc.py --json
    python scripts/validate_toc.py --toc PATH --docs-root PATH
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

DEFAULT_TOC = Path("docs/framework documentation/00_СОДЕРЖАНИЕ.md")
LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")


def parse_toc_links(toc_path: Path, docs_root: Path) -> set[Path]:
    """Извлекает declared `.md` пути из TOC, нормализует относительно `docs_root`.

    Игнорирует:
      - directory-only ссылки (path кончается на `/`)
      - external URLs (http/https/mailto)
      - non-`.md` файлы
    """
    text = toc_path.read_text(encoding="utf-8")
    declared: set[Path] = set()
    for match in LINK_RE.finditer(text):
        href = unquote(match.group("href")).strip()
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if href.endswith("/"):
            continue
        if "#" in href:
            href = href.split("#", 1)[0]
        if not href.lower().endswith(".md"):
            continue
        target = (docs_root / href).resolve()
        try:
            rel = target.relative_to(docs_root.resolve())
        except ValueError:
            continue
        declared.add(rel)
    return declared


def collect_fs_md(docs_root: Path, ignore_filenames: set[str]) -> set[Path]:
    """Собирает все `.md` файлы под `docs_root` (рекурсивно)."""
    out: set[Path] = set()
    for path in docs_root.rglob("*.md"):
        if path.name in ignore_filenames:
            continue
        out.add(path.resolve().relative_to(docs_root.resolve()))
    return out


def main() -> int:
    # Windows console default cp866 чужой для cyrillic путей в text-ветке вывода.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toc", type=Path, default=DEFAULT_TOC, help="Path to TOC file")
    parser.add_argument(
        "--docs-root", type=Path, default=None, help="Docs root (default: TOC parent)"
    )
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output for CI")
    args = parser.parse_args()

    toc_path: Path = args.toc.resolve()
    if not toc_path.is_file():
        print(f"ERROR: TOC not found: {toc_path}", file=sys.stderr)
        return 2

    docs_root: Path = (args.docs_root or toc_path.parent).resolve()
    if not docs_root.is_dir():
        print(f"ERROR: docs root not found: {docs_root}", file=sys.stderr)
        return 2

    ignore_filenames = {toc_path.name}

    declared = parse_toc_links(toc_path, docs_root)
    fs = collect_fs_md(docs_root, ignore_filenames)

    declared_missing = sorted(declared - fs)
    orphan_fs = sorted(fs - declared)

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(Path.cwd()))
        except ValueError:
            return str(p)

    result = {
        "toc": _rel(toc_path),
        "docs_root": _rel(docs_root),
        "declared_count": len(declared),
        "fs_count": len(fs),
        "declared_missing": [str(p).replace("\\", "/") for p in declared_missing],
        "orphan_fs": [str(p).replace("\\", "/") for p in orphan_fs],
    }

    has_diff = bool(declared_missing or orphan_fs)

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"TOC:        {result['toc']}")
        print(f"docs_root:  {result['docs_root']}")
        print(f"Declared:   {result['declared_count']}")
        print(f"FS:         {result['fs_count']}")
        print()
        print(f"Declared missing on disk: {len(declared_missing)}")
        for p in declared_missing:
            print(f"  - {str(p).replace(chr(92), '/')}")
        print()
        print(f"Orphan files (FS but not in TOC): {len(orphan_fs)}")
        for p in orphan_fs:
            print(f"  + {str(p).replace(chr(92), '/')}")

    return 1 if has_diff else 0


if __name__ == "__main__":
    sys.exit(main())
