"""Shared primitives for acceptance-window scripts (roadmap 260611/260612 §P4).

Extracted from ``skill_learning_acceptance.py`` so the memory-ai acceptance
(260612) reuses the каркас instead of copy-pasting it. Pure local I/O, no
network. Each concrete script supplies its own metric collection + criteria
and calls :func:`render_acceptance` / :func:`emit`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Tolerant JSONL reader: malformed lines skipped, absent file → []."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return out
    return out


def parse_dt(raw: Any) -> datetime | None:
    """ISO-парс с naive-нормализацией (tz-aware метка ломает naive-сравнения)."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=None)
    except ValueError:
        return None


def window_day(now: datetime, start: datetime, total_days: int = 14) -> int:
    return max(1, min((now - start).days + 1, total_days))


def render_acceptance(
    title: str,
    m: dict[str, Any],
    crit: dict[str, bool],
    *,
    final: bool,
    detail_lines: list[str],
    roadmap_rel: str,
) -> str:
    """Markdown отчёт: заголовок + детали + таблица критериев + вердикт."""
    verdict = (
        ("PASS" if all(crit.values()) else "FAIL")
        if (final or m.get("window_closed"))
        else "PENDING (окно открыто)"
    )
    lines = [title, "", *detail_lines, "", "| Критерий | Статус |", "|---|---|"]
    for k, ok in crit.items():
        lines.append(f"| {k} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", f"**Вердикт: {verdict}**"]
    if verdict in ("PASS", "FAIL"):
        lines.append(f"\nЗафиксировать вердикт в §18 {roadmap_rel}.")
    return "\n".join(lines)


def emit(
    text_or_json: str,
    *,
    report_name: str | None = None,
) -> None:
    """UTF-8-safe stdout (cp1251-консоль не должна ронять скрипт) + отчёт-файл."""
    import sys

    sys.stdout.buffer.write(text_or_json.encode("utf-8") + b"\n")
    if report_name:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d")
            (REPORTS_DIR / f"{report_name}_{stamp}.md").write_text(
                text_or_json, encoding="utf-8"
            )
        except OSError:
            pass


__all__ = [
    "PROJECT_ROOT",
    "REPORTS_DIR",
    "emit",
    "parse_dt",
    "read_jsonl",
    "render_acceptance",
    "window_day",
]
