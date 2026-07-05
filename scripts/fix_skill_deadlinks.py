"""Audit 260705 skills — авто-ремедиация битых markdown-ссылок в SKILL.md.

Класс `project_docs_renumbering_broke_enforcement`: перенумерация глав
(`16_ПОДКЛЮЧЕНИЕ_1С/` → `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/` и т.п.) массово
ломает относительные ссылки из скиллов. Инструмент строит индекс имён .md по
релевантным деревьям и переразрешает каждую битую ссылку по basename:

  - ровно 1 кандидат → переписать ссылку на корректный относительный путь
  - несколько кандидатов → отобрать по совпадению числового префикса главы,
    иначе пометить ambiguous (не трогать)
  - 0 кандидатов → dead (удалённая глава/скилл) — отчёт, ручное решение
  - placeholder (`path/to/`, `file.md`, `path.md`) → skip (шаблонные примеры)

Dry-run по умолчанию; ``--apply`` пишет. Пути с пробелами/кириллицей — url-quote
сохраняется как в оригинале (пробел → %20).

Usage:
  python scripts/fix_skill_deadlinks.py               # отчёт (dry-run)
  python scripts/fix_skill_deadlinks.py --apply        # применить
  python scripts/fix_skill_deadlinks.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# деревья, по которым ищем цель ссылки (без submodules/worktree/node_modules)
_SEARCH_TREES = [
    "docs/framework documentation",
    "docs/roadmap",
    "docs/wiki",
    "docs/analysis",
    ".claude/skills",
    ".claude/agents",
    "openspec",
    "scripts",
    "src",
    "tests",
]

_LINK_RE = re.compile(r"(\]\()([^)#\s]+\.md)((?:#[^)]*)?\))")
_PLACEHOLDER = re.compile(r"(^|/)(path\.md|file\.md)$|path/to/")
_CHAPTER_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)")


def build_index() -> dict[str, list[Path]]:
    """basename(.md) -> [абсолютные пути] по релевантным деревьям."""
    index: dict[str, list[Path]] = defaultdict(list)
    for tree in _SEARCH_TREES:
        root = PROJECT_ROOT / tree
        if not root.exists():
            continue
        for md in root.rglob("*.md"):
            sp = str(md)
            if "worktree" in sp or f"{os.sep}.git{os.sep}" in sp:
                continue
            index[md.name].append(md)
    return index


def _pick(base: str, candidates: list[Path]) -> Path | None:
    """Определить единственный корректный кандидат.

    1 кандидат → он. Несколько → предпочесть совпадение числового префикса главы
    (`16.6_...` → путь, содержащий `16.6`); иначе None (ambiguous, не трогаем).
    """
    if len(candidates) == 1:
        return candidates[0]
    m = _CHAPTER_PREFIX.match(base)
    if m:
        prefix = m.group(1)
        pref_hits = [c for c in candidates if prefix in c.name]
        if len(pref_hits) == 1:
            return pref_hits[0]
    return None


def _relpath(src_md: Path, target: Path) -> str:
    """POSIX-относительный путь от каталога src_md к target.

    Конвенция репо: кириллица в ссылках — сырая (читаемая), кодируется ТОЛЬКО
    пробел → %20 (как `docs/framework%20documentation/...`). Полный url-quote
    сделал бы ссылки нечитаемыми (`%D0%9A...`).
    """
    rel = os.path.relpath(target, src_md.parent).replace(os.sep, "/")
    return rel.replace(" ", "%20")


def analyze(index: dict[str, list[Path]]) -> dict[str, list[dict]]:
    """Пройти все SKILL.md; вернуть {skill: [{old, new|None, status}]}."""
    result: dict[str, list[dict]] = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
            continue
        md = skill_dir / "SKILL.md"
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        entries: list[dict] = []
        for m in _LINK_RE.finditer(text):
            raw_target = m.group(2)
            if raw_target.startswith(("http://", "https://")):
                continue
            target = unquote(raw_target)
            resolved = (md.parent / target).resolve()
            if resolved.exists():
                continue  # ссылка валидна
            if _PLACEHOLDER.search(target):
                entries.append({"old": raw_target, "new": None, "status": "placeholder"})
                continue
            base = Path(target).name
            # ссылка на скилл: цель определяется ИМЕНЕМ КАТАЛОГА (basename SKILL.md
            # неоднозначен — он у всех 97 скиллов), не индексом basename.
            if base == "SKILL.md":
                parts = Path(target).parts
                dirname = parts[-2] if len(parts) >= 2 else ""
                skill_target = SKILLS_DIR / dirname / "SKILL.md"
                if dirname and skill_target.exists():
                    entries.append(
                        {"old": raw_target, "new": _relpath(md, skill_target), "status": "fixable"}
                    )
                else:
                    entries.append({"old": raw_target, "new": None, "status": "dead"})
                continue
            cand = _pick(base, index.get(base, []))
            if cand is None:
                st = "dead" if not index.get(base) else "ambiguous"
                entries.append({"old": raw_target, "new": None, "status": st})
                continue
            entries.append({"old": raw_target, "new": _relpath(md, cand), "status": "fixable"})
        if entries:
            result[skill_dir.name] = entries
    return result


def apply_fixes(result: dict[str, list[dict]]) -> int:
    """Переписать fixable-ссылки. Возвращает число применённых замен."""
    applied = 0
    for skill, entries in result.items():
        md = SKILLS_DIR / skill / "SKILL.md"
        text = md.read_text(encoding="utf-8", errors="replace")
        changed = False
        for e in entries:
            if e["status"] != "fixable" or not e["new"]:
                continue
            old_frag = f"]({e['old']}"
            new_frag = f"]({e['new']}"
            if old_frag in text:
                text = text.replace(old_frag, new_frag)
                applied += 1
                changed = True
        if changed:
            md.write_text(text, encoding="utf-8")
    return applied


def _print_utf8(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill dead-link remediation (audit 260705)")
    ap.add_argument("--apply", action="store_true", help="применить (default: dry-run)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    index = build_index()
    result = analyze(index)

    counts: dict[str, int] = defaultdict(int)
    for entries in result.values():
        for e in entries:
            counts[e["status"]] += 1

    if args.json:
        _print_utf8(
            json.dumps({"counts": dict(counts), "per_skill": result}, ensure_ascii=False, indent=2)
        )
        return 0

    _print_utf8(
        "# fix-skill-deadlinks: fixable={} dead={} ambiguous={} placeholder={}".format(
            counts["fixable"], counts["dead"], counts["ambiguous"], counts["placeholder"]
        )
    )
    for skill, entries in result.items():
        for e in entries:
            if e["status"] == "fixable":
                _print_utf8(f"  [FIX] {skill}: {e['old']} -> {e['new']}")
            else:
                _print_utf8(f"  [{e['status'].upper()}] {skill}: {e['old']}")

    if args.apply:
        n = apply_fixes(result)
        _print_utf8(f"\nПрименено замен: {n}")
    else:
        _print_utf8(f"\n(dry-run) fixable к применению: {counts['fixable']} — прогони с --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
