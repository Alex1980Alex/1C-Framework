"""Eval/benchmark LLM wrapper — isolated from production LLM Rotation.

Roadmap 260509 §2.2 + 260516 Phase 1 SDK migration:

`cheap_llm_call` from `src/shared/llm_rotation/adapter.py` is used by
~10 production callsites. This module provides a separate path for
**eval workloads** (grounding scripts, retrieval benchmarks, NDCG).

Architecture (2026-05-16, post Phase 1 SDK migration):

  1. **Primary**: `claude-agent-sdk` Python package (subscription OAuth).
     `max_turns=1` actually works through SDK options. Returns typed
     messages (AssistantMessage, ResultMessage). Force model=Haiku for
     batch eval (cheaper, faster, less agentic than default Opus).

  2. **Fallback**: Ollama `qwen2.5-coder:7b` HTTP (same as production
     ollama-local in LLM Rotation). $0, always-on if Ollama running.

Design choices:
- Async-first via SDK `AsyncIterator[Message]` + `asyncio.wait_for` timeout.
- No retry inside call — caller decides (eval scripts batch many calls).
- No cross-call state — each `query()` is a fresh session.

Usage (replaces `cheap_llm_call` in eval scripts):

    from src.shared.benchmark_llm import benchmark_llm_call

    text = await benchmark_llm_call(
        prompt="Which of these chunks answers the query?",
        system_prompt="You are a relevance judge.",
        max_tokens=200,
    )
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Final

import httpx

logger = logging.getLogger(__name__)

# Override via BENCHMARK_CLAUDE_MODEL env (haiku/sonnet/opus alias or full name).
# Default Haiku for batch eval: cheaper, faster, less agentic than Opus.
_BENCHMARK_MODEL: Final[str] = os.environ.get("BENCHMARK_CLAUDE_MODEL", "claude-haiku-4-5")
_OLLAMA_URL: Final[str] = os.environ.get("BENCHMARK_OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL: Final[str] = os.environ.get("BENCHMARK_OLLAMA_MODEL", "qwen2.5-coder:7b")

_CLAUDE_DEFAULT_TIMEOUT: Final[int] = 120
_OLLAMA_DEFAULT_TIMEOUT: Final[int] = 90

_MODEL_ALIASES: Final[dict[str, str]] = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-5",
    "opus": "claude-opus-4-7",
}


def _resolve_model(name: str) -> str:
    """Expand short alias to full model name, or pass through if already full."""
    return _MODEL_ALIASES.get(name.lower(), name)


class BenchmarkLLMError(RuntimeError):
    """Raised when both claude CLI and Ollama paths fail."""


async def _call_claude_sdk(
    prompt: str,
    system_prompt: str | None,
    timeout: int,
) -> str:
    """Call Claude via `claude-agent-sdk` Python package.

    Uses CLI subscription OAuth (flat-rate, no per-token billing).
    `max_turns=1` actually works through SDK options — direct CLI flag
    is empirically broken (triggers error_max_turns even on trivial
    prompts; rollback documented in roadmap 260516 §0).

    Latency ~5-15s. Returns final response text combining ResultMessage
    content (preferred) + AssistantMessage text blocks (fallback).
    """
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            query,
        )
    except ImportError as e:
        raise BenchmarkLLMError(
            'claude-agent-sdk not installed. pip install -e ".[llm-rotation]"'
        ) from e

    # Optional error types — older SDK versions may not export them.
    try:
        from claude_agent_sdk import ClaudeSDKError, CLINotFoundError
    except ImportError:
        CLINotFoundError = ClaudeSDKError = Exception  # noqa: PGH003  # type: ignore  # platform-dependent: mypy disagrees on assignment vs unused-ignore

    # max_turns=3: gives Claude room to use 1-2 tool-use turns before
    # responding (CLI is agentic by default). Empirically max_turns=1
    # fails ~50% of the time with "Reached maximum number of turns"
    # even via SDK (CLI raises this regardless of API). Higher cap
    # absorbs agentic overhead while still bounded.
    options = ClaudeAgentOptions(
        system_prompt=system_prompt or "",
        max_turns=3,
        permission_mode="bypassPermissions",
        model=_resolve_model(_BENCHMARK_MODEL),
    )

    text_parts: list[str] = []
    result_content: str | None = None

    async def _collect() -> None:
        nonlocal result_content
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                candidate = getattr(msg, "result", None)
                if candidate:
                    result_content = str(candidate)

    try:
        await asyncio.wait_for(_collect(), timeout=timeout)
    except TimeoutError as e:
        raise BenchmarkLLMError(f"claude-agent-sdk timed out after {timeout}s") from e
    except CLINotFoundError as e:
        raise BenchmarkLLMError(f"claude CLI not found: {e}") from e
    except ClaudeSDKError as e:
        raise BenchmarkLLMError(f"claude-agent-sdk error: {e}") from e
    except Exception as e:
        # SDK surfaces CLI's error_max_turns as plain Exception. If we
        # already collected partial text from AssistantMessage blocks,
        # use it. Otherwise propagate as benchmark error.
        partial = "".join(text_parts).strip()
        if partial:
            logger.warning(
                "[BENCHMARK-LLM] SDK exception after partial text (%d chars): %s",
                len(partial),
                e,
            )
            return partial
        raise BenchmarkLLMError(f"claude-agent-sdk error: {e}") from e

    text = (result_content or "").strip() or "".join(text_parts).strip()

    if not text:
        raise BenchmarkLLMError("claude-agent-sdk returned empty result")
    return text


async def _call_ollama(
    prompt: str,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> str:
    """POST to Ollama /api/generate; return response text."""
    payload: dict[str, object] = {
        "model": _OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{_OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("response") or "").strip()
            if not text:
                raise BenchmarkLLMError("Ollama returned empty response")
            return text
    except (httpx.HTTPError, ConnectionError) as e:
        raise BenchmarkLLMError(f"Ollama call failed: {e}") from e


async def benchmark_llm_call(
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    timeout: int | None = None,
    prefer: str = "claude",
) -> str:
    """Eval-only LLM call. Tries `claude -p` first, falls back to Ollama.

    Args:
        prompt: User prompt.
        system_prompt: Optional system instruction.
        max_tokens: Output token cap (passed to Ollama; claude CLI ignores).
        temperature: Sampling temperature (Ollama only; claude CLI default).
        timeout: Per-attempt timeout in seconds. Default: 120 for claude,
            90 for Ollama. Use ``timeout`` to override both.
        prefer: ``"claude"`` (default) or ``"ollama"`` to skip claude
            entirely.

    Returns:
        Response text (stripped).

    Raises:
        BenchmarkLLMError: When all attempted backends fail.
    """
    errors: list[str] = []

    if prefer == "claude":
        try:
            return await _call_claude_sdk(
                prompt=prompt,
                system_prompt=system_prompt,
                timeout=timeout or _CLAUDE_DEFAULT_TIMEOUT,
            )
        except BenchmarkLLMError as e:
            errors.append(f"claude: {e}")
            logger.warning("[BENCHMARK-LLM] claude failed, falling back: %s", e)

    try:
        return await _call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout or _OLLAMA_DEFAULT_TIMEOUT,
        )
    except BenchmarkLLMError as e:
        errors.append(f"ollama: {e}")

    raise BenchmarkLLMError("all backends failed: " + "; ".join(errors))
