#!/usr/bin/env python3
"""AutoResearch v2 CLI Dashboard.

Reads TSV/JSONL logs and displays progress summary.

Usage:
    python scripts/autoresearch-dashboard.py
    python scripts/autoresearch-dashboard.py data/autoresearch/api-speed/
    python scripts/autoresearch-dashboard.py --json
"""

import json
import os
import sys
from pathlib import Path


def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file."""
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def load_state(md_path: str) -> dict:
    """Parse autoresearch.md state file."""
    state = {}
    if not os.path.exists(md_path):
        return state
    with open(md_path, "r", encoding="utf-8") as f:
        for line in f:
            for key in ("Domain", "Iteration", "BestMetric", "Plateau", "Target", "BaselineCommit", "Updated"):
                if line.startswith(f"{key}:"):
                    val = line.split(":", 1)[1].strip()
                    state[key.lower()] = val
    return state


def render_dashboard(session_dir: str, as_json: bool = False):
    """Render the dashboard for a session directory."""
    jsonl_path = os.path.join(session_dir, "autoresearch.jsonl")
    md_path = os.path.join(session_dir, "autoresearch.md")

    entries = load_jsonl(jsonl_path)
    state = load_state(md_path)

    if not entries and not state:
        print(f"[No data] {session_dir}")
        return

    domain = state.get("domain", "unknown")
    iteration = state.get("iteration", "0")
    best = state.get("bestmetric", "N/A")
    target = state.get("target", "N/A")
    plateau = state.get("plateau", "0")
    baseline_commit = state.get("baselinecommit", "N/A")
    updated = state.get("updated", "N/A")

    # Compute stats from entries
    kept = sum(1 for e in entries if e.get("verdict") == "KEEP" or e.get("action") == "keep")
    reverted = sum(1 for e in entries if e.get("verdict") == "REVERT" or e.get("action") == "revert")
    skipped = sum(1 for e in entries if e.get("verdict") == "SKIP" or e.get("action") == "skip")
    unknown = len(entries) - kept - reverted - skipped

    # Metric progression
    metrics = [e.get("metric_after") or e.get("metric") for e in entries if (e.get("metric_after") or e.get("metric")) is not None]

    if as_json:
        print(json.dumps({
            "domain": domain, "iteration": iteration, "best_metric": best,
            "target": target, "plateau": plateau, "total_entries": len(entries),
            "kept": kept, "reverted": reverted, "skipped": skipped,
            "metric_history": metrics,
        }, indent=2))
        return

    # --- ASCII Dashboard ---
    title = f"AutoResearch: {domain}"
    print(f"\n{title}")
    print("=" * max(len(title), 50))

    status = "ACTIVE"
    if target and target != "N/A" and best and best != "N/A":
        try:
            if float(best) >= float(target):
                status = "TARGET REACHED"
        except ValueError:
            pass
    if int(plateau) >= 5:
        status = "PLATEAU"

    print(f"Iterations: {iteration} | Kept: {kept} | Reverted: {reverted} | Skipped: {skipped}")
    print(f"Best: {best} | Target: {target} | Plateau: {plateau} | Status: {status}")
    print(f"Baseline: {baseline_commit} | Updated: {updated}")

    # Metric chart (simple ASCII)
    if metrics:
        print(f"\nMetric progression ({len(metrics)} points):")
        nums = [float(m) for m in metrics if m is not None]
        if nums:
            mn, mx = min(nums), max(nums)
            width = 40
            for idx, val in enumerate(nums):
                bar_len = int((val - mn) / (mx - mn + 0.001) * width) if mx > mn else width // 2
                bar = "#" * max(bar_len, 1)
                marker = " <-- best" if val == max(nums) else ""
                print(f"  {idx+1:3d} | {val:8.4f} {bar}{marker}")

    # Top improvements
    improvements = []
    for e in entries:
        delta = e.get("delta", 0)
        verdict = e.get("verdict", e.get("action", ""))
        if verdict in ("KEEP", "keep") and delta and abs(float(delta)) > 0:
            improvements.append((float(delta), e.get("change", e.get("desc", "?")), e.get("iter", "?")))

    if improvements:
        improvements.sort(key=lambda x: abs(x[0]), reverse=True)
        print(f"\nTop improvements:")
        for delta, change, it in improvements[:5]:
            sign = "+" if delta > 0 else ""
            print(f"  {sign}{delta:.4f}  iter {it}: {change[:50]}")

    print()


def main():
    as_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        session_dir = args[0]
    else:
        session_dir = "data"

    # Check if the directory itself has autoresearch files (flat layout)
    if os.path.isdir(session_dir) and os.path.exists(os.path.join(session_dir, "autoresearch.jsonl")):
        render_dashboard(session_dir, as_json)
        return

    # Check subdirectories for sessions
    if os.path.isdir(session_dir):
        found = False
        for d in sorted(Path(session_dir).iterdir()):
            if d.is_dir() and (d / "autoresearch.jsonl").exists():
                render_dashboard(str(d), as_json)
                found = True
        if not found:
            print(f"[No sessions found in {session_dir}]")
    else:
        print(f"[ERROR] Directory not found: {session_dir}")
        sys.exit(1)


if __name__ == "__main__":
    main()
