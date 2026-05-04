#!/usr/bin/env python3
"""
Hook: slash-command-tracker
Event: UserPromptExpansion, Stop
Matcher: (none)
Purpose: Bracket every slash-command invocation with a start record at
         UserPromptExpansion and an end record at Stop. Generates a per-run
         UUID and stores it in data/.current-runs.json so other hooks
         (mcp-invocation-logger, future phase markers) can attach it to their
         own log entries via shared.run_context.get_run_id().

Detection:
    UserPromptExpansion is the official Claude Code 2.x event for slash-
    command expansions (https://code.claude.com/docs/en/hooks). Its payload
    carries `command_name` and `command_args` directly, so no prompt-string
    parsing is required. UserPromptSubmit is NOT used here: empirically
    verified (2026-05-05) that real slash invocations bypass UPS on
    Windows — only the Skill tool sees them, and PreToolUse:Skill cannot
    distinguish slash-originated invocations from Claude-initiated Skill()
    calls. UserPromptExpansion fires exclusively on the slash path.

Storage:
    data/.current-runs.json  — small JSON map {session_id: {run_id, command,
                               started_at}}. Atomic-write via shared.run_context.

Log entries (in data/hook-invocations.jsonl):
    category="slash_run", outcome="start"  — emitted at UserPromptExpansion
    category="slash_run", outcome="end"    — emitted at Stop with elapsed_ms
                                             measured from started_at

Idempotency:
    UserPromptExpansion fires once per slash invocation. The Stop hook
    clears the entry after recording elapsed_ms.

Timeout: 3s
"""

import os
import sys
import uuid
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


class SlashCommandTracker(BaseHook):
    HOOK_NAME = "SlashCommandTracker"

    def execute(self, inp: HookInput) -> HookOutput | None:
        event = inp.detected_event

        if event == "UserPromptExpansion":
            self._handle_expansion(inp)
        elif event == "Stop":
            self._handle_stop(inp)

        return None

    def _handle_expansion(self, inp: HookInput) -> None:
        # Only track slash commands; mcp_prompt expansions are out of scope.
        if inp.raw.get("expansion_type") != "slash_command":
            return

        command = str(inp.raw.get("command_name", "")).strip()
        if not command:
            return

        run_id = uuid.uuid4().hex

        try:
            from shared.run_context import set_run
            set_run(inp.session_id, run_id, command)
        except Exception:
            pass

        self._log(
            event="UserPromptExpansion",
            outcome="start",
            session_id=inp.session_id,
            run_id=run_id,
            tool=f"slash:{command}",
        )

    def _handle_stop(self, inp: HookInput) -> None:
        try:
            from shared.run_context import clear_run
            entry = clear_run(inp.session_id)
        except Exception:
            entry = {}

        if not entry:
            return

        run_id = str(entry.get("run_id", ""))
        command = str(entry.get("command", ""))
        elapsed_ms = _elapsed_since(entry.get("started_at", ""))

        self._log(
            event="Stop",
            outcome="end",
            session_id=inp.session_id,
            run_id=run_id,
            tool=f"slash:{command}",
            elapsed_ms=elapsed_ms,
        )

    def _log(
        self,
        event: str,
        outcome: str,
        session_id: str,
        run_id: str,
        tool: str,
        elapsed_ms: int = 0,
    ) -> None:
        try:
            from shared.invocation_logger import log_invocation
            log_invocation(
                hook=self.HOOK_NAME,
                event=event,
                tool=tool,
                elapsed_ms=elapsed_ms,
                outcome=outcome,
                session_id=session_id,
                category="slash_run",
                run_id=run_id,
            )
        except Exception:
            pass


def _elapsed_since(started_at: str) -> int:
    if not started_at:
        return 0
    try:
        started = datetime.fromisoformat(started_at)
        return int((datetime.now() - started).total_seconds() * 1000)
    except (ValueError, TypeError):
        return 0


# Suppress BaseHook auto-log; we emit our own slash_run entries inside execute().
class _NoAutoLogSlashTracker(SlashCommandTracker):
    def run(self) -> None:  # type: ignore[override]
        try:
            inp = HookInput.from_stdin()
            self.execute(inp)
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)


if __name__ == "__main__":
    _NoAutoLogSlashTracker().run()
