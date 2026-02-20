"""Langfuse callback handler for LangChain integration.

Integrates Langfuse tracing with LangChain components:
- LLM calls (Claude, GPT, etc.)
- Tool calls
- Chain executions
- Agent decisions

Author: Claude Code
Version: 1.0.0 - Phase 46: Langfuse Integration
"""

import logging
from typing import Any, Literal

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class LangfuseCallbackHandler(BaseCallbackHandler):
    """
    Callback handler for Langfuse observability.

    Tracks:
    - LLM calls (latency, tokens, cost)
    - Chain executions
    - Tool calls
    - Agent reasoning steps
    """

    def __init__(
        self,
        enabled: bool = True,
        user_id: str | None = None,
        session_id: str | None = None,
    ):
        """
        Initialize Langfuse callback handler.

        Args:
            enabled: Whether callback is active
            user_id: User ID for attribution
            session_id: Session ID for grouping traces
        """
        super().__init__()
        self._enabled = enabled
        self._user_id = user_id
        self._session_id = session_id
        self._langfuse_client = None

        if self._enabled:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Langfuse client."""
        try:
            from langfuse import Langfuse
            import os

            public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
            secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

            if public_key and secret_key:
                self._langfuse_client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
                )
                logger.debug("[LANGFUSE] Callback handler initialized")
            else:
                logger.warning("[LANGFUSE] Missing credentials, disabling callback")
                self._enabled = False
        except ImportError:
            logger.warning("[LANGFUSE] langfuse not installed")
            self._enabled = False

    @property
    def ignore_llm(self) -> bool:
        """Whether to ignore LLM callbacks."""
        return not self._enabled

    @property
    def ignore_chain(self) -> bool:
        """Whether to ignore chain callbacks."""
        return not self._enabled

    @property
    def ignore_agent(self) -> bool:
        """Whether to ignore agent callbacks."""
        return not self._enabled

    @property
    def ignore_retriever(self) -> bool:
        """Whether to ignore retriever callbacks."""
        return not self._enabled

    def on_llm_start(
        self,
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts processing."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            # Create a generation in Langfuse
            self._current_generation = self._langfuse_client.generation(
                name="llm_call",
                input=str(prompts),
                metadata={
                    "user_id": self._user_id,
                    "session_id": self._session_id,
                },
            )
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to start LLM trace: {e}")

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """Called when LLM finishes processing."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            # Update generation with results
            generations = response.flatten()
            if generations:
                first_generation = generations[0]
                output_text = first_generation.text if hasattr(first_generation, "text") else str(first_generation)

                # Get token usage if available
                usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                self._langfuse_client.generation(
                    name="llm_call",
                    input=str(kwargs.get("prompts", "")),
                    output=output_text,
                    usage={
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    },
                    metadata={
                        "user_id": self._user_id,
                        "session_id": self._session_id,
                        "model": response.llm_output.get("model", "unknown") if response.llm_output else "unknown",
                    },
                )

                self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to end LLM trace: {e}")

    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Called when LLM encounters an error."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.generation(
                name="llm_call",
                level="ERROR",
                status_message=str(error),
            )
            self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to trace LLM error: {e}")

    def on_chain_start(
        self,
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when chain starts execution."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=kwargs.get("name", "chain"),
                input=inputs,
            )
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to start chain trace: {e}")

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when chain finishes execution."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=kwargs.get("name", "chain"),
                output=outputs,
            )
            self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to end chain trace: {e}")

    def on_chain_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Called when chain encounters an error."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=kwargs.get("name", "chain"),
                level="ERROR",
                status_message=str(error),
            )
            self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to trace chain error: {e}")

    def on_tool_start(
        self,
        inputs: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when tool starts execution."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=f"tool:{kwargs.get('name', 'unknown')}",
                input=inputs,
            )
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to start tool trace: {e}")

    def on_tool_end(
        self,
        outputs: Any,
        **kwargs: Any,
    ) -> None:
        """Called when tool finishes execution."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=f"tool:{kwargs.get('name', 'unknown')}",
                output=str(outputs),
            )
            self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to end tool trace: {e}")

    def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Called when tool encounters an error."""
        if not self._enabled or not self._langfuse_client:
            return

        try:
            self._langfuse_client.span(
                name=f"tool:{kwargs.get('name', 'unknown')}",
                level="ERROR",
                status_message=str(error),
            )
            self._langfuse_client.flush()
        except Exception as e:
            logger.warning(f"[LANGFUSE] Failed to trace tool error: {e}")
