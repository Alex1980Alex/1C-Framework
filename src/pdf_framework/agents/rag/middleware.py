"""LangGraph middleware for RAG agent (Phase 43).

Provides interception points for LLM calls:
- Token usage tracking and cost estimation
- Request/response logging
- Content safety validation
- Dynamic model selection based on query complexity
- Langfuse tracing integration (Phase 46)

Usage:
    from src.pdf_framework.agents.rag.middleware import TokenTracker, with_middleware

    tracker = TokenTracker()
    llm = with_middleware(ChatAnthropic(model="claude-opus-4-6"), tracker)
"""

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Try to import Langfuse callback (Phase 46)
try:
    from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.debug("[MIDDLEWARE] Langfuse callback not available")


# ---------------------------------------------------------------------------
# 1. Token Tracker — accumulates usage across all LLM calls in a session
# ---------------------------------------------------------------------------

@dataclass
class TokenUsage:
    """Accumulated token usage for a single agent run."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    calls: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0
    node_stats: dict[str, dict] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "errors": self.errors,
        }


class TokenTracker(AsyncCallbackHandler):
    """Callback handler that tracks token usage across all LLM calls."""

    def __init__(self, node_name: str = "unknown"):
        self.usage = TokenUsage()
        self._node_name = node_name
        self._call_start: float = 0.0

    def set_node(self, name: str) -> None:
        """Set current node name for per-node tracking."""
        self._node_name = name

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        self._call_start = time.time()

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        self._call_start = time.time()

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        latency_ms = (time.time() - self._call_start) * 1000
        self.usage.calls += 1
        self.usage.total_latency_ms += latency_ms

        # Extract token usage from response metadata
        for gen_list in response.generations:
            for gen in gen_list:
                info = gen.generation_info or {}
                usage = info.get("usage_metadata", {})
                if usage:
                    self.usage.input_tokens += usage.get("input_tokens", 0)
                    self.usage.output_tokens += usage.get("output_tokens", 0)
                    self.usage.cache_read_tokens += usage.get(
                        "cache_read_input_tokens", 0,
                    )
                    self.usage.cache_creation_tokens += usage.get(
                        "cache_creation_input_tokens", 0,
                    )

        # Per-node tracking
        node = self._node_name
        if node not in self.usage.node_stats:
            self.usage.node_stats[node] = {"calls": 0, "latency_ms": 0.0}
        self.usage.node_stats[node]["calls"] += 1
        self.usage.node_stats[node]["latency_ms"] += latency_ms

        logger.debug(
            "[MIDDLEWARE] LLM call in '%s': %.0fms, in=%d, out=%d",
            node, latency_ms,
            self.usage.input_tokens, self.usage.output_tokens,
        )

    async def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.usage.errors += 1
        logger.warning("[MIDDLEWARE] LLM error in '%s': %s", self._node_name, error)


# ---------------------------------------------------------------------------
# 2. Content Guard — validates LLM outputs for safety/format
# ---------------------------------------------------------------------------

class ContentGuard(AsyncCallbackHandler):
    """Callback handler that logs warnings for suspicious LLM outputs."""

    def __init__(self, max_output_tokens: int = 8192):
        self._max_output = max_output_tokens

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                text = gen.text or ""
                if len(text) > self._max_output * 4:  # ~4 chars per token
                    logger.warning(
                        "[GUARD] Unusually long output: %d chars (limit ~%d)",
                        len(text), self._max_output * 4,
                    )


# ---------------------------------------------------------------------------
# 3. Helper: attach middleware to LLM
# ---------------------------------------------------------------------------

def with_middleware(
    llm: Any,
    *handlers: AsyncCallbackHandler,
    enable_langfuse: bool = True,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Any:
    """Attach callback handlers to an LLM instance.

    Args:
        llm: The LLM instance
        *handlers: Additional callback handlers to attach
        enable_langfuse: Whether to add Langfuse callback (if available)
        user_id: User ID for trace attribution
        session_id: Session ID for trace grouping

    Returns:
        The same LLM with callbacks configured.
    """
    existing = list(llm.callbacks or [])
    existing.extend(handlers)

    # Add Langfuse callback if enabled and available (F3.2)
    if enable_langfuse and LANGFUSE_AVAILABLE:
        langfuse_cb = LangfuseCallbackHandler(
            enabled=True,
            user_id=user_id,
            session_id=session_id,
        )
        existing.append(langfuse_cb)

    llm.callbacks = existing
    return llm


def create_traced_llm(
    llm: Any,
    user_id: str | None = None,
    session_id: str | None = None,
    **llm_kwargs
) -> Any:
    """
    F3.2.2: Create LLM with Langfuse tracing enabled.

    Convenience function to create an LLM with automatic tracing.

    Args:
        llm: Base LLM instance
        user_id: User ID for attribution
        session_id: Session ID for grouping
        **llm_kwargs: Additional kwargs for LLM initialization

    Returns:
        LLM with Langfuse callback attached
    """
    return with_middleware(llm, user_id=user_id, session_id=session_id)
