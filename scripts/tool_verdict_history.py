#!/usr/bin/env python3
"""Читатель истории вердиктов tool-health (roadmap 260718 N-P1.2).

NB4: `verdicts.jsonl` был write-only — его никто не читал, поэтому §6.3
(«повторный broken за 30д → эскалация приоритета», тренд) не работал. Этот
модуль — ЕДИНСТВЕННЫЙ читатель истории, потребляется и баннером
(`tool-health-banner-on-start`), и аналитиком (`analyze_tool_health` — тренд в отчёт).

stdlib-only (баннер — хук в detached-контексте).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def _parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def read_verdicts(path: Path) -> list[dict]:
    """Все строки verdicts.jsonl (битые пропускаются). Пусто при отсутствии файла."""
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and e.get("tool"):
                    out.append(e)
    except OSError:
        return []
    return out


def _runs_for_tool(rows: list[dict], tool: str) -> list[tuple[datetime, str]]:
    """(run_ts, verdict) для тула, отсортированные по времени."""
    seq = []
    for e in rows:
        if e.get("tool") != tool:
            continue
        ts = _parse_ts(e.get("ts"))
        if ts is not None:
            seq.append((ts, e.get("verdict", "")))
    seq.sort(key=lambda x: x[0])
    return seq


def broken_repeat_within(tool: str, now: datetime, days: int, rows: list[dict]) -> bool:
    """True, если тул был broken в ≥2 РАЗНЫХ прогонах за последние `days` (persistent →
    приоритет p1, §6.3). Один прогон broken — первый инцидент (p high), не повтор."""
    cutoff = now - timedelta(days=days)
    distinct_runs = {
        ts.isoformat() for ts, v in _runs_for_tool(rows, tool) if v == "broken" and ts >= cutoff
    }
    return len(distinct_runs) >= 2


def verdict_trend(now: datetime, days: int, rows: list[dict]) -> dict:
    """Тренд за `days` (§6.3): переходы broken↔healthy per-tool.

    healed  — тул был broken, затем стал не-broken (вылечен);
    regressed — был не-broken, стал broken (регресс);
    persistent_broken — broken в последнем прогоне И раньше в окне.
    """
    cutoff = now - timedelta(days=days)
    tools = {e.get("tool") for e in rows if e.get("tool")}
    healed = regressed = persistent = 0
    healed_tools: list[str] = []
    for tool in tools:
        seq = [(ts, v) for ts, v in _runs_for_tool(rows, tool) if ts >= cutoff]
        if len(seq) < 2:
            continue
        was_broken = any(v == "broken" for _, v in seq)
        last_broken = seq[-1][1] == "broken"
        # ADR-055: broken→known-issue = ПОДАВЛЕНО, не «вылечено» (симметрично баннерному
        # current_active) — иначе тренд отчёта врёт «✅ вылечено» на suppressed-туле.
        last_known_issue = seq[-1][1] == "known-issue"
        first_broken = seq[0][1] == "broken"
        if was_broken and not last_broken and not last_known_issue:
            healed += 1
            healed_tools.append(tool)
        if not first_broken and last_broken:
            regressed += 1
        if last_broken and any(v == "broken" for _, v in seq[:-1]):
            persistent += 1
    return {
        "days": days,
        "healed": healed,
        "regressed": regressed,
        "persistent_broken": persistent,
        "healed_tools": sorted(healed_tools),
    }


__all__ = ["read_verdicts", "broken_repeat_within", "verdict_trend"]
