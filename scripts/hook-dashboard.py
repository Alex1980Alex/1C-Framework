#!/usr/bin/env python3
"""Hook & Skill Observability Dashboard - CLI tool.

Parses 4 log sources and displays activation metrics, latency, errors, accuracy:
1. data/hook-invocations.jsonl  → hook invocation counts, p95 latency, errors
2. data/skill-router.log       → skill recommendations
3. data/skill-usage.log        → skill activations
4. data/skill-accuracy.jsonl   → per-prompt recommend→activate correlation

Usage:
    python scripts/hook-dashboard.py                    # last 24h
    python scripts/hook-dashboard.py --period 7d        # last 7 days
    python scripts/hook-dashboard.py --period all        # all time
    python scripts/hook-dashboard.py --json              # JSON output
    python scripts/hook-dashboard.py --section accuracy  # accuracy only

Sections: summary, hooks, skills, accuracy, errors, sessions (default: all)
"""

import argparse
import json
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
SKILL_ACCURACY_LOG = DATA_DIR / "skill-accuracy.jsonl"


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


def parse_skill_accuracy_log(cutoff: datetime | None) -> list[dict]:
    """Parse skill-accuracy.jsonl (JSONL with prompt_id correlation)."""
    entries = []
    if not SKILL_ACCURACY_LOG.exists():
        return entries
    try:
        with open(SKILL_ACCURACY_LOG, "r", encoding="utf-8") as f:
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
    by_source: Counter = Counter()
    per_skill_source: dict[str, Counter] = defaultdict(Counter)
    for entry in usage_entries:
        skill = entry.get("skill", "").strip()
        source = entry.get("source", "post-tool-use").strip()
        if skill:
            activated[skill] += 1
            by_source[source] += 1
            per_skill_source[skill][source] += 1

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
            "sources": dict(per_skill_source.get(skill, {})),
        }

    # Dead skills: recommended but never activated
    dead = [s for s in recommended if s not in activated]

    return {
        "total_recommended": total_recommended,
        "total_activated": total_activated,
        "activation_rate": (total_activated / total_recommended * 100) if total_recommended > 0 else 0.0,
        "by_source": dict(by_source),
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


def compute_accuracy_metrics(accuracy_entries: list[dict]) -> dict[str, Any]:
    """Compute per-prompt accuracy: recommended skills → activated skills.

    Groups entries by prompt_id and computes match/miss rates.
    """
    # Group by prompt_id
    by_prompt: dict[str, dict] = {}
    for entry in accuracy_entries:
        pid = entry.get("prompt_id", "")
        if not pid:
            continue

        if pid not in by_prompt:
            by_prompt[pid] = {
                "recommended": [],
                "activated": [],
                "prompt": "",
                "ts": entry.get("ts", ""),
            }

        etype = entry.get("type", "")
        if etype == "recommend":
            by_prompt[pid]["recommended"] = entry.get("skills", [])
            by_prompt[pid]["prompt"] = entry.get("prompt", "")
            if not by_prompt[pid]["ts"]:
                by_prompt[pid]["ts"] = entry.get("ts", "")
        elif etype == "activate":
            skill = entry.get("skill", "")
            if skill and skill not in by_prompt[pid]["activated"]:
                by_prompt[pid]["activated"].append(skill)

    if not by_prompt:
        return {
            "total_prompts": 0,
            "matched_prompts": 0,
            "missed_prompts": 0,
            "match_rate": 0.0,
            "per_skill_precision": {},
            "recent_misses": [],
        }

    # Compute match/miss per prompt
    matched = 0
    missed = 0
    # Per-skill: how many times recommended → activated
    skill_rec_count: Counter = Counter()
    skill_act_count: Counter = Counter()
    recent_misses: list[dict] = []

    for pid, data in by_prompt.items():
        rec_set = set(data["recommended"])
        act_set = set(data["activated"])

        # Count per-skill precision
        for s in rec_set:
            skill_rec_count[s] += 1
            if s in act_set:
                skill_act_count[s] += 1

        # Match = at least one recommended skill was activated
        if rec_set & act_set:
            matched += 1
        else:
            missed += 1
            recent_misses.append({
                "prompt_id": pid,
                "ts": data["ts"][:19],
                "prompt": data["prompt"][:60],
                "recommended": data["recommended"],
            })

    total = matched + missed
    per_skill_precision = {}
    for skill in sorted(skill_rec_count.keys()):
        rec = skill_rec_count[skill]
        act = skill_act_count.get(skill, 0)
        per_skill_precision[skill] = {
            "recommended": rec,
            "activated": act,
            "precision": round(act / rec * 100, 1) if rec > 0 else 0.0,
        }

    return {
        "total_prompts": total,
        "matched_prompts": matched,
        "missed_prompts": missed,
        "match_rate": round(matched / total * 100, 1) if total > 0 else 0.0,
        "per_skill_precision": per_skill_precision,
        "recent_misses": recent_misses[-10:],  # Last 10 misses
    }


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
        f"{'=' * 62}",
        f"  HOOK & SKILL OBSERVABILITY DASHBOARD",
        f"  Period: {period}",
        f"{'=' * 62}",
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
        f"{'-' * 62}",
        f"  HOOK INVOCATIONS",
        f"{'-' * 62}",
        f"  {'Hook':<30} {'Count':>6} {'p95ms':>6} {'Block':>6} {'Err':>4}",
        f"  {'-' * 54}",
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
    by_source = skill_metrics.get("by_source", {})
    source_summary = ""
    if by_source:
        parts = [f"{src}: {cnt}" for src, cnt in sorted(by_source.items())]
        source_summary = f"  Sources: {', '.join(parts)}"

    lines = [
        f"{'-' * 74}",
        f"  SKILL ACTIVATION",
        f"{'-' * 74}",
    ]
    if source_summary:
        lines.append(source_summary)
        lines.append("")
    lines.extend([
        f"  {'Skill':<28} {'Rec':>5} {'Act':>5} {'Rate':>6}  {'Source'}",
        f"  {'-' * 68}",
    ])

    per_skill = skill_metrics.get("per_skill", {})
    if not per_skill:
        lines.append("  No skill data recorded.")
        lines.append("")
        return "\n".join(lines)

    # Sort by recommended count descending
    sorted_skills = sorted(per_skill.items(), key=lambda x: x[1]["recommended"], reverse=True)
    for skill, m in sorted_skills:
        rate_str = f"{m['rate']:.0f}%" if m["recommended"] > 0 else "-"
        sources = m.get("sources", {})
        if sources:
            src_parts = [f"{s}:{c}" for s, c in sorted(sources.items())]
            src_str = " ".join(src_parts)
        else:
            src_str = "-"
        lines.append(
            f"  {skill:<28} {m['recommended']:>5} {m['activated']:>5} {rate_str:>6}  {src_str}"
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
        return f"{'-' * 62}\n  ERRORS: None\n"

    lines = [
        f"{'-' * 62}",
        f"  ERRORS ({len(errors)} total)",
        f"{'-' * 62}",
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
        return f"{'-' * 62}\n  SESSIONS: No data\n"

    lines = [
        f"{'-' * 62}",
        f"  SESSIONS ({len(session_metrics)} total)",
        f"{'-' * 62}",
        f"  {'Session':<14} {'Invoc':>6} {'Hooks':>6} {'Dur':>7} {'Err':>4}",
        f"  {'-' * 42}",
    ]

    for sid, m in sorted(session_metrics.items(), key=lambda x: x[1]["invocations"], reverse=True)[:10]:
        dur = f"{m['duration_min']}m"
        lines.append(
            f"  {sid:<14} {m['invocations']:>6} {m['hooks']:>6} {dur:>7} {m['errors']:>4}"
        )

    lines.append("")
    return "\n".join(lines)


def format_accuracy(accuracy_metrics: dict) -> str:
    """Format accuracy section — per-prompt recommend→activate correlation."""
    total = accuracy_metrics.get("total_prompts", 0)
    if total == 0:
        return f"{'-' * 62}\n  SKILL ACCURACY: No data (skill-accuracy.jsonl empty)\n"

    matched = accuracy_metrics["matched_prompts"]
    missed = accuracy_metrics["missed_prompts"]
    rate = accuracy_metrics["match_rate"]

    lines = [
        f"{'-' * 62}",
        f"  SKILL ACCURACY (per-prompt correlation)",
        f"{'-' * 62}",
        "",
        f"  Total prompts:        {total:>6}",
        f"  Matched (>=1 act):    {matched:>6}",
        f"  Missed (0 act):       {missed:>6}",
        f"  Match rate:           {rate:>5.1f}%",
        "",
        f"  {'Skill':<30} {'Rec':>5} {'Act':>5} {'Prec':>6}",
        f"  {'-' * 50}",
    ]

    psp = accuracy_metrics.get("per_skill_precision", {})
    sorted_skills = sorted(psp.items(), key=lambda x: x[1]["recommended"], reverse=True)
    for skill, m in sorted_skills:
        prec_str = f"{m['precision']:.0f}%"
        lines.append(
            f"  {skill:<30} {m['recommended']:>5} {m['activated']:>5} {prec_str:>6}"
        )

    misses = accuracy_metrics.get("recent_misses", [])
    if misses:
        lines.append("")
        lines.append(f"  Recent misses ({len(misses)}):")
        for miss in misses[-5:]:
            skills_str = ",".join(miss["recommended"][:3])
            lines.append(
                f"    [{miss['ts']}] {miss['prompt'][:40]}... -> {skills_str}"
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
        choices=["all", "summary", "hooks", "skills", "accuracy", "errors", "sessions"],
        help="Show specific section only"
    )
    args = parser.parse_args()

    cutoff = parse_period(args.period)

    # Parse all log sources
    invocations = parse_invocations(cutoff)
    router_entries = parse_skill_router_log(cutoff)
    usage_entries = parse_skill_usage_log(cutoff)
    accuracy_entries = parse_skill_accuracy_log(cutoff)

    # Compute metrics
    hook_metrics = compute_hook_metrics(invocations)
    skill_metrics = compute_skill_metrics(router_entries, usage_entries)
    session_metrics = compute_session_metrics(invocations)
    accuracy_metrics = compute_accuracy_metrics(accuracy_entries)

    if args.json:
        output = {
            "period": args.period,
            "cutoff": cutoff.isoformat() if cutoff else None,
            "hooks": hook_metrics,
            "skills": skill_metrics,
            "accuracy": accuracy_metrics,
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
    if section in ("all", "accuracy"):
        output_parts.append(format_accuracy(accuracy_metrics))
    if section in ("all", "errors"):
        output_parts.append(format_errors(invocations))
    if section in ("all", "sessions"):
        output_parts.append(format_sessions(session_metrics))

    print("\n".join(output_parts))


if __name__ == "__main__":
    main()
