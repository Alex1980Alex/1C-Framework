#!/usr/bin/env python3
"""
Hook: tool-invocation-logger
Event: PreToolUse, PostToolUse
Matcher: built-in tools (see BUILTIN_TOOLS) — NOT mcp__ (those go to
         mcp-invocation-logger, the canonical logger for MCP calls).
Purpose: Emit ONE canonical row per built-in tool call to
         data/hook-invocations.jsonl with category="tool_call" — the built-in
         twin of mcp-invocation-logger's category="mcp_call".

Why this exists (roadmap 260713, B3/B5):
    Before this hook, built-in tools (Bash/Read/Grep/Glob/Write/Edit/Web*/Task*/
    TodoWrite/…) had NO canonical row. They were visible only as a side effect of
    whichever enforcer hooks happened to match — so ONE Bash call produced N
    `category="hook"` rows (SearchOptimizer + BulkActionGuard + ProcessGuard + …),
    double-counting in tool views, and Read/Grep/Glob had no PostToolUse at all
    (no duration, no error). This hook gives every built-in call exactly one
    canonical row with tool_call_id + args_hash, mirroring the mcp_call contract.
    Consumers count built-in tool calls from category="tool_call" (event=
    PostToolUse = completed call), NOT from the noisy category="hook" rows.

Schema (invocation_logger entry):
    category="tool_call"  — filter built-in tool calls out of the unified log
    tool_call_id=<id>     — join-key Pre↔Post (= gen_ai.tool.call.id)
    args_hash=<sha1[:12]> — fingerprint of args → retry detection
    run_id=<UUID>         — slash-command correlation (empty outside a slash run)

Pre/Post pairing: PreToolUse and PostToolUse both fire; runtime =
    ts(post) − ts(pre) joined on tool_call_id (or FIFO). Same as mcp-invocation-logger.

Timeout: 3s. Never blocks (silent logger).
"""

import hashlib
import json
import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# ── Debug shape-dump (roadmap 260718 N-P0.1) ──────────────────────────────────
# NB1: юнит-фикстура формы tool_response ЛЖЁТ — форма приходит от платформы и
# _classify_outcome строился на гипотезе (exit_code в dict), которой живой payload
# не несёт → все built-in Post = success. Этот gated-дамп захватывает РЕАЛЬНУЮ
# форму, чтобы чинить по факту, а не вслепую. Off by default: включается env
# TOOL_LOGGER_DEBUG_DUMP=1 ИЛИ наличием sentinel-файла .claude/cache/tool-response-dump.on
# (env недоступен для правки из сессии → sentinel-путь). Cap 50 записей.
_CACHE_DIR = os.path.join(os.path.dirname(_HOOK_DIR), "cache")
_DUMP_SENTINEL = os.path.join(_CACHE_DIR, "tool-response-dump.on")
_DUMP_FILE = os.path.join(_CACHE_DIR, "tool-response-shapes.jsonl")
_DUMP_CAP = 50


def _dump_enabled() -> bool:
    return os.environ.get("TOOL_LOGGER_DEBUG_DUMP") == "1" or os.path.exists(_DUMP_SENTINEL)


def _debug_dump_shape(inp: "HookInput", event: str) -> None:
    """Захватить форму tool_response реального Post-вызова (диагностика NB1)."""
    if not _dump_enabled():
        return
    try:
        if (
            os.path.exists(_DUMP_FILE)
            and sum(1 for _ in open(_DUMP_FILE, encoding="utf-8")) >= _DUMP_CAP
        ):
            return
        resp = inp.raw.get("tool_response", inp.tool_result)
        rec = {
            "tool": inp.tool_name,
            "event": event,
            "hook_event_name": inp.raw.get("hook_event_name"),
            "raw_keys": sorted(inp.raw.keys()),
            "resp_type": type(resp).__name__,
            "resp_keys": sorted(resp.keys()) if isinstance(resp, dict) else None,
            "resp_repr": repr(resp)[:2000],
        }
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_DUMP_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# Canonical built-in tool set. Mirrors the settings.json matcher. Kept as an
# internal allowlist (defense-in-depth): if the matcher ever broadens, we still
# no-op on anything not listed here — and mcp__ tools are excluded by design
# (mcp-invocation-logger owns those).
BUILTIN_TOOLS = frozenset(
    {
        "Bash",
        "PowerShell",
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "Grep",
        "Glob",
        "WebSearch",
        "WebFetch",
        "Task",
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
        "TaskOutput",
        "TodoWrite",
        "ExitPlanMode",
        "Skill",
        "Agent",
        "ToolSearch",
        "Artifact",
        "AskUserQuestion",
    }
)


def _args_fingerprint(tool_input: object) -> str:
    """Стабильный sha1[:12] аргументов вызова → детект retry (тот же args = повтор).
    Хешируем, НЕ логируем сырьё (пути/секреты не утекают)."""
    try:
        blob = json.dumps(tool_input, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""


class ToolInvocationLogger(BaseHook):
    HOOK_NAME = "ToolInvocationLogger"

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool = inp.tool_name or ""
        # No-op on anything outside the canonical built-in set (mcp__ tools are
        # handled by mcp-invocation-logger; unknown tools are left to auto-log).
        if tool not in BUILTIN_TOOLS:
            return None

        event = inp.detected_event  # P0.1: classifies Post via tool_response
        _debug_dump_shape(inp, event)  # N-P0.1: gated shape-capture (диагностика NB1)
        outcome, error = self._classify_outcome(inp, event)
        tool_call_id = inp.raw.get("tool_use_id") or inp.raw.get("toolUseID") or ""
        args_hash = _args_fingerprint(inp.tool_input)

        try:
            from shared.invocation_logger import log_invocation
            from shared.run_context import get_run_id

            log_invocation(
                hook=self.HOOK_NAME,
                event=event,
                tool=tool,
                elapsed_ms=self.elapsed_ms,
                outcome=outcome,
                session_id=inp.session_id,
                error=error,
                category="tool_call",
                run_id=get_run_id(inp.session_id),
                agent_id=inp.agent_id,
                tool_call_id=tool_call_id,
                error_type=("tool_error" if outcome == "error" else ""),
                args_hash=args_hash,
            )
        except Exception:
            pass  # Logging must never block

        return None

    @staticmethod
    def _classify_outcome(inp: HookInput, event: str) -> tuple[str, str | None]:
        """Best-effort error flag for PostToolUse. Built-in tool errors are not
        uniformly surfaced in tool_response (e.g. Bash non-zero exit is not an
        isError), so this is conservative — only obvious markers count. Absence
        of a flag means success, matching the honest-metrics stance in the roadmap."""
        if event != "PostToolUse":
            return "allow", None
        response = inp.raw.get("tool_response", inp.tool_result)
        try:
            if isinstance(response, dict):
                if response.get("isError") or response.get("is_error"):
                    msg = response.get("error") or response.get("content") or "isError=true"
                    return "error", str(msg)[:300]
                # Bash/PowerShell: типичный фейл — dict с exit_code/interrupted, НЕ isError
                # (adversarial-review 260713 P0#6: без этого все Bash-фейлы шли success=True
                # → вердикты P1.1 слепы к реальным ошибкам исполняемых тулов).
                exit_code = response.get("exit_code", response.get("exitCode"))
                if isinstance(exit_code, int) and exit_code != 0:
                    tail = str(response.get("stderr") or response.get("stdout") or "")[-300:]
                    return (
                        "error",
                        f"exit_code={exit_code}: {tail}" if tail else f"exit_code={exit_code}",
                    )
                if response.get("interrupted"):
                    return "error", "interrupted"
                content = response.get("content")
                if isinstance(content, list):
                    for item in content:
                        text = item.get("text", "") if isinstance(item, dict) else ""
                        if text and text.startswith(("Error:", "ERROR:", "Exception:")):
                            return "error", text[:300]
            elif isinstance(response, str) and response.startswith(
                ("Error:", "ERROR:", "Exception:")
            ):
                return "error", response[:300]
        except Exception:
            pass
        return "allow", None


# BaseHook.run() would auto-log each invocation with category="hook" — a
# duplicate of the canonical category="tool_call" row we write in execute().
# Override run() to suppress the auto-log (identical pattern to
# mcp-invocation-logger._NoAutoLogMcpLogger).
class _NoAutoLogToolLogger(ToolInvocationLogger):
    def run(self) -> None:  # type: ignore[override]
        try:
            inp = HookInput.from_stdin()
            self.execute(inp)
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)


if __name__ == "__main__":
    _NoAutoLogToolLogger().run()
