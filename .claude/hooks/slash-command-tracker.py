#!/usr/bin/env python3
"""
Hook: slash-command-tracker
Event: UserPromptSubmit, Stop
Matcher: (none)
Purpose: Bracket every slash-command invocation with a start record at
         UserPromptSubmit and an end record at Stop. Generates a per-run
         UUID and stores it in data/.current-runs.json so other hooks
         (mcp-invocation-logger, future phase markers) can attach it to their
         own log entries via shared.run_context.get_run_id().

Detection (2026-05-05 update):
    Originally registered on UserPromptExpansion — the official Claude Code 2.x
    event for slash-command expansions per
    https://code.claude.com/docs/en/hooks. Empirically verified on Windows
    (build 2.x, session 10108f33-...) that UPE is NOT emitted for real CLI
    `/cmd` invocations — zero hook entries even with valid registration in
    settings.json. UPS, however, fires reliably (9 hooks logged in the same
    real session). Switching detection to UserPromptSubmit + prompt parsing.

    The UPS payload's `prompt` field carries one of two forms depending on
    where in the pipeline the hook fires:
      - Pre-expansion (raw CLI typed): "/cmd arg1 arg2 ..."
      - Post-expansion (skill body inlined): contains "<command-name>NAME</command-name>"
        wrapper around the original command name (Claude Code 2.x convention).
    We check both: a `<command-name>` tag wins (most authoritative), with
    `/^\\s*\\/[a-z][a-z0-9_-]*` as fallback for raw form.

    Plain user prompts (no slash, no command-name tag) are ignored — the
    hook is a no-op for them so it doesn't pollute the slash_run log.

Storage:
    data/.current-runs.json  — small JSON map {session_id: {run_id, command,
                               started_at}}. Atomic-write via shared.run_context.

Log entries (in data/hook-invocations.jsonl):
    category="slash_run", outcome="start"  — emitted at UserPromptSubmit when
                                             a slash invocation is detected
    category="slash_run", outcome="end"    — emitted at Stop with elapsed_ms
                                             measured from started_at

Idempotency:
    Each UPS fires once per user turn. If a session already has an active
    entry (set_run was called and clear_run not yet) and a new slash command
    arrives, the old entry is overwritten — Claude Code only ever has one
    in-flight slash command per session, so this matches reality.

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


_CMD_NAME_TAG_RE = re.compile(r"<command-name>\s*/?([a-zA-Z][a-zA-Z0-9_:.-]*)\s*</command-name>")
_RAW_SLASH_RE = re.compile(r"^\s*/([a-zA-Z][a-zA-Z0-9_:.-]*)(?:\s|$)")


def _detect_slash_command(prompt: str) -> str:
    """Return the slash command name found in the prompt, or '' if none.

    Two-stage detection:
      1. <command-name>NAME</command-name> wrapper (post-expansion form)
      2. Raw "/cmd ..." prefix (pre-expansion CLI form)
    """
    if not prompt:
        return ""
    m = _CMD_NAME_TAG_RE.search(prompt)
    if m:
        return m.group(1)
    m = _RAW_SLASH_RE.match(prompt)
    if m:
        return m.group(1)
    return ""


class SlashCommandTracker(BaseHook):
    HOOK_NAME = "SlashCommandTracker"

    def execute(self, inp: HookInput):
        event = inp.detected_event

        if event == "UserPromptSubmit":
            self._handle_prompt_submit(inp)
        elif event == "Stop":
            self._handle_stop(inp)
        # UserPromptExpansion path retained for future platform fix; if the
        # event ever starts emitting again, the documented `command_name`
        # field is used directly without prompt parsing.
        elif event == "UserPromptExpansion":
            self._handle_expansion(inp)

        return None

    def _handle_prompt_submit(self, inp: HookInput) -> None:
        command = _detect_slash_command(inp.prompt or "")
        if not command:
            return  # Plain prompt — no slash invocation to track.

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

    def _handle_expansion(self, inp: HookInput) -> None:
        # Legacy path — kept in case Claude Code re-enables UPE emission for
        # slash commands. Listens to the documented `command_name` field.
        if inp.raw.get("expansion_type") != "slash_command":
            return

        command = str(inp.raw.get("command_name", "")).strip()
        if not command:
            return

        # Skip if UPS already recorded this turn — avoids duplicate run_id.
        try:
            from shared.run_context import get_run
            if get_run(inp.session_id):
                return
        except Exception:
            pass

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
