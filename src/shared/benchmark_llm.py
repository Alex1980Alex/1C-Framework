"""Eval/benchmark LLM wrapper — isolated from production LLM Rotation.

Roadmap 260509 §2.2 closure (architecture):

`cheap_llm_call` from `src/shared/llm_rotation/adapter.py` is used by
~10 production callsites (Self-RAG grader, hallucination check, query
rewriter, adaptive classifier, HyDE, contextual retrieval, entity
extractor, etc.). Touching its provider chain would silently degrade
production quality (most providers in DEFAULT_PROVIDERS are broken
per user audit, only Ollama is reliably live).

This module provides a separate path for **eval workloads** (grounding
scripts, retrieval benchmarks, NDCG experiments). It uses:

  1. **Primary**: `claude -p` subprocess via current CLI subscription.
     No API token billing — flat-rate subscription. Quality = top-tier
     (Sonnet/Opus). Subject to subscription rate limits.

  2. **Fallback**: Ollama `qwen2.5-coder:7b` HTTP (same as production
     ollama-local in LLM Rotation). $0, always-on if Ollama running.

Design choices:
- Async via `asyncio.create_subprocess_exec` (no thread blocking).
- No retry inside call — caller decides (eval scripts batch many calls,
  retry policy belongs at the loop level).
- Sequential cost: ~3-8s per `claude -p` spawn (process startup +
  inference). Caller may parallelize via `asyncio.gather` if needed,
  subject to CLI subscription rate limits.
- No cross-call state — each invocation is a fresh subprocess.

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
import shutil
from typing import Final

import httpx

logger = logging.getLogger(__name__)

_CLAUDE_BIN: Final[str | None] = shutil.which("claude")
# Empirically-tuned flags (2026-05-16; see tech-research/cache/
# claude-code-subprocess-wrappers.md "Gap vs best practices"):
#
# WHAT WORKS:
# - stdin pipe (added 2026-05-16): fixes Windows long-arg edge case (~10%
#   "Input must be provided" failures observed in grounding pipeline)
# - graceful terminate→wait→kill on timeout: proper SIGTERM signal escalation
# - --system-prompt REPLACE (added in _call_claude_cli below): bypasses
#   default Claude Code agent prompt that returns helpful markdown instead
#   of strict JSON when user asks for "JSON only"
# - --max-budget-usd 1.00: notional cost cap (subscription is flat-rate but
#   CLI tracks notional Anthropic pricing; safety net against agentic runaway)
#
# WHAT DOESN'T WORK (tried 2026-05-16, rolled back — see cache):
# - --max-turns 1..10: Claude Code CLI in -p mode is fundamentally agentic;
#   even simple "Reply: pong" triggers tool-use turns. For genuine single-
#   shot inference, migrate to claude-agent-sdk Python package (separate
#   refactor) or direct Anthropic HTTP API.
# - --output-format json: errors out with is_error=true + no `result` field
#   when --max-turns hit, defeating the structured-parsing benefit. Plain
#   text mode + permissive parsing in caller works for our use case.
# - --model haiku hardcoded: better leave to caller / provider config to
#   pick model per workload.
_CLAUDE_ARGS: Final[list[str]] = [
    "-p",
    "--no-session-persistence",
    "--disable-slash-commands",
    "--dangerously-skip-permissions",
    "--max-budget-usd", "1.00",
    # --model haiku: without explicit model the CLI uses Opus 4.7 1M-context
    # which (a) consumes more subscription quota and (b) goes more agentic
    # (reads cwd, tries tool calls) before responding. Haiku stays focused
    # on simple eval prompts. service.py provider config supplies its own
    # --model via state.config.default_model.
    "--model", "haiku",
]
_OLLAMA_URL: Final[str] = os.environ.get(
    "BENCHMARK_OLLAMA_URL", "http://localhost:11434"
)
_OLLAMA_MODEL: Final[str] = os.environ.get(
    "BENCHMARK_OLLAMA_MODEL", "qwen2.5-coder:7b"
)

_CLAUDE_DEFAULT_TIMEOUT: Final[int] = 120
_OLLAMA_DEFAULT_TIMEOUT: Final[int] = 90


class BenchmarkLLMError(RuntimeError):
    """Raised when both claude CLI and Ollama paths fail."""


async def _call_claude_cli(
    prompt: str,
    system_prompt: str | None,
    timeout: int,
) -> str:
    """Run `claude -p` subprocess; return stdout text on success."""
    if _CLAUDE_BIN is None:
        raise BenchmarkLLMError("claude CLI not found on PATH")

    # --system-prompt REPLACES the default Claude Code agent system prompt.
    # Crucial for batch eval: default prompt makes Claude render helpful
    # markdown answers with file links, ignoring "JSON only" output format
    # directives in user prompt. Replace mode strips all agent behaviors.
    args = list(_CLAUDE_ARGS)
    if system_prompt:
        args.extend(["--system-prompt", system_prompt])

    try:
        proc = await asyncio.create_subprocess_exec(
            _CLAUDE_BIN,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, FileNotFoundError) as e:
        raise BenchmarkLLMError(f"claude spawn failed: {e}") from e

    # Prompt via stdin (not CLI arg) avoids Windows long-arg edge case observed
    # 2026-05-16 where ~10% of multi-KB prompts triggered "Input must be provided"
    # error. Stdin pipe is the recommended pattern per Anthropic SDK docs.
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=timeout,
        )
    except asyncio.TimeoutError as e:
        # Graceful escalation: SIGTERM first → 5s grace → SIGKILL
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        raise BenchmarkLLMError(f"claude timed out after {timeout}s") from e

    if proc.returncode != 0:
        err = (stderr_b or b"").decode("utf-8", errors="replace").strip()
        raise BenchmarkLLMError(f"claude exit {proc.returncode}: {err[:200]}")

    text = (stdout_b or b"").decode("utf-8", errors="replace").strip()
    if not text:
        raise BenchmarkLLMError("claude returned empty stdout")
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
            return await _call_claude_cli(
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
