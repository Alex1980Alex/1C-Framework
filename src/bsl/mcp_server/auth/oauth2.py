"""BSL MCP Server OAuth2 — backward-compat wrapper around shared module.

Preserves the original login/password API while delegating to
src.shared.mcp_oauth (generic OAuth2Service).
"""

import logging

from src.shared.mcp_oauth.models import (
    AccessTokenData as _AccessTokenData,
    AuthCodeData as _AuthCodeData,
    RefreshTokenData as _RefreshTokenData,
)
from src.shared.mcp_oauth.service import OAuth2Service as _OAuth2Service
from src.shared.mcp_oauth.store import InMemoryBackend, OAuth2Store

logger = logging.getLogger(__name__)

# Re-export dataclasses with original field names for backward compat.
# Old code used login/password directly; new generic uses client_id/user_data.


class AuthCodeData:
    """Backward-compat authorization code data (login/password fields)."""

    def __init__(self, login: str, password: str, redirect_uri: str,
                 code_challenge: str, exp) -> None:
        self.login = login
        self.password = password
        self.redirect_uri = redirect_uri
        self.code_challenge = code_challenge
        self.exp = exp


class AccessTokenData:
    """Backward-compat access token data (login/password fields)."""

    def __init__(self, login: str, password: str, exp) -> None:
        self.login = login
        self.password = password
        self.exp = exp


class RefreshTokenData:
    """Backward-compat refresh token data (login/password fields)."""

    def __init__(self, login: str, password: str, exp, rotation_counter: int = 0) -> None:
        self.login = login
        self.password = password
        self.exp = exp
        self.rotation_counter = rotation_counter


class _BSLBackend(InMemoryBackend):
    """In-memory backend that stores login/password in user_data for BSL compat."""

    pass


class OAuth2Store:
    """In-memory OAuth2 store — backward-compat wrapper."""

    def __init__(self) -> None:
        self._store = OAuth2Store(_BSLBackend())
        # Sync dicts for code that accesses store.auth_codes etc. directly
        self.auth_codes: dict[str, AuthCodeData] = {}
        self.access_tokens: dict[str, AccessTokenData] = {}
        self.refresh_tokens: dict[str, RefreshTokenData] = {}
        self._cleanup_task = None

    async def start_cleanup_task(self, interval: int = 60) -> None:
        await self._store.start_cleanup(interval)
        self._cleanup_task = self._store._cleanup_task

    async def stop_cleanup_task(self) -> None:
        await self._store.stop_cleanup()

    def save_auth_code(self, code: str, data: AuthCodeData) -> None:
        self.auth_codes[code] = data

    def get_auth_code(self, code: str) -> AuthCodeData | None:
        data = self.auth_codes.pop(code, None)
        if data and data.exp < __import__("datetime").datetime.now():
            return None
        return data

    def save_access_token(self, token: str, data: AccessTokenData) -> None:
        self.access_tokens[token] = data

    def get_access_token(self, token: str) -> AccessTokenData | None:
        data = self.access_tokens.get(token)
        if data and data.exp < __import__("datetime").datetime.now():
            del self.access_tokens[token]
            return None
        return data

    def save_refresh_token(self, token: str, data: RefreshTokenData) -> None:
        self.refresh_tokens[token] = data

    def get_refresh_token(self, token: str) -> RefreshTokenData | None:
        data = self.refresh_tokens.pop(token, None)
        if data and data.exp < __import__("datetime").datetime.now():
            return None
        return data


class OAuth2Service:
    """OAuth2 service — backward-compat wrapper using login/password API."""

    def __init__(self, store: OAuth2Store, code_ttl: int = 120,
                 access_ttl: int = 3600, refresh_ttl: int = 1209600) -> None:
        self.store = store
        self.code_ttl = code_ttl
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl

    def generate_prm_document(self, public_url: str) -> dict:
        url = public_url.rstrip("/")
        return {
            "resource": url,
            "authorization_servers": [url],
            "authorization_endpoint": f"{url}/authorize",
            "token_endpoint": f"{url}/token",
            "code_challenge_methods_supported": ["S256"],
        }

    def generate_authorization_code(self, login: str, password: str,
                                    redirect_uri: str, code_challenge: str) -> str:
        import secrets
        from datetime import datetime, timedelta
        code = secrets.token_urlsafe(32)
        exp = datetime.now() + timedelta(seconds=self.code_ttl)
        self.store.save_auth_code(code, AuthCodeData(
            login=login, password=password,
            redirect_uri=redirect_uri, code_challenge=code_challenge, exp=exp,
        ))
        return code

    @staticmethod
    def validate_pkce(code_verifier: str, code_challenge: str) -> bool:
        import base64, hashlib
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return computed == code_challenge

    def exchange_code_for_tokens(self, code: str, redirect_uri: str,
                                 code_verifier: str) -> tuple[str, str, int, str] | None:
        import secrets
        from datetime import datetime, timedelta
        code_data = self.store.get_auth_code(code)
        if not code_data:
            return None
        if code_data.redirect_uri != redirect_uri:
            return None
        if not self.validate_pkce(code_verifier, code_data.code_challenge):
            return None

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        now = datetime.now()
        self.store.save_access_token(access_token, AccessTokenData(
            login=code_data.login, password=code_data.password,
            exp=now + timedelta(seconds=self.access_ttl),
        ))
        self.store.save_refresh_token(refresh_token, RefreshTokenData(
            login=code_data.login, password=code_data.password,
            exp=now + timedelta(seconds=self.refresh_ttl), rotation_counter=0,
        ))
        return (access_token, "Bearer", self.access_ttl, refresh_token)

    def refresh_tokens(self, refresh_token: str) -> tuple[str, str, int, str] | None:
        import secrets
        from datetime import datetime, timedelta
        data = self.store.get_refresh_token(refresh_token)
        if not data:
            return None
        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        now = datetime.now()
        self.store.save_access_token(new_access, AccessTokenData(
            login=data.login, password=data.password,
            exp=now + timedelta(seconds=self.access_ttl),
        ))
        self.store.save_refresh_token(new_refresh, RefreshTokenData(
            login=data.login, password=data.password,
            exp=now + timedelta(seconds=self.refresh_ttl),
            rotation_counter=data.rotation_counter + 1,
        ))
        return (new_access, "Bearer", self.access_ttl, new_refresh)

    def validate_access_token(self, token: str) -> tuple[str, str] | None:
        data = self.store.get_access_token(token)
        if not data:
            return None
        return (data.login, data.password)
