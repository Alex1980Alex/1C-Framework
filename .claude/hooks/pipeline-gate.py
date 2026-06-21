#!/usr/bin/env python3
"""
Hook: pipeline-gate
Event: UserPromptSubmit
Matcher: (none — fires on every prompt, early-returns unless pl-* command)
Purpose: ADR-017 — гейт переходов generic 4-stage пайплайна
  (Планирование→Дизайн→Кодирование→Тестирование). Детектит pl-* слэш-команду:
    - pl-code  → HARD block если дизайн (02-design.md) не done+approved;
    - pl-design/pl-test → advisory system_message если предыдущий этап не done;
    - pl-plan  → всегда пропускается (бутстрап).
  Не-pipeline промпты → no-op (non-breaking, инвариант: чужие промпты не трогаем).
Timeout: 4s
Opt-out: PIPELINE_GATE_DISABLE=1
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.pipeline_state import PIPELINE_COMMANDS, gate_check
from shared.slash_detect import detect_slash_command

# R3 (ADR-034): унифицированный decision-log гейтов (best-effort, не ронять гейт)
try:
    from shared.gate_policy import decision as _gp_decision
    from shared.gate_policy import log_decision as _gp_log
except Exception:

    def _gp_decision(*a, **k):
        return {}

    def _gp_log(*a, **k):
        return None


class PipelineGate(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PIPELINE_GATE_DISABLE") == "1":
            return None
        cmd = detect_slash_command(inp.prompt or "")
        if cmd == "implement-1c-task":
            # ADR-019 F-2 (G4): хард-гейт «Дизайн→Кодирование» для 1С-маршрута
            from shared.pipeline_1c_bridge import gate_1c_implement

            res = gate_1c_implement(inp.prompt or "")
            if not res["ok"] and res["hard"]:
                _gp_log(_gp_decision("pipeline-gate:1c-implement", False, res["reason"]))
                return HookOutput().block(f"[PIPELINE-GATE] {res['reason']}")
            return None
        if cmd not in PIPELINE_COMMANDS:
            return None  # не наш пайплайн — пропускаем (non-breaking)
        res = gate_check(cmd)
        if res["ok"]:
            return None
        if res["hard"]:
            _gp_log(_gp_decision(f"pipeline-gate:{cmd}", False, res["reason"]))
            return HookOutput().block(f"[PIPELINE-GATE] {res['reason']}")
        return HookOutput().system_message(f"[PIPELINE-GATE] {res['reason']}")


if __name__ == "__main__":
    PipelineGate().run()
