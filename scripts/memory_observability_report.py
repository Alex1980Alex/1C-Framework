#!/usr/bin/env python3
"""§27 P4 — Unified memory observability report (D4.1 + D4.2).

Rolls up EVERY §27 observability sink into one effectiveness report, answering
"is memory becoming more effective?" from the real logs (not stubs) and flagging
**observability regressions** (a process that stopped logging).

Builds on the §25 effectiveness analyzer (``analyze_memory_effectiveness.py``,
surfacing + confidence-lifecycle) and adds the cross-process metrics unlocked by
§27 P0-P2 logging:
  - ingestion : ingest_rate / dup_rate / store_growth / by-harvester
  - maintenance: forget_volume / forget_rate / cadence runs
  - routing   : target & method distribution
  - read      : federated read hit-rate / latency / per-source hit-rate
  - propagation: cascade reach / depth / cascades-prevented
  - circuit   : breaker trips
  - audit     : operation coverage / error-rate
  - freshness : per-sink last-write + stale-sink (regression) detection

Inputs (all optional — cold-start safe). Output:
  - data/reports/memory/observability-<ts>.md  (+ .json sidecar)
  - data/reports/memory/_observability_latest.md

Read-only: never mutates source logs or config. Fail-soft per-line. Window via
``--since`` (ISO prefix or "Nh"/"Nd").

Usage:
  python scripts/memory_observability_report.py [--since 7d] [--print]

Roadmap: docs/roadmap/260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md (§27 P4).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.infrastructure.event_envelope import known_sinks
from memory.maintenance.dashboard import aggregate_ingest_events
from scripts.analyze_memory_effectiveness import (
    _parse_since,
    _percentile,
    analyze_lifecycle,
    analyze_surfacing,
)

OUT_DIR = PROJECT_ROOT / "data" / "reports" / "memory"

# A sink whose newest event is older than this is reported as a regression
# (it was logging, and stopped). Override with --stale-hours.
DEFAULT_STALE_HOURS = 24 * 7


# --------------------------------------------------------------------------- #
# Generic windowed reader (handles ts/timestamp/time key drift across sinks)
# --------------------------------------------------------------------------- #
def _ts_of(obj: dict[str, Any]) -> str | None:
    ts = obj.get("ts") or obj.get("timestamp") or obj.get("time")
    return ts if isinstance(ts, str) else None


def read_window(path: Path, cutoff: datetime | None) -> list[dict[str, Any]]:
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
                if not isinstance(obj, dict):
                    continue
                if cutoff is not None:
                    ts = _ts_of(obj)
                    if ts:
                        try:
                            if datetime.fromisoformat(ts) < cutoff:
                                continue
                        except ValueError:
                            pass
                out.append(obj)
    except OSError:
        return out
    return out


# --------------------------------------------------------------------------- #
# Per-sink aggregators (D4.1)
# --------------------------------------------------------------------------- #
def analyze_ingestion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = aggregate_ingest_events(rows)  # actions/attempted/saved/dup_rate/logged_store_sizes
    first: dict[str, Any] = {}
    last: dict[str, Any] = {}
    by_harvester: Counter[str] = Counter()
    for r in rows:
        if r.get("event") == "store_size":
            store = r.get("store")
            size = r.get("size")
            if store is not None and isinstance(size, (int, float)):
                key = str(store)
                first.setdefault(key, size)
                last[key] = size
        elif r.get("event") == "ingest":
            h = r.get("harvester")
            if h:
                by_harvester[str(h)] += 1
    base["store_growth"] = {s: last[s] - first.get(s, last[s]) for s in last}
    base["by_harvester"] = dict(by_harvester)
    return base


def analyze_maintenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [r for r in rows if r.get("event") == "run"]
    archive = keep = applied_runs = 0
    dup_rates: list[float] = []
    latest_sizes: dict[str, Any] = {}
    for r in runs:
        f = r.get("forget")
        if isinstance(f, dict):
            archive += int(f.get("archive", 0) or 0)
            keep += int(f.get("keep", 0) or 0)
        if r.get("applied"):
            applied_runs += 1
        d = r.get("cross_store_dup_rate")
        if isinstance(d, (int, float)):
            dup_rates.append(float(d))
        ss = r.get("store_sizes")
        if isinstance(ss, dict):
            latest_sizes = ss
    forget_total = archive + keep
    return {
        "runs": len(runs),
        "applied_runs": applied_runs,
        "forget_volume": archive,
        "forget_rate": round(archive / forget_total, 4) if forget_total else 0.0,
        "dup_rate_latest": dup_rates[-1] if dup_rates else None,
        "store_sizes_latest": latest_sizes,
    }


def analyze_routing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    routes = [r for r in rows if r.get("event") == "route"]
    targets: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    for r in routes:
        t = r.get("targets")
        if isinstance(t, list):
            for x in t:
                targets[str(x)] += 1
        m = r.get("method")
        if m:
            methods[str(m)] += 1
    return {
        "routes": len(routes),
        "target_distribution": dict(targets),
        "method_distribution": dict(methods),
    }


def analyze_read(rows: list[dict[str, Any]]) -> dict[str, Any]:
    searches = [r for r in rows if r.get("event") == "search"]
    total = len(searches)
    hits = sum(1 for r in searches if (r.get("final") or 0) > 0)
    lat = [float(r["latency_ms"]) for r in searches if isinstance(r.get("latency_ms"), (int, float))]
    arm: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # source -> [hit_queries, queries]
    for r in searches:
        ah = r.get("arm_hits")
        if isinstance(ah, dict):
            for src, cnt in ah.items():
                arm[src][1] += 1
                if (cnt or 0) > 0:
                    arm[src][0] += 1
    return {
        "searches": total,
        "hit_rate": round(hits / total, 4) if total else 0.0,
        "latency_ms": {
            "p50": _percentile(lat, 0.50),
            "p95": _percentile(lat, 0.95),
            "count": len(lat),
        },
        "source_hit_rate": {
            k: round(v[0] / v[1], 4) if v[1] else 0.0 for k, v in sorted(arm.items())
        },
    }


def analyze_propagation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    props = [r for r in rows if r.get("event") == "propagate"]
    reach = [int(r.get("entities_updated", 0) or 0) for r in props]
    depths = [int(r.get("final_depth", 0) or 0) for r in props]
    prevented = sum(int(r.get("cascades_prevented", 0) or 0) for r in props)
    return {
        "events": len(props),
        "avg_reach": round(sum(reach) / len(reach), 2) if reach else 0.0,
        "max_reach": max(reach) if reach else 0,
        "cascades_prevented": prevented,
        "avg_depth": round(sum(depths) / len(depths), 2) if depths else 0.0,
    }


def analyze_circuit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trans = [r for r in rows if r.get("event") == "transition"]
    opens = sum(1 for r in trans if r.get("new") == "open")
    by_circuit = Counter(str(r.get("circuit")) for r in trans)
    return {"transitions": len(trans), "opens": opens, "by_circuit": dict(by_circuit)}


def analyze_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    by_action = Counter(str(r.get("action")) for r in rows)
    errors = sum(1 for r in rows if r.get("success") is False)
    return {
        "total": total,
        "by_action": dict(by_action),
        "error_rate": round(errors / total, 4) if total else 0.0,
    }


# --------------------------------------------------------------------------- #
# Freshness / observability-regression detection (D4.2 acceptance #2)
# --------------------------------------------------------------------------- #
def analyze_freshness(now: datetime, stale_hours: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, path in known_sinks(PROJECT_ROOT):
        if not path.exists():
            out.append(
                {"source": label, "status": "missing", "last_ts": None,
                 "age_hours": None, "events": 0}
            )
            continue
        rows = read_window(path, None)
        last_ts = None
        for obj in rows:
            ts = _ts_of(obj)
            if ts:
                last_ts = ts  # chronological file: last wins
        if not rows or not last_ts:
            out.append(
                {"source": label, "status": "empty", "last_ts": last_ts,
                 "age_hours": None, "events": len(rows)}
            )
            continue
        try:
            age = (now - datetime.fromisoformat(last_ts)).total_seconds() / 3600.0
        except ValueError:
            age = None
        status = "stale" if (age is not None and age > stale_hours) else "fresh"
        out.append(
            {"source": label, "status": status, "last_ts": last_ts,
             "age_hours": round(age, 1) if age is not None else None, "events": len(rows)}
        )
    return out


def effectiveness_verdict(report: dict[str, Any]) -> list[str]:
    """One-line-each signals answering 'is memory getting more effective?'."""
    s = report["surfacing"]
    li = report["lifecycle"]
    ing = report["ingestion"]
    mnt = report["maintenance"]
    rd = report["read"]
    lines = [
        f"surfacing: injected {s['injected_rate']:.0%} · no-results {s['no_results_rate']:.0%} "
        f"({s['total_invocations']} calls)",
        f"ingestion: saved {ing['saved']} · dup_rate {ing['dup_rate']:.0%} "
        f"({ing['attempted']} attempts)",
        f"forget: volume {mnt['forget_volume']} · rate {mnt['forget_rate']:.0%} "
        f"({mnt['runs']} cadence runs)",
        f"federated read: hit-rate {rd['hit_rate']:.0%} ({rd['searches']} queries)",
        f"confidence drift: {li['confidence_drift_avg']:+.3f} "
        f"({li['confidence_mutations']} mutations)",
    ]
    return lines


# --------------------------------------------------------------------------- #
# Build + render
# --------------------------------------------------------------------------- #
def build_report(since: str | None, now: datetime, stale_hours: float) -> dict[str, Any]:
    cutoff = _parse_since(since, now)
    sinks = dict(known_sinks(PROJECT_ROOT))

    def rows(label: str) -> list[dict[str, Any]]:
        return read_window(sinks[label], cutoff)

    report: dict[str, Any] = {
        "generated": now.isoformat(timespec="seconds"),
        "window": since or "all",
        "stale_hours": stale_hours,
        "surfacing": analyze_surfacing(rows("surfacing")),
        "lifecycle": analyze_lifecycle(rows("lifecycle")),
        "ingestion": analyze_ingestion(rows("ingestion")),
        "maintenance": analyze_maintenance(rows("maintenance")),
        "routing": analyze_routing(rows("routing")),
        "read": analyze_read(rows("read")),
        "propagation": analyze_propagation(rows("propagation")),
        "circuit": analyze_circuit(rows("circuit")),
        "audit": analyze_audit(rows("audit")),
        "freshness": analyze_freshness(now, stale_hours),
    }
    report["verdict"] = effectiveness_verdict(report)
    report["regressions"] = [f for f in report["freshness"] if f["status"] == "stale"]
    return report


def render_markdown(report: dict[str, Any]) -> str:
    s, li = report["surfacing"], report["lifecycle"]
    ing, mnt = report["ingestion"], report["maintenance"]
    rt, rd = report["routing"], report["read"]
    pr, ci, au = report["propagation"], report["circuit"], report["audit"]
    fresh = report["freshness"]
    n_fresh = sum(1 for f in fresh if f["status"] == "fresh")
    n_stale = sum(1 for f in fresh if f["status"] == "stale")
    n_cold = sum(1 for f in fresh if f["status"] in ("missing", "empty"))

    lines = [
        "# Memory Observability Report (§27 P4)",
        "",
        f"- **Generated:** {report['generated']}  ·  **Window:** {report['window']}",
        f"- **Sinks:** {n_fresh} fresh · {n_stale} stale (regressions) · {n_cold} cold/empty "
        f"(of {len(fresh)})",
        "",
        "## Effectiveness verdict",
        "",
    ]
    lines += [f"- {v}" for v in report["verdict"]]
    lines += [
        "",
        "## Ingestion (§26)",
        "",
        f"- Attempts: **{ing['attempted']}** · saved **{ing['saved']}** · "
        f"dup_rate **{ing['dup_rate']:.1%}** · actions `{ing['actions']}`",
        f"- By harvester: `{ing['by_harvester']}`",
        f"- Store sizes (latest): `{ing['logged_store_sizes']}`",
        f"- Store growth (window): `{ing['store_growth']}`",
        "",
        "## Maintenance cadence / forget (P4)",
        "",
        f"- Runs: **{mnt['runs']}** (applied {mnt['applied_runs']}) · "
        f"forget_volume **{mnt['forget_volume']}** · forget_rate **{mnt['forget_rate']:.1%}**",
        f"- Cross-store dup_rate (latest): **{mnt['dup_rate_latest']}**",
        f"- Store sizes (latest cadence): `{mnt['store_sizes_latest']}`",
        "",
        "## Routing (§27 D1.1)",
        "",
        f"- Routes: **{rt['routes']}** · targets `{rt['target_distribution']}` · "
        f"methods `{rt['method_distribution']}`",
        "",
        "## Federated read (§27 D1.2)",
        "",
        f"- Queries: **{rd['searches']}** · hit-rate **{rd['hit_rate']:.1%}** · "
        f"latency p50 **{rd['latency_ms']['p50']}ms** / p95 **{rd['latency_ms']['p95']}ms**",
        f"- Per-source hit-rate: `{rd['source_hit_rate']}`",
        "",
        "## Propagation (§27 D1.3)",
        "",
        f"- Events: **{pr['events']}** · avg_reach **{pr['avg_reach']}** · "
        f"max_reach **{pr['max_reach']}** · cascades_prevented **{pr['cascades_prevented']}** · "
        f"avg_depth **{pr['avg_depth']}**",
        "",
        "## Circuit breaker (§27 D1.4)",
        "",
        f"- Transitions: **{ci['transitions']}** · opens (trips) **{ci['opens']}** · "
        f"by circuit `{ci['by_circuit']}`",
        "",
        "## Audit coverage (§27 D0.3)",
        "",
        f"- Entries: **{au['total']}** · error-rate **{au['error_rate']:.1%}** · "
        f"by action `{au['by_action']}`",
        "",
        "## Surfacing & confidence (§24 / §22, via §25 analyzer)",
        "",
        f"- Surfacing: injected **{s['injected_rate']:.1%}** · no-results **{s['no_results_rate']:.1%}** "
        f"· TEI-down **{s['tei_down_rate']:.1%}** · gate-drop **{s['gate_drop_rate']:.1%}**",
        f"- Lifecycle: events **{li['total_events']}** · drift **{li['confidence_drift_avg']:+.3f}** "
        f"· reinforcement apply-rate **{li['reinforcement']['apply_rate']:.1%}**",
        "",
        "## Sink freshness / observability regressions",
        "",
        "| Sink | Status | Last seen | Age (h) | Events |",
        "|---|---|---|---|---|",
    ]
    for f in fresh:
        lines.append(
            f"| {f['source']} | {f['status']} | {f['last_ts'] or '—'} | "
            f"{f['age_hours'] if f['age_hours'] is not None else '—'} | {f['events']} |"
        )
    if report["regressions"]:
        lines += [
            "",
            f"> ⚠ **{len(report['regressions'])} observability regression(s)** — these sinks "
            "were logging and went silent past the staleness threshold:",
        ]
        lines += [f">   - `{r['source']}` (last {r['last_ts']}, {r['age_hours']}h ago)"
                  for r in report["regressions"]]
    else:
        lines += ["", "> No observability regressions (no stale sinks past threshold)."]
    lines += [
        "",
        "> `missing`/`empty` sinks are cold (never run / disabled), not regressions — "
        "MCP-side logs (routing/read/propagation/circuit/metrics) need an orchestrator run.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="§27 P4 unified memory observability report")
    ap.add_argument("--since", default=None, help="window: '24h', '7d', or ISO timestamp")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--stamp", default=None, help="override report timestamp (tests)")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS,
                    help="age past which a sink counts as a regression")
    ap.add_argument("--print", action="store_true", help="print markdown to stdout, skip files")
    args = ap.parse_args()

    now = datetime.fromisoformat(args.stamp) if args.stamp else datetime.now()
    report = build_report(args.since, now, args.stale_hours)
    md = render_markdown(report)

    if args.print:
        print(md)
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"observability-{stamp}.md"
    json_path = out_dir / f"observability-{stamp}.json"
    latest = out_dir / "_observability_latest.md"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(md, encoding="utf-8")
    print(f"Report: {md_path}")
    if report["regressions"]:
        print(f"[REGRESSION] {len(report['regressions'])} stale sink(s): "
              f"{[r['source'] for r in report['regressions']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
