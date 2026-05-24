"""Tests for BSL OAuth2 wrapper over src.shared.mcp_oauth."""

import base64
import hashlib
import secrets

import pytest

from src.bsl.mcp_server.auth.oauth2 import (
    AccessTokenData,
    AuthCodeData,
    OAuth2Service,
    OAuth2Store,
    RefreshTokenData,
)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@pytest.fixture
def store() -> OAuth2Store:
    return OAuth2Store()


@pytest.fixture
def service(store: OAuth2Store) -> OAuth2Service:
    return OAuth2Service(store, code_ttl=600, access_ttl=3600, refresh_ttl=86400)


class TestLegacyDataclasses:
    """Dataclass shape preserved for any direct importers in BSL code."""

    def test_auth_code_data_has_login_password_fields(self):
        from datetime import datetime, timedelta

        data = AuthCodeData(
            login="alex",
            password="s3cret",
            redirect_uri="http://localhost/cb",
            code_challenge="abc123",
            exp=datetime.now() + timedelta(minutes=10),
        )
        assert data.login == "alex"
        assert data.password == "s3cret"

    def test_access_token_data_has_login_password_fields(self):
        from datetime import datetime, timedelta

        data = AccessTokenData(login="u", password="p", exp=datetime.now() + timedelta(hours=1))
        assert data.login == "u" and data.password == "p"

    def test_refresh_token_rotation_counter_default_zero(self):
        from datetime import datetime, timedelta

        data = RefreshTokenData(login="u", password="p", exp=datetime.now() + timedelta(days=1))
        assert data.rotation_counter == 0


class TestStoreAliases:
    """Legacy `_task` suffix methods delegate to generic shared API."""

    @pytest.mark.asyncio
    async def test_start_stop_cleanup_task_aliases(self, store: OAuth2Store):
        await store.start_cleanup_task(interval=60)
        assert store._cleanup_task is not None
        await store.stop_cleanup_task()


class TestServiceFlow:
    """End-to-end PKCE flow with login/password user_data packing."""

    @pytest.mark.asyncio
    async def test_authorize_then_exchange_returns_tokens(self, service: OAuth2Service):
        verifier, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            login="alex",
            password="s3cret",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        assert code

        result = await service.exchange_code_for_tokens(code, "http://localhost/cb", verifier)
        assert result is not None
        access, ttype, expires_in, refresh = result
        assert ttype == "Bearer"
        assert expires_in == 3600
        assert access and refresh

    @pytest.mark.asyncio
    async def test_validate_returns_login_password_tuple(self, service: OAuth2Service):
        verifier, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            login="alex",
            password="s3cret",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        access, _, _, _ = await service.exchange_code_for_tokens(
            code, "http://localhost/cb", verifier
        )

        creds = await service.validate_access_token(access)
        assert creds == ("alex", "s3cret")

    @pytest.mark.asyncio
    async def test_validate_returns_none_for_invalid_token(self, service: OAuth2Service):
        assert await service.validate_access_token("garbage") is None

    @pytest.mark.asyncio
    async def test_refresh_rotation_preserves_credentials(self, service: OAuth2Service):
        verifier, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            login="alex",
            password="s3cret",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        _, _, _, refresh = await service.exchange_code_for_tokens(
            code, "http://localhost/cb", verifier
        )

        rotated = await service.refresh_tokens(refresh)
        assert rotated is not None
        new_access, _, _, new_refresh = rotated
        assert new_refresh != refresh  # rotation enforced

        creds = await service.validate_access_token(new_access)
        assert creds == ("alex", "s3cret")  # credentials survived rotation

    @pytest.mark.asyncio
    async def test_prm_document_endpoints(self, service: OAuth2Service):
        prm = service.generate_prm_document("http://example.com/")
        assert prm["resource"] == "http://example.com"
        assert prm["authorization_endpoint"] == "http://example.com/authorize"
        assert prm["token_endpoint"] == "http://example.com/token"
        assert "S256" in prm["code_challenge_methods_supported"]
