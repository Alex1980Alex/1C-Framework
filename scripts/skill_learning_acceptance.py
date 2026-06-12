#!/usr/bin/env python3
"""Acceptance-метрики skill-learning revival (roadmap 260611 §P4).

Окно наблюдения: 2026-06-12 → 2026-06-26. Критерии приёмки:
  1. capture >= 10           — записи в pending/saved/rejected, созданные в окне
                               (+ dup-события: повторный capture тоже сигнал входа)
  2. median pending age < 7d — медианный возраст текущего pending
  3. rejects >= 1            — записи в rejected (вкл. ttl_expired)
  4. surfacing arm fired     — arms.skill_learning > 0 в memory-first-surfacing.log
  5. dup/dup_rejected != 0   — dedup работает (ingest-лог, store=skill_learning)

Все источники локальные (JSONL + логи), без сети. Запуск:
  python scripts/skill_learning_acceptance.py [--json] [--final] [--no-report]
--final принудительно считает вердикт (иначе вердикт = PENDING до конца окна).
Отчёт пишется в data/reports/memory/skill_learning_acceptance_<stamp>.md.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Общий каркас acceptance-скриптов (260612 §P4): JSONL/даты/рендер/emit — единые.
from acceptance_common import emit as _emit
from acceptance_common import parse_dt as _parse_dt
from acceptance_common import read_jsonl as _read_jsonl
from acceptance_common import render_acceptance, window_day

SL_DIR = PROJECT_ROOT / "data" / "skill_learning"
PENDING = SL_DIR / "pending_patterns.jsonl"
SAVED = SL_DIR / "patterns.jsonl"
REJECTED = SL_DIR / "rejected_patterns.jsonl"
CACHE_DIR = Path(os.environ.get("CLAUDE_CACHE_DIR", PROJECT_ROOT / ".claude" / "cache"))
SURFACING_LOG = CACHE_DIR / "memory-first-surfacing.log"
INGEST_LOG = CACHE_DIR / "memory-ingestion.log"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"

WINDOW_START = datetime(2026, 6, 12)
WINDOW_END = datetime(2026, 6, 26)

CAPTURE_TARGET = 10
MEDIAN_AGE_TARGET_DAYS = 7.0


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    pending = _read_jsonl(PENDING)
    saved = _read_jsonl(SAVED)
    rejected = _read_jsonl(REJECTED)

    def _in_window(rec: dict[str, Any]) -> bool:
        dt = _parse_dt(rec.get("created_at"))
        return dt is not None and dt >= WINDOW_START

    captured = [r for r in pending + saved + rejected if _in_window(r)]

    # dup-события из ingest-лога: повторный capture не создаёт запись, но это
    # тоже факт входа (и заодно критерий 5 — dedup работает)
    dup_events = 0
    sl_ingest_events = 0
    for rec in _read_jsonl(INGEST_LOG):
        if rec.get("store") != "skill_learning":
            continue
        dt = _parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is None or dt < WINDOW_START:
            continue
        sl_ingest_events += 1
        if rec.get("action") == "dup":
            dup_events += 1

    ages = [
        (now - dt).total_seconds() / 86400
        for r in pending
        if (dt := _parse_dt(r.get("created_at"))) is not None
    ]
    median_age = round(statistics.median(ages), 1) if ages else None

    rejects_in_window = [
        r for r in rejected if (dt := _parse_dt(r.get("rejected_at"))) and dt >= WINDOW_START
    ]

    # arm=skill_learning в surfacing-логе: invocations, где плечо дало >0 хитов
    arm_fired = 0
    arm_invocations = 0
    for rec in _read_jsonl(SURFACING_LOG):
        arms = rec.get("arms")
        if not isinstance(arms, dict) or "skill_learning" not in arms:
            continue
        arm_invocations += 1
        if arms.get("skill_learning", 0) > 0:
            arm_fired += 1

    return {
        "now": now.isoformat(timespec="seconds"),
        "window": f"{WINDOW_START.date()} → {WINDOW_END.date()}",
        "day": window_day(now, WINDOW_START),
        "window_closed": now >= WINDOW_END,
        "counts": {"pending": len(pending), "saved": len(saved), "rejected": len(rejected)},
        "captures": len(captured) + dup_events,
        "captures_new_records": len(captured),
        "median_pending_age_days": median_age,
        "rejects": len(rejects_in_window),
        "surfacing_arm_fired": arm_fired,
        "surfacing_arm_invocations": arm_invocations,
        "dup_events": dup_events,
        "sl_ingest_events": sl_ingest_events,
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    """Per-criterion PASS/FAIL. median-age: пустой pending = vacuous PASS."""
    med = m["median_pending_age_days"]
    return {
        "captures>=10": m["captures"] >= CAPTURE_TARGET,
        "median_pending_age<7d": med is None or med < MEDIAN_AGE_TARGET_DAYS,
        "rejects>=1": m["rejects"] >= 1,
        "surfacing_arm_fired": m["surfacing_arm_fired"] > 0,
        "dup_nonzero": m["dup_events"] > 0,
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    verdict = (
        ("PASS" if all(crit.values()) else "FAIL")
        if (final or m["window_closed"])
        else "PENDING (окно открыто)"
    )
    lines = [
        f"# skill-learning acceptance — день {m['day']}/14 ({m['window']})",
        "",
        f"- Снято: {m['now']}; silo: {m['counts']}",
        f"- captures: {m['captures']} (новых записей {m['captures_new_records']}"
        f" + dup {m['dup_events']}) — цель >={CAPTURE_TARGET}",
        f"- median pending age: {m['median_pending_age_days']}d — цель <{MEDIAN_AGE_TARGET_DAYS}",
        f"- rejects в окне: {m['rejects']} — цель >=1",
        f"- surfacing arm=skill_learning: fired {m['surfacing_arm_fired']}"
        f"/{m['surfacing_arm_invocations']} invocations — цель >0",
        f"- dup-события (dedup работает): {m['dup_events']} — цель >0",
        "",
        "| Критерий | Статус |",
        "|---|---|",
    ]
    for k, ok in crit.items():
        lines.append(f"| {k} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", f"**Вердикт: {verdict}**"]
    if verdict in ("PASS", "FAIL"):
        lines.append(
            "\nЗафиксировать вердикт в §18 "
            "docs/roadmap/260611_ROADMAP_SKILL_LEARNING_REVIVAL.md."
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-learning acceptance (roadmap 260611 §P4)")
    ap.add_argument("--json", action="store_true", help="JSON output вместо markdown")
    ap.add_argument("--final", action="store_true", help="принудительный вердикт до конца окна")
    ap.add_argument("--no-report", action="store_true", help="не писать файл отчёта")
    args = ap.parse_args()

    m = collect_metrics()
    crit = evaluate(m)
    if args.json:
        out = json.dumps(
            {**m, "criteria": crit, "all_pass": all(crit.values())}, ensure_ascii=False
        )
        sys.stdout.buffer.write(out.encode("utf-8") + b"\n")
        return 0
    text = render(m, crit, args.final)
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    if not args.no_report:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d")
            (REPORTS_DIR / f"skill_learning_acceptance_{stamp}.md").write_text(
                text, encoding="utf-8"
            )
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
