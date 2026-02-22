#!/usr/bin/env python3
"""Hook & Skill Observability Dashboard — CLI tool.

Parses 3 log sources and displays activation metrics, latency, errors:
1. data/hook-invocations.jsonl  → hook invocation counts, p95 latency, errors
2. data/skill-router.log       → skill recommendations
3. data/skill-usage.log        → skill activations

Usage:
    python scripts/hook-dashboard.py                  # last 24h
    python scripts/hook-dashboard.py --period 7d      # last 7 days
    python scripts/hook-dashboard.py --period all      # all time
    python scripts/hook-dashboard.py --json            # JSON output
    python scripts/hook-dashboard.py --section skills  # skills only

Sections: summary, hooks, skills, errors, sessions (default: all)
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# --- Path resolution ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

INVOCATIONS_FILE = DATA_DIR / "hook-invocations.jsonl"
SKILL_ROUTER_LOG = DATA_DIR / "skill-router.log"
SKILL_USAGE_LOG = DATA_DIR / "skill-usage.log"


# --- Period parsing ---

def parse_period(period_str: str) -> datetime | None:
    """Parse period string to cutoff datetime. None = no filter."""
    if period_str == "all":
        return None
    now = datetime.now()
    if period_str.endswith("h"):
        hours = int(period_str[:-1])
        return now - timedelta(hours=hours)
    if period_str.endswith("d"):
        days = int(period_str[:-1])
        return now - timedelta(days=days)
    if period_str.endswith("w"):
        weeks = int(period_str[:-1])
        return now - timedelta(weeks=weeks)
    return now - timedelta(hours=24)  # default: 24h


# --- Log parsers ---

def parse_invocations(cutoff: datetime | None) -> list[dict]:
    """Parse hook-invocations.jsonl."""
    entries = []
    if not INVOCATIONS_FILE.exists():
        return entries
    try:
        with open(INVOCATIONS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if cutoff:
                        ts = datetime.fromisoformat(entry["ts"])
                        if ts < cutoff:
                            continue
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except OSError:
        pass
    return entries


def parse_skill_router_log(cutoff: datetime | None) -> list[dict]:
    """Parse skill-router.log (pipe-delimited format)."""
    entries = []
    if not SKILL_ROUTER_LOG.exists():
        return entries
    try:
        with open(SKILL_ROUTER_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(" | ")
                    ts_str = parts[0].strip()
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if cutoff and ts < cutoff:
                        continue
                    entry = {"ts": ts}
                    for part in parts[1:]:
                        if "=" in part:
                            k, v = part.split("=", 1)
                            entry[k.strip()] = v.strip()
                    entries.append(entry)
                except (ValueError, IndexError):
                    continue
    except OSError:
        pass
    return entries


def parse_skill_usage_log(cutoff: datetime | None) -> list[dict]:
    """Parse skill-usage.log (pipe-delimited format)."""
    entries = []
    if not SKILL_USAGE_LOG.exists():
        return entries
    try:
        with open(SKILL_USAGE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(" | ")
                    ts_str = parts[0].strip()
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if cutoff and ts < cutoff:
                        continue
                    entry = {"ts": ts}
                    for part in parts[1:]:
                        if "=" in part:
                            k, v = part.split("=", 1)
                            entry[k.strip()] = v.strip()
                    entries.append(entry)
                except (ValueError, IndexError):
                    continue
    except OSError:
        pass
    return entries


# --- Metrics computation ---

def compute_hook_metrics(invocations: list[dict]) -> dict[str, Any]:
    """Compute per-hook metrics from invocations."""
    by_hook: dict[str, list[dict]] = defaultdict(list)
    for inv in invocations:
        by_hook[inv.get("hook", "unknown")].append(inv)

    metrics = {}
    for hook, entries in sorted(by_hook.items()):
        latencies = [e.get("elapsed_ms", 0) for e in entries]
        outcomes = Counter(e.get("outcome", "allow") for e in entries)
        errors = [e for e in entries if e.get("error")]

        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0
        p95_idx = int(len(latencies_sorted) * 0.95)
        p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)] if latencies_sorted else 0

        metrics[hook] = {
            "count": len(entries),
            "outcomes": dict(outcomes),
            "p50_ms": p50,
            "p95_ms": p95,
            "max_ms": max(latencies) if latencies else 0,
            "errors": len(errors),
            "events": dict(Counter(e.get("event", "?") for e in entries)),
        }
    return metrics


def compute_skill_metrics(
    router_entries: list[dict],
    usage_entries: list[dict],
) -> dict[str, Any]:
    """Compute skill activation rate and per-skill metrics."""
    # Count recommendations (from skill-router.log)
    recommended: Counter = Counter()
    for entry in router_entries:
        skills_str = entry.get("skills", "")
        for skill in skills_str.split(","):
            skill = skill.strip()
            if skill:
                recommended[skill] += 1

    # Count activations (from skill-usage.log)
    activated: Counter = Counter()
    for entry in usage_entries:
        skill = entry.get("skill", "").strip()
        if skill:
            activated[skill] += 1

    total_recommended = sum(recommended.values())
    total_activated = sum(activated.values())

    # Per-skill breakdown
    all_skills = set(recommended.keys()) | set(activated.keys())
    per_skill = {}
    for skill in sorted(all_skills):
        rec = recommended.get(skill, 0)
        act = activated.get(skill, 0)
        per_skill[skill] = {
            "recommended": rec,
            "activated": act,
            "rate": (act / rec * 100) if rec > 0 else 0.0,
        }

    # Dead skills: recommended but never activated
    dead = [s for s in recommended if s not in activated]

    return {
        "total_recommended": total_recommended,
        "total_activated": total_activated,
        "activation_rate": (total_activated / total_recommended * 100) if total_recommended > 0 else 0.0,
        "per_skill": per_skill,
        "dead_skills": sorted(dead),
        "unique_recommended": len(recommended),
        "unique_activated": len(activated),
    }


def compute_session_metrics(invocations: list[dict]) -> dict[str, Any]:
    """Compute per-session metrics."""
    by_session: dict[str, list[dict]] = defaultdict(list)
    for inv in invocations:
        sid = inv.get("session", "")
        if sid:
            by_session[sid].append(inv)

    sessions = {}
    for sid, entries in by_session.items():
        timestamps = []
        for e in entries:
            try:
                timestamps.append(datetime.fromisoformat(e["ts"]))
            except (KeyError, ValueError):
                pass

        if timestamps:
            duration = (max(timestamps) - min(timestamps)).total_seconds()
        else:
            duration = 0

        sessions[sid[:12]] = {
            "invocations": len(entries),
            "hooks": len(set(e.get("hook", "") for e in entries)),
            "duration_min": round(duration / 60, 1),
            "errors": sum(1 for e in entries if e.get("error")),
        }

    return sessions


# --- Display formatters ---

def format_summary(
    hook_metrics: dict,
    skill_metrics: dict,
    invocations: list[dict],
    period: str,
) -> str:
    """Format summary section."""
    total_inv = sum(m["count"] for m in hook_metrics.values())
    total_errors = sum(m["errors"] for m in hook_metrics.values())
    total_blocks = sum(m["outcomes"].get("block", 0) for m in hook_metrics.values())

    all_latencies = []
    for inv in invocations:
        all_latencies.append(inv.get("elapsed_ms", 0))
    all_latencies.sort()
    p95_global = all_latencies[int(len(all_latencies) * 0.95)] if all_latencies else 0

    lines = [
        f"{'=' * 60}",
        f"  HOOK & SKILL OBSERVABILITY DASHBOARD",
        f"  Period: {period}",
        f"{'=' * 60}",
        "",
        f"  Total invocations:    {total_inv:>6}",
        f"  Unique hooks:         {len(hook_metrics):>6}",
        f"  Total errors:         {total_errors:>6}",
        f"  Total blocks:         {total_blocks:>6}",
        f"  Global p95 latency:   {p95_global:>5}ms",
        "",
        f"  Skills recommended:   {skill_metrics['total_recommended']:>6}",
        f"  Skills activated:     {skill_metrics['total_activated']:>6}",
        f"  Activation rate:      {skill_metrics['activation_rate']:>5.1f}%",
        f"  Dead skills:          {len(skill_metrics['dead_skills']):>6}",
        "",
    ]
    return "\n".join(lines)


def format_hooks(hook_metrics: dict) -> str:
    """Format hooks section."""
    if not hook_metrics:
        return "  No hook invocations recorded.\n"

    lines = [
        f"{'─' * 60}",
        f"  HOOK INVOCATIONS",
        f"{'─' * 60}",
        f"  {'Hook':<30} {'Count':>6} {'p95ms':>6} {'Block':>6} {'Err':>4}",
        f"  {'─' * 52}",
    ]

    # Sort by count descending
    sorted_hooks = sorted(hook_metrics.items(), key=lambda x: x[1]["count"], reverse=True)
    for hook, m in sorted_hooks:
        blocks = m["outcomes"].get("block", 0)
        lines.append(
            f"  {hook:<30} {m['count']:>6} {m['p95_ms']:>5}ms {blocks:>6} {m['errors']:>4}"
        )

    lines.append("")
    return "\n".join(lines)


def format_skills(skill_metrics: dict) -> str:
    """Format skills section."""
    lines = [
        f"{'─' * 60}",
        f"  SKILL ACTIVATION",
        f"{'─' * 60}",
        f"  {'Skill':<30} {'Rec':>5} {'Act':>5} {'Rate':>6}",
        f"  {'─' * 48}",
    ]

    per_skill = skill_metrics.get("per_skill", {})
    if not per_skill:
        lines.append("  No skill data recorded.")
        lines.append("")
        return "\n".join(lines)

    # Sort by recommended count descending
    sorted_skills = sorted(per_skill.items(), key=lambda x: x[1]["recommended"], reverse=True)
    for skill, m in sorted_skills:
        rate_str = f"{m['rate']:.0f}%" if m["recommended"] > 0 else "—"
        lines.append(
            f"  {skill:<30} {m['recommended']:>5} {m['activated']:>5} {rate_str:>6}"
        )

    if skill_metrics.get("dead_skills"):
        lines.append("")
        lines.append(f"  Dead skills (recommended but never activated):")
        for s in skill_metrics["dead_skills"][:10]:
            lines.append(f"    - {s}")

    lines.append("")
    return "\n".join(lines)


def format_errors(invocations: list[dict]) -> str:
    """Format errors section."""
    errors = [inv for inv in invocations if inv.get("error")]
    if not errors:
        return f"{'─' * 60}\n  ERRORS: None\n"

    lines = [
        f"{'─' * 60}",
        f"  ERRORS ({len(errors)} total)",
        f"{'─' * 60}",
    ]

    # Show last 10 errors
    for err in errors[-10:]:
        ts = err.get("ts", "?")[:19]
        hook = err.get("hook", "?")
        error = err.get("error", "?")[:60]
        lines.append(f"  [{ts}] {hook}: {error}")

    lines.append("")
    return "\n".join(lines)


def format_sessions(session_metrics: dict) -> str:
    """Format sessions section."""
    if not session_metrics:
        return f"{'─' * 60}\n  SESSIONS: No data\n"

    lines = [
        f"{'─' * 60}",
        f"  SESSIONS ({len(session_metrics)} total)",
        f"{'─' * 60}",
        f"  {'Session':<14} {'Invoc':>6} {'Hooks':>6} {'Dur':>7} {'Err':>4}",
        f"  {'─' * 40}",
    ]

    for sid, m in sorted(session_metrics.items(), key=lambda x: x[1]["invocations"], reverse=True)[:10]:
        dur = f"{m['duration_min']}m"
        lines.append(
            f"  {sid:<14} {m['invocations']:>6} {m['hooks']:>6} {dur:>7} {m['errors']:>4}"
        )

    lines.append("")
    return "\n".join(lines)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Hook & Skill Observability Dashboard"
    )
    parser.add_argument(
        "--period", default="24h",
        help="Time period: 1h, 24h, 7d, 4w, all (default: 24h)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--section", default="all",
        choices=["all", "summary", "hooks", "skills", "errors", "sessions"],
        help="Show specific section only"
    )
    args = parser.parse_args()

    cutoff = parse_period(args.period)

    # Parse all log sources
    invocations = parse_invocations(cutoff)
    router_entries = parse_skill_router_log(cutoff)
    usage_entries = parse_skill_usage_log(cutoff)

    # Compute metrics
    hook_metrics = compute_hook_metrics(invocations)
    skill_metrics = compute_skill_metrics(router_entries, usage_entries)
    session_metrics = compute_session_metrics(invocations)

    if args.json:
        output = {
            "period": args.period,
            "cutoff": cutoff.isoformat() if cutoff else None,
            "hooks": hook_metrics,
            "skills": skill_metrics,
            "sessions": session_metrics,
            "total_invocations": len(invocations),
            "total_errors": sum(1 for i in invocations if i.get("error")),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return

    # Format and print sections
    section = args.section
    output_parts = []

    if section in ("all", "summary"):
        output_parts.append(format_summary(hook_metrics, skill_metrics, invocations, args.period))
    if section in ("all", "hooks"):
        output_parts.append(format_hooks(hook_metrics))
    if section in ("all", "skills"):
        output_parts.append(format_skills(skill_metrics))
    if section in ("all", "errors"):
        output_parts.append(format_errors(invocations))
    if section in ("all", "sessions"):
        output_parts.append(format_sessions(session_metrics))

    print("\n".join(output_parts))


if __name__ == "__main__":
    main()
