#!/usr/bin/env python3
"""
Hook: skills-harvester
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: §26 P1 D1.2 — auto-index changed/new SKILL.md into the skill_library
         Qdrant collection (incremental, hash-idempotent), and clean up points
         for deleted skills. Closes the "skill_library indexed only by manual
         full rebuild" gap.
Timeout: 8s (TEI cold-start padding; only embeds genuinely changed skills,
         cold-start seeds hashes without embedding)

Exit codes:
  0 = always allow stop (advisory, non-blocking, fully fail-soft)

Gating: content-hash idempotency (unchanged → skip) + per-run cap + cold-start
        seed (no 80-embed storm). Opt-out: SKILLS_HARVEST_DISABLE=1,
        cap override: SKILLS_HARVEST_CAP=N.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class SkillsHarvester(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("SKILLS_HARVEST_DISABLE") == "1":
            return None
        try:
            from shared.skills_harvest import harvest_skills

            cap = int(os.environ.get("SKILLS_HARVEST_CAP", "10"))
            stats = harvest_skills(cap=cap)
        except Exception:
            return None  # fail-soft: never block stop

        if stats.get("seeded"):
            return None  # cold-start: silent seed
        up, dl = stats.get("upserted", 0), stats.get("deleted", 0)
        if up or dl:
            names = ", ".join(stats.get("items", [])[:3])
            return HookOutput().system_message(
                f"[SKILLS-HARVEST] skill_library: +{up} upserted, -{dl} removed "
                f"(cap={stats.get('skipped_cap', 0)}, err={stats.get('errors', 0)}): {names}"
            )
        return None


if __name__ == "__main__":
    SkillsHarvester().run()
