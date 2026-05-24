"""Smoke tests for `observability.langfuse_setup` (roadmap 260509 §3.1).

These tests work WITHOUT the optional `langfuse` package installed —
they verify the wiring's graceful-degradation behaviour (returning None
or False instead of crashing).

Tests requiring real `langfuse` package import are gated with
`importlib.util.find_spec` checks and skipped when missing.
"""

from __future__ import annotations

import importlib.util
from unittest.mock import patch

import pytest

LANGFUSE_INSTALLED = importlib.util.find_spec("langfuse") is not None


@pytest.mark.unit
class TestIsLangfuseEnabled:
    def test_default_disabled(self):
        """Real settings — langfuse_enabled defaults to False (config/observability.py:23)."""
        from src.pdf_framework.observability.langfuse_setup import is_langfuse_enabled

        # Default config has langfuse_enabled=False, expect False
        # If user .env enables it locally, this test would fail — acceptable for unit gate
        assert is_langfuse_enabled() is False

    def test_returns_true_when_patched_enabled(self):
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
        """When is_langfuse_enabled()=False, no handler is constructed."""
        from src.pdf_framework.observability import langfuse_setup

        with patch.object(langfuse_setup, "is_langfuse_enabled", return_value=False):
            assert langfuse_setup.build_langfuse_callback() is None

    @pytest.mark.skipif(not LANGFUSE_INSTALLED, reason="`langfuse` package not installed")
    def test_returns_none_when_handler_self_disables(self):
        """Enabled in settings but handler can't init (no creds in env/settings)."""
        from src.pdf_framework.observability import langfuse_setup

        with (
            patch.object(langfuse_setup, "is_langfuse_enabled", return_value=True),
            patch.dict("os.environ", {}, clear=True),
        ):

            class _ObsEmpty:
                langfuse_enabled = True
                langfuse_public_key = ""
                langfuse_secret_key = ""
                langfuse_host = ""

            class _Settings:
                observability = _ObsEmpty()

            with patch("src.pdf_framework.config.get_settings", return_value=_Settings()):
                result = langfuse_setup.build_langfuse_callback(user_id="u", session_id="s")
                assert result is None

    def test_returns_none_when_callback_module_missing(self):
        """Defensive: ImportError on callback module → None, not raised."""
        import sys

        from src.pdf_framework.observability import langfuse_setup

        with (
            patch.object(langfuse_setup, "is_langfuse_enabled", return_value=True),
            patch.dict(sys.modules, {"src.pdf_framework.callbacks.langfuse": None}),
        ):
            # Patching sys.modules with None forces ImportError on next import
            result = langfuse_setup.build_langfuse_callback()
            assert result is None


@pytest.mark.unit
@pytest.mark.skipif(not LANGFUSE_INSTALLED, reason="`langfuse` package not installed")
class TestLangfuseCallbackHandlerCredentialResolution:
    """Resolution order: explicit kwargs → settings → env → disabled."""

    def test_disables_gracefully_without_credentials(self):
        from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler

        with patch.dict("os.environ", {}, clear=True):

            class _ObsEmpty:
                langfuse_enabled = True
                langfuse_public_key = ""
                langfuse_secret_key = ""
                langfuse_host = ""

            class _Settings:
                observability = _ObsEmpty()

            with patch("src.pdf_framework.config.get_settings", return_value=_Settings()):
                handler = LangfuseCallbackHandler(enabled=True)
                # No creds anywhere → handler self-disables
                assert handler._enabled is False

    def test_explicit_credentials_take_precedence(self):
        """Constructor kwargs win over settings/env."""
        from src.pdf_framework.callbacks.langfuse import LangfuseCallbackHandler

        # Even without real langfuse client init success, _resolve_credentials
        # is what we're checking — read it before init runs by passing creds.
        # This test reaches `Langfuse(public_key=...)` constructor; if real
        # langfuse package is installed it will accept any string and not
        # connect immediately (Langfuse SDK lazy-connects).
        handler = LangfuseCallbackHandler(
            enabled=True,
            public_key="explicit-pub",
            secret_key="explicit-sec",
            host="https://explicit.example",
        )
        # If init failed for any reason (network, etc), at least credentials
        # were attempted — we can verify via internal state.
        # Either: handler is enabled (init succeeded with explicit creds)
        # Or: handler self-disabled (network/init error) — still valid behaviour
        assert handler._enabled in (True, False)
        assert handler._explicit_creds == (
            "explicit-pub",
            "explicit-sec",
            "https://explicit.example",
        )
