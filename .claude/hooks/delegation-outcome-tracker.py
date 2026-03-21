#!/usr/bin/env python3
"""
Hook: delegation-outcome-tracker
Event: PreToolUse
Matcher: Write
Purpose: Records delegation outcomes for content > 15 lines to JSONL
Timeout: 3s

Non-blocking: records silently, never blocks Write operations.
Data: data/delegation-outcomes.jsonl (structured outcomes for bandit learning).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

try:
    from shared.session_state import SessionState
except ImportError:
    SessionState = None

OUTCOMES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "delegation-outcomes.jsonl"

CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".jsx", ".tsx", ".bsl"}
SKIP_PATHS = {".claude/cache/", ".claude/data/", "node_modules/", "__pycache__/", ".git/"}

DOMAIN_MAP = [
    ("docs/roadmap", "roadmap"),
    (".claude/skills/", "skill"),
    (".claude/hooks/", "hook"),
    ("src/shared/", "shared"),
    ("src/bsl/", "bsl"),
    ("src/pdf_framework/", "framework"),
    ("tests/", "test"),
    ("scripts/", "script"),
    ("docs/", "docs"),
]


def _infer_content_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in {".md", ".txt", ".rst"}:
        return "docs"
    if ext in {".json", ".toml", ".yml", ".yaml", ".env"}:
        return "config"
    return "other"


def _infer_domain(normalized_path: str) -> str:
    for prefix, domain in DOMAIN_MAP:
        if prefix in normalized_path:
            return domain
    return "other"


def _auto_classify(content_type: str, lines: int, domain: str) -> str:
    """Estimate delegation level from content characteristics."""
    if domain in ("hook", "skill"):
        return "Never"
    if content_type == "code":
        return "Hard"
    if content_type == "docs":
        return "Medium" if lines > 30 else "Soft"
    if content_type == "config":
        return "Soft"
    return "Medium"


class DelegationOutcomeTracker(BaseHook):
    """Records delegation outcomes for Write operations > 15 lines."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        file_path = inp.tool_input.get("file_path", "")
        content = inp.tool_input.get("content", "")
        if not file_path or not content:
            return None

        normalized = file_path.replace("\\", "/")
        if any(skip in normalized for skip in SKIP_PATHS):
            return None

        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        if lines <= 15:
            return None

        delegated = False
        session_id = ""
        if SessionState:
            try:
                delegated = SessionState.has_llm_delegation()
                session_id = SessionState.get_session_id()
            except Exception:
                pass

        content_type = _infer_content_type(file_path)
        domain = _infer_domain(normalized)
        ext = os.path.splitext(file_path)[1].lower()

        content_lower = content[:2000].lower()
        has_code = any(kw in content_lower for kw in ("def ", "class ", "import ", "function ", "async "))
        has_architecture = any(kw in content_lower for kw in ("architecture", "pattern", "design", "итерац"))

        classification = _auto_classify(content_type, lines, domain)

        outcome = {
            "timestamp": datetime.now().isoformat(),
            "session_id": inp.session_id or session_id,
            "file": os.path.basename(file_path),
            "content_type": content_type,
            "domain": domain,
            "estimated_lines": lines,
            "delegated": delegated,
            "classification": classification,
            "correct_classification": None,
            "rewrite_pct": 0,
            "reward": None,
            "context_features": {
                "has_code": has_code,
                "has_architecture": has_architecture,
                "file_extension": ext,
                "target_dir": "/".join(normalized.split("/")[:-1])[-50:],
            },
        }

        try:
            OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTCOMES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        except Exception:
            pass

        return None


if __name__ == "__main__":
    DelegationOutcomeTracker().run()
