#!/usr/bin/env python3
"""Читатель лога аномалий записи session_state (`.claude/cache/session-state-failures.jsonl`).

Пишет этот лог единая точка мутаций `session_state._mutate` (2026-07-26). Читатель нужен,
чтобы сток не оказался write-only: в этом репозитории такое уже случалось —
`verdicts.jsonl` писался месяц, пока не появился `tool_verdict_history` (260718 N-P1.2).
Потребители: каденс-хук (строка в баннер) и человек (`--print` из CLI).

События:
  - `mutation_lost`  — мутация НЕ сохранена, исключение ре-райзнуто, но вызывающий его глушит
                       ⇒ факт виден только здесь. Это дефект: state разошёлся с реальностью.
  - `lock_fail_open` — межпроцессный лок не взяли за отведённое ожидание, мутация прошла БЕЗ
                       взаимного исключения. Не дефект сам по себе, а ведущий индикатор
                       риска lost-update: рост здесь предсказывает `mutation_lost`.

stdlib-only, ничего не кидает: любая проблема чтения → пустой результат.

CLI:
    python .claude/hooks/shared/session_state_failures.py --print [--since 7d]
    python .claude/hooks/shared/session_state_failures.py --json  [--since 24h]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

MUTATION_LOST = "mutation_lost"
LOCK_FAIL_OPEN = "lock_fail_open"


def _log_path() -> Path:
    from shared.session_state import _faillog_path  # ленивый импорт: единый резолв пути

    return _faillog_path()


def _parse_ts(value: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt  # одна шкала с naive-писателем


def parse_since(spec: str) -> float:
    """`7d` / `24h` / `90m` / `7` → дни (float). Непонятное → 7 дней."""
    spec = (spec or "").strip().lower()
    try:
        if spec.endswith("d"):
            return float(spec[:-1])
        if spec.endswith("h"):
            return float(spec[:-1]) / 24
        if spec.endswith("m"):
            return float(spec[:-1]) / 1440
        return float(spec)
    except ValueError:
        return 7.0


def read_events(since_days: float = 7.0, path: Path | None = None) -> list[dict]:
    """Записи лога не старше `since_days` (без ts — берём: лучше показать, чем потерять)."""
    try:
        log = path or _log_path()
        if not log.is_file():
            return []
        raw = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    cutoff = datetime.now() - timedelta(days=since_days)
    out: list[dict] = []
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(rec, dict):
            continue
        ts = _parse_ts(rec.get("ts"))
        if ts is not None and ts < cutoff:
            continue
        out.append(rec)
    return out


def summary(events: list[dict]) -> dict:
    """Агрегаты для баннера/отчёта: сколько, по каким операциям, с какими ошибками."""
    lost = [e for e in events if e.get("event") == MUTATION_LOST]
    fail_open = [e for e in events if e.get("event") == LOCK_FAIL_OPEN]
    return {
        "total": len(events),
        "lost": len(lost),
        "fail_open": len(fail_open),
        "by_op": dict(Counter(str(e.get("op") or "?") for e in lost).most_common()),
        "by_error": dict(Counter(str(e.get("error_type") or "?") for e in lost).most_common()),
        "last_ts": max((str(e.get("ts") or "") for e in events), default=""),
    }


def banner_line(since_days: float = 7.0) -> str | None:
    """Строка для баннера каденса или None, когда потерь нет.

    Молчим при отсутствии `mutation_lost`: одинокий `lock_fail_open` — не поломка, а
    характеристика нагрузки; шумом в баннере он обесценил бы сигнал.
    """
    stat = summary(read_events(since_days))
    if not stat["lost"]:
        return None
    ops = ", ".join(f"{op}×{n}" for op, n in list(stat["by_op"].items())[:3])
    errs = ", ".join(stat["by_error"]) or "?"
    days = int(since_days) if float(since_days).is_integer() else since_days
    tail = f"; fail-open лока {stat['fail_open']}" if stat["fail_open"] else ""
    return (
        f"[STATE-WRITE] {stat['lost']} потерянных мутаций session_state за {days}д "
        f"({ops}; {errs}){tail}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Аномалии записи session_state")
    ap.add_argument("--since", default="7d", help="окно: 7d / 24h / 90m (default 7d)")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--print", dest="human", action="store_true", help="человекочитаемо")
    args = ap.parse_args()

    days = parse_since(args.since)
    events = read_events(days)
    stat = summary(events)
    if args.json:
        print(json.dumps({"since_days": days, **stat}, ensure_ascii=False, indent=1))
        return 0
    line = banner_line(days)
    print(f"Лог: {_log_path()}")
    print(
        f"Окно: {days}д · записей {stat['total']} · потерь {stat['lost']} · "
        f"fail-open {stat['fail_open']} · последняя {stat['last_ts'] or '—'}"
    )
    if stat["by_op"]:
        print("По операциям: " + ", ".join(f"{k}×{v}" for k, v in stat["by_op"].items()))
    if stat["by_error"]:
        print("По ошибкам:   " + ", ".join(f"{k}×{v}" for k, v in stat["by_error"].items()))
    print(line or "[OK] потерь мутаций в окне нет")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI-обёртка
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(main())
