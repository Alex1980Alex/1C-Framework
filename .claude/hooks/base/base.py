"""
BaseHook — Base class for all Claude Code hooks.

Provides:
- Standard JSON input parsing via stdin
- HookInput/HookOutput dataclasses
- Event detection (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
- Integration with invocation_logger for structured logging
- Graceful degradation (never blocks on errors)

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class HookEvent(Enum):
    """Hook event types as defined by Claude Code."""
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"


class HookOutcome(Enum):
    """Possible hook execution outcomes."""
    ALLOW = "allow"          # Let action proceed
    BLOCK = "block"          # Block the action
    MESSAGE = "message"      # Add system message but allow
    ADVISE = "advise"        # Advisory message only
    LEARN = "learn"          # Created learn tasks
    ERROR = "error"          # Hook error (graceful degradation)
    SKIP = "skip"            # Hook skipped execution


@dataclass
class HookInput:
    """
    Parsed hook input from stdin JSON.

    Expected JSON structure:
    {
        "detected_event": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "...", "content": "..."},
        "prompt": "...",  // For UserPromptSubmit
        "invocation_id": "...",
        "agent_id": "..."
    }
    """
    detected_event: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Dict[str, Any] = field(default_factory=dict)
    prompt: Optional[str] = None
    invocation_id: Optional[str] = None
    agent_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stdin(cls) -> "HookInput":
        """
        Parse hook input from stdin.

        Returns:
            HookInput instance with parsed data

        Example:
            >>> inp = HookInput.from_stdin()
            >>> if inp.detected_event == "PreToolUse":
            ...     print(f"Tool: {inp.tool_name}")
        """
        try:
            raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            data = {}

        # Ensure tool_input is always a dict (Claude Code may send string)
        tool_input = data.get("tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {"_raw": tool_input}

        return cls(
            detected_event=data.get("detected_event"),
            tool_name=data.get("tool_name"),
            tool_input=tool_input,
            prompt=data.get("prompt"),
            invocation_id=data.get("invocation_id"),
            agent_id=data.get("agent_id"),
            raw_data=data
        )

    def get_event(self) -> Optional[HookEvent]:
        """Get parsed event as HookEvent enum."""
        if not self.detected_event:
            return None
        try:
            return HookEvent(self.detected_event)
        except ValueError:
            return None

    def is_pre_tool_use(self) -> bool:
        """Check if this is a PreToolUse event."""
        return self.detected_event == "PreToolUse"

    def is_post_tool_use(self) -> bool:
        """Check if this is a PostToolUse event."""
        return self.detected_event == "PostToolUse"

    def is_stop(self) -> bool:
        """Check if this is a Stop event."""
        return self.detected_event == "Stop"


@dataclass
class HookOutput:
    """
    Hook output container.

    Supports multiple output formats:
    - System message (via system_message)
    - Block response (via block + reason)
    - Plain text advice (via print)
    """
    _should_block: bool = False
    _block_reason: str = ""
    _system_message: str = ""
    _print_output: List[str] = field(default_factory=list)
    _exit_code: int = 0

    def block(self, reason: str, exit_code: int = 2) -> None:
        """
        Block the current action with a reason.

        Args:
            reason: Human-readable reason for the block
            exit_code: Exit code (default: 2 = block)

        Example:
            >>> output = HookOutput()
            >>> output.block("Skill not activated: langgraph-core")
        """
        self._should_block = True
        self._block_reason = reason
        self._exit_code = exit_code

    def system_message(self, message: str) -> None:
        """
        Add a system message to the context.

        Args:
            message: System message content

        Example:
            >>> output = HookOutput()
            >>> output.system_message("Please activate the langgraph-core skill")
        """
        self._system_message = message

    def print(self, text: str) -> None:
        """
        Add plain text output (printed to stdout).

        Note: Plain text has 100% activation rate vs JSON systemMessage (55%).

        Args:
            text: Text to print

        Example:
            >>> output = HookOutput()
            >>> output.print("ACTIVATE: langgraph-core")
        """
        self._print_output.append(text)

    def advise(self, message: str) -> None:
        """
        Add an advisory message (non-blocking).

        Args:
            message: Advisory message content

        Example:
            >>> output = HookOutput()
            >>> output.advise("Consider using the deployment skill for Docker commands")
        """
        self._print_output.append(message)

    def is_blocking(self) -> bool:
        """Check if this output will block execution."""
        return self._should_block

    def get_exit_code(self) -> int:
        """Get the exit code for this output."""
        return self._exit_code

    def has_content(self) -> bool:
        """Check if this output has any content (message, block, or print)."""
        return bool(
            self._should_block or
            self._system_message or
            self._print_output
        )

    def flush(self) -> None:
        """
        Flush all output to stdout.

        Format:
        1. Print output (plain text) - highest priority
        2. Block message (if blocking)
        3. System message (JSON format for <system-reminder>)

        Example:
            >>> output = HookOutput()
            >>> output.print("Hello")
            >>> output.flush()
        """
        # Plain text output first (100% activation)
        # UTF-8 safe output for Windows cp1251 consoles
        for text in self._print_output:
            try:
                print(text)
            except UnicodeEncodeError:
                sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
                sys.stdout.buffer.write(b"\n")

        # Block message
        if self._should_block:
            block_msg = f"[BLOCK] {self._block_reason}"
            try:
                print(block_msg)
            except UnicodeEncodeError:
                sys.stdout.buffer.write(block_msg.encode("utf-8", errors="replace"))
                sys.stdout.buffer.write(b"\n")

        # System message (JSON format for <system-reminder>)
        if self._system_message:
            msg = json.dumps({"systemMessage": self._system_message}, ensure_ascii=False)
            try:
                print(msg)
            except UnicodeEncodeError:
                sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))
                sys.stdout.buffer.write(b"\n")


class BaseHook:
    """
    Base class for all Claude Code hooks.

    Provides:
    - Standard event handling (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
    - Integration with invocation_logger for structured logging
    - Graceful degradation (never blocks on errors)
    - Timer-based performance tracking

    Usage:
        ```python
        class MyHook(BaseHook):
            def run(self, inp: HookInput) -> HookOutput:
                if inp.tool_name == "Write":
                    return HookOutput().block("Use Edit instead")
                return HookOutput()

        if __name__ == "__main__":
            MyHook.main()
        ```
    """

    # Hook metadata (override in subclasses)
    HOOK_NAME: str = "BaseHook"
    HOOK_VERSION: str = "1.0.0"

    def __init__(self):
        """Initialize hook with timer (if available)."""
        self._timer = None
        self._start_time = None

    def _setup_timer(self) -> None:
        """Setup invocation timer if invocation_logger is available."""
        try:
            from shared.invocation_logger import InvocationTimer
            self._timer = InvocationTimer(self.HOOK_NAME).start()
            self._start_time = datetime.now()
        except Exception:
            pass

    def _log_outcome(self, outcome: HookOutcome, error: Optional[str] = None) -> None:
        """Log hook invocation outcome."""
        if not self._timer:
            return

        try:
            elapsed_ms = 0
            if self._start_time:
                elapsed_ms = int((datetime.now() - self._start_time).total_seconds() * 1000)

            self._timer.log(outcome=outcome.value, error=error)
        except Exception:
            pass

    def run(self, inp: HookInput) -> HookOutput:
        """
        Main hook logic. Override this method in subclasses.

        Args:
            inp: Parsed hook input

        Returns:
            HookOutput with action/message

        Example:
            >>> def run(self, inp: HookInput) -> HookOutput:
            ...     if inp.is_pre_tool_use() and inp.tool_name == "Bash":
            ...         return HookOutput().block("Use native tools instead")
            ...     return HookOutput()
        """
        return HookOutput()

    def execute(self) -> None:
        """
        Execute hook with full error handling and logging.

        This method:
        1. Parses stdin input
        2. Calls run() with parsed input
        3. Flushes output
        4. Exits with appropriate code
        """
        self._setup_timer()

        try:
            inp = HookInput.from_stdin()
            output = self.run(inp)

            # Flush output
            if output.has_content():
                output.flush()

            # Log outcome
            if output.is_blocking():
                self._log_outcome(HookOutcome.BLOCK)
            elif output._print_output or output._system_message:
                self._log_outcome(HookOutcome.MESSAGE)
            else:
                self._log_outcome(HookOutcome.ALLOW)

            # Exit with appropriate code
            sys.exit(output.get_exit_code())

        except SystemExit:
            # Allow sys.exit() to propagate
            raise

        except Exception as e:
            # Graceful degradation: never block on errors
            self._log_outcome(HookOutcome.ERROR, error=str(e))
            sys.exit(0)

    @classmethod
    def main(cls) -> None:
        """Entry point for hook execution."""
        hook = cls()
        hook.execute()


# Export for use in hooks
__all__ = [
    "BaseHook",
    "HookEvent",
    "HookOutcome",
    "HookInput",
    "HookOutput"
]
