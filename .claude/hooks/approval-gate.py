#!/usr/bin/env python3
"""
Hook: approval-gate
Event: PreToolUse
Matcher: Skill
Purpose: Block implementation skills (implement-1c-task, opsx:apply) unless
         the active OpenSpec change has approved status in .openspec.yaml.
Timeout: 3s

Part of SDD Phase 3: Approval Gate.
Prevents AI from implementing code changes without human approval of the design.

ADR-041 R1: чтение .openspec.yaml-статуса/профиля и список active changes вынесены в ЕДИНЫЙ модуль
shared/approval_state.py — тот же ридер использует pipeline_1c_bridge.gate_1c_implement (G4 honors
OpenSpec-approval → нет расхождения двух гейтов). Решения логируются в единый decision-log через
shared/gate_policy (как pipeline-gate). Поведение блокировки НЕ изменено (тот же ридер, тот же критерий).
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)


from base.protocol import BaseHook, HookInput, HookOutput
from shared.approval_state import list_active_changes as _get_active_changes
from shared.approval_state import read_approval_status as _read_approval_status
from shared.approval_state import read_profile as _read_profile

# ADR-034 R3: единый decision-log гейтов (best-effort, не ронять гейт)
try:
    from shared.gate_policy import decision as _gp_decision
    from shared.gate_policy import log_decision as _gp_log
except Exception:

    def _gp_decision(*a, **k):
        return {}

    def _gp_log(*a, **k):
        return None


# Skills that require approval before execution
_IMPLEMENTATION_SKILLS = {
    "implement-1c-task",
    "openspec-apply-change",
    "opsx:apply",
    "opsx-apply",
}


class ApprovalGate(BaseHook):
    """PreToolUse:Skill - blocks implementation skills without approved design."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Skill":
            return None

        skill_name = inp.tool_input.get("skill", "")
        if skill_name not in _IMPLEMENTATION_SKILLS:
            return None

        changes = _get_active_changes()
        if not changes:
            return None  # No active changes = nothing to gate

        unapproved = []
        for name, yaml_path in changes:
            status = _read_approval_status(yaml_path)
            profile = _read_profile(yaml_path)
            if status != "approved":
                unapproved.append((name, status or "pending", profile))

        if not unapproved:
            _gp_log(_gp_decision("approval-gate", True, "all active changes approved"))
            return None  # All approved

        change_list = "\n".join(
            f"  - {name} [profile: {profile}] (status: {status})"
            for name, status, profile in unapproved
        )
        first_name = unapproved[0][0]
        _gp_log(_gp_decision("approval-gate", False, f"unapproved: {[u[0] for u in unapproved]}"))
        return HookOutput().block(
            f"APPROVAL GATE: Design must be approved before implementation.\n\n"
            f"Unapproved changes:\n{change_list}\n\n"
            f"To approve: /opsx:approve {first_name}\n"
            f'To reject:  /opsx:approve {first_name} --reject --comment "reason"\n\n'
            f"Review design.md and specs/ before approving.\n"
            f"Profile rules: openspec/profiles/<profile>.yaml"
        )


if __name__ == "__main__":
    ApprovalGate().run()
