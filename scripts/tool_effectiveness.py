#!/usr/bin/env python3
"""Общий rule-слой эффективности инструментов (roadmap 260713 P2.2).

Детерминированные метрики эффективности по консенсусу 2026 (OTel GenAI +
deepeval/MCP-Bench), вынесенные в single-source из дублирующих реализаций
`scripts/tool_usage_report.py` и `scripts/analyze_tool_health.py`:

  - **pair_durations** — реальная латентность вызова (Pre→Post-пара, join по
    ``tool_call_id`` иначе FIFO; tz-guard как в Sonar parse_dt);
  - **percentile** — p50/p95 без numpy;
  - **effectiveness_from_posts** — retry (`repeats`, тот же ``args_hash``) vs
    abandonment (последняя попытка тула — ошибка);
  - **step_efficiency** — доля избыточных вызовов (repeats/calls);
  - **rollup_by_server** — Tool Success Rate + эффективность per-server (MCP
    группируются по ``mcp__<server>__<op>``; built-in — общая корзина).

stdlib-only (без numpy/duckdb) — используется в detached Stop-хук-контексте.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

BUILTIN_BUCKET = "(built-in)"


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def percentile(values: list[int], q: float) -> float:
    """Перцентиль (linear interpolation), q ∈ [0,1]. stdlib, без numpy."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    idx = q * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def pair_durations(pres: list[dict], posts: list[dict]) -> list[int]:
    """Список реальных длительностей Pre→Post (мс). Join по ``tool_call_id``,
    иначе FIFO (ранний неиспользованный Pre не позже Post). tz-guard: naive vs
    aware вычитание бросает TypeError (класс бага Sonar parse_dt) — пропускаем."""
    if not posts:
        return []
    pres_sorted = sorted(pres, key=lambda e: e.get("ts", ""))
    posts_sorted = sorted(posts, key=lambda e: e.get("ts", ""))
    pre_by_id: dict[str, dict] = {}
    for p in pres_sorted:
        cid = p.get("tool_call_id")
        if cid:
            pre_by_id.setdefault(cid, p)
    used: set[int] = set()
    out: list[int] = []
    for post in posts_sorted:
        pre = None
        cid = post.get("tool_call_id")
        if cid and cid in pre_by_id and id(pre_by_id[cid]) not in used:
            pre = pre_by_id[cid]
        else:
            for p in pres_sorted:
                if id(p) in used:
                    continue
                if p.get("ts", "") <= post.get("ts", ""):
                    pre = p
                    break
        if pre is None:
            continue
        a, b = parse_ts(pre.get("ts")), parse_ts(post.get("ts"))
        if a and b:
            try:
                d = int((b - a).total_seconds() * 1000)
            except (TypeError, ValueError):
                continue
            if d >= 0:
                used.add(id(pre))  # помечаем Pre использованным ТОЛЬКО при валидной паре
                out.append(d)
    return out


def _is_error_post(e: dict) -> bool:
    return e.get("outcome") == "error" or bool(e.get("error"))


def effectiveness_from_posts(posts: list[dict]) -> dict:
    """retry/abandonment по завершённым Post одного инструмента.

    ``repeats`` — повтор идентичного вызова (тот же ``args_hash`` = retry).
    ``abandonment`` — последняя (по ts) попытка тула завершилась ошибкой (не
    восстановились). ⚠ у built-in тулов детект ошибки best-effort (Bash non-zero
    exit не всегда помечается) → метрики built-in консервативны.
    """
    ordered = sorted(posts, key=lambda e: e.get("ts", ""))
    seen: set = set()
    repeats = 0
    for e in ordered:
        ah = e.get("args_hash")
        if ah:
            if ah in seen:
                repeats += 1
            seen.add(ah)
    abandonment = bool(ordered) and _is_error_post(ordered[-1])
    return {"repeats": repeats, "abandonment": abandonment}


def step_efficiency(calls: int, repeats: int) -> float:
    """Доля избыточных вызовов (retry) в общем числе вызовов, ∈ [0,1].
    0 = ни одного повтора; выше = хуже (больше потраченных шагов)."""
    if calls <= 0:
        return 0.0
    return round(repeats / calls, 4)


def server_of(tool: str | None) -> str:
    """MCP-сервер инструмента: ``mcp__<server>__<op>`` → ``<server>``.
    Built-in/нативные (Read/Bash/Edit/…) → общая корзина ``(built-in)``."""
    t = tool or ""
    if t.startswith("mcp__") and "__" in t[5:]:
        return t[5:].split("__", 1)[0]
    return BUILTIN_BUCKET


def rollup_by_server(tools_stats: dict[str, dict]) -> dict[str, dict]:
    """Агрегат per-server из per-tool статистики (выход aggregate_tools).

    Каждой группе: calls / errors / success / success_rate / error_rate /
    repeats / step_efficiency / abandonment_tools (сколько тулов группы брошены
    на ошибке) / tools (число инструментов). unused-тулы (0 вызовов) не искажают
    success_rate — их calls=0 не добавляют веса.
    """
    agg: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "errors": 0,
            "repeats": 0,
            "abandonment_tools": 0,
            "tools": 0,
        }
    )
    for tool, st in tools_stats.items():
        g = agg[server_of(tool)]
        g["calls"] += int(st.get("calls", 0))
        g["errors"] += int(st.get("errors", 0))
        g["repeats"] += int(st.get("repeats", 0))
        g["tools"] += 1
        if st.get("abandonment"):
            g["abandonment_tools"] += 1
    out: dict[str, dict] = {}
    for server, g in agg.items():
        calls = g["calls"]
        success = calls - g["errors"]
        out[server] = {
            **g,
            "success": success,
            "success_rate": round(success / calls, 4) if calls else 1.0,
            "error_rate": round(g["errors"] / calls, 4) if calls else 0.0,
            "step_efficiency": step_efficiency(calls, g["repeats"]),
        }
    return out


__all__ = [
    "BUILTIN_BUCKET",
    "parse_ts",
    "percentile",
    "pair_durations",
    "effectiveness_from_posts",
    "step_efficiency",
    "server_of",
    "rollup_by_server",
]
