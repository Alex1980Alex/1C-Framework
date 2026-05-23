#!/usr/bin/env python3
"""
Hook: audit-coverage-check
Event: SessionStart
Purpose:
  - Lightweight smoke check of code↔docs↔skills coverage at session start.
  - Calls scripts/audit_docs_skills.py --json --stdout (timeout 4s).
  - Parses gap counts, emits informational systemMessage if coverage drops.
  - Roadmap 260515 §Phase B3 — closes Gap 6 (no periodic scan).
Timeout: 5s (hook), 4s (subprocess).

Graceful degradation: any error → silent allow.
Disable via AUDIT_COVERAGE_NO_CHECK=1 env (CI / dev with broken audit script).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SUBPROCESS_TIMEOUT_S = 4
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_docs_skills.py"
DISABLE_ENV = "AUDIT_COVERAGE_NO_CHECK"


def _run_audit() -> dict | None:
    """Run audit script in JSON mode. Returns parsed dict or None on error."""
    if not AUDIT_SCRIPT.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT), "--json", "--stdout"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_S,
            cwd=str(PROJECT_ROOT),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode not in (0, 1):
            return None
        # Audit script prints "Scanning codebase..." before JSON. Match `{` AT
        # line start to avoid false-positives if banner ever contains `{}` (e.g.
        # f-string interpolation like "Scanning {root}..."). Fragility flagged
        # by code-verify subagent ae0304c17ba3707c7.
        out = result.stdout or ""
        brace = out.find("\n{")
        if brace < 0:
            # Fallback: file starts with `{` (no banner)
            if out.lstrip().startswith("{"):
                return json.loads(out[out.find("{") :])
            return None
        return json.loads(out[brace + 1 :])
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return None


class AuditCoverageCheck(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get(DISABLE_ENV) == "1":
            return None

        audit = _run_audit()
        if not audit:
            return None

        summary = audit.get("summary", {})
        doc_gaps = audit.get("doc_gaps", [])
        skill_gaps = audit.get("skill_gaps", [])

        total_doc_gaps = len(doc_gaps) if isinstance(doc_gaps, list) else 0
        total_skill_gaps = len(skill_gaps) if isinstance(skill_gaps, list) else 0

        if total_doc_gaps == 0 and total_skill_gaps == 0:
            return None

        lines = [
            f"[AUDIT-COVERAGE] {total_doc_gaps} doc gap(s) + "
            f"{total_skill_gaps} skill gap(s) detected"
        ]
        if isinstance(summary, dict):
            covered = sum(v for k, v in summary.items() if "coverage" in k.lower())
            if covered:
                lines.append(f"  summary: {summary}")
        lines.append(
            "  Run `make audit-docs` for full report or `make audit-docs-update` to auto-fix"
        )

        return HookOutput().system_message("\n".join(lines))


if __name__ == "__main__":
    AuditCoverageCheck().run()
