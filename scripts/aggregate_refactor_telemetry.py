"""Aggregate refactor telemetry JSONL files into summary and proposed confidence updates.

Usage:
    python scripts/aggregate_refactor_telemetry.py [OPTIONS]

Options:
    --min-samples N       Minimum samples before proposing confidence change (default: 20)
    --delta-threshold X   Minimum confidence delta to emit proposal (default: 0.05)
    --since YYYY-MM-DD    Only include events from this date onward
    --stdout              Print summary to stdout instead of file
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _load_events(data_dir: Path, since: date | None = None) -> list[dict]:
    events: list[dict] = []
    for path in sorted(data_dir.glob("refactor-telemetry*.jsonl*")):
        opener = gzip.open if path.suffix == ".gz" else lambda p, *a, **kw: open(p, *a, **kw)
        with opener(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if since is not None:
                    event_date = event.get("timestamp", "")[:10]
                    if event_date < since.isoformat():
                        continue
                events.append(event)
    return events


def _compute_percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0, "p95": 0, "p99": 0}
    sorted_vals = sorted(values)
    return {
        "p50": sorted_vals[len(sorted_vals) // 2],
        "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
        "p99": sorted_vals[int(len(sorted_vals) * 0.99)],
    }


def _top_errors(codes: list[str | None], limit: int = 5) -> list[tuple[str, int, float]]:
    counts: dict[str, int] = defaultdict(int)
    total = len(codes)
    for code in codes:
        if code is not None:
            counts[code] += 1
    ranked = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    return [(code, cnt, cnt / total if total else 0) for code, cnt in ranked]


def aggregate(
    events: list[dict],
    current_confidence: dict[str, float] | None = None,
    min_samples: int = 20,
    delta_threshold: float = 0.05,
) -> tuple[str, dict[str, float]]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in events:
        key = (e.get("symbol_kind", "unknown"), e.get("primary_backend", "none"))
        groups[key].append(e)

    lines: list[str] = []
    proposals: dict[str, float] = {}
    current = current_confidence or {}

    lines.append("# Refactor Telemetry Summary\n")

    for (kind, backend), group in sorted(groups.items()):
        total = len(group)
        total_applies = sum(1 for e in group if e.get("applied"))
        success = sum(1 for e in group if e.get("applied") and not e.get("rolled_back"))
        fallback = sum(1 for e in group if e.get("fallback_used"))
        rollback = sum(1 for e in group if e.get("rolled_back"))
        durations = [e.get("duration_ms", 0) for e in group]
        error_codes = [e.get("error_code") for e in group]

        success_rate = success / total_applies if total_applies else 0
        fallback_rate = fallback / total if total else 0
        rollback_rate = rollback / total_applies if total_applies else 0
        proposed = max(0.1, min(0.95, success_rate * (1 - rollback_rate))) if total_applies else 0
        pctls = _compute_percentiles(durations)
        top_errs = _top_errors(error_codes)

        lines.append(f"## {kind} / {backend}\n")
        lines.append(f"- total_calls: {total}")
        lines.append(f"- total_applies: {total_applies}")
        lines.append(f"- success_rate: {success_rate:.3f}")
        lines.append(f"- fallback_rate: {fallback_rate:.3f}")
        lines.append(f"- rollback_rate: {rollback_rate:.3f}")
        lines.append(f"- proposed_confidence: {proposed:.3f}")
        lines.append(
            f"- latency: p50={pctls['p50']:.0f}ms p95={pctls['p95']:.0f}ms p99={pctls['p99']:.0f}ms"
        )
        if top_errs:
            lines.append("- top_errors:")
            for code, cnt, pct in top_errs:
                lines.append(f"  - {code}: {cnt} ({pct:.1%})")
        lines.append("")

        cur = current.get(kind, 0)
        if total >= min_samples and abs(proposed - cur) > delta_threshold:
            proposals[kind] = proposed

    summary = "\n".join(lines)
    return summary, proposals


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate refactor telemetry")
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--delta-threshold", type=float, default=0.05)
    parser.add_argument("--since", type=date.fromisoformat, default=None)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    events = _load_events(DATA_DIR, since=args.since)
    summary, proposals = aggregate(
        events,
        min_samples=args.min_samples,
        delta_threshold=args.delta_threshold,
    )

    if args.stdout:
        print(summary)
        if proposals:
            print("\n# Proposed Confidence Updates\n")
            for kind, conf in sorted(proposals.items()):
                print(f"  {kind}: {conf:.3f}")
    else:
        out_summary = DATA_DIR / "refactor-telemetry-summary.md"
        out_summary.write_text(summary, encoding="utf-8")
        print(f"Summary written to {out_summary}")

        if proposals:
            import yaml

            proposed_yaml = DATA_DIR / "refactor-telemetry-proposed.yaml"
            yaml.dump(
                {"proposed_confidence": proposals},
                proposed_yaml.open("w", encoding="utf-8"),
                default_flow_style=False,
            )
            print(f"Proposals written to {proposed_yaml}")
        else:
            print("No confidence proposals (insufficient data or delta too small)")


if __name__ == "__main__":
    main()
