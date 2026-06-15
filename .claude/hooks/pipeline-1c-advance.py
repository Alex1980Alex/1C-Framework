#!/usr/bin/env python3
"""
Hook: pipeline-1c-advance
Event: PostToolUse
Matcher: Write|Edit
Purpose: Двигает этапы 1С-пайплайна по записи 1С-артефактов (ADR-019 B′ F-1.5):
         ANALYSIS-REPORT → этапы 1,2 (Планирование+Дизайн); IMPLEMENTATION-PROGRESS
         → этап 3 (Кодирование). best-effort, НЕ блокирует. Guard в
         `pipeline_1c_bridge.advance_for_artifact` режет не-1С пайплайны.
Timeout: 5s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class Pipeline1CAdvance(BaseHook):
    HOOK_NAME = "Pipeline1CAdvance"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name not in ("Write", "Edit", "MultiEdit"):
            return None
        ti = inp.tool_input or {}
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not path:
            return None

        from shared.pipeline_1c_bridge import advance_for_artifact

        adv = advance_for_artifact(path)
        if adv:
            return HookOutput().system_message(
                f"[pipeline-1c-advance] этап(ы) {adv} → done (1С-пайплайн, ADR-019 F-1.5)"
            )
        return None


if __name__ == "__main__":
    Pipeline1CAdvance().run()
