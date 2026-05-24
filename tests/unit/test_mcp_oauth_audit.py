"""Tests for src.shared.mcp_oauth.audit — audit event emission."""

import base64
import hashlib
import secrets

import pytest

from src.shared.mcp_oauth import (
    AuditedOAuth2Service,
    OAuth2Store,
    OAuthAuditEvent,
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
def events() -> list[OAuthAuditEvent]:
    return []


@pytest.fixture
def service(store: OAuth2Store, events: list[OAuthAuditEvent]) -> AuditedOAuth2Service:
    return AuditedOAuth2Service(store, audit_emit=events.append)


class TestEventModel:
    def test_event_to_dict_iso_timestamp(self):
        e = OAuthAuditEvent(event_type="code_issued", client_id="abc")
        d = e.to_dict()
        assert d["event_type"] == "code_issued"
        assert d["client_id"] == "abc"
        assert isinstance(d["timestamp"], str)
        assert "T" in d["timestamp"]

    def test_event_defaults_success_true(self):
        e = OAuthAuditEvent(event_type="token_validated")
        assert e.success is True
        assert e.failure_reason is None


class TestSuccessPath:
    @pytest.mark.asyncio
    async def test_code_issued_emitted(self, service, events):
        _, challenge = _pkce_pair()
        await service.generate_authorization_code(
            client_id="cli",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        assert any(e.event_type == "code_issued" and e.client_id == "cli" for e in events)

    @pytest.mark.asyncio
    async def test_full_flow_emits_5_event_types(self, service, events):
        verifier, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            client_id="cli",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        result = await service.exchange_code_for_tokens(code, "http://localhost/cb", verifier)
        access, _, _, refresh = result
        await service.refresh_tokens(refresh)
        await service.validate_access_token(access)

        types = [e.event_type for e in events]
        assert "code_issued" in types
        assert "token_exchanged" in types
        assert "token_refreshed" in types
        assert "token_validated" in types
        assert all(e.success for e in events)


class TestFailurePath:
    @pytest.mark.asyncio
    async def test_invalid_token_emits_rejected(self, service, events):
        await service.validate_access_token("garbage")
        rejected = [e for e in events if e.event_type == "token_rejected"]
        assert len(rejected) == 1
        assert rejected[0].success is False
        assert rejected[0].failure_reason == "invalid_or_expired_token"

    @pytest.mark.asyncio
    async def test_invalid_pkce_emits_token_exchanged_failure(self, service, events):
        _, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            client_id="cli",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        wrong_verifier = secrets.token_urlsafe(32)
        result = await service.exchange_code_for_tokens(code, "http://localhost/cb", wrong_verifier)
        assert result is None

        failures = [e for e in events if e.event_type == "token_exchanged" and not e.success]
        assert len(failures) == 1
        assert failures[0].failure_reason == "invalid_code_or_pkce_or_redirect"

    @pytest.mark.asyncio
    async def test_invalid_refresh_emits_refresh_failure(self, service, events):
        result = await service.refresh_tokens("garbage_refresh")
        assert result is None
        failures = [e for e in events if e.event_type == "token_refreshed" and not e.success]
        assert len(failures) == 1
        assert failures[0].failure_reason == "invalid_or_expired_refresh"


class TestEmitterRobustness:
    @pytest.mark.asyncio
    async def test_emitter_exception_swallowed(self, store):
        def bad_sink(_event: OAuthAuditEvent) -> None:
            raise RuntimeError("sink failure should not break auth")

        service = AuditedOAuth2Service(store, audit_emit=bad_sink)
        _, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            client_id="cli",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        assert code  # auth flow completes despite sink failure

    @pytest.mark.asyncio
    async def test_default_noop_emitter(self, store):
        service = AuditedOAuth2Service(store)  # no audit_emit
        _, challenge = _pkce_pair()
        code = await service.generate_authorization_code(
            client_id="cli",
            redirect_uri="http://localhost/cb",
            code_challenge=challenge,
        )
        assert code  # works without emitter
