#!/usr/bin/env python3
"""Acceptance-метрики memory-ai full verification (roadmap 260612 §P4).

Окно наблюдения: 2026-06-12 → 2026-06-26. Критерии приёмки:
  1. episodes>=5        — новые строки вне ``session_summary`` в окне
  2. surfacing sqlite>0 — R1-плечо отдало >0 хитов хотя бы в одной invocation
                          окна (B1: эпизодика реально всплывает)
  3. dup_nonzero        — dup-события store=memory_ai в ingest-логе (W1-дедуп жив)
  4. hash_complete      — 0 строк без content_hash в metadata (write-contract
                          не зарастает после P0.2-бэкфилла)
  5. reflection_reachable — триггер консолидации достижим на текущем корпусе
                          (``clusters_triggered>0``, реальный ``reflect(dry_run=True)``)
  6. reflection_wrote   — ≥1 ingest-событие с ``harvester="reflection"``:
                          ``ingest_items`` эмитит статистику ТОЛЬКО при ``not dry_run``,
                          значит событие = доказательство, что джоб реально писал
  7. archive_ran        — job archive_episodic исполнился ≥1 раз (P3.2; целостность
                          охраняет unit-тест, здесь — факт исполнения)

Почему 5+6, а не «создано ≥1 ребра В ОКНЕ» (замена 2026-07-17): reflection
идемпотентен (content_hash-дедуп) и отработал 2026-06-11 — за день до открытия окна.
Корректно работающий идемпотентный джоб на почти статичном корпусе обязан давать 0
новых рёбер, поэтому оконный счётчик был **неудовлетворим по построению** —
единственный из шести, измерявший ОДНОРАЗОВОЕ событие оконным фильтром. Важно: он
не «проспал» баг (он честно горел красным) — он просто не отличал «сломано» от
«нечего делать», а лечится это наблюдением ЗАПИСИ, а не проверкой состояния.
Отсюда пара: 5 ловит мёртвый триггер (до фикса ``min_cluster=3`` → triggered=0 →
FAIL), 6 ловит возврат в dry-run (флаг ``MEMORY_MAINTENANCE_APPLY_REFLECT`` живёт в
gitignored settings.local.json — клон/другая машина/удалённая строка = 5 недель
«успешных» прогонов с rc=0 и нулём записей). Вариант «рёбер всего ≥1» отвергнут:
он был бы зелёным всё это время и не ловит ни того, ни другого. Ср. вакуумно-истинный
``archive_ran`` ниже — тот же класс дефекта, зеркально.

Все источники локальные (SQLite + JSONL-логи + Jaccard-просчёт), без сети. Запуск:
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
from datetime import datetime, timedelta
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
# Freshness bound for criterion 6. Counting all history would latch green forever after
# a single write and stop detecting the regression the criterion exists for. The cadence
# fires every ~10 sessions, so 30d is several cadences of slack.
REFLECTION_WRITE_MAX_AGE_DAYS = int(os.environ.get("REFLECTION_WRITE_MAX_AGE_DAYS", "30"))


def _db_path() -> Path:
    from memory.ai_memory.db import resolve_db_path

    return resolve_db_path()


def _reflection_clusters_triggered() -> int:
    """Is reflection's consolidation trigger reachable on the current corpus?

    Drives the real ``reflect(dry_run=True)`` rather than re-deriving the trigger:
    re-implementing it here would drop the ``importance_theta`` branch and start the
    very drift this task just removed (a hardcoded min_cluster copy in reflect_memory.py
    is what kept the trigger pinned at an unreachable 3). A dry run is fully local —
    ``ingest_items`` builds no client and never embeds on that path — so the module's
    "no network" contract holds; ~10ms.

    Loaded by file path, NOT via ``sys.path`` + ``import shared.reflection``: this
    module already puts <repo>/src at sys.path[0], so a bare ``shared`` resolves to
    ``src/shared`` and the import dies silently ([[feedback-hook-src-shared-collision]]).

    Returns 0 on any failure → criterion reads NO. An acceptance gate that cannot
    measure must fail loudly, not pass quietly.
    """
    try:
        import importlib.util as ilu

        path = PROJECT_ROOT / ".claude" / "hooks" / "shared" / "reflection.py"
        spec = ilu.spec_from_file_location("reflection_for_acceptance", path)
        if spec is None or spec.loader is None:
            return 0
        rf = ilu.module_from_spec(spec)
        sys.modules[spec.name] = rf  # see the @dataclass note in reflection.py's fallback
        try:
            spec.loader.exec_module(rf)
        except Exception:
            sys.modules.pop(spec.name, None)  # no half-initialised module left behind
            raise
        # link_fn=None + dry_run=True -> plan only: no upsert, no links, no ingest event
        return int(rf.reflect(dry_run=True).get("clusters_triggered", 0))
    except Exception:
        return 0


def _reflection_wrote(now: datetime | None = None) -> int:
    """Recent ingest events attributable to reflection = proof it still runs with --apply.

    ``ingest_items`` emits stats only when ``not dry_run``, so any event carrying
    ``harvester="reflection"`` is a write-path observation. This is the criterion that
    survives the regression the other two miss: the enabling flag lives in gitignored
    settings.local.json, so a clone / another machine / a deleted line silently returns
    reflect to the 5-week dry-run — leaving corpus-derived checks green.

    **Windowed on purpose.** Unlike the DERIVES_FROM edges of criterion 5, these events
    are NOT one-shot: an apply run over an already-consolidated corpus still resolves
    each cluster to ``skipped_dup`` and emits a ``dup`` event per hash. So every apply
    run with ``clusters_triggered>0`` yields >=1 event and the window is satisfiable —
    the idempotency argument that killed the in-window edge count does NOT carry over
    here. Counting all history instead would latch green after one write and stop
    detecting the very regression this criterion exists for.
    """
    now = now or datetime.now()
    cutoff = now - timedelta(days=REFLECTION_WRITE_MAX_AGE_DAYS)
    n = 0
    for rec in read_jsonl(INGEST_LOG):
        if rec.get("harvester") != "reflection" or rec.get("store") != "learned_patterns":
            continue
        dt = parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is not None and dt >= cutoff:
            n += 1
    return n


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

    # reflection, часть 1 — состоялась ли консолидация (DERIVES_FROM-рёбра).
    # `_total` — рабочий критерий; `_in_window` оставлен наблюдаемости ради: он и
    # показал, что рёбра созданы 2026-06-11, за день до окна (см. docstring).
    derives_total = 0
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
                    derives_total += 1
                    dt = parse_dt(created_at)
                    if dt is not None and dt >= WINDOW_START:
                        derives_in_window += 1
            finally:
                conn.close()
    except sqlite3.Error:
        pass

    clusters_triggered = _reflection_clusters_triggered()
    reflection_writes = _reflection_wrote()

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
        "derives_from_total": derives_total,
        "derives_from_in_window": derives_in_window,
        "reflection_clusters_triggered": clusters_triggered,
        "reflection_write_events": reflection_writes,
        "archive_runs": archive_runs,
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    return {
        f"episodes>={EPISODES_TARGET}": m["episodes_non_session"] >= EPISODES_TARGET,
        "surfacing_sqlite_fired": m["surfacing_sqlite_fired"] > 0,
        "dup_nonzero": m["dup_events"] > 0,
        "hash_complete": m["rows_without_hash"] == 0,
        "reflection_reachable": m["reflection_clusters_triggered"] > 0,
        "reflection_wrote": m["reflection_write_events"] > 0,
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
        f"- reflection: кластеров за триггером {m['reflection_clusters_triggered']} — цель >0"
        " (достижим ли триггер на текущем корпусе)",
        f"- reflection: ingest-событий harvester=reflection {m['reflection_write_events']}"
        " — цель >0 (доказательство, что джоб писал, а не крутился в dry-run)",
        f"- reflection: DERIVES_FROM-рёбер всего {m['derives_from_total']}, из них в окне"
        f" {m['derives_from_in_window']} — НЕ критерии (джоб идемпотентен, см. docstring)",
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
