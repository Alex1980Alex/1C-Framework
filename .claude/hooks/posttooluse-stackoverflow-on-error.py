#!/usr/bin/env python3
"""
Hook: posttooluse-stackoverflow-on-error
Event: PostToolUse
Matcher: Bash
Purpose: When Bash exits non-zero AND stderr contains traceback / error signature,
         extract last meaningful error line and emit advisory systemMessage with
         WebSearch SO suggestion. Complementary к posttooluse-bash-errors.py
         (which only classifies type — this proposes concrete recovery action).
Timeout: 3s

Per §14.5 Option C (roadmap 260523), PostToolUse half. Pairs with UPS-time
prework-stackoverflow.py (proactive cache lookup) — both close §14.1 row 5 gap.

References:
- roadmap 260523 §14.5 — pre-work analysis pipeline, SO automation
- complementary hook: posttooluse-bash-errors.py (error type classifier)
"""

import os
import re
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput  # noqa: E402

# Patterns that indicate SO-searchable error signatures.
# Order matters: last-match wins (most specific signature usually trails output).
SIGNATURE_PATTERNS = [
    # Python traceback last line: e.g. "ModuleNotFoundError: No module named 'foo'"
    re.compile(
        r"^(?P<exc>[A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning)):\s+(?P<msg>.+)$",
        re.MULTILINE,
    ),
    # pip resolver errors
    re.compile(
        r"^ERROR:\s+(?P<msg>(?:Could not find a version|No matching distribution|"
        r"ResolutionImpossible|Cannot install).+)$",
        re.MULTILINE,
    ),
    # npm errors
    re.compile(r"^npm ERR!\s+(?P<msg>(?!gyp|code\s|errno|stack).+)$", re.MULTILINE),
    # Generic "fatal:" (git, build tools)
    re.compile(r"^fatal:\s+(?P<msg>.+)$", re.MULTILINE),
]

# Min total length to consider (skip trivial outputs like `echo ok`).
# Real error signatures (`npm ERR! 404`, `fatal: ...`) могут быть ~30 chars,
# поэтому threshold низкий.
MIN_TEXT_LEN = 20

# Skip commands where errors are expected/handled.
SKIP_CMD_SUBSTRINGS = (
    "|| true",
    "2>/dev/null",
    "2>$null",
    "set +e",
)

HOOK_NAME = "posttooluse-stackoverflow-on-error"


def _normalize_response(tool_response: object) -> str:
    """Flatten various tool_response shapes into a single text string.

    Bash tool_response обычно имеет dict-форму с `stdout`/`stderr`/`output` keys —
    нужно extract'нуть текстовые секции, а НЕ репрезентовать dict через `str()`
    (это даёт single-line `{'stdout': '...'}` и ломает многострочные regex anchors).
    """
    if isinstance(tool_response, list):
        text_parts = []
        for block in tool_response:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)
    if isinstance(tool_response, dict):
        parts = []
        for key in ("stdout", "stderr", "output", "text"):
            val = tool_response.get(key)
            if isinstance(val, str) and val:
                parts.append(val)
        if parts:
            return "\n".join(parts)
        # Fallback: empty if no text fields (avoid single-line `str(dict)` repr
        # which breaks ^-anchored multiline regexes).
        return ""
    if isinstance(tool_response, str):
        return tool_response
    return ""


def _extract_signature(text: str) -> str | None:
    """Return last-occurring SO-searchable signature, or None."""
    best: tuple[int, str] | None = None  # (position, signature)
    for pattern in SIGNATURE_PATTERNS:
        for match in pattern.finditer(text):
            exc = match.groupdict().get("exc", "")
            msg = match.groupdict().get("msg", "").strip()
            if not msg:
                continue
            # Trim very long messages (SO search works better on signatures)
            if len(msg) > 200:
                msg = msg[:200].rstrip()
            sig = f"{exc}: {msg}" if exc else msg
            pos = match.start()
            if best is None or pos > best[0]:
                best = (pos, sig)
    return best[1] if best else None


def _bash_exit_failed(tool_response: object, text: str) -> bool:
    """Best-effort detection that Bash exited non-zero.

    tool_response может быть dict с явным `exit_code`, либо текст где встретилось
    "Exit code: N" / "exit code N" / "command failed". Если не уверены — fallback на
    presence of traceback-like patterns в тексте.
    """
    # Explicit exit code field — authoritative когда есть.
    if isinstance(tool_response, dict):
        ec = tool_response.get("exit_code")
        if isinstance(ec, int):
            return ec != 0
        if isinstance(ec, str) and ec.strip():
            return ec.strip() != "0"
        # Field absent → fall through to textual indicators below.

    # Textual indicators
    lower = text.lower()
    if "exit code:" in lower or "command failed" in lower or "non-zero exit" in lower:
        # Extract digit if possible
        m = re.search(r"exit\s*code:?\s*(\d+)", lower)
        if m and m.group(1) != "0":
            return True
        if m and m.group(1) == "0":
            return False
        return True

    # Heuristic fallback: real error signatures обычно сопровождаются ненулевым exit
    if "Traceback (most recent call last)" in text:
        return True
    if re.search(r"^npm ERR!", text, re.MULTILINE):
        return True
    if re.search(r"^fatal:", text, re.MULTILINE):
        return True

    return False


class PostToolUseStackOverflowOnError(BaseHook):
    """PostToolUse:Bash → suggest WebSearch SO if error signature found."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Bash":
            return None

        tool_response = inp.raw.get("tool_response", "")
        text = _normalize_response(tool_response)
        if not text or len(text) < MIN_TEXT_LEN:
            return None

        # Skip commands where errors expected
        tool_input = inp.tool_input if isinstance(inp.tool_input, dict) else {}
        command = str(tool_input.get("command", "")) if tool_input else ""
        if command:
            for skip in SKIP_CMD_SUBSTRINGS:
                if skip in command:
                    return None

        if not _bash_exit_failed(tool_response, text):
            return None

        signature = _extract_signature(text)
        if not signature:
            return None

        # Build advisory message — non-blocking, advisory only
        # Quote signature for SO search; truncate query suggestion
        query = signature[:160]
        message = (
            f"[SO-ON-ERROR] Bash failed with signature: `{signature[:120]}`.\n"
            f"Consider: WebSearch `site:stackoverflow.com {query} is:answer votes:5`\n"
            f"Or check skill `tech-research` cache для known patterns."
        )
        return HookOutput().system_message(message)


if __name__ == "__main__":
    PostToolUseStackOverflowOnError().run()
