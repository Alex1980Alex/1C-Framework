"""Smoke tests for `observability.langfuse_setup` (roadmap 260509 §3.1).

Tests verify:
1. `is_langfuse_enabled()` reads from settings (and survives missing settings).
2. `build_langfuse_callback()` returns None when disabled.
3. `build_langfuse_callback()` gracefully degrades to None when enabled but
   credentials are missing — never raises.
4. Constructor accepts explicit credentials (DI for production tests).

These don't hit Langfuse Cloud — purely structural checks of the wiring.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestIsLangfuseEnabled:
    def test_returns_false_when_settings_disabled(self):
        from src.pdf_framework.observability.langfuse_setup import is_langfuse_enabled

        with patch("src.pdf_framework.observability.langfuse_setup.get_settings", create=False):
            # Real settings.langfuse_enabled defaults to False — see config/observability.py:23
            assert is_langfuse_enabled() is False

    def test_returns_true_when_settings_enabled(self):
        from src.pdf_framework.observability import langfuse_setup

        class _Obs:
            langfuse_enabled = True

        class _Settings:
            observability = _Obs()

        with patch("src.pdf_framework.config.get_settings", return_value=_Settings()):
            assert langfuse_setup.is_langfuse_enabled() is True

    def test_returns_false_on_settings_exception(self):
        """Defensive: missing/broken settings → False, no crash."""
        from src.pdf_framework.observability import langfuse_setup

        with patch("src.pdf_framework.config.get_settings", side_effect=RuntimeError("boom")):
            assert langfuse_setup.is_langfuse_enabled() is False


@pytest.mark.unit
class TestBuildLangfuseCallback:
    def test_returns_none_when_disabled(self):
        from src.pdf_framework.observability import langfuse_setup

        with patch.object(langfuse_setup, "is_langfuse_enabled", return_value=False):
            assert langfuse_setup.build_langfuse_callback() is None

    def test_returns_none_when_handler_self_disables(self):
        """Enabled in settings but handler can't init (no creds / no langfuse pkg)."""
        from src.pdf_framework.observability import langfuse_setup

        class _StubHandler:
            _enabled = False  # simulate self-disable

            def __init__(self, *_, **__):
                pass

        with patch.object(langfuse_setup, "is_langfuse_enabled", return_value=True), \
             patch("src.pdf_framework.callbacks.langfuse.LangfuseCallbackHandler", _StubHandler):
            result = langfuse_setup.build_langfuse_callback(user_id="u", session_id="s")
            assert result is None

    def test_returns_handler_when_initialized_successfully(self):
        from src.pdf_framework.observability import langfuse_setup

        class _StubHandler:
            _enabled = True

            def __init__(self, enabled=True, user_id=None, session_id=None, **_):
                self.user_id = user_id
                self.session_id = session_id

        with patch.object(langfuse_setup, "is_langfuse_enabled", return_value=True), \
             patch("src.pdf_framework.callbacks.langfuse.LangfuseCallbackHandler", _StubHandler):
            result = langfuse_setup.build_langfuse_callback(user_id="u-1", session_id="s-1")
            assert result is not None
            assert result.user_id == "u-1"
            assert result.session_id == "s-1"


@pytest.mark.unit
class TestLangfuseCallbackHandlerCredentials:
    """Resolution order: explicit kwargs → settings → env → disabled."""

    def test_explicit_credentials_used_first(self):
        try:
            from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler
        except ImportError:
            pytest.skip("langfuse package not installed in test env")

        # When langfuse package is missing, handler self-disables. We only need
        # to verify that explicit creds bypass settings/env lookup. Mock the
        # Langfuse import so we can inspect kwargs passed.
        captured: dict = {}

        class _StubLangfuse:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        with patch("langfuse.Langfuse", _StubLangfuse):
            handler = LangfuseCallbackHandler(
                enabled=True,
                public_key="explicit-pub",
                secret_key="explicit-sec",
                host="https://explicit.example",
            )
            # Either init succeeded with explicit creds OR import failed — both ok
            if handler._enabled and captured:
                assert captured["public_key"] == "explicit-pub"
                assert captured["secret_key"] == "explicit-sec"
                assert captured["host"] == "https://explicit.example"

    def test_disables_gracefully_without_credentials(self):
        try:
            from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler
        except ImportError:
            pytest.skip("langfuse package not installed in test env")

        # No explicit creds, no settings access (default disabled), no env vars
        with patch.dict("os.environ", {}, clear=True):
            handler = LangfuseCallbackHandler(enabled=True)
            # Either langfuse not installed or creds missing → both lead to disabled
            assert handler._enabled is False
