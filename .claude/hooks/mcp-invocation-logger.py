#!/usr/bin/env python3
"""
Hook: mcp-invocation-logger
Event: PreToolUse, PostToolUse
Matcher: mcp__.*
Purpose: Log every MCP tool invocation to data/hook-invocations.jsonl with
         category="mcp_call" and run_id correlation back to the slash command
         that initiated it.

Why this exists:
    Before this hook, only mcp__llm-rotation__llm_complete was logged via a
    dedicated PostToolUse hook. Every other MCP server (bsl-semantic-search,
    1c-mcp-crud, edt-mcp, memory-orchestrator, pdf-vector-graph,
    bsl-platform-context, bsl-debugger, ast-grep-mcp, …) was invisible in the
    audit log. This hook closes that gap with a regex matcher that catches
    EVERY current and future MCP server with no per-server wiring.

Schema additions in invocation_logger entry:
    category="mcp_call"   — filter MCP calls out of the unified hook log
    run_id=<UUID>         — set by slash-command-tracker; correlates this MCP
                            call back to the parent /analyze-1c-task,
                            /implement-1c-task, etc. Empty if the user did not
                            invoke a slash command.

Pre/Post pairing:
    PreToolUse and PostToolUse both fire for the same tool invocation. The
    consumer of the JSONL log can compute MCP runtime as
    `ts(post) - ts(pre)` joined on (session, tool, run_id).

Timeout: 3s
"""

import os
import sys
import time
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


class McpInvocationLogger(BaseHook):
    HOOK_NAME = "McpInvocationLogger"

    def execute(self, inp: HookInput) -> HookOutput | None:
        # Defense-in-depth: matcher mcp__.* in settings.json should already filter,
        # but if matcher ever changes we still want to no-op on non-MCP tools.
        if not inp.tool_name or not inp.tool_name.startswith("mcp__"):
            return None

        # Workaround: base/protocol.py:46 detected_event checks
        #   if "tool_result" in self.raw  →  "PostToolUse"
        # but modern Claude Code sends the key as "tool_response", so the
        # property misclassifies Post events as Pre. Derive directly here.
        event = (
            "PostToolUse"
            if ("tool_response" in inp.raw or "tool_result" in inp.raw)
            else "PreToolUse"
        )

        outcome, error = self._classify_outcome(inp, event)

        try:
            from shared.invocation_logger import log_invocation
            from shared.run_context import get_run_id

            log_invocation(
                hook=self.HOOK_NAME,
                event=event,
                tool=inp.tool_name,
                elapsed_ms=self.elapsed_ms,
                outcome=outcome,
                session_id=inp.session_id,
                error=error,
                category="mcp_call",
                run_id=get_run_id(inp.session_id),
            )
        except Exception:
            pass  # Logging must never block

        return None

    @staticmethod
    def _classify_outcome(inp: HookInput, event: str) -> tuple[str, str | None]:
        """For PostToolUse, peek at tool_response to flag errors."""
        if event != "PostToolUse":
            return "allow", None

        response = inp.raw.get("tool_response", inp.tool_result)
        try:
            if isinstance(response, dict):
                if response.get("isError") or response.get("is_error"):
                    msg = response.get("error") or response.get("content") or "isError=true"
                    return "error", str(msg)[:300]
                content = response.get("content")
                if isinstance(content, list):
                    for item in content:
                        text = item.get("text", "") if isinstance(item, dict) else ""
                        # Heuristic: many MCP servers return errors as plain text
                        # in content[].text. Conservative match — only obvious markers.
                        if text and text.startswith(("Error:", "ERROR:", "Exception:")):
                            return "error", text[:300]
            elif isinstance(response, str) and response.startswith(
                ("Error:", "ERROR:", "Exception:")
            ):
                return "error", response[:300]
        except Exception:
            pass
        return "allow", None


# BaseHook.run() also auto-logs each invocation — but with category="hook"
# and no run_id. We override run() here to suppress the duplicate auto-log
# and rely solely on our explicit log_invocation() inside execute().
class _NoAutoLogMcpLogger(McpInvocationLogger):
    def run(self) -> None:  # type: ignore[override]
        try:
            inp = HookInput.from_stdin()
            self.execute(inp)
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)


if __name__ == "__main__":
    _NoAutoLogMcpLogger().run()
