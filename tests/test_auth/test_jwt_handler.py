"""Tests for JWT token handling (Phase 12.3)."""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from src.api.auth.jwt_handler import JWTHandler, TokenPayload, get_jwt_handler


# ---------------------------------------------------------------------------
# JWTHandler init
# ---------------------------------------------------------------------------

class TestJWTHandlerInit:
    def test_default_parameters(self):
        handler = JWTHandler(secret="test-secret")
        assert handler._secret == "test-secret"
        assert handler._algorithm == "HS256"
        assert handler._expire_hours == 24

    def test_custom_parameters(self):
        handler = JWTHandler(secret="s", algorithm="HS512", expire_hours=48)
        assert handler._algorithm == "HS512"
        assert handler._expire_hours == 48


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

class TestCreateToken:
    def setup_method(self):
        self.handler = JWTHandler(secret="test-secret-key-123")

    def test_creates_string_token(self):
        token = self.handler.create_token("tenant_a")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_default_role_is_viewer(self):
        token = self.handler.create_token("tenant_a")
        payload = self.handler.verify_token(token)
        assert payload is not None
        assert payload.role == "viewer"

    def test_custom_role(self):
        for role in ("viewer", "editor", "admin"):
            token = self.handler.create_token("t", role=role)
            payload = self.handler.verify_token(token)
            assert payload.role == role

    def test_tenant_id_preserved(self):
        token = self.handler.create_token("my-org-123")
        payload = self.handler.verify_token(token)
        assert payload.tenant_id == "my-org-123"

    def test_different_tenants_get_different_tokens(self):
        t1 = self.handler.create_token("a")
        t2 = self.handler.create_token("b")
        assert t1 != t2

    def test_expiration_is_set(self):
        token = self.handler.create_token("t")
        payload = self.handler.verify_token(token)
        assert payload.exp > datetime.now(timezone.utc)

    def test_iat_is_set(self):
        token = self.handler.create_token("t")
        payload = self.handler.verify_token(token)
        # iat should be roughly now
        diff = abs((datetime.now(timezone.utc) - payload.iat).total_seconds())
        assert diff < 5


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

class TestVerifyToken:
    def setup_method(self):
        self.handler = JWTHandler(secret="verify-secret", expire_hours=1)

    def test_valid_token(self):
        token = self.handler.create_token("t", "admin")
        payload = self.handler.verify_token(token)
        assert payload is not None
        assert payload.tenant_id == "t"
        assert payload.role == "admin"

    def test_returns_token_payload_type(self):
        token = self.handler.create_token("t")
        payload = self.handler.verify_token(token)
        assert isinstance(payload, TokenPayload)

    def test_invalid_token_returns_none(self):
        result = self.handler.verify_token("not-a-jwt-token")
        assert result is None

    def test_wrong_secret_returns_none(self):
        token = self.handler.create_token("t")
        other_handler = JWTHandler(secret="different-secret")
        assert other_handler.verify_token(token) is None

    def test_expired_token_returns_none(self):
        handler = JWTHandler(secret="exp-secret", expire_hours=0)
        # Create a token that expires immediately
        import jwt as pyjwt

        now = datetime.now(timezone.utc)
        payload = {
            "tenant_id": "t",
            "role": "viewer",
            "exp": now - timedelta(seconds=10),
            "iat": now - timedelta(hours=1),
        }
        token = pyjwt.encode(payload, "exp-secret", algorithm="HS256")
        assert handler.verify_token(token) is None

    def test_empty_token_returns_none(self):
        assert self.handler.verify_token("") is None

    def test_tampered_token_returns_none(self):
        token = self.handler.create_token("t")
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        assert self.handler.verify_token(tampered) is None

    def test_missing_fields_returns_none(self):
        import jwt as pyjwt

        # Token missing role field
        now = datetime.now(timezone.utc)
        payload = {
            "tenant_id": "t",
            "exp": now + timedelta(hours=1),
            "iat": now,
        }
        token = pyjwt.encode(payload, "verify-secret", algorithm="HS256")
        assert self.handler.verify_token(token) is None


# ---------------------------------------------------------------------------
# extract_tenant_id
# ---------------------------------------------------------------------------

class TestExtractTenantId:
    def setup_method(self):
        self.handler = JWTHandler(secret="extract-secret")

    def test_extracts_tenant_id(self):
        token = self.handler.create_token("org-42")
        assert self.handler.extract_tenant_id(token) == "org-42"

    def test_invalid_token_returns_none(self):
        assert self.handler.extract_tenant_id("bad-token") is None


# ---------------------------------------------------------------------------
# get_default_token
# ---------------------------------------------------------------------------

class TestGetDefaultToken:
    def test_default_token_is_admin(self):
        handler = JWTHandler(secret="def-secret")
        token = handler.get_default_token()
        payload = handler.verify_token(token)
        assert payload.tenant_id == "default"
        assert payload.role == "admin"


# ---------------------------------------------------------------------------
# TokenPayload model
# ---------------------------------------------------------------------------

class TestTokenPayload:
    def test_model_fields(self):
        now = datetime.now(timezone.utc)
        tp = TokenPayload(
            tenant_id="org",
            role="editor",
            exp=now + timedelta(hours=1),
            iat=now,
        )
        assert tp.tenant_id == "org"
        assert tp.role == "editor"

    def test_role_validation(self):
        now = datetime.now(timezone.utc)
        # Invalid role should fail validation
        with pytest.raises(Exception):
            TokenPayload(
                tenant_id="t",
                role="superuser",
                exp=now,
                iat=now,
            )


# ---------------------------------------------------------------------------
# get_jwt_handler singleton
# ---------------------------------------------------------------------------

class TestGetJWTHandler:
    def test_returns_handler(self):
        # Reset global
        import src.api.auth.jwt_handler as mod
        mod._jwt_handler = None

        handler = get_jwt_handler(secret="singleton-secret")
        assert isinstance(handler, JWTHandler)

    def test_returns_same_instance(self):
        import src.api.auth.jwt_handler as mod
        mod._jwt_handler = None

        h1 = get_jwt_handler(secret="singleton-secret-2")
        h2 = get_jwt_handler()
        assert h1 is h2

        # Cleanup
        mod._jwt_handler = None
