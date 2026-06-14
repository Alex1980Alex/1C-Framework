"""pdf-docs acceptance-окно (roadmap 260612 pdf-docs §P4, окно 14 дней с 2026-06-12).

Третий потребитель ``acceptance_common`` (после skill_learning / memory-ai).
Критерии:
- orphans_zero — physical pdf/wiki коллекции только из политики P0.3
- wiki_run_end_present — run_end wiki в data/indexing-progress.jsonl (P3.1)
- freshness_ok — возраст обоих индексов < 30d (P3.2)
- b3_suggest_green — semantic-suggest хука даёт верную главу (P2.B3)
- golden_recall>=baseline — live eval против post-A2 baseline
  (data/eval/pdf_docs_golden_acceptance_baseline.json; P0.2-baseline до A2-prune —
  исторический, 3 GT-id ушли вместе со страницами wiki-слоя, см. §18)
- d2_decision_recorded — ADR D2 (non-goal) зафиксирован в карте 27.12.4

Usage:
    python scripts/pdf_docs_acceptance.py [--json] [--final] [--no-report]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from acceptance_common import emit, render_acceptance, window_day

WINDOW_START = datetime(2026, 6, 12)
WINDOW_DAYS = 14
PROGRESS_LOG = PROJECT_ROOT / "data" / "indexing-progress.jsonl"
BASELINE_PATH = PROJECT_ROOT / "data" / "eval" / "pdf_docs_golden_acceptance_baseline.json"
MAP_CHAPTER = (
    PROJECT_ROOT
    / "docs"
    / "framework documentation"
    / "27_UNIFIED_MEMORY"
    / "27.12.4_Блок_Выход_Чтение.md"
)
# Политика P0.3 (skill qdrant-operations): physical-коллекции pdf/wiki корпусов
ALLOWED_PHYSICAL = {
    "pdf_documents_mrl_1024",
    "pdf_documents_4096_backup",
    "wiki_pages_v1_mrl_1024",
    "wiki_pages_v1_4096_backup",
}
RECALL_EPS = 0.01  # допуск на джиттер; eval детерминирован, eps страхует re-embed


def _collect_orphans() -> tuple[list[str], str | None]:
    try:
        import httpx

        with httpx.Client(timeout=10) as h:
            names = [
                c["name"]
                for c in h.get("http://localhost:6333/collections").json()["result"]["collections"]
                if c["name"].startswith(("pdf_documents", "wiki_pages_v1"))
            ]
        return [n for n in names if n not in ALLOWED_PHYSICAL], None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _collect_freshness() -> dict[str, Any]:
    try:
        from memory_maintenance import collect_docs_freshness

        return collect_docs_freshness()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _collect_b3() -> bool:
    hook = PROJECT_ROOT / ".claude" / "hooks" / "docs-change-enforcer.py"
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(hook),
                "--semantic-suggest",
                "src/memory/orchestrator/unified_search.py",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode == 0 and "27_UNIFIED_MEMORY" in (proc.stdout or "")
    except Exception:
        return False


def _collect_golden() -> dict[str, Any]:
    """Live eval vs baseline; {ok, detail} (fail-soft при TEI/Qdrant down)."""
    try:
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "detail": f"baseline unreadable: {exc}"}
    try:
        from eval_pdf_docs_golden import run_eval

        current = run_eval(None)
    except Exception as exc:
        return {"ok": False, "detail": f"eval failed: {type(exc).__name__}: {exc}"}

    detail: list[str] = []
    ok = True
    for coll, base in baseline.get("collections", {}).items():
        cur = current.get("collections", {}).get(coll, {})
        for metric in ("ndcg_at_10", "chunk_recall_at_10"):
            b, c = base.get(metric), cur.get(metric)
            if b is None or c is None:
                ok = False
                detail.append(f"{coll}.{metric}: missing (base={b}, cur={c})")
            elif c < b - RECALL_EPS:
                ok = False
                detail.append(f"{coll}.{metric}: {c} < baseline {b}")
            else:
                detail.append(f"{coll}.{metric}: {c} (baseline {b})")
        if cur.get("errors"):
            ok = False
            detail.append(f"{coll}: {len(cur['errors'])} eval errors")
    return {"ok": ok, "detail": "; ".join(detail)}


def _collect_d2() -> bool:
    try:
        return "non-goal (ADR D2" in MAP_CHAPTER.read_text(encoding="utf-8")
    except OSError:
        return False


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    orphans, orphan_err = _collect_orphans()
    freshness = _collect_freshness()
    wiki_run_end = bool(
        isinstance(freshness, dict)
        and isinstance(freshness.get("wiki_pages_v1"), dict)
        and freshness["wiki_pages_v1"].get("last_run_end")
    )
    return {
        "now": now.isoformat(timespec="seconds"),
        "day": window_day(now, WINDOW_START, WINDOW_DAYS),
        "window": f"{WINDOW_START:%Y-%m-%d} +{WINDOW_DAYS}d",
        "window_closed": (now - WINDOW_START).days >= WINDOW_DAYS,
        "orphans": orphans,
        "orphan_check_error": orphan_err,
        "freshness": freshness,
        "wiki_run_end": wiki_run_end,
        "b3_green": _collect_b3(),
        "golden": _collect_golden(),
        "d2_recorded": _collect_d2(),
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    fresh = m["freshness"]
    fresh_ok = (
        isinstance(fresh, dict)
        and "error" not in fresh
        and fresh
        and all(isinstance(st, dict) and not st.get("stale") for st in fresh.values())
    )
    return {
        "orphans_zero": not m["orphans"] and m["orphan_check_error"] is None,
        "wiki_run_end_present": m["wiki_run_end"],
        "freshness_ok": bool(fresh_ok),
        "b3_suggest_green": m["b3_green"],
        "golden_recall>=baseline": bool(m["golden"].get("ok")),
        "d2_decision_recorded": m["d2_recorded"],
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    fr = m["freshness"] if isinstance(m["freshness"], dict) else {}
    fr_lines = [
        f"  - {coll}: {st.get('points')} pts, age {st.get('age_days')}d"
        + (" ⚠ STALE" if st.get("stale") else "")
        for coll, st in fr.items()
        if isinstance(st, dict)
    ]
    detail = [
        f"- Снято: {m['now']}",
        f"- orphan-коллекции вне политики: {m['orphans'] or 'нет'}"
        + (f" (check error: {m['orphan_check_error']})" if m["orphan_check_error"] else ""),
        "- freshness:",
        *fr_lines,
        f"- B3 semantic-suggest: {'зелёный' if m['b3_green'] else 'КРАСНЫЙ'}",
        f"- golden vs baseline: {m['golden'].get('detail', '?')}",
        f"- ADR D2 в карте 27.12.4: {'да' if m['d2_recorded'] else 'НЕТ'}",
    ]
    return render_acceptance(
        f"# pdf-docs acceptance — день {m['day']}/{WINDOW_DAYS} ({m['window']})",
        m,
        crit,
        final=final,
        detail_lines=detail,
        roadmap_rel="docs/roadmap/260612_ROADMAP_PDF_DOCS_FULL_VERIFICATION.md",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="pdf-docs acceptance (roadmap 260612 §P4)")
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
    emit(render(m, crit, args.final), report_name=None if args.no_report else "pdf_docs_acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
