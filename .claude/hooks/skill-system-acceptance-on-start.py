#!/usr/bin/env python3
"""
Hook: skill-system-acceptance-on-start
Event: SessionStart
Purpose: Автономное наблюдение acceptance-окна Skill System Full Verification
  (roadmap 260612 §P4, 2026-06-13 → 2026-06-27). Раз в день (sentinel) считает
  метрики через scripts/skill_system_acceptance.py (локальные логи + live
  dry-run зеркала skill_library) и эмитит прогресс-баннер. После закрытия окна
  эмитит ФИНАЛЬНЫЙ вердикт каждый старт, пока в §18 роадмапа не появится
  маркер «Acceptance вердикт» — после этого замолкает. Каркас общий:
  shared/acceptance_watch.py.
Opt-out: SKILL_SYSTEM_ACCEPTANCE_DISABLE=1
Timeout: 10s (live dry-run зеркала ходит в локальный Qdrant)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.acceptance_watch import acceptance_banner


def _progress(m: dict, _crit: dict) -> str:
    return (
        f"ghosts={m['ghosts']}, drift={m['drift']}, ingest={m['ingest_events']}, "
        f"F1={m['router_f1']}, floor_gated={m['floor_gated']}, "
        f"arm_fired={m['arm_fired']}/{m['invocations']}, "
        f"health_age={m['health_age_days']}d"
    )


class SkillSystemAcceptance(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        msg = acceptance_banner(
            disable_env="SKILL_SYSTEM_ACCEPTANCE_DISABLE",
            sentinel_name="skill-system-acceptance-state.json",
            roadmap_rel="docs/roadmap/260612_ROADMAP_SKILL_SYSTEM_FULL_VERIFICATION.md",
            window_end=datetime(2026, 6, 27),
            metrics_module="skill_system_acceptance",
            script_rel="scripts/skill_system_acceptance.py",
            banner_tag="SKILL-SYS-ACCEPTANCE",
            progress_line=_progress,
        )
        return HookOutput().system_message(msg) if msg else None


if __name__ == "__main__":
    SkillSystemAcceptance().run()
