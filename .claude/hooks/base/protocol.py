"""
Hook Protocol for PDF Vector & Graph Framework.

Provides base abstractions for Claude Code hooks:
- HookInput: parsed stdin JSON from Claude Code
- HookOutput: builder for stdout JSON responses
- BaseHook: abstract base class for all hooks

Adapted from 1C-Enterprise_Framework base/protocol.py (simplified).
All hooks inherit from BaseHook and implement execute().

Graceful degradation: any uncaught exception -> sys.exit(0) (allow, never block).
"""

import json
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class HookInput:
    """Parsed stdin input from Claude Code hook system."""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        # UserPromptSubmit
        self.prompt = raw.get("prompt", raw.get("content", ""))
        # PreToolUse / PostToolUse
        self.tool_name = raw.get("tool_name", "")
        self.tool_input = raw.get("tool_input") or {}
        self.tool_result = raw.get("tool_response", raw.get("tool_result", ""))
        # Stop
        self.transcript = raw.get("transcript", "")
        self.reason = raw.get("reason", "")
        # Common
        self.session_id = raw.get("session_id", "")

    @property
    def detected_event(self) -> str:
        """Detect hook event type from input fields."""
        if self.tool_name:
            if "tool_result" in self.raw:
                return "PostToolUse"
            return "PreToolUse"
        if self.transcript or self.reason:
            return "Stop"
        if self.prompt:
            return "UserPromptSubmit"
        return "Unknown"

    @classmethod
    def from_stdin(cls) -> "HookInput":
        """Read and parse JSON from stdin (UTF-8 safe on Windows)."""
        try:
            raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
        except (json.JSONDecodeError, EOFError, ValueError, AttributeError):
            # Fallback: try text mode (e.g. when buffer not available)
            try:
                data = json.loads(sys.stdin.read())
            except Exception:
                data = {}
        return cls(data)


class HookOutput:
    """Builder for structured stdout JSON response to Claude Code.

    Usage:
        HookOutput().system_message("text").emit()
        HookOutput().block("reason").emit_and_exit(2)
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def allow(self) -> "HookOutput":
        """Allow the tool call to proceed (default)."""
        self._data["continue"] = True
        return self

    def block(self, reason: str) -> "HookOutput":
        """Block the tool call with a reason."""
        self._data["continue"] = False
        self._data["decision"] = "block"
        self._data["reason"] = reason
        return self

    def system_message(self, msg: str) -> "HookOutput":
        """Inject a system message for Claude (allow + message)."""
        self._data["continue"] = True
        self._data["systemMessage"] = msg
        return self

    def modified_input(self, new_input: Dict[str, Any]) -> "HookOutput":
        """Modify the tool input parameters."""
        self._data["modifiedInput"] = new_input
        return self

    def claude_fallback(self, hook_name: str, prompt: str,
                        priority: str = "normal") -> "HookOutput":
        """Request Claude to perform a fallback action."""
        self._data["claudeFallback"] = {
            "hook_name": hook_name,
            "prompt": prompt,
            "priority": priority,
        }
        return self

    def hook_context(self, message: str) -> "HookOutput":
        """PostToolUse: inject context into Claude via hookSpecificOutput wrapper.

        This is the ONLY working PostToolUse feedback mechanism (confirmed 2026-03-29).
        Plain additionalContext doesn't work (#18427). The hookSpecificOutput wrapper
        delivers the message as a system-reminder "PostToolUse:Tool hook additional context".
        Exit code must be 0 (not blocking).
        """
        self._data["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
        return self

    def emit(self) -> None:
        """Write JSON to stdout (UTF-8 safe on Windows)."""
        if self._data:
            output = json.dumps(self._data, ensure_ascii=False)
            try:
                sys.stdout.buffer.write(output.encode("utf-8"))
                sys.stdout.buffer.write(b"\n")
                sys.stdout.buffer.flush()
            except AttributeError:
                print(output)

    def emit_and_exit(self, code: int = 0) -> None:
        """Write JSON to stdout and exit with code."""
        self.emit()
        sys.exit(code)


class BaseHook(ABC):
    """Abstract base class for all PDF Framework hooks.

    Subclasses implement execute() and are run via:
        if __name__ == "__main__":
            MyHook().run()
    """

    def __init__(self):
        self.start_time = time.time()

    @abstractmethod
    def execute(self, inp: HookInput) -> Optional[HookOutput]:
        """Main hook logic. Return HookOutput or None to pass through."""
        ...

    def run(self) -> None:
        """Entry point: read stdin -> execute -> emit output -> log invocation."""
        inp = HookInput.from_stdin()
        outcome = "allow"
        error_msg = None
        try:
            result = self.execute(inp)
            if result is not None:
                # Determine outcome from result data
                if result._data.get("decision") == "block":
                    outcome = "block"
                elif result._data.get("systemMessage"):
                    outcome = "message"
                result.emit()
        except Exception as e:
            outcome = "error"
            error_msg = f"{type(e).__name__}: {e}"
            # Log error before graceful degradation
            try:
                from pathlib import Path as _P
                from datetime import datetime as _DT
                _log = _P(__file__).resolve().parent.parent / "cache" / "hook-errors.log"
                _log.parent.mkdir(parents=True, exist_ok=True)
                with open(str(_log), "a", encoding="utf-8") as _f:
                    _cls = type(self).__name__
                    _f.write(f"{_DT.now().isoformat()} [{_cls}] {type(e).__name__}: {e}\n")
            except Exception:
                pass
            # Graceful degradation: never block on internal error
            sys.exit(0)
        finally:
            # Log invocation (always, even on error)
            try:
                from shared.invocation_logger import log_invocation
                log_invocation(
                    hook=type(self).__name__,
                    event=inp.detected_event,
                    tool=inp.tool_name or None,
                    elapsed_ms=self.elapsed_ms,
                    outcome=outcome,
                    session_id=inp.session_id,
                    error=error_msg,
                )
            except Exception:
                pass  # Logging must never block

    @property
    def elapsed_ms(self) -> int:
        """Milliseconds since hook start."""
        return int((time.time() - self.start_time) * 1000)
