#!/usr/bin/env python3
"""
Hook: patterns-harvester
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: §26 P1 D1.1 — auto-ingest confirmed feedback-drafts + session-lessons
         into the learned_patterns Qdrant collection (mirrors save_pattern).
         Closes the "save_pattern called only manually" ingestion gap.
Timeout: 8s (TEI cold-start padding; only embeds genuinely new items)

Exit codes:
  0 = always allow stop (advisory, non-blocking, fully fail-soft)

Gating: content_hash dedup (re-run = 0 new) + per-session cap + content-quality
        floor + §22 confidence seed 0.70. Opt-out: PATTERNS_HARVEST_DISABLE=1,
        cap override: PATTERNS_HARVEST_CAP=N.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class PatternsHarvester(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PATTERNS_HARVEST_DISABLE") == "1":
            return None
        try:
            from shared.pattern_harvest import harvest

            cap = int(os.environ.get("PATTERNS_HARVEST_CAP", "5"))
            stats = harvest(cap=cap)
        except Exception:
            return None  # fail-soft: never block stop

        created = stats.get("created", 0)
        if created:
            names = ", ".join(stats.get("items", [])[:3])
            return HookOutput().system_message(
                f"[PATTERNS-HARVEST] +{created} pattern(s) → learned_patterns "
                f"(dup={stats.get('skipped_dup', 0)}, cap={stats.get('skipped_cap', 0)}, "
                f"err={stats.get('errors', 0)}): {names}"
            )
        return None


if __name__ == "__main__":
    PatternsHarvester().run()
