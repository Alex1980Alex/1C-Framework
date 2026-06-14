#!/usr/bin/env python3
"""Acceptance-метрики memory-ai full verification (roadmap 260612 §P4).

Окно наблюдения: 2026-06-12 → 2026-06-26. Критерии приёмки:
  1. episodes>=5        — новые строки вне ``session_summary`` в окне
  2. surfacing sqlite>0 — R1-плечо отдало >0 хитов хотя бы в одной invocation
                          окна (B1: эпизодика реально всплывает)
  3. dup_nonzero        — dup-события store=memory_ai в ingest-логе (W1-дедуп жив)
  4. hash_complete      — 0 строк без content_hash в metadata (write-contract
                          не зарастает после P0.2-бэкфилла)
  5. reflection>=1      — ≥1 DERIVES_FROM-ребро создано в окне (R4 консолидация)
  6. archive_ran        — job archive_episodic исполнился ≥1 раз (P3.2; целостность
                          охраняет unit-тест, здесь — факт исполнения)

Все источники локальные (SQLite + JSONL-логи), без сети. Запуск:
  python scripts/memory_ai_acceptance.py [--json] [--final] [--no-report]
--final принудительно считает вердикт (иначе PENDING до конца окна).
Отчёт: data/reports/memory/memory_ai_acceptance_<stamp>.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acceptance_common import (
    emit,
    parse_dt,
    read_jsonl,
    render_acceptance,
    window_day,
)

CACHE_DIR = Path(os.environ.get("CLAUDE_CACHE_DIR", PROJECT_ROOT / ".claude" / "cache"))
SURFACING_LOG = CACHE_DIR / "memory-first-surfacing.log"
INGEST_LOG = CACHE_DIR / "memory-ingestion.log"
MAINTENANCE_RUNS = CACHE_DIR / "memory-maintenance-runs.jsonl"

WINDOW_START = datetime(2026, 6, 12)
WINDOW_END = datetime(2026, 6, 26)
EPISODES_TARGET = 5


def _db_path() -> Path:
    from memory.ai_memory.db import resolve_db_path

    return resolve_db_path()


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()

    episodes = 0
    no_hash = 0
    total_rows = 0
    try:
        conn = sqlite3.connect(str(_db_path()))
        try:
            for content_dt, category, raw_md in conn.execute(
                "SELECT created_at, category, metadata FROM important_messages"
            ):
                total_rows += 1
                try:
                    md = json.loads(raw_md) if raw_md else {}
                except (json.JSONDecodeError, TypeError):
                    md = {}
                if not (isinstance(md, dict) and md.get("content_hash")):
                    no_hash += 1
                dt = parse_dt(content_dt)
                if (
                    dt is not None
                    and dt >= WINDOW_START
                    and (category or "general") != "session_summary"
                ):
                    episodes += 1
        finally:
            conn.close()
    except sqlite3.Error:
        pass

    # R1 sqlite-плечо в surfacing-логе (окно по ts)
    sqlite_fired = 0
    invocations = 0
    for rec in read_jsonl(SURFACING_LOG):
        dt = parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is None or dt < WINDOW_START:
            continue
        layers = rec.get("layers")
        if not isinstance(layers, dict):
            continue
        invocations += 1
        if (layers.get("sqlite") or 0) > 0:
            sqlite_fired += 1

    # dup-события memory_ai в ingest-логе
    dup_events = 0
    for rec in read_jsonl(INGEST_LOG):
        if rec.get("store") != "memory_ai" or rec.get("action") != "dup":
            continue
        dt = parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is not None and dt >= WINDOW_START:
            dup_events += 1

    # reflection: DERIVES_FROM-рёбра, созданные в окне
    derives_in_window = 0
    try:
        lr = Path(
            os.environ.get("LINK_REGISTRY_PATH") or PROJECT_ROOT / "data" / "link_registry.db"
        )
        if lr.exists():
            conn = sqlite3.connect(str(lr))
            try:
                for (created_at,) in conn.execute(
                    "SELECT created_at FROM entity_links WHERE link_type = 'derives_from'"
                ):
                    dt = parse_dt(created_at)
                    if dt is not None and dt >= WINDOW_START:
                        derives_in_window += 1
            finally:
                conn.close()
    except sqlite3.Error:
        pass

    # archive_episodic исполнился успешно: trace-маппинг jobs→rc даёт 0 (success),
    # -1 (error), "skipped" (skip) — считаем строго rc==0 (code-verify finding:
    # `!= "skipped"` был вакуумно-истинным на None/-1).
    archive_runs = 0
    for rec in read_jsonl(MAINTENANCE_RUNS):
        dt = parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is None or dt < WINDOW_START:
            continue
        jobs = rec.get("jobs")
        if isinstance(jobs, dict) and jobs.get("archive_episodic") == 0:
            archive_runs += 1

    return {
        "now": now.isoformat(timespec="seconds"),
        "window": f"{WINDOW_START.date()} → {WINDOW_END.date()}",
        "day": window_day(now, WINDOW_START),
        "window_closed": now >= WINDOW_END,
        "total_rows": total_rows,
        "episodes_non_session": episodes,
        "rows_without_hash": no_hash,
        "surfacing_sqlite_fired": sqlite_fired,
        "surfacing_invocations": invocations,
        "dup_events": dup_events,
        "derives_from_in_window": derives_in_window,
        "archive_runs": archive_runs,
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    return {
        f"episodes>={EPISODES_TARGET}": m["episodes_non_session"] >= EPISODES_TARGET,
        "surfacing_sqlite_fired": m["surfacing_sqlite_fired"] > 0,
        "dup_nonzero": m["dup_events"] > 0,
        "hash_complete": m["rows_without_hash"] == 0,
        "reflection>=1": m["derives_from_in_window"] >= 1,
        "archive_ran": m["archive_runs"] >= 1,
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    detail = [
        f"- Снято: {m['now']}; строк в БД: {m['total_rows']}",
        f"- эпизоды вне session_summary в окне: {m['episodes_non_session']}"
        f" — цель >={EPISODES_TARGET}",
        f"- surfacing layers.sqlite>0: {m['surfacing_sqlite_fired']}"
        f"/{m['surfacing_invocations']} invocations — цель >0",
        f"- dup-события memory_ai: {m['dup_events']} — цель >0",
        f"- строк без content_hash: {m['rows_without_hash']} — цель 0",
        f"- DERIVES_FROM в окне (reflection): {m['derives_from_in_window']} — цель >=1",
        f"- archive_episodic исполнений: {m['archive_runs']} — цель >=1",
    ]
    return render_acceptance(
        f"# memory-ai acceptance — день {m['day']}/14 ({m['window']})",
        m,
        crit,
        final=final,
        detail_lines=detail,
        roadmap_rel="docs/roadmap/260612_ROADMAP_MEMORY_AI_FULL_VERIFICATION.md",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="memory-ai acceptance (roadmap 260612 §P4)")
    ap.add_argument("--json", action="store_true", help="JSON output вместо markdown")
    ap.add_argument("--final", action="store_true", help="принудительный вердикт до конца окна")
    ap.add_argument("--no-report", action="store_true", help="не писать файл отчёта")
    args = ap.parse_args()

    m = collect_metrics()
    crit = evaluate(m)
    if args.json:
        emit(
            json.dumps({**m, "criteria": crit, "all_pass": all(crit.values())}, ensure_ascii=False)
        )
        return 0
    emit(
        render(m, crit, args.final), report_name=None if args.no_report else "memory_ai_acceptance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
