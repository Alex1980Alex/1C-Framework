"""Langfuse callback handler for LangChain integration.

Migrated to the **Langfuse v4 SDK** (2026-07-04). The previous implementation
called ``client.generation()`` / ``client.span()`` — v2 methods that do **not**
exist on the v4 client, so every event raised ``AttributeError`` which the
broad ``except`` swallowed → tracing was silently dead on the installed SDK
(4.6.x).

This class now subclasses Langfuse's **native** LangChain handler
(``langfuse.langchain.CallbackHandler``), which emits correct v4
OpenTelemetry-based observations with proper span nesting. Credentials are
wired by constructing the global ``Langfuse`` client before ``super().__init__``
so the native handler discovers an authenticated client via ``get_client()``.

Backward-compatible constructor ``(enabled, user_id, session_id, public_key,
secret_key, host)`` is preserved for existing callers (``agents/rag/middleware``,
``observability/langfuse_setup.build_langfuse_callback``).

v4 behaviour notes:
  * on_llm_start / on_chain_start / on_tool_start / … are inherited from the
    native handler — the manual v2 methods were removed.
  * Missing credentials → the underlying client self-disables and all events
    become graceful no-ops (no exceptions). ``_enabled`` reflects this.
  * Per-trace ``user_id`` / ``session_id`` in v4 are attached via runnable-config
    metadata (``langfuse_user_id`` / ``langfuse_session_id``); they are stored
    here for backward-compat but not injected per-event by this shim.

Author: Claude Code
Version: 2.0.0 — Langfuse v4 migration (was Phase 46 v2 manual handler)
"""

import logging

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler as _LangfuseNativeHandler

    _LANGFUSE_IMPORTABLE = True
except ImportError:  # pragma: no cover - optional dependency
    Langfuse = None  # type: ignore[assignment,misc]
    _LangfuseNativeHandler = object  # type: ignore[assignment,misc]
    _LANGFUSE_IMPORTABLE = False


class LangfuseCallbackHandler(_LangfuseNativeHandler):
    """LangChain callback handler backed by the Langfuse v4 native handler."""

    def __init__(
        self,
        enabled: bool = True,
        user_id: str | None = None,
        session_id: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ):
        """Initialize the Langfuse v4-backed callback handler.

        Resolution order for credentials (see ``_resolve_credentials``):
          1. explicit constructor args (DI for tests)
          2. get_settings().observability.langfuse_*  (pydantic-settings, .env)
          3. os.environ.LANGFUSE_*  (legacy fallback)
          4. None → handler disabled; underlying client no-ops.
        """
        self._enabled = bool(enabled) and _LANGFUSE_IMPORTABLE
        self._user_id = user_id
        self._session_id = session_id
        self._explicit_creds = (public_key, secret_key, host)

        if not _LANGFUSE_IMPORTABLE:
            logger.warning("[LANGFUSE] langfuse not installed — handler disabled")
            return

        pub, sec, resolved_host = self._resolve_credentials()
        if self._enabled and pub and sec:
            # v4: constructing the client registers the global singleton that the
            # native LangChain handler discovers via get_client().
            Langfuse(public_key=pub, secret_key=sec, host=resolved_host)
            logger.debug("[LANGFUSE] v4 native LangChain handler initialized")
        elif self._enabled:
            logger.warning("[LANGFUSE] Missing credentials — tracing disabled (no-op)")
            self._enabled = False

        # Native handler discovers the (authenticated or self-disabled) global
        # client; when creds are absent all events become graceful no-ops.
        super().__init__()

    def _resolve_credentials(self) -> tuple[str, str, str]:
        """Resolve (public_key, secret_key, host) via DI → settings → env fallback."""
        explicit_pub, explicit_sec, explicit_host = self._explicit_creds
        public_key = explicit_pub or ""
        secret_key = explicit_sec or ""
        host = explicit_host or ""

        if not (public_key and secret_key):
            try:
                from src.pdf_framework.config import get_settings

                obs = get_settings().observability
                public_key = public_key or obs.langfuse_public_key
                secret_key = secret_key or obs.langfuse_secret_key
                host = host or obs.langfuse_host
            except Exception as e:
                logger.debug(f"[LANGFUSE] Settings resolution skipped: {e}")

        if not (public_key and secret_key):
            import os

            public_key = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY", "")
            secret_key = secret_key or os.environ.get("LANGFUSE_SECRET_KEY", "")
            host = host or os.environ.get("LANGFUSE_HOST", "")

        if not host:
            host = "https://cloud.langfuse.com"

        return public_key, secret_key, host
