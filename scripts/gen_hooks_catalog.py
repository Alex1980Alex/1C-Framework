"""Audit 260705 skills P1/P2.1 — генератор каталога хуков из settings.json (single source).

Убивает класс «4x-дрейф» доков 13.2/реестра триады: таблица «событие x хук x
matcher x timeout» + счётчики выводятся ИЗ `.claude/settings.json`, а не правятся
руками. Доки вставляют вывод (или ссылаются на генератор), CI-проверка сверяет
заявленные счётчики с фактом.

Usage:
  python scripts/gen_hooks_catalog.py                 # markdown-каталог (для вставки в 13.2)
  python scripts/gen_hooks_catalog.py --counts         # только счётчики по событиям
  python scripts/gen_hooks_catalog.py --router-counts  # счётчики реестра триады (bundles/skills/домены)
  python scripts/gen_hooks_catalog.py --json           # машинный вывод (хуки + триада)
  python scripts/gen_hooks_catalog.py --check UPS=19,bundles=66,skills=98  # сверить, exit 1 при расхождении
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS = PROJECT_ROOT / ".claude" / "settings.json"
SKILL_ROUTER_CONFIG = PROJECT_ROOT / ".claude" / "skills" / "skill-router-config.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# порядок вывода событий (жизненный цикл)
_EVENT_ORDER = [
    "UserPromptSubmit",
    "UserPromptExpansion",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionStart",
]

_SCRIPT_RE = re.compile(r"([\w.-]+\.py)")


def _script_name(command: str) -> str:
    """Последний .py-токен команды = имя хук-скрипта; иначе усечённая команда."""
    names = _SCRIPT_RE.findall(command or "")
    return names[-1] if names else (command or "")[:40]


def load_catalog(settings_path: Path = SETTINGS) -> dict[str, list[dict[str, Any]]]:
    """settings.json -> {event: [{script, matcher, timeout}, ...]} в порядке регистрации."""
    cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = cfg.get("hooks", {})
    catalog: dict[str, list[dict[str, Any]]] = {}
    for event, groups in hooks.items():
        rows: list[dict[str, Any]] = []
        for group in groups:
            matcher = group.get("matcher", "")
            for h in group.get("hooks", []):
                rows.append(
                    {
                        "script": _script_name(h.get("command", "")),
                        "matcher": matcher or "(all)",
                        "timeout": h.get("timeout"),
                    }
                )
        catalog[event] = rows
    return catalog


def counts(catalog: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """{event: N команд}; ключ TOTAL — итог по всем событиям."""
    c = {ev: len(rows) for ev, rows in catalog.items()}
    c["TOTAL"] = sum(len(rows) for rows in catalog.values())
    return c


def router_counts(
    config_path: Path = SKILL_ROUTER_CONFIG,
    skills_dir: Path = SKILLS_DIR,
) -> dict[str, Any]:
    """skill-router-config.json + каталог скиллов -> счётчики реестра триады.

    Убивает тот же класс «дрейф счётчика», что и hook-каталог, но для
    `hooks-skills-mcp-triad/SKILL.md` (bundles / version / skills / доменная
    разбивка). Источник истины — конфиг и файловая система, не текст доки.

    Возвращает: {bundles, version, skills, grouped, ungrouped, domains: {dom: n}}.
    """
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    bundles = cfg.get("bundles", {})
    domains = cfg.get("domains", {})

    dom_counts: dict[str, int] = {}
    for dom, members in domains.items():
        # domains[dom] — список имён бандлов (см. skill-router-config.json)
        n = len(members) if isinstance(members, (list, dict)) else 0
        dom_counts[dom] = n
    grouped = sum(dom_counts.values())

    # скиллы = директории с SKILL.md
    skills = 0
    if skills_dir.exists():
        skills = sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())

    total_bundles = len(bundles)
    return {
        "bundles": total_bundles,
        "version": cfg.get("version"),
        "skills": skills,
        "grouped": grouped,
        # clamp: домены теоретически могут пересекаться (бандл в 2 доменах) →
        # grouped завысится; не даём ungrouped уйти в минус (reviewer 260706 rec1)
        "ungrouped": max(0, total_bundles - grouped),
        "domains": dom_counts,
    }


TRIAD_SKILL = PROJECT_ROOT / ".claude" / "skills" / "hooks-skills-mcp-triad" / "SKILL.md"

# «66 bundles» / «66 бандл...» и «98 скиллов» в тексте реестра триады
_DOC_BUNDLE_RE = re.compile(r"(\d+)\s+(?:bundles|бандл\w*)", re.IGNORECASE)
_DOC_SKILL_RE = re.compile(r"\((\d+)\s+скилл\w*\)")


def verify_doc(
    doc_path: Path = TRIAD_SKILL,
    config_path: Path = SKILL_ROUTER_CONFIG,
    skills_dir: Path = SKILLS_DIR,
) -> list[str]:
    """Сверить ЗАЯВЛЕННЫЕ в реестре триады счётчики с фактом (self-updating).

    Не хардкодит эталон: извлекает все «N bundles»/«(N скиллов)» из SKILL.md и
    сравнивает с актуальным `router_counts`. Растёт каталог — правится только
    доки (или регенерация), CI ловит рассинхрон без правки самого guard'а.

    Возвращает список расхождений (пустой = синхронно).
    """
    # graceful: недостижимый конфиг/док → чистое сообщение + fail-closed (reviewer 260706 rec2)
    try:
        rc = router_counts(config_path, skills_dir)
        text = doc_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, json.JSONDecodeError) as e:
        return [f"источник недоступен ({type(e).__name__}): {e}"]
    problems: list[str] = []

    for m in _DOC_BUNDLE_RE.finditer(text):
        declared = int(m.group(1))
        if declared != rc["bundles"]:
            problems.append(
                f"«{declared} bundles» в SKILL.md != факт {rc['bundles']} (skill-router-config.json)"
            )
    for m in _DOC_SKILL_RE.finditer(text):
        declared = int(m.group(1))
        if declared != rc["skills"]:
            problems.append(f"«({declared} скиллов)» в SKILL.md != факт {rc['skills']}")

    # дедуп (одно и то же расхождение повторяется на каждое упоминание)
    return list(dict.fromkeys(problems))


def _ordered_events(catalog: dict[str, list[dict[str, Any]]]) -> list[str]:
    known = [e for e in _EVENT_ORDER if e in catalog]
    extra = [e for e in catalog if e not in _EVENT_ORDER]
    return known + extra


def render_markdown(catalog: dict[str, list[dict[str, Any]]]) -> str:
    """Каталог -> markdown (таблица на событие + сводка счётчиков)."""
    c = counts(catalog)
    lines: list[str] = []
    lines.append("<!-- АВТО-ГЕНЕРАЦИЯ: python scripts/gen_hooks_catalog.py — НЕ править руками -->")
    lines.append("")
    summary = " / ".join(f"{ev} {c[ev]}" for ev in _ordered_events(catalog))
    lines.append(f"**Всего регистраций: {c['TOTAL']}** ({summary}).")
    lines.append("")
    for ev in _ordered_events(catalog):
        rows = catalog[ev]
        lines.append(f"### {ev} ({len(rows)})")
        lines.append("")
        lines.append("| Хук | Matcher | Timeout |")
        lines.append("|-----|---------|---------|")
        for r in rows:
            to = f"{r['timeout']}s" if r["timeout"] is not None else "—"
            lines.append(f"| `{r['script']}` | `{r['matcher']}` | {to} |")
        lines.append("")
    return "\n".join(lines)


def _print_utf8(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


# псевдонимы для --check (доки часто пишут UPS вместо UserPromptSubmit)
_ALIASES = {
    "UPS": "UserPromptSubmit",
    "UPE": "UserPromptExpansion",
    "Pre": "PreToolUse",
    "Post": "PostToolUse",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Hook catalog generator (audit 260705 P2.1)")
    ap.add_argument("--counts", action="store_true", help="только счётчики хуков")
    ap.add_argument(
        "--router-counts",
        action="store_true",
        help="счётчики реестра триады (bundles/version/skills/домены)",
    )
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument(
        "--check",
        default="",
        help="сверить: 'UPS=19,bundles=66,skills=98' -> exit 1 при расхождении "
        "(ключи хуков + bundles/version/skills)",
    )
    ap.add_argument(
        "--verify-doc",
        action="store_true",
        help="сверить счётчики в hooks-skills-mcp-triad/SKILL.md с фактом (self-updating), exit 1 при дрейфе",
    )
    args = ap.parse_args()

    catalog = load_catalog()
    c = counts(catalog)
    # router-счётчики нужны только check/router-counts/verify-doc/json → вычисляем
    # лениво в соответствующих ветках, чтобы --counts/--json/markdown не зависели
    # от skill-router-config.json (reviewer 260706 rec3). Ветки взаимоисключающи.

    if args.check:
        rc = router_counts()
        checkable = {
            **c,
            **{k: rc[k] for k in ("bundles", "version", "skills", "grouped", "ungrouped")},
        }
        mismatches = []
        for pair in args.check.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            key, val = pair.split("=", 1)
            key = _ALIASES.get(key.strip(), key.strip())
            expected = int(val.strip())
            actual = checkable.get(key)
            if actual != expected:
                mismatches.append(f"{key}: заявлено {expected}, факт {actual}")
        if mismatches:
            _print_utf8("COUNT DRIFT:\n" + "\n".join("  - " + m for m in mismatches))
            return 1
        _print_utf8("counts OK")
        return 0

    if args.verify_doc:
        problems = verify_doc()
        if problems:
            _print_utf8("TRIAD DOC DRIFT:\n" + "\n".join("  - " + p for p in problems))
            return 1
        _print_utf8("triad SKILL.md counts OK")
        return 0

    if args.router_counts:
        rc = router_counts()
        _print_utf8(
            f"bundles: {rc['bundles']}  (grouped {rc['grouped']} / ungrouped {rc['ungrouped']})"
        )
        _print_utf8(f"version: {rc['version']}")
        _print_utf8(f"skills: {rc['skills']}")
        for dom, n in rc["domains"].items():
            _print_utf8(f"  {dom}: {n}")
        return 0

    if args.json:
        rc = router_counts()
        _print_utf8(
            json.dumps(
                {"counts": c, "router": rc, "catalog": catalog}, ensure_ascii=False, indent=2
            )
        )
    elif args.counts:
        for ev in _ordered_events(catalog):
            _print_utf8(f"{ev}: {c[ev]}")
        _print_utf8(f"TOTAL: {c['TOTAL']}")
    else:
        _print_utf8(render_markdown(catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
