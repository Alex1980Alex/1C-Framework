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
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler


def is_langfuse_enabled() -> bool:
    """Return True iff Langfuse is enabled in settings.

    Cheap check used by middleware to skip handler construction when the
    feature is disabled — avoids importing `langfuse` package at all.
    """
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

    if not handler.is_enabled:  # type: ignore[attr-defined]
        # Handler self-disabled (missing creds / langfuse not installed)
        logger.info("[LANGFUSE] handler self-disabled — see preceding warning")
        return None

    return handler
