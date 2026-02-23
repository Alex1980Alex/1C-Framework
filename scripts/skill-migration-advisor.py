#!/usr/bin/env python3
"""Skill Migration Advisor - scans skills and patterns, finds candidates for migration.

Analyzes:
1. research_protocol patterns that could be migrated to full patterns (if skill exists)
2. Skills without corresponding content patterns
3. Content patterns without matching skills

Usage:
    python scripts/skill-migration-advisor.py              # show candidates
    python scripts/skill-migration-advisor.py --apply      # auto-apply migrations
    python scripts/skill-migration-advisor.py --json       # JSON output
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

# --- Path resolution ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
PATTERNS_FILE = HOOKS_DIR / "shared" / "code-skill-patterns.json"
SKILL_ROUTER_CONFIG = HOOKS_DIR / "shared" / "skill-router-config.json"


def load_patterns() -> Dict[str, Any]:
    """Load patterns config."""
    if not PATTERNS_FILE.exists():
        return {}
    with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_patterns(config: Dict[str, Any]):
    """Save patterns config."""
    with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def scan_existing_skills() -> List[str]:
    """Scan for existing skill directories."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for item in SKILLS_DIR.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                skills.append(item.name)
    return skills


def find_migration_candidates(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find research_protocol patterns that could be migrated to content patterns."""
    candidates = []

    # Get existing pattern skills
    existing_skills = set()
    for mapping in config.get("patterns", {}).get("mappings", []):
        existing_skills.add(mapping["skill"])

    # Check research_protocol patterns
    for rp in config.get("research_protocol", {}).get("patterns", []):
        label = rp.get("label", "")
        domain = rp.get("domain", "")
        pattern = rp.get("pattern", "")

        # Check if a matching skill exists on disk
        matching_skill = None
        available_skills = scan_existing_skills()
        for skill_name in available_skills:
            if label.lower().replace(" ", "-") in skill_name.lower():
                matching_skill = skill_name
                break

        candidates.append({
            "label": label,
            "domain": domain,
            "pattern": pattern,
            "matching_skill": matching_skill,
            "action": "migrate" if matching_skill else "create_skill",
            "reason": f"Skill '{matching_skill}' exists" if matching_skill else "No matching skill found",
        })

    return candidates


def find_uncovered_skills(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find skills that exist on disk but have no content patterns."""
    pattern_skills = set()
    for section_name in ("patterns", "bash_rules", "directory_rules"):
        section = config.get(section_name, {})
        for mapping in section.get("mappings", []):
            pattern_skills.add(mapping.get("skill", ""))

    available_skills = scan_existing_skills()
    uncovered = []
    for skill in available_skills:
        if skill not in pattern_skills:
            uncovered.append({
                "skill": skill,
                "has_pattern": False,
                "suggestion": "Add content pattern or directory rule",
            })

    return uncovered


def apply_migration(config: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    """Apply a single migration: move from research_protocol to patterns."""
    skill = candidate.get("matching_skill")
    if not skill:
        return False

    # Add to patterns
    new_pattern = {
        "pattern": candidate["pattern"],
        "skill": skill,
        "label": candidate["label"],
        "domain": candidate["domain"],
    }
    config.setdefault("patterns", {}).setdefault("mappings", []).append(new_pattern)

    # Remove from research_protocol
    rp_patterns = config.get("research_protocol", {}).get("patterns", [])
    config["research_protocol"]["patterns"] = [
        p for p in rp_patterns if p.get("pattern") != candidate["pattern"]
    ]

    # Update metadata
    meta = config.get("metadata", {})
    stats = meta.get("stats", {})
    stats["total_patterns"] = len(config["patterns"]["mappings"])
    stats["total_research_protocol"] = len(config["research_protocol"]["patterns"])
    meta.setdefault("migration_history", []).append({
        "label": candidate["label"],
        "from": "research_protocol",
        "to": "patterns",
        "skill": skill,
        "date": __import__("datetime").datetime.now().isoformat(),
    })

    return True


def main():
    parser = argparse.ArgumentParser(description="Skill Migration Advisor")
    parser.add_argument("--apply", action="store_true", help="Apply migrations automatically")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    config = load_patterns()
    if not config:
        print("[WARN] No patterns config found at", PATTERNS_FILE)
        return

    # Analysis
    candidates = find_migration_candidates(config)
    uncovered = find_uncovered_skills(config)

    migratable = [c for c in candidates if c["action"] == "migrate"]
    need_skill = [c for c in candidates if c["action"] == "create_skill"]

    if args.json:
        output = {
            "migration_candidates": candidates,
            "uncovered_skills": uncovered,
            "stats": {
                "migratable": len(migratable),
                "need_skill": len(need_skill),
                "uncovered": len(uncovered),
            }
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    # Display
    print("\n" + "=" * 50)
    print("  Skill Migration Advisor")
    print("=" * 50)

    print(f"\n--- Migration Candidates ({len(migratable)}) ---")
    for c in migratable:
        print(f"  [MIGRATE] {c['label']} -> skill '{c['matching_skill']}'")
        print(f"            pattern: {c['pattern']}")

    print(f"\n--- Need Skill Creation ({len(need_skill)}) ---")
    for c in need_skill:
        print(f"  [CREATE] {c['label']} ({c['domain']})")
        print(f"           pattern: {c['pattern']}")

    print(f"\n--- Uncovered Skills ({len(uncovered)}) ---")
    for u in uncovered:
        print(f"  [UNCOVERED] {u['skill']}")

    # Coverage stats
    patterns_count = len(config.get("patterns", {}).get("mappings", []))
    research_count = len(config.get("research_protocol", {}).get("patterns", []))
    total = patterns_count + research_count
    coverage = f"{patterns_count / total * 100:.0f}%" if total else "N/A"
    print(f"\n--- Coverage ---")
    print(f"  Patterns: {patterns_count}, Research Protocol: {research_count}")
    print(f"  Coverage: {coverage} (target: 90%)")

    # Apply if requested
    if args.apply and migratable:
        print(f"\n--- Applying {len(migratable)} migrations ---")
        applied = 0
        for c in migratable:
            if apply_migration(config, c):
                print(f"  [OK] Migrated: {c['label']}")
                applied += 1
        if applied:
            save_patterns(config)
            print(f"  Saved {applied} migrations to {PATTERNS_FILE}")


if __name__ == "__main__":
    main()
