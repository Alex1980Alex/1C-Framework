#!/usr/bin/env python3
"""Memory maintenance cadence orchestrator (§26 P4, D4.1 + D4.2 + D4.3).

Sequences the §26 maintenance jobs, then emits the dashboard:
  1. reflect          — episodic→semantic consolidation (P2)     [subprocess]
  2. sync             — MIRRORS links + conflict resolution (P3)  [subprocess]
  3. promote          — learned→wiki drafts (apply-only)          [subprocess]
  4. forget           — ForgetGate archival bound (D4.2)          [inline]
→ D4.3 dashboard (store sizes / cross_store_dup_rate / ingest+dup rates /
forget summary / link stats) → ``data/reports/memory/memory_maintenance_*.md``.

READ-ONLY by default (dry-run): sub-jobs run in their own dry-run, ``forget``
only plans, ``promote`` is skipped. ``--apply`` propagates ``--apply`` to the
dry-run-capable sub-jobs, runs ``promote``, and archives (sets ``expired_at``)
the forget set. Each job is fail-soft (a down store never aborts the cadence)
and opt-out via ``--skip``.

Usage:
  python scripts/memory_maintenance.py             # dry-run cadence + dashboard
  python scripts/memory_maintenance.py --apply     # run jobs + archive
  python scripts/memory_maintenance.py --skip reflect,promote
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.maintenance.dashboard import (
    aggregate_ingest_events,
    build_dashboard,
    render_dashboard,
)
from memory.maintenance.forget_gate import plan_forget, summarize_forget
from memory.orchestrator.cross_store_index import build_index, find_cross_store_dups, summarize
from memory.orchestrator.link_registry import LinkRegistry
from scripts.cross_store_index import run_scan

PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"
INGEST_LOG = PROJECT_ROOT / ".claude" / "cache" / "memory-ingestion.log"
# MEMORY_AI_DB_PATH override — test isolation (roadmap 260612 P0.3)
MEMORY_AI_DB = Path(os.environ.get("MEMORY_AI_DB_PATH") or PROJECT_ROOT / "data" / "memory_ai.db")
SKILL_JSONL = PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"
SL_PENDING = PROJECT_ROOT / "data" / "skill_learning" / "pending_patterns.jsonl"
SL_REJECTED = PROJECT_ROOT / "data" / "skill_learning" / "rejected_patterns.jsonl"
# P3.1 (roadmap 260611): pending старше TTL без подтверждения → auto-reject
PENDING_TTL_DAYS = int(os.environ.get("SKILL_PENDING_TTL_DAYS", "30"))
WIKI_DRAFTS = PROJECT_ROOT / "docs" / "wiki" / "drafts"
COLLECTION = "learned_patterns"
# Docs freshness (roadmap 260612 P3.2): возраст последнего run_end per коллекция
PROGRESS_LOG = PROJECT_ROOT / "data" / "indexing-progress.jsonl"
DOCS_COLLECTIONS = ("pdf_documents", "wiki_pages_v1")
DOCS_STALE_DAYS = int(os.environ.get("DOCS_STALE_DAYS", "30"))

# name -> (argv after python, supports --apply, apply-only)
# reindex_wiki (260612 P3.3): генерация wiki .md (export_graph_to_wiki в promote)
# и индексация СВЯЗАНЫ в одном каденсе — реиндекс после promote, иначе
# расщеплённый мозг wiki .md <-> wiki_pages_v1. pdf_documents — ручной триггер
# (корпус статичный, см. §18 роадмапа 260612).
SUBPROCESS_JOBS: dict[str, tuple[list[str], bool, bool]] = {
    "reflect": (["scripts/reflect_memory.py"], True, False),
    "sync": (["scripts/cross_store_sync.py", "--no-report"], True, False),
    "promote": (["-m", "scripts.export_graph_to_wiki", "promote-patterns"], False, True),
    "reindex_wiki": (
        ["scripts/eval_hermes_phase4.py", "index-wiki", "--prune"],
        False,
        True,  # apply-only: пишет в production wiki_pages_v1
    ),
    # 260612 Skill System A5: mirror каталога .claude/skills/ -> skill_library
    # (upsert drift/changed, prune ghosts со снапшотом) — drift сходится к 0
    # каждым каденсом; дешёво при отсутствии правок (content_hash skip).
    "reindex_skill_library": (
        ["scripts/reindex_skill_library.py"],
        True,
        True,  # apply-only: пишет в production skill_library
    ),
    # 260612 Skill System P2.3 (S6): потребитель skill-accuracy.jsonl — отчёт
    # «review candidates» (high-waste / router-miss / never-used / no-traffic).
    "skill_review": (
        [
            "scripts/skill-health-analyzer.py",
            "--no-eval",
            "--exit-zero",
            "--output",
            "data/reports/skills/skill-health-report.md",
        ],
        False,
        False,  # read-only отчёт — безопасен и в dry-run каденсе
    ),
}


def _run_subprocess(name: str, apply: bool) -> dict[str, Any]:
    """Run a sub-job; return {rc, tail}. Fail-soft (never raises)."""
    argv, supports_apply, apply_only = SUBPROCESS_JOBS[name]
    if apply_only and not apply:
        return {"rc": None, "tail": "skipped (apply-only)"}
    if not PYTHON_EXE.exists():
        return {"rc": -1, "tail": "python.exe missing"}
    cmd = [str(PYTHON_EXE), *argv]
    if apply and supports_apply:
        cmd.append("--apply")
    try:
        r = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        tail = " | ".join((r.stdout or "").strip().splitlines()[-3:])
        return {"rc": r.returncode, "tail": tail or "(no stdout)"}
    except Exception as exc:  # fail-soft: a job crash never aborts the cadence
        return {"rc": -1, "tail": f"{type(exc).__name__}: {exc}"}


def _qdrant_client():
    from scripts.dedupe_learned_patterns import _client

    return _client()


def run_forget(apply: bool, now: datetime) -> dict[str, Any]:
    """ForgetGate sweep (D4.2): plan archival via plan_forget; apply sets expired_at."""
    try:
        from scripts.dedupe_learned_patterns import fetch_points

        client = _qdrant_client()
        points = fetch_points(client)
    except Exception as exc:  # fail-soft
        return {"error": f"{type(exc).__name__}: {exc}"}
    plan = plan_forget(points, now)
    summary = summarize_forget(plan)
    if apply and plan.archive:
        archived = 0
        for pid in plan.archive:
            try:
                client.set_payload(
                    collection_name=COLLECTION,
                    payload={"expired_at": now.isoformat()},
                    points=[pid],
                )
                archived += 1
            except Exception:  # per-point fail-soft
                pass
        summary["applied_archived"] = archived
        # §27 P0 D0.2: mirror the MCP decay path — make script-side archival visible
        # to confidence-lifecycle.log + bump the epoch (else surfacing-cache goes stale).
        if archived:
            try:
                from memory.vector_memory.lifecycle_log import log_event

                log_event(
                    "forget",
                    source="memory_maintenance",
                    archived=archived,
                    candidates=len(plan.archive),
                    invariant_protected=len(plan.invariant_protected),
                )
            except Exception:
                pass
            try:
                from memory.vector_memory.epoch import bump as _epoch_bump

                _epoch_bump()
            except Exception:
                pass
    return summary


def run_review_pending(apply: bool, now: datetime) -> dict[str, Any]:
    """P3.1 (roadmap 260611): модерация pending-карантина skill-learning.

    Pending старше ``PENDING_TTL_DAYS`` без подтверждения → auto-reject
    (``reject_reason=ttl_expired``) в rejected-silo, который блокирует повторный
    авто-захват (P0.2 dedup). Dry-run по умолчанию (только план); ``--apply``
    переносит записи (atomic rewrite pending: tmp + os.replace). Fail-soft.
    """
    try:
        lines = SL_PENDING.read_text(encoding="utf-8").splitlines() if SL_PENDING.exists() else []
    except OSError as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    remaining: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        age_days: float | None = None
        try:
            age_days = (now - datetime.fromisoformat(rec.get("created_at", ""))).days
        except (TypeError, ValueError):  # null / malformed created_at → честный skip
            pass
        # Записи без валидного created_at не auto-reject'ятся (честный skip).
        if age_days is not None and age_days > PENDING_TTL_DAYS:
            expired.append(rec)
        else:
            remaining.append(rec)

    summary: dict[str, Any] = {
        "pending": len(remaining) + len(expired),
        "expired": len(expired),
        "ttl_days": PENDING_TTL_DAYS,
        "applied": False,
    }
    if not (apply and expired):
        return summary

    try:
        SL_REJECTED.parent.mkdir(parents=True, exist_ok=True)
        with SL_REJECTED.open("a", encoding="utf-8") as fh:
            for rec in expired:
                rec["rejected_at"] = now.isoformat()
                rec["reject_reason"] = "ttl_expired"
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # atomic rewrite pending (P0.1 contract: tmp + os.replace, kill-safe)
        tmp = SL_PENDING.with_name(SL_PENDING.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for rec in remaining:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, SL_PENDING)
    except OSError as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        return summary

    summary["applied"] = True
    # observability: per-item rejected event, общий content_hash fact-key
    try:
        from memory.orchestrator.ingest_metrics import record_ingest

        for rec in expired:
            record_ingest(
                "skill_learning",
                "rejected",
                content_hash=rec.get("content_hash", ""),
                reason="ttl_expired",
                harvester="review_pending",
            )
    except Exception:
        pass
    return summary


def run_merge_patterns(apply: bool, now: datetime) -> dict[str, Any]:
    """§БП G2 (audit 260705) — background consolidation of the skill_learning SAVED silo.

    Wires the previously-orphaned ``PatternMerger`` into the cadence. Dedups
    near-identical learned patterns by NORMALIZED content (lowercase +
    whitespace-collapsed; keep-higher-confidence winner, tag-union,
    application-count aggregation) that the O(1) write-time ``content_hash``
    check cannot catch (it only collapses byte-identical content). (Note:
    PatternMerger computes a ``by_name`` index but does not consume it — the
    active grouping is normalized-content only.) This is the mem0 ADD-only / Letta
    sleep-time consolidation pattern: expensive similarity-dedup runs in the
    background cadence, NOT in a hot-path Stop-hook.

    Dry-run by default (only reports duplicate groups); ``--apply`` rewrites
    ``patterns.jsonl`` (PatternMerger snapshots ``patterns.jsonl.bak`` first).
    Fail-soft — a merge crash never aborts the cadence.
    """
    try:
        from memory.skill_learning.merge_patterns import PatternMerger

        merger = PatternMerger(SKILL_JSONL.parent)
        result = asyncio.run(merger.merge_duplicates(dry_run=not apply))
    except Exception as exc:  # fail-soft
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "duplicates_found": result.duplicates_found,
        "patterns_merged": result.patterns_merged,
        "patterns_kept": result.patterns_kept,
        "space_saved_bytes": result.space_saved_bytes,
        "applied": bool(apply and result.patterns_merged > 0),
    }


def run_archive_episodic(apply: bool, now: datetime) -> dict[str, Any]:
    """P3.2 (roadmap 260612): bounded growth для эпизодики — archive-stamp.

    Decay-категории (``session_summary``/``general``) старше
    ``ARCHIVE_AFTER_DAYS`` с importance ниже порога получают
    ``metadata.archived_at`` (invalidate-not-delete, инвариант §22 P3);
    читатели R1/R2 фильтруют archived. Курируемые категории
    (decision/preference/feedback/...) не архивируются по возрасту.

    P3.3: job стоит ПОСЛЕ reflect в каденсе — кластеры успевают
    консолидироваться в semantic до ухода эпизодов в архив.
    """
    try:
        from memory.ai_memory.retention import is_archived, should_archive
    except Exception as exc:
        return {"rc": -1, "error": f"{type(exc).__name__}: {exc}"}

    candidates: list[tuple[str, str, dict[str, Any]]] = []
    try:
        conn = sqlite3.connect(str(MEMORY_AI_DB))
        try:
            rows = conn.execute(
                "SELECT id, category, created_at, importance, metadata FROM important_messages"
            ).fetchall()
            for rid, category, created_at, importance, raw_md in rows:
                try:
                    md = json.loads(raw_md) if raw_md else {}
                except (json.JSONDecodeError, TypeError):
                    md = {}
                if not isinstance(md, dict) or is_archived(md):
                    continue
                if should_archive(category, created_at, float(importance or 0.0), now):
                    candidates.append((rid, raw_md or "{}", md))
            archived = 0
            if apply and candidates:
                for rid, _raw, md in candidates:
                    md["archived_at"] = now.isoformat()
                    conn.execute(
                        "UPDATE important_messages SET metadata = ? WHERE id = ?",
                        (json.dumps(md, ensure_ascii=False), rid),
                    )
                    archived += 1
                conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # fail-soft: cadence survives a broken episodic DB
        return {"rc": -1, "error": f"{type(exc).__name__}: {exc}"}

    summary = {
        "rc": 0,
        "candidates": len(candidates),
        "archived": archived if apply else 0,
        "applied": bool(apply and candidates),
    }
    if apply and candidates:
        try:
            from memory.orchestrator.ingest_metrics import record_ingest

            for _rid, _raw, md in candidates:
                record_ingest(
                    "memory_ai",
                    "archived",
                    content_hash=md.get("content_hash", ""),
                    harvester="archive_episodic",
                )
        except Exception:
            pass
    return summary


def collect_store_sizes() -> dict[str, Any]:
    """Cheap point/row/line/file counts per store (fail-soft per store)."""
    sizes: dict[str, Any] = {}
    try:
        sizes["learned_patterns"] = _qdrant_client().count(collection_name=COLLECTION).count
    except Exception:
        pass
    try:
        conn = sqlite3.connect(str(MEMORY_AI_DB))
        try:
            sizes["memory_ai"] = conn.execute("SELECT COUNT(*) FROM important_messages").fetchone()[
                0
            ]
        finally:
            conn.close()
    except Exception:
        pass
    try:
        with SKILL_JSONL.open(encoding="utf-8") as fh:
            sizes["skill_learning"] = sum(1 for ln in fh if ln.strip())
    except Exception:
        pass
    try:
        sizes["wiki"] = len(list(WIKI_DRAFTS.glob("*.md"))) if WIKI_DRAFTS.exists() else 0
    except Exception:
        pass
    # D6 (roadmap 260612 P4): docs-коллекции считаются ТОЧКАМИ в Qdrant,
    # а не drafts на диске (раньше при 3k живых точек store_sizes видел 0)
    for coll in DOCS_COLLECTIONS:
        try:
            sizes[coll] = _qdrant_client().count(collection_name=coll).count
        except Exception:
            pass
    # §27 P0 D0.1: persist store sizes to memory-ingestion.log for bounded-growth tracking
    try:
        from memory.orchestrator.ingest_metrics import record_store_size

        for store, size in sizes.items():
            if isinstance(size, int):
                record_store_size(store, size)
    except Exception:
        pass
    return sizes


def collect_docs_freshness() -> dict[str, Any]:
    """Возраст последнего run_end per docs-коллекция (roadmap 260612 P3.2).

    Скан data/indexing-progress.jsonl терпим к битым строкам; матчинг —
    подстрока имени коллекции в run_end-строке (run_end summary index_wiki
    несёт collection; исторический pdf — имя скрипта reindex_pdf_documents).
    """
    last_run_end: dict[str, str | None] = dict.fromkeys(DOCS_COLLECTIONS)
    try:
        with PROGRESS_LOG.open(encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if '"run_end"' not in ln:
                    continue
                for coll in DOCS_COLLECTIONS:
                    if coll in ln:
                        try:
                            ts = json.loads(ln).get("ts")
                        except json.JSONDecodeError:
                            continue
                        if ts:
                            last_run_end[coll] = ts  # файл хронологический — последняя побеждает
    except OSError:
        pass

    points: dict[str, Any] = {}
    for coll in DOCS_COLLECTIONS:
        try:
            points[coll] = _qdrant_client().count(collection_name=coll).count
        except Exception:
            points[coll] = None

    from memory.maintenance.dashboard import compute_docs_freshness

    return compute_docs_freshness(
        last_run_end, points, now=datetime.now().astimezone(), max_age_days=DOCS_STALE_DAYS
    )


def collect_cross_store() -> dict[str, Any]:
    try:
        records, scan_errors = run_scan()
        index = build_index(records)
        out = summarize(records, index, find_cross_store_dups(index))
        if scan_errors:  # surface per-store scan failures (observability)
            out["scan_errors"] = scan_errors
        return out
    except Exception as exc:  # fail-soft
        return {"error": f"{type(exc).__name__}: {exc}"}


def collect_ingest() -> dict[str, Any]:
    if not INGEST_LOG.exists():
        return {}
    events: list[dict[str, Any]] = []
    try:
        for ln in INGEST_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                events.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    except OSError:
        return {}
    return aggregate_ingest_events(events)


def collect_link_stats() -> dict[str, Any]:
    try:
        return LinkRegistry().get_registry_stats()
    except Exception:
        return {}


def run_rebuild_link_stats(apply: bool) -> dict[str, Any] | str:
    """P0.2 roadmap 260612 LinkRegistry: idempotent-пересчёт link_stats
    из entity_links в каденсе — рассинхрон (orphan-строки после удалений
    легаси-путями) не накапливается. Apply-only: дефолт каденса READ-ONLY."""
    if not apply:
        return "skipped (dry-run)"
    try:
        return LinkRegistry().rebuild_stats()
    except Exception as exc:  # fail-soft: каденс не прерывается
        return {"error": type(exc).__name__}


def main() -> int:
    ap = argparse.ArgumentParser(description="memory maintenance cadence (§26 P4)")
    ap.add_argument("--apply", action="store_true", help="run jobs + archive (default: dry-run)")
    ap.add_argument(
        "--skip",
        default="",
        help=(
            "comma list: reflect,sync,promote,reindex_wiki,reindex_skill_library,"
            "skill_review,forget,review_pending,merge,archive_episodic,rebuild_link_stats"
        ),
    )
    ap.add_argument("--no-report", action="store_true", help="do not write dashboard file")
    ap.add_argument("--stamp", default=None, help="override timestamp (tests)")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    now = datetime.now()
    stamp = args.stamp or now.strftime("%Y%m%d_%H%M%S")

    jobs: dict[str, Any] = {}
    # reindex_wiki СРАЗУ после promote (260612 P3.3): export wiki .md и индексация
    # wiki_pages_v1 — один пайплайн, иначе дрейф .md <-> Qdrant.
    # reindex_skill_library + skill_review (260612 Skill System A5/P2.3): зеркало
    # каталога скиллов в skill_library + отчёт review-кандидатов из метрик.
    for name in (
        "reflect",
        "sync",
        "promote",
        "reindex_wiki",
        "reindex_skill_library",
        "skill_review",
    ):
        jobs[name] = "skipped" if name in skip else _run_subprocess(name, args.apply)
    forget = {"skipped": True} if "forget" in skip else run_forget(args.apply, now)
    # P3.1 (roadmap 260611): pending-карантин не должен гнить — TTL auto-reject
    review_pending = (
        {"skipped": True} if "review_pending" in skip else run_review_pending(args.apply, now)
    )
    jobs["review_pending"] = review_pending
    # §БП G2 (audit 260705): background-консолидация SAVED-силоса skill_learning —
    # раньше PatternMerger был orphaned (0 вызовов). Дедуп по нормализованному
    # содержимому вне hot-path (mem0 ADD-only / Letta dreaming). Независим от reindex_skill_library
    # (тот зеркалит КАТАЛОГ .claude/skills/, не patterns.jsonl) → порядок не важен.
    jobs["merge"] = "skipped" if "merge" in skip else run_merge_patterns(args.apply, now)
    # P3.2/P3.3 (roadmap 260612): после reflect — эпизодика консолидирована, можно в архив.
    # Skip — строкой (конвенция reflect/sync/promote): trace-маппинг jobs→rc различает
    # "skipped" / 0 (исполнился) / -1 (error) — acceptance-критерий archive_ran на этом стоит.
    jobs["archive_episodic"] = (
        "skipped" if "archive_episodic" in skip else run_archive_episodic(args.apply, now)
    )
    # P0.2 roadmap 260612 LinkRegistry: stats-гигиена перед сборкой дашборда
    jobs["rebuild_link_stats"] = (
        "skipped" if "rebuild_link_stats" in skip else run_rebuild_link_stats(args.apply)
    )

    cross_store = collect_cross_store()
    docs_freshness = collect_docs_freshness()
    dash = build_dashboard(
        store_sizes=collect_store_sizes(),
        cross_store=cross_store,
        link_stats=collect_link_stats(),
        ingest=collect_ingest(),
        forget=forget,
        jobs=jobs,
        docs_freshness=docs_freshness,
    )

    if not args.no_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / f"memory_maintenance_{stamp}.md").write_text(
            render_dashboard(dash, stamp), encoding="utf-8"
        )
        (REPORTS_DIR / f"memory_maintenance_{stamp}.json").write_text(
            json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # §27 P2 D2.2: append one summary line per run to a single tail-able stream
    # (vs N timestamped dashboards) so long-run trend analysis is `tail`-able.
    try:
        from memory.infrastructure.trace_log import write_trace

        write_trace(
            "memory-maintenance-runs.jsonl",
            "run",
            disable_env="MEMORY_MAINTENANCE_LOG_DISABLE",
            applied=bool(args.apply),
            total_facts=dash.get("total_facts"),
            store_sizes=dash.get("store_sizes"),
            cross_store_dup_rate=(
                cross_store.get("cross_store_dup_rate") if isinstance(cross_store, dict) else None
            ),
            forget=(forget if isinstance(forget, dict) else None),
            jobs={k: (v.get("rc") if isinstance(v, dict) else v) for k, v in jobs.items()},
        )
    except Exception:
        pass

    # ASCII-safe stdout
    print("# memory maintenance cadence", "(APPLY)" if args.apply else "(dry-run)")
    print(f"store_sizes={dash['store_sizes']} total_facts={dash['total_facts']}")
    print(f"forget={forget}")
    print(f"review_pending={review_pending}")
    print(f"jobs={ {k: (v.get('rc') if isinstance(v, dict) else v) for k, v in jobs.items()} }")
    stale = [c for c, st in docs_freshness.items() if st.get("stale")]
    print(f"docs_freshness={docs_freshness}" + (f" ALERT stale={stale}" if stale else ""))
    if isinstance(cross_store, dict):
        print(f"cross_store_dup_rate={cross_store.get('cross_store_dup_rate')}")
    if not args.no_report:
        print(f"report: data/reports/memory/memory_maintenance_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
