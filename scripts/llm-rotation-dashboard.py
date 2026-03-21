#!/usr/bin/env python3
"""LLM Provider Performance Comparison Dashboard.

Reads data/llm-rotation-completions.jsonl and shows per-provider stats.
Usage:
    python scripts/llm-rotation-dashboard.py
    python scripts/llm-rotation-dashboard.py --json
    python scripts/llm-rotation-dashboard.py --last 100
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, quantiles

PRICE_PER_1K_TOKENS = {
    "zai-glm5": 0.002,
    "zhipu": 0.001,
    "gemini": 0.0,
    "openrouter": 0.0,
    "mistral": 0.001,
    "ollama-local": 0.0,
    "ollama-cloud": 0.0,
}


def parse_entries(file_path: Path, last_n: int | None = None) -> list[dict]:
    """Parse JSONL file, filter out health checks and 'none' provider."""
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Skip health check probes and "none" (all-failed markers)
            if entry.get("health_check") or entry.get("provider") == "none":
                continue
            entries.append(entry)

    if last_n is not None and last_n > 0:
        entries = entries[-last_n:]
    return entries


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 2:
        return values[0]
    return quantiles(values, n=100)[94]


def compute_stats(entries: list[dict]) -> dict:
    total = len(entries)
    errors = sum(1 for e in entries if e.get("error"))

    times = [e["response_time"] for e in entries if e.get("response_time")]
    avg_time = mean(times) if times else 0.0
    p95_time = p95(times)

    tokens = [
        (e.get("prompt_tokens", 0) or 0) + (e.get("completion_tokens", 0) or 0)
        for e in entries
    ]
    avg_tokens = mean(tokens) if tokens else 0.0

    total_cost = sum(
        ((e.get("prompt_tokens", 0) or 0) + (e.get("completion_tokens", 0) or 0))
        * PRICE_PER_1K_TOKENS.get(e.get("provider", ""), 0.0) / 1000.0
        for e in entries
    )

    return {
        "requests": total,
        "errors": errors,
        "error_pct": (errors / total * 100) if total > 0 else 0.0,
        "avg_time": round(avg_time, 3),
        "p95_time": round(p95_time, 3),
        "avg_tokens": round(avg_tokens, 1),
        "total_cost": round(total_cost, 6),
    }


def format_table(by_provider: dict[str, dict], summary: dict) -> str:
    hdr = (
        f"{'Provider':<15} {'Requests':>9} {'Errors':>7} {'Err%':>6} "
        f"{'AvgTime':>8} {'P95Time':>8} {'AvgTok':>8} {'TotalCost':>11}"
    )
    sep = "-" * len(hdr)
    lines = [hdr, sep]

    for name in sorted(by_provider):
        s = by_provider[name]
        lines.append(
            f"{name:<15} {s['requests']:>9} {s['errors']:>7} "
            f"{s['error_pct']:>5.1f}% {s['avg_time']:>7.2f}s "
            f"{s['p95_time']:>7.2f}s {s['avg_tokens']:>8.0f} "
            f"${s['total_cost']:>9.4f}"
        )

    lines.append(sep)
    lines.append(
        f"{'TOTAL':<15} {summary['total_requests']:>9} "
        f"{summary['total_errors']:>7} {summary['error_pct']:>5.1f}% "
        f"{'':>8} {'':>8} {'':>8} "
        f"${summary['total_cost']:>9.4f}"
    )
    return "\n".join(lines)


def date_range(entries: list[dict]) -> tuple[str, str]:
    timestamps = []
    for e in entries:
        ts = e.get("ts")
        if ts:
            try:
                timestamps.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                continue
    if not timestamps:
        return ("N/A", "N/A")
    return (
        min(timestamps).strftime("%Y-%m-%d %H:%M"),
        max(timestamps).strftime("%Y-%m-%d %H:%M"),
    )


def main():
    parser = argparse.ArgumentParser(description="LLM Provider Comparison Dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--last", type=int, metavar="N", help="Last N entries only")
    args = parser.parse_args()

    path = Path("data/llm-rotation-completions.jsonl")
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    entries = parse_entries(path, args.last)
    if not entries:
        print("No entries found.", file=sys.stderr)
        sys.exit(0)

    grouped: dict[str, list[dict]] = {}
    for e in entries:
        grouped.setdefault(e.get("provider", "unknown"), []).append(e)

    by_provider = {name: compute_stats(es) for name, es in grouped.items()}

    total_req = sum(s["requests"] for s in by_provider.values())
    total_err = sum(s["errors"] for s in by_provider.values())
    total_cost = sum(s["total_cost"] for s in by_provider.values())
    start, end = date_range(entries)

    summary = {
        "total_requests": total_req,
        "total_errors": total_err,
        "error_pct": (total_err / total_req * 100) if total_req > 0 else 0.0,
        "total_cost": round(total_cost, 6),
        "date_range": {"start": start, "end": end},
    }

    if args.json:
        print(json.dumps({"providers": by_provider, "summary": summary}, indent=2))
    else:
        print(format_table(by_provider, summary))
        print(f"\nDate range: {start} to {end}")


if __name__ == "__main__":
    main()
