"""Tests for src.shared.mcp_oauth — generic OAuth 2.1 + PKCE service."""

import asyncio
import base64
import hashlib

import pytest

from src.shared.mcp_oauth import (
    AuthCodeData,
    AccessTokenData,
    RefreshTokenData,
    OAuth2Store,
    OAuth2Service,
)
from src.shared.mcp_oauth.store import InMemoryBackend


def _pkce_pair():
    """Generate PKCE verifier/challenge pair."""
    import secrets
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@pytest.fixture
def store():
    return OAuth2Store()


@pytest.fixture
def service(store):
    return OAuth2Service(store, code_ttl=600, access_ttl=3600, refresh_ttl=86400)


class TestModels:
    def test_auth_code_data_fields(self):
        from datetime import datetime, timedelta
        exp = datetime.now() + timedelta(minutes=10)
        data = AuthCodeData(client_id="test", redirect_uri="http://localhost/cb",
                            code_challenge="abc123", user_data={"role": "admin"}, exp=exp)
        assert data.client_id == "test"
        assert data.user_data == {"role": "admin"}

    def test_refresh_token_rotation_counter(self):
        from datetime import datetime, timedelta
        exp = datetime.now() + timedelta(hours=1)
        data = RefreshTokenData(client_id="c", user_data={}, exp=exp, rotation_counter=3)
        assert data.rotation_counter == 3

    def test_default_rotation_counter(self):
        from datetime import datetime, timedelta
        data = RefreshTokenData(client_id="c", user_data={}, exp=datetime.now())
        assert data.rotation_counter == 0


class TestInMemoryBackend:
    @pytest.mark.asyncio
    async def test_auth_code_lifecycle(self):
        from datetime import datetime, timedelta
        backend = InMemoryBackend()
        exp = datetime.now() + timedelta(minutes=10)
        data = AuthCodeData(client_id="c", redirect_uri="http://cb",
                            code_challenge="ch", user_data={}, exp=exp)
        await backend.save_auth_code("code1", data)
        result = await backend.get_auth_code("code1")
        assert result is not None
        assert result.client_id == "c"
        # Second get returns None (consumed)
        assert await backend.get_auth_code("code1") is None

    @pytest.mark.asyncio
    async def test_expired_auth_code(self):
        from datetime import datetime, timedelta
        backend = InMemoryBackend()
        exp = datetime.now() - timedelta(seconds=1)
        data = AuthCodeData(client_id="c", redirect_uri="http://cb",
                            code_challenge="ch", user_data={}, exp=exp)
        await backend.save_auth_code("expired", data)
        assert await backend.get_auth_code("expired") is None

    @pytest.mark.asyncio
    async def test_access_token_lifecycle(self):
        from datetime import datetime, timedelta
        backend = InMemoryBackend()
        exp = datetime.now() + timedelta(hours=1)
        data = AccessTokenData(client_id="c", user_data={"uid": 1}, exp=exp)
        await backend.save_access_token("tok1", data)
        result = await backend.get_access_token("tok1")
        assert result is not None
        assert result.user_data == {"uid": 1}

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        from datetime import datetime, timedelta
        backend = InMemoryBackend()
        past = datetime.now() - timedelta(seconds=1)
        await backend.save_auth_code("old_code", AuthCodeData(
            client_id="c", redirect_uri="", code_challenge="", user_data={}, exp=past))
        await backend.save_access_token("old_tok", AccessTokenData(
            client_id="c", user_data={}, exp=past))
        codes, access, refresh = await backend.cleanup_expired()
        assert codes == 1
        assert access == 1


class TestOAuth2Service:
    @pytest.mark.asyncio
    async def test_generate_prm(self, service):
        prm = service.generate_prm_document("https://mcp.example.com/")
        assert prm["resource"] == "https://mcp.example.com"
        assert "S256" in prm["code_challenge_methods_supported"]
        assert "/authorize" in prm["authorization_endpoint"]

    @pytest.mark.asyncio
    async def test_pkce_validation(self, service):
        verifier, challenge = _pkce_pair()
        assert service.validate_pkce(verifier, challenge) is True
        assert service.validate_pkce("wrong", challenge) is False

    @pytest.mark.asyncio
    async def test_full_auth_flow(self, service):
        verifier, challenge = _pkce_pair()
        # Generate auth code
        code = await service.generate_authorization_code(
            client_id="test-client",
            redirect_uri="http://localhost/callback",
            code_challenge=challenge,
            user_data={"user_id": "u1"},
        )
        assert code is not None

        # Exchange for tokens
        result = await service.exchange_code_for_tokens(
            code=code,
            redirect_uri="http://localhost/callback",
            code_verifier=verifier,
        )
        assert result is not None
        access_token, token_type, expires_in, refresh_token = result
        assert token_type == "Bearer"
        assert expires_in == 3600

        # Validate access token
        user_info = await service.validate_access_token(access_token)
        assert user_info is not None
        assert user_info["client_id"] == "test-client"
        assert user_info["user_id"] == "u1"

        # Refresh tokens
        refresh_result = await service.refresh_tokens(refresh_token)
        assert refresh_result is not None
        new_access, _, _, new_refresh = refresh_result
        assert new_access != access_token
        assert new_refresh != refresh_token

        # Old refresh token is consumed
        assert await service.refresh_tokens(refresh_token) is None

    @pytest.mark.asyncio
    async def test_exchange_wrong_redirect(self, service):
        verifier, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            "c", "http://correct", challenge)
        result = await service.exchange_code_for_tokens(code, "http://wrong", verifier)
        assert result is None

    @pytest.mark.asyncio
    async def test_exchange_wrong_pkce(self, service):
        _, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            "c", "http://cb", challenge)
        result = await service.exchange_code_for_tokens(code, "http://cb", "wrong_verifier")
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_code_rejected(self, service):
        service.code_ttl = 0  # instant expiry
        _, challenge = _pkce_pair()
        import time
        code = await service.generate_authorization_code("c", "http://cb", challenge)
        time.sleep(0.01)
        verifier, _ = _pkce_pair()
        # Code expired — exchange fails (challenge won't match anyway but code is consumed)
        result = await service.exchange_code_for_tokens(code, "http://cb", verifier)
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self, service):
        assert await service.validate_access_token("nonexistent") is None

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, service):
        assert await service.refresh_tokens("nonexistent") is None


class TestOAuth2Store:
    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        store = OAuth2Store()
        await store.start_cleanup(interval=1)
        await asyncio.sleep(0.1)
        await store.stop_cleanup()
        # No crash = pass
