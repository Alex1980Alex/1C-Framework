"""Tests for src.shared.mcp_oauth.fastapi router + dependency."""

import base64
import hashlib
import secrets
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.shared.mcp_oauth import OAuth2Service, OAuth2Store
from src.shared.mcp_oauth.fastapi import build_oauth_router, require_oauth


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


@pytest.fixture
def app_enabled() -> FastAPI:
    app = FastAPI()
    store = OAuth2Store()
    service = OAuth2Service(store)
    app.state.oauth_service = service
    app.state.oauth_enabled = True
    app.include_router(build_oauth_router())

    @app.get("/protected")
    async def protected(user: dict = Depends(require_oauth)):
        return {"user": user}

    return app


@pytest.fixture
def app_disabled() -> FastAPI:
    app = FastAPI()
    app.state.oauth_enabled = False
    app.include_router(build_oauth_router())

    @app.get("/protected")
    async def protected(user: dict = Depends(require_oauth)):
        return {"user": user}

    return app


class TestPRMMetadata:
    def test_prm_document_has_required_fields(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.get("/.well-known/oauth-protected-resource")
            assert r.status_code == 200
            data = r.json()
            assert "resource" in data
            assert data["authorization_endpoint"].endswith("/authorize")
            assert data["token_endpoint"].endswith("/token")
            assert "S256" in data["code_challenge_methods_supported"]

    def test_authz_server_metadata(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.get("/.well-known/oauth-authorization-server")
            assert r.status_code == 200
            data = r.json()
            assert data["grant_types_supported"] == ["authorization_code", "refresh_token"]
            assert data["code_challenge_methods_supported"] == ["S256"]


class TestAuthorizeFlow:
    def test_authorize_redirects_with_code(self, app_enabled):
        _, challenge = _pkce_pair()
        with TestClient(app_enabled) as cli:
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                },
                follow_redirects=False,
            )
            assert r.status_code == 302
            location = r.headers["location"]
            assert location.startswith("http://localhost/cb")
            params = parse_qs(urlparse(location).query)
            assert "code" in params

    def test_authorize_preserves_state(self, app_enabled):
        _, challenge = _pkce_pair()
        with TestClient(app_enabled) as cli:
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                    "state": "xyz123",
                },
                follow_redirects=False,
            )
            params = parse_qs(urlparse(r.headers["location"]).query)
            assert params["state"] == ["xyz123"]

    def test_authorize_rejects_plain_pkce(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": "abc",
                    "code_challenge_method": "plain",
                },
                follow_redirects=False,
            )
            assert r.status_code == 400


class TestTokenExchange:
    def test_full_authorization_code_flow(self, app_enabled):
        verifier, challenge = _pkce_pair()
        with TestClient(app_enabled) as cli:
            # Step 1: get code
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                },
                follow_redirects=False,
            )
            code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]

            # Step 2: exchange
            r = cli.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost/cb",
                    "code_verifier": verifier,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data["token_type"] == "Bearer"
            assert data["access_token"]
            assert data["refresh_token"]

    def test_refresh_grant_rotates_tokens(self, app_enabled):
        verifier, challenge = _pkce_pair()
        with TestClient(app_enabled) as cli:
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                },
                follow_redirects=False,
            )
            code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
            tokens = cli.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost/cb",
                    "code_verifier": verifier,
                },
            ).json()

            r = cli.post(
                "/token",
                data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
            )
            assert r.status_code == 200
            new_tokens = r.json()
            assert new_tokens["refresh_token"] != tokens["refresh_token"]

    def test_token_unsupported_grant_type(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.post("/token", data={"grant_type": "client_credentials"})
            assert r.status_code == 400

    def test_token_invalid_grant_returns_400(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "garbage",
                    "redirect_uri": "http://localhost/cb",
                    "code_verifier": "verifier",
                },
            )
            assert r.status_code == 400
            assert r.json()["error"] == "invalid_grant"


class TestRequireOAuthDependency:
    def test_missing_bearer_returns_401(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.get("/protected")
            assert r.status_code == 401
            assert "Bearer" in r.headers.get("www-authenticate", "")

    def test_invalid_token_returns_401(self, app_enabled):
        with TestClient(app_enabled) as cli:
            r = cli.get("/protected", headers={"Authorization": "Bearer garbage"})
            assert r.status_code == 401

    def test_valid_token_allows_request(self, app_enabled):
        verifier, challenge = _pkce_pair()
        with TestClient(app_enabled) as cli:
            r = cli.get(
                "/authorize",
                params={
                    "client_id": "cli",
                    "redirect_uri": "http://localhost/cb",
                    "code_challenge": challenge,
                },
                follow_redirects=False,
            )
            code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
            tokens = cli.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost/cb",
                    "code_verifier": verifier,
                },
            ).json()

            r = cli.get(
                "/protected",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            assert r.status_code == 200
            assert r.json()["user"]["client_id"] == "cli"

    def test_feature_flag_disabled_bypasses_auth(self, app_disabled):
        """With oauth_enabled=False, /protected lets requests through without token."""
        with TestClient(app_disabled) as cli:
            r = cli.get("/protected")
            assert r.status_code == 200
            assert r.json()["user"] == {}
