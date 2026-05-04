#!/usr/bin/env python3
"""
Hook: mcp-invocation-logger
Event: PreToolUse, PostToolUse
Matcher: mcp__.*
Purpose: Log every MCP tool invocation to data/hook-invocations.jsonl.

Registered on regex matcher mcp__.* in settings.json so EVERY MCP server
(current and future — bsl-semantic-search, 1c-mcp-crud, edt-mcp,
memory-orchestrator, pdf-vector-graph, etc.) is auto-logged with no
per-server wiring.

How it logs:
    BaseHook.run() unconditionally calls shared.invocation_logger.log_invocation()
    with {hook, event, tool, elapsed_ms, outcome, session_id} after execute()
    returns. This hook's execute() is a no-op — the side-effect of being
    registered IS the logging.

Pre/Post pair:
    A PreToolUse entry plus a PostToolUse entry with the same tool+session
    let the consumer compute MCP call runtime as ts_post - ts_pre.

Timeout: 3s
"""

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


class McpInvocationLogger(BaseHook):
    HOOK_NAME = "McpInvocationLogger"

    def execute(self, inp: HookInput) -> HookOutput | None:
        return None


if __name__ == "__main__":
    McpInvocationLogger().run()
