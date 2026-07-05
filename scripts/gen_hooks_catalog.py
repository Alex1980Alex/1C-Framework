"""Audit 260705 skills P1/P2.1 — генератор каталога хуков из settings.json (single source).

Убивает класс «4x-дрейф» доков 13.2/реестра триады: таблица «событие x хук x
matcher x timeout» + счётчики выводятся ИЗ `.claude/settings.json`, а не правятся
руками. Доки вставляют вывод (или ссылаются на генератор), CI-проверка сверяет
заявленные счётчики с фактом.

Usage:
  python scripts/gen_hooks_catalog.py                 # markdown-каталог (для вставки в 13.2)
  python scripts/gen_hooks_catalog.py --counts         # только счётчики по событиям
  python scripts/gen_hooks_catalog.py --json           # машинный вывод
  python scripts/gen_hooks_catalog.py --check UPS=19,PreToolUse=21   # сверить и exit 1 при расхождении
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
    ap.add_argument("--counts", action="store_true", help="только счётчики")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument(
        "--check", default="", help="сверить: 'UPS=19,PreToolUse=21' -> exit 1 при расхождении"
    )
    args = ap.parse_args()

    catalog = load_catalog()
    c = counts(catalog)

    if args.check:
        mismatches = []
        for pair in args.check.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            key, val = pair.split("=", 1)
            key = _ALIASES.get(key.strip(), key.strip())
            expected = int(val.strip())
            actual = c.get(key)
            if actual != expected:
                mismatches.append(f"{key}: заявлено {expected}, факт {actual}")
        if mismatches:
            _print_utf8("HOOK-COUNT DRIFT:\n" + "\n".join("  - " + m for m in mismatches))
            return 1
        _print_utf8("hook counts OK")
        return 0

    if args.json:
        _print_utf8(json.dumps({"counts": c, "catalog": catalog}, ensure_ascii=False, indent=2))
    elif args.counts:
        for ev in _ordered_events(catalog):
            _print_utf8(f"{ev}: {c[ev]}")
        _print_utf8(f"TOTAL: {c['TOTAL']}")
    else:
        _print_utf8(render_markdown(catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
