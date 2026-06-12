#!/usr/bin/env python3
"""
Hook: skill-learning-acceptance-on-start
Event: SessionStart
Purpose: Автономное наблюдение acceptance-окна skill-learning revival
  (roadmap 260611 §P4, 2026-06-12 → 2026-06-26). Раз в день (sentinel) считает
  метрики через scripts/skill_learning_acceptance.py (локальные JSONL + логи,
  без сети) и эмитит прогресс-баннер. После закрытия окна эмитит ФИНАЛЬНЫЙ
  вердикт каждый старт сессии, пока вердикт не зафиксирован в §18 роадмапа
  (маркер "Acceptance вердикт") — после этого замолкает навсегда. Каркас
  (sentinel, маркер, fail-soft) общий: shared/acceptance_watch.py (260612 §P4).
Opt-out: SKILL_LEARNING_ACCEPTANCE_DISABLE=1
Timeout: 5s
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.acceptance_watch import acceptance_banner


def _progress(m: dict, _crit: dict) -> str:
    return (
        f"captures={m['captures']}/10, median_age={m['median_pending_age_days']}d, "
        f"rejects={m['rejects']}, arm_fired={m['surfacing_arm_fired']}, "
        f"dup={m['dup_events']}"
    )


class SkillLearningAcceptance(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        msg = acceptance_banner(
            disable_env="SKILL_LEARNING_ACCEPTANCE_DISABLE",
            sentinel_name="skill-learning-acceptance-state.json",
            roadmap_rel="docs/roadmap/260611_ROADMAP_SKILL_LEARNING_REVIVAL.md",
            window_end=datetime(2026, 6, 26),
            metrics_module="skill_learning_acceptance",
            script_rel="scripts/skill_learning_acceptance.py",
            banner_tag="SL-ACCEPTANCE",
            progress_line=_progress,
        )
        return HookOutput().system_message(msg) if msg else None


if __name__ == "__main__":
    SkillLearningAcceptance().run()
