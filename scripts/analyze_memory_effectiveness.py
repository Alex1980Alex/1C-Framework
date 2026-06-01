#!/usr/bin/env python3
"""Section 25 Part A — Memory effectiveness analyzer (read-only).

Reads the two memory JSONL trace logs and aggregates quality/health metrics
into a Markdown report (+ JSON sidecar + _latest.md), mirroring the auto-report
pattern of scripts/analyze_run.py / post-indexing-analyzer.

Inputs (both optional -- cold-start safe):
  - .claude/cache/memory-first-surfacing.log   (24.4 surfacing trace)
  - .claude/cache/confidence-lifecycle.log     (22.4 confidence trace)

Output:
  - data/reports/memory/memory-effectiveness-<ts>.md  (+ .json sidecar)
  - data/reports/memory/_latest.md

Read-only: never mutates source logs or config. Fail-soft per-line (corrupt
JSON skipped). Window via --since (ISO prefix or "Nh"/"Nd").

Usage:
  python scripts/analyze_memory_effectiveness.py [--since 24h] [--print]

Roadmap: docs/roadmap/260601_ROADMAP_MEMORY_EFFECTIVENESS.md (section 3, 4).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SURFACING_LOG = PROJECT_ROOT / ".claude" / "cache" / "memory-first-surfacing.log"
LIFECYCLE_LOG = PROJECT_ROOT / ".claude" / "cache" / "confidence-lifecycle.log"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "reports" / "memory"
TUNING_PREV_FILE = PROJECT_ROOT / "data" / "memory" / "surfacing_tuning.prev.json"
TUNER_SCRIPT = PROJECT_ROOT / "scripts" / "tune_memory_surfacing.py"

THRESHOLDS = {
    "tei_down_rate": 0.30,
    "gate_drop_rate": 0.50,
    "no_results_rate": 0.40,
    "cache_hit_rate_floor": 0.01,
}

# §25 B2 auto-rollback (closes the "auto-откат при регрессии на следующем окне" gap):
# config-attributable quality regressions. TEI-down is deliberately EXCLUDED -- that's
# an infra outage, not the surfacing config's fault, so it must not trigger a rollback.
AUTO_ROLLBACK_SIGNALS = ("gate_drop_rate", "no_results_rate")


def _parse_since(since: str | None, now: datetime) -> datetime | None:
    if not since:
        return None
    try:
        s = since.strip().lower()
        if s.endswith("h"):
            return now - timedelta(hours=float(s[:-1]))
        if s.endswith("d"):
            return now - timedelta(days=float(s[:-1]))
        return datetime.fromisoformat(since)
    except Exception:
        return None


def _read_jsonl(path: Path, cutoff: datetime | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue
                if cutoff is not None:
                    ts = obj.get("ts")
                    if isinstance(ts, str):
                        try:
                            if datetime.fromisoformat(ts) < cutoff:
                                continue
                        except ValueError:
                            pass
                out.append(obj)
    except OSError:
        return out
    return out


def _pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return round(s[lo] + (s[hi] - s[lo]) * frac, 2)


def analyze_surfacing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    outcomes: dict[str, int] = {}
    cache_hits = 0
    tei_seen = 0
    tei_down = 0
    gate_archived = gate_floor = gate_passed = 0
    arm_totals: dict[str, int] = {}
    durations: list[float] = []
    rerank_states: dict[str, int] = {}

    for r in rows:
        oc = r.get("outcome", "?")
        outcomes[oc] = outcomes.get(oc, 0) + 1
        if r.get("cache") == "hit":
            cache_hits += 1
        tei = r.get("tei")
        if tei is not None:
            tei_seen += 1
            if tei == "down":
                tei_down += 1
        g = r.get("gate")
        if isinstance(g, dict):
            gate_archived += int(g.get("archived", 0) or 0)
            gate_floor += int(g.get("below_floor", 0) or 0)
            gate_passed += int(g.get("passed", 0) or 0)
        arms = r.get("arms")
        if isinstance(arms, dict):
            for k, v in arms.items():
                arm_totals[k] = arm_totals.get(k, 0) + int(v or 0)
        d = r.get("duration_ms")
        if isinstance(d, (int, float)):
            durations.append(float(d))
        rk = r.get("rerank")
        if rk is not None:
            rerank_states[rk] = rerank_states.get(rk, 0) + 1

    gate_total = gate_archived + gate_floor + gate_passed
    return {
        "total_invocations": total,
        "outcomes": outcomes,
        "no_results_rate": _pct(outcomes.get("no-results", 0), total),
        "injected_rate": _pct(
            outcomes.get("injected", 0) + outcomes.get("injected-cached", 0), total
        ),
        "cache_hit_rate": _pct(cache_hits, total),
        "tei_down_rate": _pct(tei_down, tei_seen),
        "tei_observations": tei_seen,
        "gate_drop_rate": _pct(gate_archived + gate_floor, gate_total),
        "gate_breakdown": {
            "archived": gate_archived,
            "below_floor": gate_floor,
            "passed": gate_passed,
        },
        "arm_contribution": arm_totals,
        "rerank_states": rerank_states,
        "latency_ms": {
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "count": len(durations),
        },
    }


def analyze_lifecycle(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events: dict[str, int] = {}
    drifts: list[float] = []
    applied = skipped = errors = candidates = 0

    for r in rows:
        ev = r.get("event", "?")
        events[ev] = events.get(ev, 0) + 1
        if ev in ("reinforce", "apply"):
            old = r.get("old_confidence")
            new = r.get("new_confidence")
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                drifts.append(float(new) - float(old))
        if ev == "session":
            applied += int(r.get("applied", 0) or 0)
            skipped += int(r.get("skipped", 0) or 0)
            errors += int(r.get("errors", 0) or 0)
            candidates += int(r.get("candidates", 0) or 0)

    avg_drift = round(sum(drifts) / len(drifts), 4) if drifts else 0.0
    return {
        "total_events": len(rows),
        "event_mix": events,
        "confidence_drift_avg": avg_drift,
        "confidence_mutations": len(drifts),
        "reinforcement": {
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
            "candidates": candidates,
            "apply_rate": _pct(applied, candidates),
        },
    }


def recommendations(surf: dict[str, Any], life: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    if surf["total_invocations"] == 0:
        recs.append(
            "No surfacing data in window -- log empty (cold-start) or MEMORY_SURFACE_LOG_DISABLE=1."
        )
        return recs
    if surf["tei_down_rate"] > THRESHOLDS["tei_down_rate"]:
        recs.append(
            f"tei_down_rate={surf['tei_down_rate']:.0%} > {THRESHOLDS['tei_down_rate']:.0%}: "
            "TEI often unavailable -> raise lexical weight or check pdf-rag-tei Docker."
        )
    if surf["gate_drop_rate"] > THRESHOLDS["gate_drop_rate"]:
        recs.append(
            f"gate_drop_rate={surf['gate_drop_rate']:.0%} > {THRESHOLDS['gate_drop_rate']:.0%}: "
            "many patterns dropped by gating -> review MIN_SURFACE_CONF / archived policy."
        )
    if surf["no_results_rate"] > THRESHOLDS["no_results_rate"]:
        recs.append(
            f"no_results_rate={surf['no_results_rate']:.0%} > {THRESHOLDS['no_results_rate']:.0%}: "
            "many empty outcomes -> check collection coverage / thresholds."
        )
    if (
        surf["total_invocations"] >= 20
        and surf["cache_hit_rate"] < THRESHOLDS["cache_hit_rate_floor"]
    ):
        recs.append(
            "cache_hit_rate ~0 under traffic -> check execution-cache / epoch invalidation."
        )
    if life["confidence_mutations"] and life["confidence_drift_avg"] < -0.02:
        recs.append(
            f"confidence_drift_avg={life['confidence_drift_avg']} < 0: trust trending down -> "
            "review reinforcement success heuristic (too many failures?)."
        )
    if not recs:
        recs.append("No threshold anomalies detected (section 4).")
    return recs


def render_markdown(report: dict[str, Any]) -> str:
    s = report["surfacing"]
    li = report["lifecycle"]
    lines = [
        "# Memory Effectiveness Report (section 25 Part A)",
        "",
        f"- **Generated:** {report['generated']}",
        f"- **Window:** {report['window']}",
        f"- **Surfacing log:** {report['surfacing_rows']} rows · "
        f"**Lifecycle log:** {report['lifecycle_rows']} rows",
        "",
        "## Surfacing quality (section 24)",
        "",
        f"- Invocations: **{s['total_invocations']}**",
        f"- Injected rate: **{s['injected_rate']:.1%}** · No-results: **{s['no_results_rate']:.1%}**",
        f"- Cache hit rate: **{s['cache_hit_rate']:.1%}**",
        f"- TEI-down rate: **{s['tei_down_rate']:.1%}** ({s['tei_observations']} obs)",
        f"- Gate drop rate: **{s['gate_drop_rate']:.1%}** "
        f"(archived={s['gate_breakdown']['archived']}, "
        f"below_floor={s['gate_breakdown']['below_floor']}, "
        f"passed={s['gate_breakdown']['passed']})",
        f"- Latency: p50 **{s['latency_ms']['p50']}ms** · p95 **{s['latency_ms']['p95']}ms** "
        f"({s['latency_ms']['count']} samples)",
        f"- Arm contribution: `{s['arm_contribution']}`",
        f"- Outcomes: `{s['outcomes']}`",
        f"- Rerank states: `{s['rerank_states']}`",
        "",
        "## Confidence lifecycle (section 22)",
        "",
        f"- Events: **{li['total_events']}** · mix: `{li['event_mix']}`",
        f"- Confidence drift avg: **{li['confidence_drift_avg']}** "
        f"({li['confidence_mutations']} mutations)",
        f"- Reinforcement: applied **{li['reinforcement']['applied']}** / "
        f"candidates {li['reinforcement']['candidates']} "
        f"(rate {li['reinforcement']['apply_rate']:.1%}), "
        f"skipped {li['reinforcement']['skipped']}, errors {li['reinforcement']['errors']}",
        "",
        "## Recommendations (rule-based, not applied)",
        "",
    ]
    lines += [f"- {r}" for r in report["recommendations"]]
    lines += [
        "",
        "> Offline precision@k / NDCG@k require a memory golden-set "
        "(roadmap section 25 B0) -- not computed here.",
        "",
    ]
    return "\n".join(lines)


def build_report(since: str | None, now: datetime) -> dict[str, Any]:
    cutoff = _parse_since(since, now)
    surf_rows = _read_jsonl(SURFACING_LOG, cutoff)
    life_rows = _read_jsonl(LIFECYCLE_LOG, cutoff)
    report: dict[str, Any] = {
        "generated": now.isoformat(timespec="seconds"),
        "window": since or "all",
        "surfacing_rows": len(surf_rows),
        "lifecycle_rows": len(life_rows),
        "surfacing": analyze_surfacing(surf_rows),
        "lifecycle": analyze_lifecycle(life_rows),
    }
    report["recommendations"] = recommendations(report["surfacing"], report["lifecycle"])
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="section 25 memory effectiveness analyzer (read-only)")
    ap.add_argument("--since", default=None, help="window: '24h', '7d', or ISO timestamp")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--stamp", default=None, help="override report timestamp (tests)")
    ap.add_argument("--print", action="store_true", help="print markdown to stdout, skip files")
    args = ap.parse_args()

    now = datetime.fromisoformat(args.stamp) if args.stamp else datetime.now()
    report = build_report(args.since, now)
    md = render_markdown(report)

    if args.print:
        print(md)
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"memory-effectiveness-{stamp}.md"
    json_path = out_dir / f"memory-effectiveness-{stamp}.json"
    latest = out_dir / "_latest.md"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(md, encoding="utf-8")
    print(f"Report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
