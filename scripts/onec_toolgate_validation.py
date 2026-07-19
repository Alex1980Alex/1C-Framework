#!/usr/bin/env python3
"""Авто-валидация ADR-035 Фазы 1 — advisory T1-T2 в onec-task-completion-stop.

Наблюдает advisory-события (`.claude/cache/onec-toolgate-events.jsonl`, пишутся на КАЖДОЙ
1С-задаче хуком `onec-task-completion-stop`) в окне 2026-06-22 → 2026-07-06 (14 дней) и
выдаёт per-tool рекомендацию для Фазы 2 ADR-035 (промоут T1-T2 в hard).

Метрика — **presence_rate** (доля 1С-задач, где инструмент уже использован):
  - presence_rate >= PROMOTE_RATE (0.6) → "promote-candidate": инструмент уже частая практика
    → hard-блок редко-триггерился бы (низкая фрикция);
  - presence_rate < PROMOTE_RATE → "keep-advisory";
  - total < MIN_SAMPLES (8 задач) → "insufficient-data".
Для `impact` дополнительно — presence на edit-подмножестве (config_edit=True): более релевантный
знаменатель (impact ценен перед правкой существующего кода) и частичный фильтр применимости.

⚠ **CAVEAT (не авто-промоут):** presence_rate — лишь ПРОКСИ. Высокий presence может отражать,
что advisory УЖЕ работает (survivorship), а не что hard-блок безопасен; presence не различает
«инструмент неприменим к части задач» vs «применим и всегда вызывается». Поэтому "promote-candidate"
= КАНДИДАТ, требующий **ручной проверки применимости per-tool** + (в идеале) cross-task follow_rate,
а НЕ слепого флипа в hard. Решение о промоуте — за владельцем пайплайна (ADR-035 Фаза 2).

Запуск: python scripts/onec_toolgate_validation.py [--json] [--final] [--no-report]
Отчёт: data/reports/memory/onec_toolgate_validation_<stamp>.md. Каркас — acceptance_common.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from acceptance_common import emit as _emit
from acceptance_common import parse_dt as _parse_dt
from acceptance_common import read_jsonl as _read_jsonl
from acceptance_common import render_acceptance, window_day

EVENTS_LOG = PROJECT_ROOT / ".claude" / "cache" / "onec-toolgate-events.jsonl"

WINDOW_START = datetime(2026, 6, 22)  # дата приземления ADR-035 Фазы 1
WINDOW_END = datetime(2026, 7, 6)  # +14 дней
WINDOW_DAYS = 14
MIN_SAMPLES = 8  # 1С-задач за окно для надёжного вердикта
PROMOTE_RATE = 0.6  # presence_rate >= → инструмент частая практика → promote-candidate

TOOLS = ("impact", "debug_trace", "ref_search")
TOOL_HUMAN = {
    "impact": "bsl_impact_analysis (перед правкой экспортного метода)",
    "debug_trace": "1c-debug live BP-trace (runtime-логика)",
    "ref_search": "bsl_search/similar (эталон на Планировании)",
}


def _verdict_for(total: int, rate: float | None) -> str:
    if total < MIN_SAMPLES:
        return "insufficient-data"
    if rate is not None and rate >= PROMOTE_RATE:
        return "promote-candidate"  # кандидат — НЕ авто-hard (нужна ручная проверка применимости)
    return "keep-advisory"


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    recs = []
    for r in _read_jsonl(EVENTS_LOG):
        dt = _parse_dt(r.get("ts"))
        if dt is None or dt < WINDOW_START:
            continue
        recs.append(r)

    total = len(recs)
    edit_tasks = sum(1 for r in recs if r.get("config_edit"))

    per: dict[str, dict[str, Any]] = {}
    for t in TOOLS:
        present = sum(1 for r in recs if r.get(t))
        rate = round(present / total, 3) if total else None
        per[t] = {"present": present, "rate": rate, "verdict": _verdict_for(total, rate)}

    # impact на edit-подмножестве — более релевантный знаменатель + частичный фильтр применимости
    impact_on_edit = sum(1 for r in recs if r.get("config_edit") and r.get("impact"))
    impact_rate_edit = round(impact_on_edit / edit_tasks, 3) if edit_tasks else None

    # В2 260718 W1: честный знаменатель вместо survivorship-presence — поле impact_applicable
    # с 2026-07-18. Старые записи без поля дают .get()→None (falsy) → в знаменатель не входят.
    applicable_tasks = sum(1 for r in recs if r.get("impact_applicable"))
    impact_on_applicable = sum(1 for r in recs if r.get("impact_applicable") and r.get("impact"))
    impact_rate_applicable = (
        round(impact_on_applicable / applicable_tasks, 3) if applicable_tasks else None
    )

    # рек.3 (2026-07-19): YAxUnit-смоук на том же applicable-знаменателе (экспортная серверная
    # поверхность); yaxunit_applicable появился 2026-07-19 — старые записи без поля не в знаменателе.
    yaxunit_applicable_tasks = sum(1 for r in recs if r.get("yaxunit_applicable"))
    yaxunit_on_applicable = sum(
        1 for r in recs if r.get("yaxunit_applicable") and r.get("yaxunit_smoke")
    )
    yaxunit_rate_applicable = (
        round(yaxunit_on_applicable / yaxunit_applicable_tasks, 3)
        if yaxunit_applicable_tasks
        else None
    )

    if total < MIN_SAMPLES:
        recommendation = "insufficient-data"
    else:
        cand = [t for t in TOOLS if per[t]["verdict"] == "promote-candidate"]
        recommendation = (
            ("promote-candidate (manual-review): " + ", ".join(cand)) if cand else "keep-advisory"
        )

    return {
        "now": now.isoformat(timespec="seconds"),
        "window": f"{WINDOW_START.date()} → {WINDOW_END.date()}",
        "day": window_day(now, WINDOW_START, WINDOW_DAYS),
        "window_closed": now >= WINDOW_END,
        "total_tasks": total,
        "edit_tasks": edit_tasks,
        "per_tool": per,
        "impact_rate_on_edits": impact_rate_edit,
        "applicable_tasks": applicable_tasks,  # В2: задач с правкой экспортного метода
        "impact_rate_on_applicable": impact_rate_applicable,  # honest denominator
        "yaxunit_applicable_tasks": yaxunit_applicable_tasks,  # рек.3: те же экспорт-задачи
        "yaxunit_rate_on_applicable": yaxunit_rate_applicable,  # honest denominator
        "recommendation": recommendation,
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    """Готовность вердикта (НЕ качество): накоплены ли данные и вычислено ли решение."""
    return {
        "данные накоплены (>=8 задач или окно закрыто)": (
            m["total_tasks"] >= MIN_SAMPLES or m["window_closed"]
        ),
        "решение вычислено (не insufficient-data)": m["recommendation"] != "insufficient-data",
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    rec = m["recommendation"]
    if rec.startswith("promote-candidate"):
        tools = rec.split(": ", 1)[1]
        rec_human = (
            f"КАНДИДАТЫ в hard (presence высок): {tools}. НЕ авто-флип: проверить применимость "
            "per-tool вручную (presence может отражать работу advisory, не безопасность hard) — "
            "решение за владельцем (ADR-035 Фаза 2)"
        )
    elif rec == "keep-advisory":
        rec_human = (
            "РЕКОМЕНДАЦИЯ: оставить advisory (инструменты не достигли порога частой практики)"
        )
    else:
        rec_human = "недостаточно данных — продолжить наблюдение (нужно >=8 1С-задач за окно)"
    detail = [
        f"- Снято: {m['now']}",
        f"- 1С-задач за окно: {m['total_tasks']} (из них edit-задач: {m['edit_tasks']})",
    ]
    for t in TOOLS:
        p = m["per_tool"][t]
        detail.append(
            f"- {TOOL_HUMAN[t]}: presence {p['present']}/{m['total_tasks']} "
            f"(rate {p['rate']}) -> {p['verdict']}"
        )
    detail.append(f"- impact на edit-подмножестве: rate {m['impact_rate_on_edits']}")
    detail.append(
        f"- impact на ПРИМЕНИМОМ (правка экспортного метода, честный знаменатель, В2): "
        f"{m.get('impact_rate_on_applicable')} на {m.get('applicable_tasks', 0)} задач"
    )
    detail.append(
        f"- YAxUnit-смоук на ПРИМЕНИМОМ (правка экспортного метода, рек.3): "
        f"{m.get('yaxunit_rate_on_applicable')} на {m.get('yaxunit_applicable_tasks', 0)} задач"
    )
    detail.append(f"- **{rec_human}**")
    return render_acceptance(
        f"# onec-toolgate validation (ADR-035 Фаза 1) — день {m['day']}/{WINDOW_DAYS} ({m['window']})",
        m,
        crit,
        final=final,
        detail_lines=detail,
        roadmap_rel=".claude/skills/architecture-research/adr/035-mandatory-high-leverage-1c-tools.md",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-035 Фаза 1 validation (advisory T1-T2)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--final", action="store_true", help="принудительный вердикт до конца окна")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()
    m = collect_metrics()
    crit = evaluate(m)
    if args.json:
        _emit(
            json.dumps({**m, "criteria": crit, "all_pass": all(crit.values())}, ensure_ascii=False)
        )
        return 0
    _emit(
        render(m, crit, args.final),
        report_name=None if args.no_report else "onec_toolgate_validation",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
