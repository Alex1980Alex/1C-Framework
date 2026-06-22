#!/usr/bin/env python3
"""
Hook: onec-toolgate-validation-on-start
Event: SessionStart
Purpose: Автономное наблюдение валидации ADR-035 Фазы 1 (advisory T1-T2 в
  onec-task-completion-stop, окно 2026-06-22 → 2026-07-06). Раз в день (sentinel)
  считает presence_rate через scripts/onec_toolgate_validation.py (advisory-события из
  .claude/cache/onec-toolgate-events.jsonl) и эмитит прогресс-баннер с per-tool
  рекомендацией (promote-candidate vs keep-advisory — для Фазы 2 ADR-035). После закрытия
  окна — ФИНАЛЬНЫЙ вердикт каждый старт, пока в ADR-035 не появится «Acceptance вердикт».
  Каркас общий: shared/acceptance_watch.py.
Opt-out: ONEC_TOOLGATE_VALIDATION_DISABLE=1
Timeout: 8s
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.acceptance_watch import acceptance_banner


def _progress(m: dict, _crit: dict) -> str:
    pt = m["per_tool"]
    return (
        f"1С-задач={m['total_tasks']} (edit={m['edit_tasks']}), "
        f"presence impact={pt['impact']['rate']}/debug={pt['debug_trace']['rate']}/"
        f"ref={pt['ref_search']['rate']} -> {m['recommendation']}"
    )


class OnecToolgateValidation(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        msg = acceptance_banner(
            disable_env="ONEC_TOOLGATE_VALIDATION_DISABLE",
            sentinel_name="onec-toolgate-validation-state.json",
            roadmap_rel=(
                ".claude/skills/architecture-research/adr/035-mandatory-high-leverage-1c-tools.md"
            ),
            window_end=datetime(2026, 7, 6),
            metrics_module="onec_toolgate_validation",
            script_rel="scripts/onec_toolgate_validation.py",
            banner_tag="ONEC-TOOLGATE-VALIDATION",
            progress_line=_progress,
            window_days=14,
        )
        return HookOutput().system_message(msg) if msg else None


if __name__ == "__main__":
    OnecToolgateValidation().run()
