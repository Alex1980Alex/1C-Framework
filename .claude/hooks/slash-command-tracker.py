#!/usr/bin/env python3
"""
Hook: slash-command-tracker
Event: UserPromptSubmit, Stop
Matcher: (none)
Purpose: Bracket every slash-command invocation with a start record at
         UserPromptSubmit and an end record at Stop. Generates a per-run UUID
         and stores it in data/.current-runs.json so other hooks
         (mcp-invocation-logger, future phase markers) can attach it to their
         own log entries via shared.run_context.get_run_id().

Detection:
    User prompt that starts with "/<command>" — the first non-whitespace token.
    Slash commands invoked by Claude Code arrive as a UserPromptSubmit with the
    command-name tag plus arguments in the prompt body.

Storage:
    data/.current-runs.json  — small JSON map {session_id: {run_id, command,
                               started_at}}. Atomic-write via shared.run_context.

Log entries (in data/hook-invocations.jsonl):
    category="slash_run", outcome="start"  — emitted at UserPromptSubmit
    category="slash_run", outcome="end"    — emitted at Stop with elapsed_ms
                                             measured from started_at

Idempotency:
    UserPromptSubmit fires once per user message. If the user submits a non-
    slash prompt while a run is active, the active run is left intact (the user
    might be replying to the agent mid-run). The Stop hook clears the entry.

Timeout: 3s
"""

import os
import re
import sys
import uuid
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

_SLASH_RE = re.compile(r"^\s*/([\w:.-]+)")


class SlashCommandTracker(BaseHook):
    HOOK_NAME = "SlashCommandTracker"

    def execute(self, inp: HookInput) -> HookOutput | None:
        event = inp.detected_event

        if event == "UserPromptSubmit":
            self._handle_prompt(inp)
        elif event == "Stop":
            self._handle_stop(inp)

        return None

    def _handle_prompt(self, inp: HookInput) -> None:
        command = _extract_slash_command(inp.prompt)
        if not command:
            return

        run_id = uuid.uuid4().hex

        try:
            from shared.run_context import set_run
            set_run(inp.session_id, run_id, command)
        except Exception:
            pass

        self._log(
            event="UserPromptSubmit",
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


def _extract_slash_command(prompt: str) -> str:
    if not prompt:
        return ""
    match = _SLASH_RE.match(prompt)
    if not match:
        return ""
    name = match.group(1)
    # Filter out built-in non-tracking prefixes (e.g. "//comments")
    if not name or name.startswith("/"):
        return ""
    return name


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
