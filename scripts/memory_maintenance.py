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
MEMORY_AI_DB = PROJECT_ROOT / "data" / "memory_ai.db"
SKILL_JSONL = PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"
WIKI_DRAFTS = PROJECT_ROOT / "docs" / "wiki" / "drafts"
COLLECTION = "learned_patterns"

# name -> (argv after python, supports --apply, apply-only)
SUBPROCESS_JOBS: dict[str, tuple[list[str], bool, bool]] = {
    "reflect": (["scripts/reflect_memory.py"], True, False),
    "sync": (["scripts/cross_store_sync.py", "--no-report"], True, False),
    "promote": (["-m", "scripts.export_graph_to_wiki", "promote-patterns"], False, True),
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
    # §27 P0 D0.1: persist store sizes to memory-ingestion.log for bounded-growth tracking
    try:
        from memory.orchestrator.ingest_metrics import record_store_size

        for store, size in sizes.items():
            if isinstance(size, int):
                record_store_size(store, size)
    except Exception:
        pass
    return sizes


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


def main() -> int:
    ap = argparse.ArgumentParser(description="memory maintenance cadence (§26 P4)")
    ap.add_argument("--apply", action="store_true", help="run jobs + archive (default: dry-run)")
    ap.add_argument("--skip", default="", help="comma list: reflect,sync,promote,forget")
    ap.add_argument("--no-report", action="store_true", help="do not write dashboard file")
    ap.add_argument("--stamp", default=None, help="override timestamp (tests)")
    args = ap.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    now = datetime.now()
    stamp = args.stamp or now.strftime("%Y%m%d_%H%M%S")

    jobs: dict[str, Any] = {}
    for name in ("reflect", "sync", "promote"):
        jobs[name] = "skipped" if name in skip else _run_subprocess(name, args.apply)
    forget = {"skipped": True} if "forget" in skip else run_forget(args.apply, now)

    cross_store = collect_cross_store()
    dash = build_dashboard(
        store_sizes=collect_store_sizes(),
        cross_store=cross_store,
        link_stats=collect_link_stats(),
        ingest=collect_ingest(),
        forget=forget,
        jobs=jobs,
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
    print(f"jobs={ {k: (v.get('rc') if isinstance(v, dict) else v) for k, v in jobs.items()} }")
    if isinstance(cross_store, dict):
        print(f"cross_store_dup_rate={cross_store.get('cross_store_dup_rate')}")
    if not args.no_report:
        print(f"report: data/reports/memory/memory_maintenance_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
