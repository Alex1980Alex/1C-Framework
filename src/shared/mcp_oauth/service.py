"""OAuth 2.1 + PKCE service.

Generic authorization code flow with PKCE (RFC 7636),
refresh token rotation, and RFC 9728 PRM support.
"""

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from .models import AccessTokenData, AuthCodeData, RefreshTokenData
from .store import OAuth2Store

logger = logging.getLogger(__name__)


class OAuth2Service:
    """Generic OAuth 2.1 service with PKCE."""

    def __init__(
        self,
        store: OAuth2Store,
        code_ttl: int = 600,
        access_ttl: int = 3600,
        refresh_ttl: int = 86400,
    ) -> None:
        self.store = store
        self.code_ttl = code_ttl
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl

    def generate_prm_document(self, public_url: str) -> dict:
        """Generate Protected Resource Metadata (RFC 9728)."""
        url = public_url.rstrip("/")
        return {
            "resource": url,
            "authorization_servers": [url],
            "authorization_endpoint": f"{url}/authorize",
            "token_endpoint": f"{url}/token",
            "code_challenge_methods_supported": ["S256"],
        }

    async def generate_authorization_code(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        user_data: dict | None = None,
    ) -> str:
        """Generate authorization code with PKCE challenge."""
        code = secrets.token_urlsafe(32)
        exp = datetime.now() + timedelta(seconds=self.code_ttl)
        await self.store.save_auth_code(
            code,
            AuthCodeData(
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                user_data=user_data or {},
                exp=exp,
            ),
        )
        logger.debug("Auth code issued for client %s, expires %s", client_id, exp)
        return code

    @staticmethod
    def validate_pkce(code_verifier: str, code_challenge: str) -> bool:
        """Validate PKCE S256 challenge."""
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return computed == code_challenge

    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> tuple[str, str, int, str] | None:
        """Exchange authorization code for access + refresh tokens.

        Returns (access_token, token_type, expires_in, refresh_token) or None.
        """
        code_data = await self.store.get_auth_code(code)
        if not code_data:
            logger.warning("Invalid or expired authorization code")
            return None

        if code_data.redirect_uri != redirect_uri:
            logger.warning("redirect_uri mismatch")
            return None

        if not self.validate_pkce(code_verifier, code_data.code_challenge):
            logger.warning("PKCE validation failed")
            return None

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        now = datetime.now()

        await self.store.save_access_token(
            access_token,
            AccessTokenData(
                client_id=code_data.client_id,
                user_data=code_data.user_data,
                exp=now + timedelta(seconds=self.access_ttl),
            ),
        )
        await self.store.save_refresh_token(
            refresh_token,
            RefreshTokenData(
                client_id=code_data.client_id,
                user_data=code_data.user_data,
                exp=now + timedelta(seconds=self.refresh_ttl),
                rotation_counter=0,
            ),
        )

        logger.debug("Tokens issued for client %s", code_data.client_id)
        return (access_token, "Bearer", self.access_ttl, refresh_token)

    async def refresh_tokens(
        self, refresh_token: str
    ) -> tuple[str, str, int, str] | None:
        """Rotate refresh token, issue new access + refresh pair."""
        data = await self.store.get_refresh_token(refresh_token)
        if not data:
            logger.warning("Invalid or expired refresh token")
            return None

        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        now = datetime.now()

        await self.store.save_access_token(
            new_access,
            AccessTokenData(
                client_id=data.client_id,
                user_data=data.user_data,
                exp=now + timedelta(seconds=self.access_ttl),
            ),
        )
        await self.store.save_refresh_token(
            new_refresh,
            RefreshTokenData(
                client_id=data.client_id,
                user_data=data.user_data,
                exp=now + timedelta(seconds=self.refresh_ttl),
                rotation_counter=data.rotation_counter + 1,
            ),
        )

        logger.debug(
            "Tokens refreshed for client %s (rotation #%d)",
            data.client_id, data.rotation_counter + 1,
        )
        return (new_access, "Bearer", self.access_ttl, new_refresh)

    async def validate_access_token(self, token: str) -> dict | None:
        """Validate access token, return user_data or None."""
        data = await self.store.get_access_token(token)
        if not data:
            return None
        return {"client_id": data.client_id, **data.user_data}
