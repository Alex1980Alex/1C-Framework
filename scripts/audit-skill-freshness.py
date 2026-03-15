#!/usr/bin/env python3
"""
audit-skill-freshness.py — Check reference skills for staleness.

Scans all SKILL.md files for YAML frontmatter with last_verified/updated fields.
Reports skills that haven't been verified in > 30 days.

Usage:
    python scripts/audit-skill-freshness.py
    python scripts/audit-skill-freshness.py --days 60
    python scripts/audit-skill-freshness.py --output data/skill-freshness-report.md

Output: prints report to stdout, optionally saves to file.
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# YAML frontmatter regex (between --- markers)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
# Simple YAML field extraction (avoids PyYAML dependency)
_FIELD_RE = re.compile(r"^(\w[\w-]*):\s*(.+)$", re.MULTILINE)


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter fields from SKILL.md content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    yaml_block = match.group(1)
    fields = {}
    for m in _FIELD_RE.finditer(yaml_block):
        key = m.group(1).strip()
        val = m.group(2).strip().strip('"').strip("'")
        fields[key] = val
    return fields


def parse_date(date_str: str) -> datetime | None:
    """Try parsing common date formats."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def scan_skills(max_age_days: int) -> tuple[list, list, list]:
    """Scan all skills, return (fresh, stale, no_date) lists."""
    fresh = []
    stale = []
    no_date = []
    now = datetime.now()
    threshold = now - timedelta(days=max_age_days)

    if not SKILLS_DIR.exists():
        print(f"Skills directory not found: {SKILLS_DIR}", file=sys.stderr)
        return fresh, stale, no_date

    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        # Skip archived skills
        if "_archived" in skill_md.parts:
            continue
        skill_name = skill_md.parent.name
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue

        fields = parse_frontmatter(content)
        if not fields.get("name"):
            continue

        # Check date fields (priority: last_verified > updated > none)
        date_str = fields.get("last_verified") or fields.get("updated")
        if not date_str:
            no_date.append({
                "name": skill_name,
                "path": str(skill_md.relative_to(PROJECT_ROOT)),
                "fields": fields,
            })
            continue

        dt = parse_date(date_str)
        if dt is None:
            no_date.append({
                "name": skill_name,
                "path": str(skill_md.relative_to(PROJECT_ROOT)),
                "fields": fields,
                "date_str": date_str,
            })
            continue

        entry = {
            "name": skill_name,
            "path": str(skill_md.relative_to(PROJECT_ROOT)),
            "date": dt,
            "age_days": (now - dt).days,
            "fields": fields,
        }

        if dt < threshold:
            stale.append(entry)
        else:
            fresh.append(entry)

    return fresh, stale, no_date


def format_report(fresh, stale, no_date, max_age_days) -> str:
    """Format the freshness report as markdown."""
    lines = [
        "# Skill Freshness Report",
        f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Threshold:** {max_age_days} days",
        f"**Total skills:** {len(fresh) + len(stale) + len(no_date)}",
        f"**Fresh:** {len(fresh)} | **Stale:** {len(stale)} | **No date:** {len(no_date)}",
    ]

    if stale:
        lines.append("\n## Stale Skills (need review)")
        lines.append("\n| Skill | Age (days) | Last verified | Path |")
        lines.append("|-------|-----------|---------------|------|")
        for s in sorted(stale, key=lambda x: -x["age_days"]):
            lines.append(
                f"| {s['name']} | {s['age_days']} | "
                f"{s['date'].strftime('%Y-%m-%d')} | `{s['path']}` |"
            )

    if no_date:
        lines.append("\n## Skills Without Date")
        lines.append("\n| Skill | Path |")
        lines.append("|-------|------|")
        for s in sorted(no_date, key=lambda x: x["name"]):
            lines.append(f"| {s['name']} | `{s['path']}` |")

    if fresh:
        lines.append(f"\n## Fresh Skills ({len(fresh)})")
        lines.append("\n| Skill | Age (days) | Last verified |")
        lines.append("|-------|-----------|---------------|")
        for s in sorted(fresh, key=lambda x: x["age_days"]):
            lines.append(
                f"| {s['name']} | {s['age_days']} | "
                f"{s['date'].strftime('%Y-%m-%d')} |"
            )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Audit skill freshness")
    parser.add_argument("--days", type=int, default=30, help="Max age in days (default: 30)")
    parser.add_argument("--output", type=str, help="Save report to file")
    args = parser.parse_args()

    fresh, stale, no_date = scan_skills(args.days)
    report = format_report(fresh, stale, no_date, args.days)

    print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport saved to: {args.output}")

    # Exit code: 1 if stale skills found
    sys.exit(1 if stale else 0)


if __name__ == "__main__":
    main()
