#!/usr/bin/env python3
"""Check benchmark results against a baseline for regression detection.

Reads the latest benchmark JSONL file and compares success rate
against a configurable threshold. Exits with code 1 on regression.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _latest_run(data_dir: Path) -> Path | None:
    # Strategy 1: find benchmark output dirs (contain *_report.csv)
    candidates = sorted(data_dir.rglob("*_report.csv"), key=lambda p: p.stat().st_mtime)
    if candidates:
        report_dir = candidates[-1].parent
        jsonl_files = sorted(report_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if jsonl_files:
            return jsonl_files[-1]

    # Strategy 2: find any JSONL with benchmark events
    jsonl_files = sorted(data_dir.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    for jf in reversed(jsonl_files):
        with open(jf, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "primary_backend" in ev:
                    return jf
                break
    return None


def check(run_dir: Path, threshold: float) -> int:
    jsonl_path = _latest_run(run_dir)
    if jsonl_path is None:
        print(f"ERROR: No .jsonl files found in {run_dir}")
        return 2

    total = 0
    applied = 0
    per_backend: dict[str, dict[str, int]] = {}

    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            backend = event.get("primary_backend", "unknown")
            if backend not in per_backend:
                per_backend[backend] = {"total": 0, "applied": 0}
            per_backend[backend]["total"] += 1
            if event.get("applied"):
                applied += 1
                per_backend[backend]["applied"] += 1

    if total == 0:
        print("ERROR: No events found in JSONL")
        return 2

    rate = applied / total
    print(f"Run:       {jsonl_path.name}")
    print(f"Total:     {total}")
    print(f"Applied:   {applied}")
    print(f"Rate:      {rate:.1%}")
    print(f"Threshold: {threshold:.1%}")
    print()

    for backend, stats in sorted(per_backend.items()):
        b_rate = stats["applied"] / max(stats["total"], 1)
        print(f"  {backend}: {b_rate:.1%} ({stats['applied']}/{stats['total']})")

    if rate < threshold:
        print(f"\nREGRESSION: {rate:.1%} < {threshold:.1%}")
        return 1

    print("\nOK: above threshold")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Check benchmark regression")
    ap.add_argument(
        "--data-dir", type=Path, default=None, help="Directory with benchmark JSONL files"
    )
    ap.add_argument(
        "--threshold", type=float, default=0.70, help="Minimum success rate (default: 0.70)"
    )
    args = ap.parse_args()

    data_dir = args.data_dir or REPO_ROOT / "data"
    sys.exit(check(data_dir, args.threshold))


if __name__ == "__main__":
    main()
