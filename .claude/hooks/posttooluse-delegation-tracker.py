#!/usr/bin/env python3
"""
Hook: posttooluse-delegation-tracker
Event: PostToolUse
Matcher: mcp__llm-rotation__llm_complete
Purpose: Track Z.AI delegation outcomes — provider, model, response time,
         quality score. Log to data/delegation-outcomes.jsonl (JSONL append).
         hookSpecificOutput feedback on anomalies (slow/empty response).
Timeout: 3s
"""

import json
import os
import sys
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.circuit_breaker import with_circuit_breaker


def _classify_content(text: str) -> str:
    """Auto-classify content type from response text."""
    if not text:
        return "empty"
    if "```" in text or "def " in text or "class " in text:
        return "code"
    if text.startswith("#") or "## " in text or "| " in text:
        return "docs"
    if any(kw in text.lower() for kw in ["error", "failed", "exception"]):
        return "error_report"
    if len(text) < 200:
        return "short_answer"
    return "general"


def _quality_heuristic(text: str, response_time: float) -> dict:
    """Compute heuristic quality score."""
    score = 0.5
    details = {}

    # Length bonus
    if len(text) > 100:
        score += 0.1
        details["length_ok"] = True
    if len(text) > 500:
        score += 0.1
        details["length_good"] = True

    # Code blocks bonus
    code_blocks = text.count("```")
    if code_blocks >= 2:
        score += 0.1
        details["has_code"] = True

    # Structure bonus (headers, lists)
    if "## " in text or "- " in text:
        score += 0.05
        details["has_structure"] = True

    # Speed bonus/penalty
    if response_time < 3.0:
        score += 0.1
        details["fast"] = True
    elif response_time > 10.0:
        score -= 0.15
        details["slow"] = True

    return {"score": round(min(score, 1.0), 2), "details": details}


def _log_outcome(entry: dict) -> None:
    """Log delegation outcome to SQLite (fallback: JSONL)."""
    try:
        from shared.db_writer import log_delegation
        log_delegation(
            provider=entry.get("provider", "unknown"),
            model=entry.get("model", "unknown"),
            content_type=entry.get("content_type", ""),
            response_time=entry.get("response_time", 0),
            text_length=entry.get("text_length", 0),
            quality_score=entry.get("quality_score", 0),
            attempt=entry.get("attempt", 1),
            prompt_tokens=entry.get("prompt_tokens", 0),
            completion_tokens=entry.get("completion_tokens", 0),
            session_id=entry.get("session_id", ""),
            quality_details=entry.get("quality_details"),
        )
    except Exception:
        # Fallback to JSONL
        try:
            project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
            log_path = os.path.join(project_dir, "data", "delegation-outcomes.jsonl")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


class PostToolUseDelegationTracker(BaseHook):
    """PostToolUse hook for mcp__llm-rotation__llm_complete: track delegation outcomes."""

    @with_circuit_breaker("posttooluse-delegation-tracker")
    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        # Parse tool_response — Claude Code wraps MCP results as content blocks:
        # [{"type": "text", "text": "{...json...}"}]
        tool_response = inp.raw.get("tool_response", "")

        # Unwrap content blocks
        raw_text = ""
        if isinstance(tool_response, list):
            for block in tool_response:
                if isinstance(block, dict) and block.get("type") == "text":
                    raw_text += block.get("text", "")
        elif isinstance(tool_response, str):
            raw_text = tool_response
        elif isinstance(tool_response, dict):
            raw_text = json.dumps(tool_response)

        # Parse the inner JSON
        resp: dict = {}
        try:
            parsed = json.loads(raw_text)
            resp = parsed if isinstance(parsed, dict) else {"text": str(parsed)}
        except (json.JSONDecodeError, AttributeError):
            resp = {"text": raw_text}

        provider = str(resp.get("provider", "unknown"))
        model = str(resp.get("model", "unknown"))
        response_time = float(resp.get("response_time", 0) or 0)
        text = str(resp.get("text", ""))
        usage = resp.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        attempt = int(resp.get("attempt", 1) or 1)

        # Classify and score
        content_type = _classify_content(text)
        quality = _quality_heuristic(text, response_time)

        # Build entry
        entry = {
            "ts": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "content_type": content_type,
            "response_time": round(float(response_time), 2),
            "text_length": len(text),
            "quality_score": quality["score"],
            "quality_details": quality["details"],
            "attempt": attempt,
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "session_id": (inp.session_id or "unknown")[:16],
            "source": "posttooluse",
        }

        _log_outcome(entry)

        # Feedback on anomalies
        messages = []
        if not text:
            messages.append(
                "Z.AI returned empty response. "
                "Consider retrying or using a different provider."
            )
        elif response_time > 15.0:
            messages.append(
                f"Z.AI response was slow ({response_time:.1f}s "
                f"from {provider}). Consider switching provider."
            )
        elif quality["score"] < 0.4:
            messages.append(
                f"Z.AI quality score low ({quality['score']:.2f}). "
                "Response may need review."
            )

        if messages:
            return HookOutput().hook_context(
                "[delegation-tracker] " + " ".join(messages)
            )

        return None


if __name__ == "__main__":
    PostToolUseDelegationTracker().run()
