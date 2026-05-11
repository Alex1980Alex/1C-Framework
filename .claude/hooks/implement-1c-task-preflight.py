#!/usr/bin/env python3
"""
Hook: implement-1c-task-preflight
Event: UserPromptSubmit
Matcher: (none — content-based filter on slash-command name)
Purpose: When the user invokes `/implement-1c-task`, run the pipeline smoke
         test (scripts/smoke_test_implement_1c_task.py) before Stage 0 starts
         so the SKILL gets a fresh, authoritative read of the MCP environment.
         Emits a single systemMessage with the detected pipeline mode and the
         list of unreachable critical servers; never blocks (the user can still
         force-run if they accept the degradation).

Trigger detection mirrors slash-command-tracker.py — `<command-name>` tag wins,
falls back to a raw "/cmd" prefix with leading backtick/quote stripping (Claude
Code v2.1.126+ wraps real CLI invocations as `\\`/cmd args`).

Logging:
  category="preflight" entries in data/hook-invocations.jsonl, correlated to the
  slash-command run via run_id (set by slash-command-tracker, fetched here via
  shared.run_context.get_run_id()). The slash-command-tracker hook runs first
  in the UserPromptSubmit chain; if for some reason run_id is missing we still
  log with an empty string (Phase 8 invariant: log_invocation accepts "").

Roadmap: docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md (Phase 5.2)

Timeouts:
  - hook (settings.json):  30s — outer budget Claude Code enforces
  - subprocess (this file): 25s — `SMOKE_TEST_TIMEOUT`; covers 3x stdio MCP
    handshakes @ 6s + TCP/HTTP probes; leaves 5s slack so we still emit
    `systemMessage` before the outer hook timeout fires.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput  # noqa: E402
from shared.slash_detect import detect_slash_command  # noqa: E402

TARGET_COMMAND = "implement-1c-task"
SMOKE_TEST_TIMEOUT = 25  # seconds; matches handshake budget in smoke-test (3x ~6s + slack)

PROJECT_ROOT = Path(_HOOK_DIR).resolve().parent.parent
SMOKE_TEST_SCRIPT = PROJECT_ROOT / "scripts" / "smoke_test_implement_1c_task.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
ROADMAP_REF = "docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md"


class ImplementOneCTaskPreflight(BaseHook):
    HOOK_NAME = "ImplementOneCTaskPreflight"

    def execute(self, inp: HookInput):
        if detect_slash_command(inp.prompt or "") != TARGET_COMMAND:
            return None

        if not SMOKE_TEST_SCRIPT.exists():
            self._log_preflight(inp, exit_code=-1, mode="missing-script")
            return HookOutput().system_message(
                f"[implement-1c-task-preflight] WARN: smoke-test script not found at "
                f"{SMOKE_TEST_SCRIPT.relative_to(PROJECT_ROOT)}. Skill will use its own Stage 0 probe. "
                f"See {ROADMAP_REF} (Phase 5)."
            )

        python = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable

        try:
            proc = subprocess.run(
                [python, str(SMOKE_TEST_SCRIPT), "--json"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SMOKE_TEST_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            self._log_preflight(inp, exit_code=-1, mode="timeout")
            return HookOutput().system_message(
                f"[implement-1c-task-preflight] WARN: smoke-test timed out after "
                f"{SMOKE_TEST_TIMEOUT}s — MCP environment may be unstable. "
                f"Skill Stage 0 will retry; if it also fails, run "
                f"`python scripts/smoke_test_implement_1c_task.py` manually."
            )
        except Exception as exc:  # spawn errors, missing python, etc.
            self._log_preflight(inp, exit_code=-1, mode=f"error:{type(exc).__name__}")
            return HookOutput().system_message(
                f"[implement-1c-task-preflight] WARN: smoke-test failed to launch "
                f"({type(exc).__name__}: {exc}). Pipeline preflight skipped — Skill Stage 0 "
                f"will probe MCP itself."
            )

        exit_code = proc.returncode
        try:
            data = json.loads(proc.stdout) if proc.stdout else None
        except (json.JSONDecodeError, ValueError):
            data = None

        mode = (data or {}).get("mode", "unknown")
        failed = self._failed_handshakes(data)
        debug_hmr_ready = bool(((data or {}).get("mcp_health") or {}).get("debug_hmr"))
        self._log_preflight(inp, exit_code=exit_code, mode=mode, debug_hmr_ready=debug_hmr_ready)

        return HookOutput().system_message(self._render_message(exit_code, mode, failed, debug_hmr_ready))

    @staticmethod
    def _failed_handshakes(data) -> list:
        if not data:
            return []
        out = []
        for h in data.get("handshakes") or []:
            if not h.get("ok"):
                name = h.get("name", "?")
                detail = h.get("detail", "")
                out.append(f"{name} ({detail})" if detail else name)
        return out

    @staticmethod
    def _render_message(exit_code: int, mode: str, failed: list) -> str:
        prefix = "[implement-1c-task-preflight]"
        if exit_code == 0:
            return (
                f"{prefix} OK Pipeline mode: Full. All critical MCP servers reachable "
                f"(edt-mcp + 1c-mcp-crud + bsl-debugger + bsl-semantic-search)."
            )
        if exit_code == 1:
            failed_part = ("\n  Unreachable: " + "; ".join(failed)) if failed else ""
            return (
                f"{prefix} WARN Pipeline mode: {mode}. Some stages will be skipped or "
                f"fall back to bsl-semantic-search/bsl-code-search.{failed_part}\n"
                f"  Recovery: {ROADMAP_REF}"
            )
        if exit_code == 2:
            failed_part = ("\n  Unreachable: " + "; ".join(failed)) if failed else ""
            return (
                f"{prefix} FAIL Pipeline mode: unusable. None of the critical MCP "
                f"servers respond.{failed_part}\n"
                f"  Fix the environment before running /implement-1c-task. "
                f"Diagnostics: `python scripts/smoke_test_implement_1c_task.py`. "
                f"Recovery steps: {ROADMAP_REF}"
            )
        return (
            f"{prefix} WARN smoke-test returned unexpected exit_code={exit_code}, "
            f"mode={mode}. Pipeline preflight inconclusive — Skill Stage 0 will re-probe."
        )

    def _log_preflight(self, inp: HookInput, exit_code: int, mode: str) -> None:
        try:
            from shared.invocation_logger import log_invocation
            from shared.run_context import get_run_id
            log_invocation(
                hook=self.HOOK_NAME,
                event="UserPromptSubmit",
                tool=f"slash:{TARGET_COMMAND}",
                elapsed_ms=self.elapsed_ms,
                outcome=f"mode={mode};exit={exit_code}",
                session_id=inp.session_id,
                category="preflight",
                run_id=get_run_id(inp.session_id),
            )
        except Exception:
            pass


class _NoAutoLogPreflight(ImplementOneCTaskPreflight):
    """Suppress BaseHook auto-log so we emit a single category=preflight record
    instead of a duplicate category=hook one. Mirrors slash-command-tracker."""

    def run(self) -> None:  # type: ignore[override]
        try:
            inp = HookInput.from_stdin()
            result = self.execute(inp)
            if result is not None:
                result.emit()
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)


if __name__ == "__main__":
    _NoAutoLogPreflight().run()
