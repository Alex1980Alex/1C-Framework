"""Summarize a single run from data/indexing-progress.jsonl.

Usage:
    python scripts/_progress_summarize.py                   # summarize most recent run
    python scripts/_progress_summarize.py --run-id <ID>      # summarize specific run
    python scripts/_progress_summarize.py --list             # list known runs
    python scripts/_progress_summarize.py --log <path>       # alternate JSONL path

Output (per run):
  * run_start / run_end timestamps + total elapsed
  * stage table — name, started_at, elapsed, status
  * event tallies — count per event name
  * sliding_window forward_s histogram (Phase 1/2 wall-clock signal)
  * late_chunk_fallback aggregate — total fallback%, top 10 worst modules
  * oom_recovery occurrences

Stdlib-only. Streams the JSONL once per call.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOG = SCRIPT_DIR.parent / "data" / "indexing-progress.jsonl"


def _load_records(path: Path, run_id: str | None) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"ERROR: log file not found: {path}")
        sys.exit(1)
    recs: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if run_id and r.get("run_id") != run_id:
            continue
        recs.append(r)
    return recs


def _list_runs(path: Path) -> None:
    seen: dict[str, dict[str, Any]] = {}
    for r in _load_records(path, None):
        rid = r.get("run_id") or "<no-run-id>"
        cur = seen.get(rid)
        if cur is None:
            seen[rid] = {
                "script": r.get("script", "?"),
                "first_ts": r.get("ts", ""),
                "last_ts": r.get("ts", ""),
                "records": 1,
            }
        else:
            cur["records"] += 1
            ts = r.get("ts", "")
            if ts:
                cur["last_ts"] = ts
    if not seen:
        print(f"No runs found in {path}")
        return
    print(f"{'run_id':<50} {'script':<28} {'records':>8}  {'first_ts':<25}")
    print("-" * 120)
    for rid, info in sorted(seen.items(), key=lambda kv: kv[1]["first_ts"]):
        print(f"{rid:<50} {info['script']:<28} {info['records']:>8}  {info['first_ts']:<25}")


def _histogram(values: list[float], bins: int = 6) -> list[tuple[float, float, int]]:
    """Return [(lo, hi, count), ...] equal-width bins over min..max."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [(lo, hi, len(values))]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, counts[i]) for i in range(bins)]


def _summarize_one(recs: list[dict[str, Any]]) -> None:
    if not recs:
        print("No records for this run_id.")
        return

    run_id = recs[0].get("run_id", "?")
    script = recs[0].get("script", "?")
    run_start = next((r for r in recs if r.get("category") == "run_start"), None)
    run_end = next((r for r in recs if r.get("category") == "run_end"), None)
    total_s = run_end.get("elapsed_s") if run_end else (recs[-1].get("elapsed_s") or 0.0)

    print("=" * 72)
    print(f"run_id : {run_id}")
    print(f"script : {script}")
    if run_start:
        print(f"started: {run_start.get('ts')}")
    if run_end:
        print(f"ended  : {run_end.get('ts')}  status: {'COMPLETE' if run_end else 'INCOMPLETE'}")
    else:
        print("ended  : (no run_end — process killed or still running)")
    print(f"elapsed: {total_s:.2f}s")
    if run_end:
        summary = {k: v for k, v in run_end.items()
                   if k not in ("ts", "run_id", "script", "category", "elapsed_s")}
        if summary:
            print(f"summary: {summary}")
    print("=" * 72)

    # ---- Stages
    stages = [r for r in recs if r.get("category") in ("stage_start", "stage_end")]
    open_starts: dict[str, float] = {}
    rows: list[tuple[str, float, float, str]] = []
    for r in stages:
        name = r.get("name") or ""
        ts_elapsed = r.get("elapsed_s") or 0.0
        if r["category"] == "stage_start":
            open_starts[name] = ts_elapsed
        else:
            start = open_starts.pop(name, None)
            dur = r.get("elapsed_s_inner") or r.get("elapsed_s")
            # stage_end's "elapsed_s" is the in-stage duration when wired in
            # _progress.py (see ProgressTracker.stage). Use it directly.
            status = "OK" if r.get("ok") else "FAIL"
            rows.append((name, start if start is not None else ts_elapsed,
                         r.get("elapsed_s", 0.0), status))
    if rows:
        print(f"\nStages ({len(rows)}):")
        print(f"  {'name':<28} {'started_at':>12} {'duration':>12}  status")
        for name, started, dur, status in rows:
            print(f"  {name:<28} {started:>10.2f}s {dur:>10.2f}s  {status}")

    # ---- Event tallies
    events = [r for r in recs if r.get("category") == "event"]
    if events:
        counter: Counter[str] = Counter(r.get("name", "?") for r in events)
        print(f"\nEvent counts ({len(events)} total):")
        for name, n in counter.most_common():
            print(f"  {name:<28} {n:>6}")

    # ---- Heartbeats
    hbs = [r for r in recs if r.get("category") == "heartbeat"]
    if hbs:
        max_idle = max((r.get("idle_s") or 0.0) for r in hbs)
        print(f"\nHeartbeats: {len(hbs)} (max idle observed: {max_idle:.1f}s)")
        # Show distribution of `current=...` snapshots — useful when files
        # vary wildly in processing time (god-objects vs small modules).
        currents = Counter(r.get("current") for r in hbs if r.get("current"))
        if currents:
            print("  files seen in heartbeats (top 5):")
            for cur, n in currents.most_common(5):
                print(f"    {n:>4}× {cur}")

    # ---- Sliding-window timings (the roadmap 260518 Phase 1/2 signal)
    sliding = [r for r in events if r.get("name") == "sliding_window" and "forward_s" in r]
    if sliding:
        fwd = [r["forward_s"] for r in sliding]
        print(f"\nSliding window forward_s ({len(sliding)} windows):")
        print(f"  min={min(fwd):.2f}s  median={statistics.median(fwd):.2f}s  "
              f"mean={statistics.mean(fwd):.2f}s  max={max(fwd):.2f}s")
        if len(fwd) >= 2:
            print(f"  stdev={statistics.stdev(fwd):.2f}s  total={sum(fwd):.1f}s")
        # Histogram
        print("  histogram:")
        for lo, hi, n in _histogram(fwd):
            bar = "▇" * min(n, 40)
            print(f"    {lo:6.2f}–{hi:6.2f}s  {n:>5}  {bar}")

    # ---- Sliding-start / module-level
    sliding_starts = [r for r in events if r.get("name") == "sliding_start"]
    if sliding_starts:
        print(f"\nSliding-window invocations: {len(sliding_starts)}")
        # Top 5 by token count — roughly the heaviest god-object modules.
        top = sorted(sliding_starts, key=lambda r: -(r.get("total_tokens") or 0))[:5]
        print(f"  {'total_tokens':>13} {'windows':>9} {'parent_chars':>13}")
        for r in top:
            print(f"  {r.get('total_tokens', 0):>13} {r.get('windows', 0):>9} "
                  f"{r.get('parent_chars', 0):>13}")

    # ---- Late-chunk fallback (Phase 1/2 quality signal)
    fallbacks = [r for r in events if r.get("name") == "late_chunk_fallback"]
    if fallbacks:
        total_fb = sum((r.get("fallback") or 0) for r in fallbacks)
        total_grp = sum((r.get("group") or 0) for r in fallbacks)
        ratio = (100.0 * total_fb / total_grp) if total_grp else 0.0
        print(f"\nLate-chunking fallback:")
        print(f"  groups with fallback: {len(fallbacks)}")
        print(f"  total fallback chunks: {total_fb} / {total_grp} ({ratio:.1f}%)")
        # By-module aggregate (a single module can produce many region groups).
        by_mod: dict[str, dict[str, int]] = defaultdict(
            lambda: {"fb": 0, "total": 0, "groups": 0})
        for r in fallbacks:
            mod = r.get("module_path") or "<unknown>"
            by_mod[mod]["fb"] += r.get("fallback") or 0
            by_mod[mod]["total"] += r.get("group") or 0
            by_mod[mod]["groups"] += 1
        print("  top 10 worst modules:")
        ranked = sorted(by_mod.items(),
                        key=lambda kv: -(kv[1]["fb"] / max(1, kv[1]["total"])))[:10]
        for mod, st in ranked:
            r_pct = 100.0 * st["fb"] / max(1, st["total"])
            print(f"    {r_pct:5.1f}%  {st['fb']:>5}/{st['total']:>5}  "
                  f"({st['groups']:>2} groups)  {mod}")

    # ---- OOM
    ooms = [r for r in events if r.get("name") == "oom_recovery"]
    if ooms:
        print(f"\nOOM recoveries: {len(ooms)}")
        for r in ooms[:5]:
            print(f"  batch={r.get('batch')} largest_chars={r.get('largest_chars')} "
                  f"largest_name={r.get('largest_name')}")
    print()


def _latest_run(path: Path) -> str | None:
    by_run: dict[str, str] = {}
    for r in _load_records(path, None):
        rid = r.get("run_id")
        ts = r.get("ts", "")
        if rid and ts:
            prev = by_run.get(rid, "")
            if ts > prev:
                by_run[rid] = ts
    if not by_run:
        return None
    return max(by_run.items(), key=lambda kv: kv[1])[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize an indexing-progress.jsonl run")
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG,
                    help=f"Path to JSONL log (default: {DEFAULT_LOG.name})")
    ap.add_argument("--run-id", default=None,
                    help="Run ID to summarize; default = most recent run")
    ap.add_argument("--list", action="store_true",
                    help="List all known runs and exit")
    args = ap.parse_args()

    if args.list:
        _list_runs(args.log)
        return 0

    rid = args.run_id or _latest_run(args.log)
    if rid is None:
        print(f"No runs found in {args.log}")
        return 1
    recs = _load_records(args.log, rid)
    _summarize_one(recs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
