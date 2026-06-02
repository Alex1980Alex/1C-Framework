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
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)


from base.protocol import BaseHook, HookInput, HookOutput

# Skills that require approval before execution
_IMPLEMENTATION_SKILLS = {
    "implement-1c-task",
    "openspec-apply-change",
    "opsx:apply",
    "opsx-apply",
}

# Project root (hooks/ -> .claude/ -> project root)
_PROJECT_ROOT = os.path.normpath(os.path.join(_HOOK_DIR, "..", ".."))
_CHANGES_DIR = os.path.join(_PROJECT_ROOT, "openspec", "changes")


def _get_active_changes():
    """Find all active (non-archived) change directories with .openspec.yaml."""
    if not os.path.isdir(_CHANGES_DIR):
        return []

    changes = []
    for entry in os.listdir(_CHANGES_DIR):
        if entry == "archive":
            continue
        change_dir = os.path.join(_CHANGES_DIR, entry)
        if os.path.isdir(change_dir):
            yaml_path = os.path.join(change_dir, ".openspec.yaml")
            if os.path.isfile(yaml_path):
                changes.append((entry, yaml_path))
    return changes


def _read_approval_status(yaml_path):
    """Read approval.status from .openspec.yaml (no pyyaml dependency)."""
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        in_approval = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "approval:" or stripped.startswith("approval:"):
                # Check if inline value: "approval: {status: approved}"
                after = stripped.split(":", 1)[1].strip()
                if after and after != "":
                    # Try to extract status from inline format
                    if "status:" in after:
                        for part in after.replace("{", "").replace("}", "").split(","):
                            if "status:" in part:
                                return part.split(":", 1)[1].strip().strip("'\"")
                in_approval = True
                continue
            if in_approval:
                if stripped.startswith("status:"):
                    return stripped.split(":", 1)[1].strip().strip("'\"")
                # If we hit a non-indented line, approval section ended
                if not line.startswith(" ") and not line.startswith("\t") and stripped:
                    break
        return None  # No approval section found
    except Exception:
        return None


def _read_profile(yaml_path):
    """Read top-level `profile` field from .openspec.yaml.

    Returns the profile name (e.g. "python-framework") or "1c-bsl" as default
    when the field is absent (backward-compat for existing BSL changes).
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            stripped = line.strip()
            # Top-level field only (no leading indent)
            if (
                not line.startswith(" ")
                and not line.startswith("\t")
                and stripped.startswith("profile:")
            ):
                value = stripped.split(":", 1)[1].strip().strip("'\"")
                if value:
                    return value
        return "1c-bsl"  # default for existing changes without profile field
    except Exception:
        return "1c-bsl"


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
            return None  # All approved

        change_list = "\n".join(
            f"  - {name} [profile: {profile}] (status: {status})"
            for name, status, profile in unapproved
        )
        first_name = unapproved[0][0]
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
