#!/usr/bin/env python3
"""
Hook: memory-ai-acceptance-on-start
Event: SessionStart
Purpose: Автономное наблюдение acceptance-окна memory-ai full verification
  (roadmap 260612 §P4, 2026-06-12 → 2026-06-26). Раз в день (sentinel) считает
  метрики через scripts/memory_ai_acceptance.py (SQLite + локальные логи, без
  сети) и эмитит прогресс-баннер. После закрытия окна эмитит ФИНАЛЬНЫЙ вердикт
  каждый старт сессии, пока строка «Acceptance вердикт: <итог>» не появится в
  §18 роадмапа — после этого замолкает навсегда. Каркас (sentinel, маркер,
  fail-soft) общий с skill-learning-наблюдением: shared/acceptance_watch.py.
Opt-out: MEMORY_AI_ACCEPTANCE_DISABLE=1
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
        f"episodes={m['episodes_non_session']}/5, "
        f"sqlite_fired={m['surfacing_sqlite_fired']}, dup={m['dup_events']}, "
        f"no_hash={m['rows_without_hash']}, "
        f"reflect={m['reflection_clusters_triggered']}trig/{m['derives_from_total']}links, "
        f"archive_runs={m['archive_runs']}"
    )


class MemoryAiAcceptance(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        msg = acceptance_banner(
            disable_env="MEMORY_AI_ACCEPTANCE_DISABLE",
            sentinel_name="memory-ai-acceptance-state.json",
            roadmap_rel="docs/roadmap/260612_ROADMAP_MEMORY_AI_FULL_VERIFICATION.md",
            window_end=datetime(2026, 6, 26),
            metrics_module="memory_ai_acceptance",
            script_rel="scripts/memory_ai_acceptance.py",
            banner_tag="MEM-AI-ACCEPTANCE",
            progress_line=_progress,
        )
        return HookOutput().system_message(msg) if msg else None


if __name__ == "__main__":
    MemoryAiAcceptance().run()
