"""Tests for FastAPI authentication dependencies (Phase 12.3)."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.auth.jwt_handler import JWTHandler, TokenPayload


SECRET = "test-dep-secret"


@pytest.fixture
def jwt_handler():
    return JWTHandler(secret=SECRET)


@pytest.fixture
def valid_token(jwt_handler):
    return jwt_handler.create_token("test-tenant", "editor")


@pytest.fixture
def mock_settings_auth_enabled():
    """Mock settings with auth enabled."""
    settings = MagicMock()
    settings.auth.enabled = True
    settings.auth.jwt_secret = SECRET
    settings.auth.jwt_algorithm = "HS256"
    settings.auth.token_expire_hours = 24
    settings.auth.default_tenant = "default"
    return settings


@pytest.fixture
def mock_settings_auth_disabled():
    """Mock settings with auth disabled."""
    settings = MagicMock()
    settings.auth.enabled = False
    settings.auth.default_tenant = "default"
    return settings


# ---------------------------------------------------------------------------
# get_current_tenant
# ---------------------------------------------------------------------------

class TestGetCurrentTenant:
    @pytest.mark.asyncio
    async def test_auth_disabled_returns_default(self, mock_settings_auth_disabled):
        from src.api.auth.dependencies import get_current_tenant

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_disabled):
            result = await get_current_tenant(credentials=None)
            assert result == "default"

    @pytest.mark.asyncio
    async def test_auth_enabled_no_credentials_raises(self, mock_settings_auth_enabled):
        from fastapi import HTTPException
        from src.api.auth.dependencies import get_current_tenant

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant(credentials=None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_enabled_valid_token(self, mock_settings_auth_enabled, valid_token):
        from src.api.auth.dependencies import get_current_tenant

        creds = MagicMock()
        creds.credentials = valid_token

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            result = await get_current_tenant(credentials=creds)
            assert result == "test-tenant"

    @pytest.mark.asyncio
    async def test_auth_enabled_invalid_token_raises(self, mock_settings_auth_enabled):
        from fastapi import HTTPException
        from src.api.auth.dependencies import get_current_tenant

        creds = MagicMock()
        creds.credentials = "invalid-token"

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_tenant(credentials=creds)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_role
# ---------------------------------------------------------------------------

class TestGetCurrentRole:
    @pytest.mark.asyncio
    async def test_auth_disabled_returns_admin(self, mock_settings_auth_disabled):
        from src.api.auth.dependencies import get_current_role

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_disabled):
            result = await get_current_role(credentials=None)
            assert result == "admin"

    @pytest.mark.asyncio
    async def test_auth_enabled_returns_role(self, mock_settings_auth_enabled, valid_token):
        from src.api.auth.dependencies import get_current_role

        creds = MagicMock()
        creds.credentials = valid_token

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            result = await get_current_role(credentials=creds)
            assert result == "editor"

    @pytest.mark.asyncio
    async def test_auth_enabled_no_creds_raises(self, mock_settings_auth_enabled):
        from fastapi import HTTPException
        from src.api.auth.dependencies import get_current_role

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_role(credentials=None)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_token_payload
# ---------------------------------------------------------------------------

class TestGetTokenPayload:
    @pytest.mark.asyncio
    async def test_auth_disabled_returns_default_payload(self, mock_settings_auth_disabled):
        from src.api.auth.dependencies import get_token_payload

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_disabled):
            payload = await get_token_payload(credentials=None)
            assert isinstance(payload, TokenPayload)
            assert payload.tenant_id == "default"
            assert payload.role == "admin"
            assert payload.exp.year == 2099

    @pytest.mark.asyncio
    async def test_auth_enabled_valid_token(self, mock_settings_auth_enabled, valid_token):
        from src.api.auth.dependencies import get_token_payload

        creds = MagicMock()
        creds.credentials = valid_token

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            payload = await get_token_payload(credentials=creds)
            assert isinstance(payload, TokenPayload)
            assert payload.tenant_id == "test-tenant"
            assert payload.role == "editor"

    @pytest.mark.asyncio
    async def test_auth_enabled_invalid_raises(self, mock_settings_auth_enabled):
        from fastapi import HTTPException
        from src.api.auth.dependencies import get_token_payload

        creds = MagicMock()
        creds.credentials = "bad-token"

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            with pytest.raises(HTTPException) as exc_info:
                await get_token_payload(credentials=creds)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_enabled_no_creds_raises(self, mock_settings_auth_enabled):
        from fastapi import HTTPException
        from src.api.auth.dependencies import get_token_payload

        with patch("src.api.auth.dependencies.get_settings", return_value=mock_settings_auth_enabled):
            with pytest.raises(HTTPException) as exc_info:
                await get_token_payload(credentials=None)
            assert exc_info.value.status_code == 401
