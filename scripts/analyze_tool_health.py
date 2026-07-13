#!/usr/bin/env python3
"""analyze_tool_health.py — авто-анализ здоровья и эффективности инструментов/MCP.

Roadmap 260713 P1.1 + §6 (decision layer). Замыкает цикл «лог → анализ → метрика
→ вердикт» над главным логом инструментов `data/hook-invocations.jsonl`.

Читает канонические строки вызовов (category ∈ {mcp_call, tool_call} — по одной
паре Pre/Post на вызов; category="hook" энфомер-строки НЕ вызовы и игнорируются)
за скользящее окно, агрегирует per-tool (calls / errors / success-rate / реальная
Pre→Post латентность p50/p95 / repeats / abandonment) и присваивает ВЕРДИКТ по
детерминированным правилам §6.1:

  broken      success-rate < 0.5 при calls≥5, ИЛИ 0 success при attempts≥3
  degraded    error-rate > 0.10, ИЛИ p95 > 2× baseline, ИЛИ error-rate +5пп к baseline
  ineffective success ок, но repeats/calls > 0.3, ИЛИ abandonment при calls≥3
  unused      был в baseline, но 0 вызовов в окне (инструмент «замолчал»)
  healthy     всё остальное

Выход (detached Stop-хук вызывает этот скрипт — паттерн post-indexing-analyzer):
  data/reports/tools/_latest.md    — человекочитаемый отчёт (+ секция ⚠ ALERTS)
  data/reports/tools/_latest.json  — sidecar (вердикты + alerts для SessionStart-баннера)
  data/reports/tools/verdicts.jsonl — append-only история вердиктов (тренд, эскалация)
  data/reports/tools/baseline.json — ratchet-baseline (лучший p95/error-rate, паттерн mypy-baseline)

Решение (§6.2) — НЕ в этом скрипте: он ПИШЕТ вердикты + alerts; SessionStart-баннер
их сюрфейсит и эскалирует broken (авто-задача). Молчаливого авто-фикса нет.

stdlib-only (без duckdb) — надёжно в detached-контексте. DuckDB-views для интерактива
остаются в audit_query.py.

Запуск: python scripts/analyze_tool_health.py [--window-days 14] [--json-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "hook-invocations.jsonl"
ROTATED = ROOT / "data" / "hook-invocations.1.jsonl"
REPORTS = ROOT / "data" / "reports" / "tools"

# scripts/ на path — модуль грузится и как скрипт, и через importlib в тестах.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from tool_effectiveness import (  # single-source rule-слой (roadmap 260713 P2.2)
    effectiveness_from_posts,
    pair_durations,
    parse_ts,
    percentile,
    rollup_by_server,
)

# Обратно-совместимые алиасы (внутренние helper'ы вынесены в tool_effectiveness).
_parse_ts = parse_ts
_pct = percentile
_pair_duration_list = pair_durations

CANONICAL_CATEGORIES = ("mcp_call", "tool_call")

# ── пороги вердиктов (§6.1) — вынесены для тюнинга/тестов ─────────────────────
MIN_CALLS_FOR_BROKEN = 5  # мин. вызовов чтобы success-rate был статзначим
MIN_ATTEMPTS_ZERO_SUCCESS = 3  # 0 успехов при ≥ этого = broken
BROKEN_SUCCESS_RATE = 0.50
DEGRADED_MIN_CALLS = 3  # симметрично broken: единичная транзиентная ошибка не = degraded
DEGRADED_ERROR_RATE = 0.10
P95_REGRESSION_FACTOR = 2.0  # p95 > 2× baseline = degraded
ERROR_RATE_RATCHET = 0.05  # +5пп к baseline error-rate = degraded
INEFFECTIVE_MIN_CALLS_ABANDON = 3  # abandonment учитывается при calls ≥ этого


# ── чтение лога за окно ───────────────────────────────────────────────────────


def iter_window_rows(now: datetime, window_days: int, logs: list[Path] | None = None):
    """Канонические строки вызовов за окно [now-window_days, now]. Битые/чужие пропускаются."""
    cutoff = now - timedelta(days=window_days)
    for log in logs if logs is not None else [LOG, ROTATED]:
        if not log.exists():
            continue
        with open(log, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("category") not in CANONICAL_CATEGORIES:
                    continue
                if not e.get("tool"):
                    continue
                ts = _parse_ts(e.get("ts"))
                if ts is None or ts < cutoff:
                    continue
                yield e


# ── агрегация per-tool ────────────────────────────────────────────────────────


def aggregate_tools(rows: list[dict]) -> dict[str, dict]:
    """Per-tool статистика вызовов. calls = завершённые (Post). Эффективность
    (repeats/abandonment) — по завершённым Post с args_hash/outcome (общий модуль)."""
    pre: dict[str, list] = defaultdict(list)
    post: dict[str, list] = defaultdict(list)
    for e in rows:
        (post if e.get("event") == "PostToolUse" else pre)[e["tool"]].append(e)

    out: dict[str, dict] = {}
    for tool in set(pre) | set(post):
        posts = sorted(post[tool], key=lambda e: e.get("ts", ""))
        calls = len(posts)
        errors = sum(1 for p in posts if p.get("outcome") == "error" or p.get("error"))
        durations = pair_durations(pre[tool], posts)
        eff = effectiveness_from_posts(posts)  # retry/abandonment (single-source)
        success = calls - errors
        out[tool] = {
            "calls": calls,
            "errors": errors,
            "success": success,
            "success_rate": round(success / calls, 4) if calls else 1.0,
            "error_rate": round(errors / calls, 4) if calls else 0.0,
            "p50_ms": round(percentile(durations, 0.50), 1),
            "p95_ms": round(percentile(durations, 0.95), 1),
            "paired": len(durations),
            "repeats": eff["repeats"],
            "abandonment": eff["abandonment"],
        }
    return out


# ── вердикт (§6.1) ────────────────────────────────────────────────────────────


def assign_verdict(stats: dict, baseline: dict | None) -> tuple[str, str]:
    """Вердикт + одно-строчное обоснование. baseline = {p95_ms, error_rate} лучшего окна (или None)."""
    calls = stats["calls"]
    sr = stats["success_rate"]
    er = stats["error_rate"]
    success = stats["success"]

    # broken — приоритетнее degraded
    if success == 0 and calls >= MIN_ATTEMPTS_ZERO_SUCCESS:
        return "broken", f"0 успешных из {calls} попыток"
    if calls >= MIN_CALLS_FOR_BROKEN and sr < BROKEN_SUCCESS_RATE:
        return "broken", f"success-rate {sr:.0%} < 50% при {calls} вызовах"

    # degraded — error-rate порог требует мин. вызовов (иначе единичная транзиентная
    # ошибка MCP [-32000/500] светила бы degraded ~14д, пока не выпадет из окна).
    if calls >= DEGRADED_MIN_CALLS and er > DEGRADED_ERROR_RATE:
        return "degraded", f"error-rate {er:.0%} > 10% ({calls} вызовов)"
    if baseline:
        base_p95 = baseline.get("p95_ms") or 0
        if base_p95 > 0 and stats["p95_ms"] > P95_REGRESSION_FACTOR * base_p95:
            return "degraded", f"p95 {stats['p95_ms']:.0f}ms > 2× baseline ({base_p95:.0f}ms)"
        base_er = baseline.get("error_rate")
        if base_er is not None and er - base_er > ERROR_RATE_RATCHET:
            return "degraded", f"error-rate +{(er - base_er):.0%} к baseline"

    # ineffective — в целом работает (error_rate ≤ 10%, иначе выше отдал бы degraded),
    # но ПОСЛЕДНЯЯ попытка провалилась и брошена (abandonment). Это рекуррентный сигнал,
    # отличный от degraded: низкий общий error-rate, но свежая траектория — провал.
    # Сознательно НЕ используем repeats как драйвер вердикта: повтор УСПЕШНОГО вызова
    # (ping/targets/get_metadata, тот же args_hash при 100% success) — идемпотентный опрос,
    # норма; а повтор ПАДАЮЩЕГО инфлейтит error_rate → уже пойман degraded. repeats остаётся
    # информативной колонкой отчёта, но не решает вердикт (иначе FP на polling-тулах).
    if stats["abandonment"] and calls >= INEFFECTIVE_MIN_CALLS_ABANDON:
        return "ineffective", "последняя попытка — ошибка (не восстановлено), общий success высок"

    return "healthy", f"{sr:.0%} success, {calls} вызовов"


def compute_health(rows: list[dict], baseline: dict, now: datetime) -> dict:
    """Собрать per-tool статистику + вердикты + детект unused (был в baseline, 0 вызовов сейчас)."""
    stats = aggregate_tools(rows)
    tools: dict[str, dict] = {}
    for tool, st in stats.items():
        verdict, reason = assign_verdict(st, baseline.get(tool))
        tools[tool] = {**st, "verdict": verdict, "reason": reason}

    # unused: инструмент присутствовал в baseline, но 0 вызовов в текущем окне
    active = set(stats)
    for tool in baseline:
        if tool not in active:
            tools[tool] = {
                "calls": 0,
                "errors": 0,
                "success": 0,
                "success_rate": 1.0,
                "error_rate": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "paired": 0,
                "repeats": 0,
                "abandonment": False,
                "verdict": "unused",
                "reason": "был в baseline, 0 вызовов в окне (замолчал)",
            }
    # rule-слой P2.2: Tool Success Rate + step efficiency per-server (по активным).
    servers = rollup_by_server(stats)
    return {
        "tools": tools,
        "servers": servers,
        "generated": now.isoformat(timespec="seconds"),
    }


# ── ratchet-baseline (паттерн mypy-baseline) ─────────────────────────────────


def update_baseline(baseline: dict, stats: dict[str, dict]) -> dict:
    """Ratchet: baseline = лучший (min) p95 и error-rate per-tool. Ухудшение НЕ пишется
    (чтобы degraded ловился), улучшение обновляет планку."""
    out = dict(baseline)
    for tool, st in stats.items():
        if st["calls"] < MIN_CALLS_FOR_BROKEN:  # мало данных — не двигаем baseline
            continue
        prev = out.get(tool, {})
        out[tool] = {
            "p95_ms": min(prev.get("p95_ms", st["p95_ms"]), st["p95_ms"]) if prev else st["p95_ms"],
            "error_rate": (
                min(prev.get("error_rate", st["error_rate"]), st["error_rate"])
                if prev
                else st["error_rate"]
            ),
        }
    return out


# ── I/O ───────────────────────────────────────────────────────────────────────


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    import os

    os.replace(tmp, path)


_VERDICT_ORDER = {"broken": 0, "degraded": 1, "ineffective": 2, "unused": 3, "healthy": 4}
_VERDICT_MARK = {
    "broken": "🔴",
    "degraded": "🟠",
    "ineffective": "🟡",
    "unused": "⚪",
    "healthy": "🟢",
}


def render_md(health: dict, window_days: int) -> str:
    tools = health["tools"]
    ranked = sorted(
        tools.items(), key=lambda kv: (_VERDICT_ORDER.get(kv[1]["verdict"], 9), -kv[1]["calls"])
    )
    alerts = [(t, s) for t, s in ranked if s["verdict"] in ("broken", "degraded")]

    lines = [
        f"# Tool Health Report (окно {window_days}д)",
        f"_сгенерировано {health['generated']}; вердикты по §6.1 roadmap 260713_",
        "",
    ]
    counts: dict[str, int] = defaultdict(int)
    for _t, s in tools.items():
        counts[s["verdict"]] += 1
    summary = " · ".join(
        f"{_VERDICT_MARK[v]} {v}={counts[v]}" for v in _VERDICT_ORDER if counts.get(v)
    )
    lines += [f"**Итог:** {summary or 'нет данных'}", ""]

    if alerts:
        lines += ["## ⚠ ALERTS (broken / degraded)", ""]
        for tool, s in alerts:
            lines.append(
                f"- {_VERDICT_MARK[s['verdict']]} **`{tool}`** — {s['verdict']}: {s['reason']}"
            )
        lines += [""]

    # ── rule-слой P2.2: эффективность per-server (Tool Success Rate + step efficiency) ──
    servers = health.get("servers") or {}
    active_servers = {s: v for s, v in servers.items() if v.get("calls", 0) > 0}
    if active_servers:
        lines += [
            "## Эффективность (rule-слой, per-server)",
            "",
            "| Сервер | Вызовов | success-rate | error-rate | step-eff (retry%) | брошено тулов |",
            "|---|---|---|---|---|---|",
        ]
        for server, v in sorted(active_servers.items(), key=lambda kv: -kv[1]["calls"]):
            lines.append(
                f"| `{server}` | {v['calls']} | {v['success_rate']:.0%} | {v['error_rate']:.0%} | "
                f"{v['step_efficiency']:.0%} | {v['abandonment_tools']}/{v['tools']} |"
            )
        lines += [
            "",
            "> success-rate = доля вызовов без ошибки; step-eff = доля избыточных вызовов "
            "(повтор с тем же args_hash = retry, ↓ лучше); «брошено тулов» = сколько инструментов "
            "сервера завершили окно на ошибке (abandonment).",
            "",
        ]

    lines += [
        "## Все инструменты",
        "",
        "| Инструмент | Вердикт | Вызовов | success | p95 | repeats | Обоснование |",
        "|---|---|---|---|---|---|---|",
    ]
    for tool, s in ranked:
        lines.append(
            f"| `{tool}` | {_VERDICT_MARK[s['verdict']]} {s['verdict']} | {s['calls']} | "
            f"{s['success_rate']:.0%} | {s['p95_ms']:.0f}ms | {s['repeats']} | {s['reason']} |"
        )
    lines += [
        "",
        "> Латентность p95 = реальная (Pre→Post-пара), не overhead хука. success-rate у built-in "
        "консервативен (Bash non-zero exit не всегда помечается ошибкой). Решение по alert'ам — за человеком; "
        "broken эскалируется авто-задачей (SessionStart-баннер).",
    ]
    return "\n".join(lines) + "\n"


def run(window_days: int = 14, now: datetime | None = None, json_only: bool = False) -> dict:
    """Полный прогон: прочитать окно → вердикты → записать отчёты + verdicts.jsonl + baseline."""
    now = now or datetime.now()
    rows = list(iter_window_rows(now, window_days))
    baseline = _load_json(REPORTS / "baseline.json", {})
    health = compute_health(rows, baseline, now)

    # sidecar json (для SessionStart-баннера): вердикты + alerts
    alerts = [
        {"tool": t, "verdict": s["verdict"], "reason": s["reason"]}
        for t, s in health["tools"].items()
        if s["verdict"] in ("broken", "degraded")
    ]
    sidecar = {
        "generated": health["generated"],
        "window_days": window_days,
        "alerts": alerts,
        "counts": {
            v: sum(1 for s in health["tools"].values() if s["verdict"] == v) for v in _VERDICT_ORDER
        },
        "servers": health.get("servers", {}),  # rule-слой P2.2 (per-server эффективность)
        "tools": health["tools"],
    }
    _atomic_write(REPORTS / "_latest.json", json.dumps(sidecar, ensure_ascii=False, indent=2))
    if not json_only:
        _atomic_write(REPORTS / "_latest.md", render_md(health, window_days))

    # verdicts.jsonl — append-only история (тренд/эскалация)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(REPORTS / "verdicts.jsonl", "a", encoding="utf-8") as f:
        for tool, s in health["tools"].items():
            f.write(
                json.dumps(
                    {
                        "ts": health["generated"],
                        "tool": tool,
                        "verdict": s["verdict"],
                        "window_days": window_days,
                        "calls": s["calls"],
                        "success_rate": s["success_rate"],
                        "reason": s["reason"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    # ratchet baseline (только по тулам с достаточными данными)
    stats_only = {t: s for t, s in health["tools"].items() if s["verdict"] != "unused"}
    _atomic_write(
        REPORTS / "baseline.json",
        json.dumps(update_baseline(baseline, stats_only), ensure_ascii=False, indent=2),
    )
    return sidecar


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Tool health analyzer (roadmap 260713 P1.1)")
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--json-only", action="store_true", help="не писать _latest.md")
    args = ap.parse_args(argv)
    sidecar = run(window_days=args.window_days, json_only=args.json_only)
    print(
        f"tool-health: {sidecar['counts']} | alerts={len(sidecar['alerts'])} "
        f"→ {REPORTS / '_latest.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
