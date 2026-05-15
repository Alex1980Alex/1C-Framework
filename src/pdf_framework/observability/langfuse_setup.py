"""Centralised Langfuse initialization helper (roadmap 260509 §3.1).

Single entrypoint to wire Langfuse observability into the framework.
Reads credentials from pydantic-settings (`observability.langfuse_*`) so
behaviour is consistent with other framework subsystems and the docs at
[09.4 Мониторинг](docs/framework documentation/09_АДМИНИСТРИРОВАНИЕ/09.4_Мониторинг.md).

Resolution chain (handler-side, see `LangfuseCallbackHandler._resolve_credentials`):
  1. explicit constructor kwargs (DI for tests)
  2. settings.observability.langfuse_*   ← canonical
  3. os.environ.LANGFUSE_*               ← legacy fallback
  4. nothing → handler disables itself with a warning

Usage:
    from src.pdf_framework.observability.langfuse_setup import build_langfuse_callback

    handler = build_langfuse_callback(user_id="u-1", session_id="s-1")
    if handler is not None:
        llm.callbacks = (llm.callbacks or []) + [handler]
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler


def is_langfuse_enabled() -> bool:
    """Return True iff Langfuse is enabled in settings.

    Также проверяет opt-out env `MEMORY_HOOK_NO_LANGFUSE=1` для standalone hooks
    (per memory-first-hook.py convention).
    """
    if os.environ.get("MEMORY_HOOK_NO_LANGFUSE") == "1":
        return False
    try:
        from src.pdf_framework.config import get_settings

        return bool(get_settings().observability.langfuse_enabled)
    except Exception as e:  # pragma: no cover — defensive
        logger.debug(f"[LANGFUSE] is_langfuse_enabled fallback (False): {e}")
        return False


def build_langfuse_callback(
    user_id: str | None = None,
    session_id: str | None = None,
) -> "LangfuseCallbackHandler | None":
    """Construct a `LangfuseCallbackHandler` if enabled, else return None.

    Reads `langfuse_enabled` from settings. When disabled or `langfuse`
    package is not installed, returns None — caller should treat None as
    "no observability" and not add to callbacks list.

    Returns:
        Configured handler when enabled+importable+credentials-resolved,
        else None.
    """
    if not is_langfuse_enabled():
        return None

    try:
        from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler
    except ImportError as e:
        logger.warning(f"[LANGFUSE] callback module import failed: {e}")
        return None

    handler = LangfuseCallbackHandler(
        enabled=True,
        user_id=user_id,
        session_id=session_id,
    )

    if not getattr(handler, "_enabled", False):
        # Handler self-disabled (missing creds / langfuse not installed)
        logger.info("[LANGFUSE] handler self-disabled — see preceding warning")
        return None

    return handler


def emit_observation(
    name: str,
    *,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    flush: bool = True,
) -> None:
    """Эмитит одну Langfuse observation для standalone Python хуков.

    Pattern: `doneyli/claude-code-langfuse-template` (roadmap §5c.4).
    Graceful: ImportError / network / config errors — log + return (никогда не raise).
    Args см. cache `langfuse-standalone-spans-2026.md`.
    """
    if not is_langfuse_enabled():
        return
    try:
        from langfuse import Langfuse
    except ImportError:
        logger.debug("[LANGFUSE] langfuse package not installed (emit_observation skipped)")
        return
    try:
        from src.pdf_framework.config import get_settings
        obs = get_settings().observability
        if not (obs.langfuse_public_key and obs.langfuse_secret_key):
            return
        client = Langfuse(
            public_key=obs.langfuse_public_key,
            secret_key=obs.langfuse_secret_key,
            host=obs.langfuse_host or "https://cloud.langfuse.com",
        )
        meta: dict[str, Any] = {}
        if metadata:
            meta.update(metadata)
        if session_id is not None:
            meta["session_id"] = session_id
        if user_id is not None:
            meta["user_id"] = user_id
        span = client.start_observation(name=name, as_type="span", input=input)
        try:
            if output is not None or meta:
                span.update(output=output, metadata=meta if meta else None)
        finally:
            span.end()
        if flush:
            client.flush()
    except Exception:
        logger.debug("[LANGFUSE] emit_observation failed (suppressed)", exc_info=True)
