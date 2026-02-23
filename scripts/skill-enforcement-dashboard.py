#!/usr/bin/env python3
"""Skill Enforcement Dashboard - CLI tool.

Reads hook-invocations.jsonl and code-skill-patterns.json
to display enforcement metrics: decisions, by-level, performance, accuracy, coverage.

Usage:
    python scripts/skill-enforcement-dashboard.py                    # all sections
    python scripts/skill-enforcement-dashboard.py --section decisions # one section
    python scripts/skill-enforcement-dashboard.py --json             # JSON output
    python scripts/skill-enforcement-dashboard.py --period 7d        # last 7 days

Sections: decisions, levels, performance, accuracy, coverage (default: all)
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Path resolution ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"

INVOCATIONS_FILE = DATA_DIR / "hook-invocations.jsonl"
PATTERNS_FILE = HOOKS_DIR / "shared" / "code-skill-patterns.json"


# --- Period parsing ---

def parse_period(period_str: str) -> Optional[datetime]:
    """Parse period string to cutoff datetime. None = no filter."""
    if period_str == "all":
        return None
    now = datetime.now()
    if period_str.endswith("h"):
        return now - timedelta(hours=int(period_str[:-1]))
    if period_str.endswith("d"):
        return now - timedelta(days=int(period_str[:-1]))
    return now - timedelta(hours=24)


def load_invocations(cutoff: Optional[datetime]) -> List[Dict[str, Any]]:
    """Load enforcement invocations from hook-invocations.jsonl."""
    entries = []
    if not INVOCATIONS_FILE.exists():
        return entries

    with open(INVOCATIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter for code-skill-enforcer entries
            hook_name = entry.get("hook", "")
            if "CodeSkillEnforcer" not in hook_name and "code-skill-enforcer" not in hook_name:
                continue

            # Filter by period
            if cutoff:
                ts_str = entry.get("timestamp", "")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").split("+")[0])
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

            entries.append(entry)

    return entries


def load_patterns() -> Dict[str, Any]:
    """Load patterns config."""
    if not PATTERNS_FILE.exists():
        return {}
    with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Dashboard sections ---

def section_decisions(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Decision breakdown: block/allow/advise/learn."""
    outcomes = Counter()
    for e in entries:
        outcome = e.get("outcome", "unknown")
        outcomes[outcome] += 1

    total = len(entries)
    return {
        "total_invocations": total,
        "outcomes": dict(outcomes),
        "block_rate": f"{outcomes.get('block', 0) / total * 100:.1f}%" if total else "N/A",
    }


def section_levels(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Breakdown by enforcement level (A-F)."""
    levels = Counter()
    for e in entries:
        extra = e.get("extra", {})
        level = extra.get("level", "unknown")
        levels[level] += 1
    return {"by_level": dict(levels)}


def section_performance(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Latency statistics."""
    latencies = []
    for e in entries:
        ms = e.get("elapsed_ms")
        if ms is not None:
            latencies.append(float(ms))

    if not latencies:
        return {"avg_ms": "N/A", "p95_ms": "N/A", "max_ms": "N/A", "count": 0}

    latencies.sort()
    p95_idx = int(len(latencies) * 0.95)
    return {
        "avg_ms": f"{sum(latencies) / len(latencies):.1f}",
        "p95_ms": f"{latencies[p95_idx]:.1f}" if p95_idx < len(latencies) else "N/A",
        "max_ms": f"{max(latencies):.1f}",
        "count": len(latencies),
    }


def section_accuracy(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Accuracy: how many blocks led to skill activation vs abandonment."""
    blocks = [e for e in entries if e.get("outcome") == "block"]
    # Heuristic: if a block is followed by an allow for same skill, it was activated
    # Without full session tracking, report counts
    skills_blocked = Counter()
    for e in blocks:
        extra = e.get("extra", {})
        skill = extra.get("skill", "unknown")
        skills_blocked[skill] += 1

    return {
        "total_blocks": len(blocks),
        "blocked_skills": dict(skills_blocked),
    }


def section_coverage(config: Dict[str, Any]) -> Dict[str, Any]:
    """Pattern coverage: patterns vs research_protocol."""
    patterns_count = len(config.get("patterns", {}).get("mappings", []))
    research_count = len(config.get("research_protocol", {}).get("patterns", []))
    total = patterns_count + research_count
    coverage_pct = f"{patterns_count / total * 100:.0f}%" if total else "N/A"

    return {
        "content_patterns": patterns_count,
        "directory_rules": len(config.get("directory_rules", {}).get("mappings", [])),
        "bash_rules": len(config.get("bash_rules", {}).get("mappings", [])),
        "research_rules": len(config.get("research_rules", {}).get("mappings", [])),
        "research_protocol": research_count,
        "post_verification": len(config.get("post_verification", {}).get("rules", [])),
        "pattern_coverage": coverage_pct,
        "target": "90%",
    }


# --- Display ---

def print_section(title: str, data: Dict[str, Any]):
    """Print a dashboard section."""
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")


def main():
    parser = argparse.ArgumentParser(description="Skill Enforcement Dashboard")
    parser.add_argument("--period", default="24h", help="Time period: 1h, 24h, 7d, all")
    parser.add_argument("--section", default="all",
                        help="Section: decisions, levels, performance, accuracy, coverage, all")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    cutoff = parse_period(args.period)
    entries = load_invocations(cutoff)
    config = load_patterns()

    sections = {
        "decisions": lambda: section_decisions(entries),
        "levels": lambda: section_levels(entries),
        "performance": lambda: section_performance(entries),
        "accuracy": lambda: section_accuracy(entries),
        "coverage": lambda: section_coverage(config),
    }

    if args.section == "all":
        selected = list(sections.keys())
    else:
        selected = [args.section]

    results = {}
    for name in selected:
        if name in sections:
            results[name] = sections[name]()

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"\nSkill Enforcement Dashboard (period: {args.period})")
        print(f"Invocations: {len(entries)}")
        for name, data in results.items():
            print_section(name.upper(), data)


if __name__ == "__main__":
    main()
