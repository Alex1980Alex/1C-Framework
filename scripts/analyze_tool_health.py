#!/usr/bin/env python3
"""analyze_tool_health.py — авто-анализ здоровья и эффективности инструментов/MCP.

Roadmap 260713 P1.1 + §6 (decision layer). Замыкает цикл «лог → анализ → метрика
→ вердикт» над главным логом инструментов `data/hook-invocations.jsonl`.

Читает канонические строки вызовов (category ∈ {mcp_call, tool_call} — по одной
паре Pre/Post на вызов; category="hook" энфомер-строки НЕ вызовы и игнорируются)
за скользящее окно, агрегирует per-tool (calls / errors / success-rate / реальная
Pre→Post латентность p50/p95 / repeats / abandonment) и присваивает ВЕРДИКТ по
детерминированным правилам §6.1.

NB1 (roadmap 260718): платформа НЕ шлёт PostToolUse на неуспешный built-in вызов
(Bash non-zero exit / Edit «строка не найдена» / Read miss) → Post = только успехи,
error-rate из Post ≡ 0. Честный провал built-in = НЕПАРНЫЙ Pre (Pre без Post);
attempts = завершённые + непарные-Pre, errors = ошибки-Post + непарные-Pre
(completion_stats). Правила вердиктов:

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
ROTATED = ROOT / "data" / "hook-invocations.1.jsonl"  # kept for back-compat/tests
REPORTS = ROOT / "data" / "reports" / "tools"


def _all_logs() -> list[Path]:
    """LOG + все ротированные архивы (roadmap 260718 N-P0.2), новейшие первыми:
    [LOG, .1, .2, …, .N] — по возрастанию номера = по убыванию свежести. Раньше
    аналитика читала только [LOG, .1] → окно 14д не покрывалось (window_incomplete).
    """
    logs = [LOG]
    n = 1
    while True:
        p = LOG.with_name(f"hook-invocations.{n}.jsonl")
        if not p.exists():
            break
        logs.append(p)
        n += 1
    return logs


# scripts/ на path — модуль грузится и как скрипт, и через importlib в тестах.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from tool_effectiveness import (  # single-source rule-слой (roadmap 260713 P2.2)
    completion_stats,
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
P95_FLOOR_MS = 500  # p95 ниже пола НЕ деградация независимо от baseline-ratio (NB2)
ERROR_RATE_RATCHET = 0.05  # +5пп к baseline error-rate = degraded
INEFFECTIVE_MIN_CALLS_ABANDON = 3  # abandonment учитывается при calls ≥ этого
BASELINE_UNUSED_TTL_DAYS = 30  # неактивный тул выбывает из baseline (unused не вечен, #2)
VERDICTS_CAP_BYTES = 5_000_000  # ротация verdicts.jsonl (append-история не безгранична, #3)

# NB2 (roadmap 260718): у инструментов с КОНТЕНТ-ЗАВИСИМОЙ латентностью (Bash с
# pytest-прогоном ≠ echo; Grep по репо ≠ по файлу; execute_code произвольного BSL)
# p95 определяется СОДЕРЖИМЫМ вызова, а не здоровьем инструмента → p95 > 2×baseline
# = FP-фабрика (все 6 живых degraded были такими). Для них p95-ветка degraded
# ОТКЛЮЧЕНА (латентность — информационно в отчёте); error-rate degraded остаётся.
CONTENT_VARIABLE_BUILTINS = frozenset(
    {
        "Bash",
        "PowerShell",
        "Read",
        "Grep",
        "Glob",
        "Skill",
        "Agent",
        "Task",
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
        "TaskOutput",
        "WebFetch",
        "WebSearch",
    }
)
# MCP-операции с рантайм-исполнением произвольного кода/запроса/тестов
CONTENT_VARIABLE_MCP_SUFFIXES = (
    "execute_code",
    "execute_query",
    "run_all_tests",
    "run_module_tests",
    "build_project",
    "run_yaxunit_tests",
)


def _is_content_variable(tool: str) -> bool:
    if tool in CONTENT_VARIABLE_BUILTINS:
        return True
    return any(tool.endswith(s) for s in CONTENT_VARIABLE_MCP_SUFFIXES)


# ── чтение лога за окно ───────────────────────────────────────────────────────


def _to_naive_local(ts: datetime) -> datetime:
    """Aware → локальный naive. Класс бага Sonar parse_dt: naive-vs-aware сравнение
    бросает TypeError — одна aware-строка в логе не должна ронять весь прогон."""
    if ts.tzinfo is not None:
        try:
            return ts.astimezone().replace(tzinfo=None)
        except (ValueError, OSError, OverflowError):
            return ts.replace(tzinfo=None)
    return ts


def iter_window_rows(now: datetime, window_days: int, logs: list[Path] | None = None):
    """Канонические строки вызовов за окно [now-window_days, now]. Битые/чужие пропускаются.
    tz-guard: aware-ts нормализуется к локальному naive (adversarial-review 260713 #9)."""
    cutoff = now - timedelta(days=window_days)
    for log in logs if logs is not None else _all_logs():
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
                if not isinstance(e, dict):  # валидный JSON, но не объект ("123")
                    continue
                if e.get("category") not in CANONICAL_CATEGORIES:
                    continue
                if not e.get("tool"):
                    continue
                ts = _parse_ts(e.get("ts"))
                if ts is None or _to_naive_local(ts) < cutoff:
                    continue
                yield e


def earliest_log_ts(logs: list[Path] | None = None) -> datetime | None:
    """Самый ранний валидный ts доступных лог-файлов (первая парсибельная строка самого
    старого). Детект неполноты окна: двойная ротация могла молча срезать хвост (#7)."""
    # старейший архив (макс. N) — первым: он определяет реальную границу покрытия
    for log in logs if logs is not None else list(reversed(_all_logs())):
        if not log.exists():
            continue
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        ts = _parse_ts(obj.get("ts")) if isinstance(obj, dict) else None
                    except ValueError:
                        continue
                    if ts is not None:
                        return _to_naive_local(ts)
        except OSError:
            continue
    return None


# ── агрегация per-tool ────────────────────────────────────────────────────────


def aggregate_tools(rows: list[dict], now: datetime | None = None) -> dict[str, dict]:
    """Per-tool статистика вызовов.

    **NB1 (roadmap 260718):** платформа НЕ шлёт PostToolUse на неуспешный built-in
    вызов → error-rate из Post-строк структурно ≡ 0 (Post = только успехи). Честный
    провал built-in = **непарный Pre** (``completion_stats``). Поэтому:
      attempts (calls) = завершённые (Post) + провалившиеся-непарные-Pre;
      errors = ошибки-в-Post (MCP isError и пр.) + непарные-Pre;
      in-flight (непарный Pre моложе grace) в attempts НЕ входит — Post ещё может прийти.
    ``paired``-длительности и repeats/abandonment — по завершённым Post (без изменений)."""
    now = now or datetime.now()
    pre: dict[str, list] = defaultdict(list)
    post: dict[str, list] = defaultdict(list)
    for e in rows:
        (post if e.get("event") == "PostToolUse" else pre)[e["tool"]].append(e)

    out: dict[str, dict] = {}
    for tool in set(pre) | set(post):
        posts = sorted(post[tool], key=lambda e: e.get("ts", ""))
        completed = len(posts)
        post_errors = sum(1 for p in posts if p.get("outcome") == "error" or p.get("error"))
        comp = completion_stats(pre[tool], posts, now=now)  # непарные Pre = провалы
        incomplete = comp["failed"]
        attempts = completed + incomplete  # in_flight исключён (ещё не разрешился)
        errors = post_errors + incomplete
        success = completed - post_errors
        durations = pair_durations(pre[tool], posts)
        eff = effectiveness_from_posts(posts)  # retry/abandonment (single-source)
        out[tool] = {
            "calls": attempts,
            "errors": errors,
            "success": success,
            "success_rate": round(success / attempts, 4) if attempts else 1.0,
            "error_rate": round(errors / attempts, 4) if attempts else 0.0,
            "completed": completed,
            "incomplete": incomplete,  # непарные Pre (fail/interrupt) — сигнал NB1
            "in_flight": comp["in_flight"],
            "p50_ms": round(percentile(durations, 0.50), 1),
            "p95_ms": round(percentile(durations, 0.95), 1),
            "paired": len(durations),
            "repeats": eff["repeats"],
            "abandonment": eff["abandonment"],
        }
    return out


# ── вердикт (§6.1) ────────────────────────────────────────────────────────────


def assign_verdict(stats: dict, baseline: dict | None, tool: str = "") -> tuple[str, str]:
    """Вердикт + одно-строчное обоснование. baseline = {p95_ms, error_rate} лучшего окна (или None).
    tool — имя инструмента (для NB2: p95-ветка отключена у content-variable тулов)."""
    calls = stats["calls"]
    sr = stats["success_rate"]
    er = stats["error_rate"]
    success = stats["success"]

    # broken — приоритетнее degraded
    if success == 0 and calls >= MIN_ATTEMPTS_ZERO_SUCCESS:
        return "broken", f"0 успешных из {calls} попыток"
    if calls >= MIN_CALLS_FOR_BROKEN and sr < BROKEN_SUCCESS_RATE:
        return "broken", f"success-rate {sr:.0%} < 50% при {calls} вызовах"

    # degraded — ВСЕ ветки (абсолютный порог И baseline-сравнения) требуют мин. вызовов:
    # единичная транзиентная ошибка (calls=1, er=1.0) через baseline-ветку er−base>5пп
    # иначе светила бы degraded ~14д (adversarial-review 260713 #1b).
    if calls >= DEGRADED_MIN_CALLS:
        if er > DEGRADED_ERROR_RATE:
            return "degraded", f"error-rate {er:.0%} > 10% ({calls} вызовов)"
        if baseline:
            # NB2: p95-regression ТОЛЬКО у инструментов со стабильной латентностью
            # (не content-variable) И выше абсолютного пола — иначе Bash/Grep/execute_code
            # с тяжёлым содержимым вечно degraded (все 6 живых FP были такими).
            base_p95 = baseline.get("p95_ms") or 0
            if (
                not _is_content_variable(tool)
                and stats["p95_ms"] > P95_FLOOR_MS
                and base_p95 > 0
                and stats["p95_ms"] > P95_REGRESSION_FACTOR * base_p95
            ):
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
    stats = aggregate_tools(rows, now=now)
    tools: dict[str, dict] = {}
    for tool, st in stats.items():
        verdict, reason = assign_verdict(st, baseline.get(tool), tool=tool)
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
                "completed": 0,
                "incomplete": 0,
                "in_flight": 0,
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


def update_baseline(baseline: dict, stats: dict[str, dict], now: datetime | None = None) -> dict:
    """Ratchet: baseline = лучший (min) p95 и error-rate per-tool. Ухудшение НЕ пишется
    (чтобы degraded ловился), улучшение обновляет планку.

    Adversarial-review 260713 фиксы:
      #1c — p95 ратчетится ТОЛЬКО при paired>0: p95_ms=0.0 (нет Pre/Post-пар) затягивал
            0.0 в baseline навсегда → p95-regression детект отключался перманентно;
      #2  — записи несут `last_seen`; неактивный тул старше BASELINE_UNUSED_TTL_DAYS
            выбывает (prune) — unused-вердикт не светит вечно по отключённым серверам.
    Выход из «degraded навсегда» (легитимное замедление, #1a) — CLI `--reset-baseline`.
    """
    now = now or datetime.now()
    out: dict[str, dict] = {}
    for tool, prev in baseline.items():
        if tool in stats:
            out[tool] = dict(prev)
            continue
        # неактивный тул: жив пока last_seen моложе TTL (легаси-записи без last_seen
        # получают штамп сейчас — один TTL-цикл на выбытие)
        seen = _parse_ts(prev.get("last_seen")) or now
        if (now - _to_naive_local(seen)).days <= BASELINE_UNUSED_TTL_DAYS:
            out[tool] = {**prev, "last_seen": prev.get("last_seen") or now.isoformat()}
        # иначе — prune (выбыл из baseline, unused-вердикт по нему больше не светит)
    for tool, st in stats.items():
        if st["calls"] < MIN_CALLS_FOR_BROKEN:  # мало данных — не двигаем baseline
            # но активность фиксируем, чтобы тул не выбыл по TTL
            if tool in out:
                out[tool]["last_seen"] = now.isoformat()
            continue
        prev = out.get(tool, {})
        entry = {
            "error_rate": (
                min(prev["error_rate"], st["error_rate"])
                if "error_rate" in prev
                else st["error_rate"]
            ),
            "last_seen": now.isoformat(),
        }
        # p95: только реальные Pre/Post-пары; paired=0 даёт p95=0.0 — НЕ ратчетим (#1c);
        # легаси-запись с затянутым 0.0 лечится заменой на текущее значение
        if st.get("paired", 0) > 0:
            prev_p95 = prev.get("p95_ms") or 0
            entry["p95_ms"] = min(prev_p95, st["p95_ms"]) if prev_p95 > 0 else st["p95_ms"]
        elif prev.get("p95_ms"):
            entry["p95_ms"] = prev["p95_ms"]  # сохранить прежнюю планку
        out[tool] = entry
    return out


# ── I/O ───────────────────────────────────────────────────────────────────────


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_write(path: Path, text: str) -> None:
    """Атомарная запись через уникальный tmp (mkstemp): фиксированное tmp-имя давало
    гонку двух конкурентных прогонов на Windows (PermissionError, #4)."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=path.stem + "-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, str(path))
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _rotate_jsonl(path: Path, cap_bytes: int) -> None:
    """Ротация append-истории: при превышении cap сохранить новейшую половину (#3)."""
    import os
    import tempfile

    try:
        if path.exists() and path.stat().st_size > cap_bytes:
            data = path.read_bytes()[-(cap_bytes // 2) :]
            idx = data.find(b"\n")
            if idx != -1:
                data = data[idx + 1 :]
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="verdicts-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, str(path))
            except OSError:
                os.unlink(tmp)
                raise
    except OSError:
        pass  # ротация не блокирует прогон


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
    if health.get("window_incomplete"):
        lines += [
            f"> ⚠ **Окно неполное**: лог покрывает только с {health.get('window_covered_from', '?')} "
            "(ротация срезала хвост) — вердикты по усечённым данным.",
            "",
        ]

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
        "| Инструмент | Вердикт | Вызовов | success | неуд.* | p95 | repeats | Обоснование |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tool, s in ranked:
        lines.append(
            f"| `{tool}` | {_VERDICT_MARK[s['verdict']]} {s['verdict']} | {s['calls']} | "
            f"{s['success_rate']:.0%} | {s.get('incomplete', 0)} | {s['p95_ms']:.0f}ms | "
            f"{s['repeats']} | {s['reason']} |"
        )
    lines += [
        "",
        "> Латентность p95 = реальная (Pre→Post-пара), не overhead хука. *«неуд.» = непарный "
        "Pre (Pre без Post): платформа НЕ шлёт PostToolUse на неуспешный built-in вызов "
        "(Bash non-zero exit / Edit «строка не найдена» / Read miss) — это ЕДИНСТВЕННЫЙ честный "
        "сигнал провала built-in (NB1, roadmap 260718); блоки гардов сюда не попадают. Решение по "
        "alert'ам — за человеком; broken эскалируется авто-задачей (SessionStart-баннер).",
    ]
    return "\n".join(lines) + "\n"


def run(window_days: int = 14, now: datetime | None = None, json_only: bool = False) -> dict:
    """Полный прогон: прочитать окно → вердикты → записать отчёты + verdicts.jsonl + baseline."""
    now = now or datetime.now()
    rows = list(iter_window_rows(now, window_days))
    baseline = _load_json(REPORTS / "baseline.json", {})
    health = compute_health(rows, baseline, now)

    # неполнота окна (#7): самый ранний доступный ts моложе cutoff → часть окна срезана
    # ротацией; вердикты по усечённым данным помечаются, а не выдаются как полные
    cutoff = now - timedelta(days=window_days)
    earliest = earliest_log_ts()
    window_incomplete = bool(earliest and earliest > cutoff + timedelta(days=1))
    if window_incomplete:
        health["window_incomplete"] = True
        health["window_covered_from"] = earliest.isoformat(timespec="seconds")

    # sidecar json (для SessionStart-баннера): вердикты + alerts
    alerts = [
        {"tool": t, "verdict": s["verdict"], "reason": s["reason"]}
        for t, s in health["tools"].items()
        if s["verdict"] in ("broken", "degraded")
    ]
    sidecar = {
        "generated": health["generated"],
        "window_days": window_days,
        "window_incomplete": window_incomplete,
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

    # verdicts.jsonl — append-история с ротацией (#3)
    REPORTS.mkdir(parents=True, exist_ok=True)
    _rotate_jsonl(REPORTS / "verdicts.jsonl", VERDICTS_CAP_BYTES)
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

    # ratchet baseline (только по тулам с достаточными данными; TTL-prune внутри)
    stats_only = {t: s for t, s in health["tools"].items() if s["verdict"] != "unused"}
    _atomic_write(
        REPORTS / "baseline.json",
        json.dumps(update_baseline(baseline, stats_only, now), ensure_ascii=False, indent=2),
    )
    return sidecar


def reset_baseline(tools: list[str] | None = None) -> int:
    """Сброс ratchet-baseline (#1a): единственный выход из «degraded навсегда» при
    ЛЕГИТИМНОМ замедлении/росте error-rate. `tools=None` → сброс всего файла;
    иначе — удалить перечисленные ключи. Возвращает число удалённых записей."""
    path = REPORTS / "baseline.json"
    baseline = _load_json(path, {})
    if not baseline:
        return 0
    if tools is None:
        removed = len(baseline)
        _atomic_write(path, "{}")
        return removed
    removed = 0
    for t in tools:
        if t in baseline:
            del baseline[t]
            removed += 1
    _atomic_write(path, json.dumps(baseline, ensure_ascii=False, indent=2))
    return removed


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Tool health analyzer (roadmap 260713 P1.1)")
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--json-only", action="store_true", help="не писать _latest.md")
    ap.add_argument(
        "--reset-baseline",
        nargs="*",
        metavar="TOOL",
        help="сбросить ratchet-baseline: без аргументов — целиком, иначе перечисленные тулы "
        "(выход из «degraded навсегда» при легитимном замедлении)",
    )
    args = ap.parse_args(argv)
    if args.reset_baseline is not None:
        n = reset_baseline(args.reset_baseline or None)
        print(f"baseline reset: удалено {n} записей → {REPORTS / 'baseline.json'}")
        return 0
    sidecar = run(window_days=args.window_days, json_only=args.json_only)
    inc = " ⚠ окно неполное (ротация срезала хвост)" if sidecar.get("window_incomplete") else ""
    print(
        f"tool-health: {sidecar['counts']} | alerts={len(sidecar['alerts'])}{inc} "
        f"→ {REPORTS / '_latest.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
