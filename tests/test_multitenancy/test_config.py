"""Tests for Phase 12 configuration (AuthSettings)."""

import pytest

from src.pdf_framework.config import AuthSettings, Settings


# ---------------------------------------------------------------------------
# AuthSettings
# ---------------------------------------------------------------------------

class TestAuthSettings:
    def test_defaults(self):
        s = AuthSettings()
        assert s.enabled is False
        assert s.jwt_secret == "change-me-in-production"
        assert s.jwt_algorithm == "HS256"
        assert s.token_expire_hours == 24
        assert s.default_tenant == "default"

    def test_enabled_flag(self):
        s = AuthSettings(enabled=True)
        assert s.enabled is True

    def test_custom_secret(self):
        s = AuthSettings(jwt_secret="my-secret-key")
        assert s.jwt_secret == "my-secret-key"

    def test_custom_algorithm(self):
        s = AuthSettings(jwt_algorithm="HS512")
        assert s.jwt_algorithm == "HS512"

    def test_custom_expire_hours(self):
        s = AuthSettings(token_expire_hours=48)
        assert s.token_expire_hours == 48

    def test_custom_default_tenant(self):
        s = AuthSettings(default_tenant="my-org")
        assert s.default_tenant == "my-org"


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------

class TestSettingsIntegration:
    def test_auth_in_settings(self):
        s = Settings()
        assert hasattr(s, "auth")
        assert isinstance(s.auth, AuthSettings)

    def test_auth_defaults_in_root(self):
        s = Settings()
        assert s.auth.enabled is False
        assert s.auth.jwt_algorithm == "HS256"

    def test_all_phase_12_settings_present(self):
        """Verify Phase 12 added AuthSettings to root Settings."""
        s = Settings()
        # Auth settings should exist
        assert hasattr(s, "auth")
        assert hasattr(s.auth, "enabled")
        assert hasattr(s.auth, "jwt_secret")
        assert hasattr(s.auth, "jwt_algorithm")
        assert hasattr(s.auth, "token_expire_hours")
        assert hasattr(s.auth, "default_tenant")
