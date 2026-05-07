"""Slash-command detection from a Claude Code UserPromptSubmit `prompt` field.

Two callers today (slash-command-tracker.py, implement-1c-task-preflight.py),
extracted here so the regex/heuristic only lives in one place. Drift between
the two copies is a real risk — the backtick-noise rule on Windows
(v2.1.126+) was lost once during a UPE→UPS rewrite and re-introduced after a
live regression in session 2800d2fd-… (2026-05-05). One source of truth
prevents the next round.

Detection (in order, first hit wins):
  1. `<command-name>NAME</command-name>` wrapper (post-expansion form Claude
     Code 2.x injects when the slash command's body is inlined into the
     prompt — most authoritative).
  2. Raw "/cmd ..." prefix (pre-expansion CLI form). Leading backtick / quote
     noise is stripped first because Claude Code v2.1.126+ wraps real CLI
     invocations as ``/cmd args`` (commit fbdf1b720). Synthetic stdin tests
     don't carry the backtick — the regression is invisible to health-checks
     and only surfaces in real sessions.

Plain prompts without either marker return the empty string — callers should
treat that as "no slash command detected" and pass through.
"""

from __future__ import annotations

import re

_CMD_NAME_TAG_RE = re.compile(r"<command-name>\s*/?([a-zA-Z0-9][a-zA-Z0-9_:.-]*)\s*</command-name>")
_RAW_SLASH_RE = re.compile(r"^\s*/([a-zA-Z0-9][a-zA-Z0-9_:.-]*)(?:\s|$)")
_LEADING_NOISE_RE = re.compile(r"^\s*[`'\"]+")


def detect_slash_command(prompt: str) -> str:
    """Return the slash command name found in the prompt, or '' if none."""
    if not prompt:
        return ""
    m = _CMD_NAME_TAG_RE.search(prompt)
    if m:
        return m.group(1)
    cleaned = _LEADING_NOISE_RE.sub("", prompt)
    m = _RAW_SLASH_RE.match(cleaned)
    if m:
        return m.group(1)
    return ""
