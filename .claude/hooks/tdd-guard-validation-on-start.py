#!/usr/bin/env python3
"""
Hook: tdd-guard-validation-on-start
Event: SessionStart
Purpose: Автономное наблюдение валидации tdd-guard (roadmap 260613 Этап 4.3, окно
  2026-06-13 → 2026-06-20). Раз в день (sentinel) считает метрики через
  scripts/tdd_guard_validation.py (advisory-события из кеша) и эмитит прогресс-баннер
  с авто-рекомендацией (hard-block vs keep-advisory). После закрытия окна эмитит
  ФИНАЛЬНЫЙ вердикт каждый старт, пока в §18 роадмапа не появится «tdd-guard вердикт».
  Каркас общий: shared/acceptance_watch.py.
Opt-out: TDD_GUARD_VALIDATION_DISABLE=1
Timeout: 8s
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.acceptance_watch import acceptance_banner


def _progress(m: dict, _crit: dict) -> str:
    return (
        f"enabled={m['enabled']}, advisory={m['advisories']} ({m['per_day']}/д), "
        f"modules={m['unique_modules']}, followed={m['followed']}/ignored={m['ignored']}, "
        f"→ {m['recommendation']}"
    )


class TddGuardValidation(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        msg = acceptance_banner(
            disable_env="TDD_GUARD_VALIDATION_DISABLE",
            sentinel_name="tdd-guard-validation-state.json",
            roadmap_rel="docs/roadmap/260613_ROADMAP_TOOLING_ADOPTION.md",
            window_end=datetime(2026, 6, 20),
            metrics_module="tdd_guard_validation",
            script_rel="scripts/tdd_guard_validation.py",
            banner_tag="TDD-GUARD-VALIDATION",
            progress_line=_progress,
        )
        return HookOutput().system_message(msg) if msg else None


if __name__ == "__main__":
    TddGuardValidation().run()
