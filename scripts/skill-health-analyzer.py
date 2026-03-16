#!/usr/bin/env python3
"""Analyze skill router quality metrics and generate health reports.

Reads skill-accuracy.jsonl (router recommend/activate events),
identifies problematic skills (noisy, missed, unused), generates report.

Usage:
    python scripts/skill-health-analyzer.py
    python scripts/skill-health-analyzer.py --days 7 --min-samples 2
    python scripts/skill-health-analyzer.py --output data/custom-report.md
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SkillStats:
    recommended_count: int = 0
    activated_count: int = 0
    manual_count: int = 0

    @property
    def precision(self) -> float:
        return self.activated_count / self.recommended_count if self.recommended_count else 0.0

    @property
    def waste_rate(self) -> float:
        if not self.recommended_count:
            return 0.0
        return (self.recommended_count - self.activated_count) / self.recommended_count


def load_accuracy_events(filepath: Path, days: int) -> list[dict]:
    """Load events from skill-accuracy.jsonl filtered by date range."""
    if not filepath.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    entries = []

    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts_str = entry.get("ts", "")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str)
                    if ts >= cutoff:
                        entries.append(entry)
            except (json.JSONDecodeError, ValueError):
                continue

    return entries


def get_f1_score() -> float | None:
    """Run eval script and extract F1(All) score."""
    eval_script = PROJECT_ROOT / "scripts" / "eval-skill-router.py"
    if not eval_script.exists():
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(eval_script)],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        # Parse "  F1:        0.7189" from "All (required + optional" section
        in_all_section = False
        for line in result.stdout.splitlines():
            if "All (required + optional" in line:
                in_all_section = True
            elif in_all_section and line.strip().startswith("F1:"):
                return float(line.split("F1:")[1].strip())
            elif in_all_section and line.strip() == "":
                in_all_section = False
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return None


def compute_skill_stats(events: list[dict]) -> tuple[dict[str, SkillStats], int]:
    """Compute per-skill statistics from skill-accuracy.jsonl events.

    skill-accuracy.jsonl has two event types:
      {"type": "recommend", "prompt_id": "...", "skills": ["a", "b"]}
      {"type": "activate",  "prompt_id": "...", "skill": "x"}

    Returns (stats_dict, unique_prompt_count).
    """
    # Collect per prompt_id: which skills were recommended and activated
    prompts: dict[str, dict] = defaultdict(lambda: {"recommended": set(), "activated": set()})

    for event in events:
        pid = event.get("prompt_id", "")
        if not pid:
            continue
        etype = event.get("type", "")
        if etype == "recommend":
            for skill in event.get("skills", []):
                prompts[pid]["recommended"].add(skill)
        elif etype == "activate":
            skill = event.get("skill", "")
            if skill:
                prompts[pid]["activated"].add(skill)

    stats: dict[str, SkillStats] = defaultdict(SkillStats)

    for prompt_data in prompts.values():
        recommended = prompt_data["recommended"]
        activated = prompt_data["activated"]

        for skill in recommended:
            stats[skill].recommended_count += 1
            if skill in activated:
                stats[skill].activated_count += 1

        # Manual activations: activated but NOT recommended by router
        for skill in activated:
            if skill not in recommended:
                stats[skill].manual_count += 1

    return dict(stats), len(prompts)


def identify_problems(
    stats: dict[str, SkillStats],
) -> tuple[list[str], list[str], list[str]]:
    """Identify skills with quality issues.

    Returns (high_waste, router_miss, never_used) lists.
    """
    high_waste = []
    router_miss = []
    never_used = []

    for skill, s in stats.items():
        if s.recommended_count > 5 and s.waste_rate > 0.8:
            high_waste.append(skill)
        if s.manual_count > 2:
            router_miss.append(skill)
        if s.recommended_count > 10 and s.activated_count == 0:
            never_used.append(skill)

    return high_waste, router_miss, never_used


def generate_report(
    total_prompts: int,
    stats: dict[str, SkillStats],
    f1: float | None,
    high_waste: list[str],
    router_miss: list[str],
    never_used: list[str],
    min_samples: int,
    days: int,
) -> str:
    """Generate markdown health report."""
    lines = [
        "# Skill Router Health Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Period:** last {days} days",
        f"**Total prompts:** {total_prompts}",
        f"**Unique skills:** {len(stats)}",
        f"**F1(All):** {f1:.4f}" if f1 is not None else "**F1(All):** N/A (eval not run)",
        "",
        "## Skill Statistics",
        "",
        "| Skill | Recs | Acts | Manual | Precision | Waste |",
        "|-------|------|------|--------|-----------|-------|",
    ]

    sorted_skills = sorted(
        stats.items(), key=lambda x: x[1].waste_rate, reverse=True,
    )

    for skill, s in sorted_skills:
        if s.recommended_count >= min_samples or s.manual_count > 0:
            lines.append(
                f"| {skill} | {s.recommended_count} | {s.activated_count} | "
                f"{s.manual_count} | {s.precision:.2f} | {s.waste_rate:.2f} |"
            )

    lines.extend(["", "## Action Items", ""])

    if high_waste:
        lines.append("### HIGH WASTE (noisy triggers — rewrite description)")
        for skill in sorted(high_waste):
            s = stats[skill]
            lines.append(
                f"- **{skill}**: waste={s.waste_rate:.2f} "
                f"({s.recommended_count} recs, {s.activated_count} acts)"
            )
        lines.append("")

    if router_miss:
        lines.append("### ROUTER MISS (add keywords to router config)")
        for skill in sorted(router_miss):
            s = stats[skill]
            lines.append(f"- **{skill}**: {s.manual_count} manual activations")
        lines.append("")

    if never_used:
        lines.append("### NEVER USED (candidates for archiving)")
        for skill in sorted(never_used):
            s = stats[skill]
            lines.append(
                f"- **{skill}**: {s.recommended_count} recs, 0 activations"
            )
        lines.append("")

    if not (high_waste or router_miss or never_used):
        lines.append("No action items. All skills healthy (or insufficient data).")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Skill router health analyzer")
    parser.add_argument("--days", type=int, default=30, help="Analyze last N days")
    parser.add_argument("--output", type=Path, help="Output report path")
    parser.add_argument("--min-samples", type=int, default=3, help="Min recs to show")
    parser.add_argument("--no-eval", action="store_true", help="Skip F1 eval run")
    args = parser.parse_args()

    metrics_path = PROJECT_ROOT / "data" / "skill-accuracy.jsonl"
    output_path = args.output or PROJECT_ROOT / "data" / "skill-health-report.md"

    events = load_accuracy_events(metrics_path, args.days)
    stats, prompt_count = compute_skill_stats(events)
    f1 = None if args.no_eval else get_f1_score()

    high_waste, router_miss, never_used = identify_problems(stats)

    report = generate_report(
        prompt_count, stats, f1, high_waste, router_miss, never_used,
        args.min_samples, args.days,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReport saved to: {output_path}")

    return 1 if (high_waste or router_miss or never_used) else 0


if __name__ == "__main__":
    sys.exit(main())
