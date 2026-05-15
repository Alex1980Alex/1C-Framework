"""BSL-specific OAuth2 wrapper preserving login/password credential model.

Thin async adapter over `src.shared.mcp_oauth`:
- Packs (login, password) into `user_data` dict on `generate_authorization_code`
- Unpacks back to `(login, password)` tuple on `validate_access_token`
- Preserves legacy `start_cleanup_task` / `stop_cleanup_task` method names
- Preserves legacy dataclass shape (login/password fields) for direct importers

New code should use `src.shared.mcp_oauth` directly with arbitrary `user_data`.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.mcp_oauth import OAuth2Service as _GenericOAuth2Service
from src.shared.mcp_oauth import OAuth2Store as _GenericOAuth2Store


@dataclass
class AuthCodeData:
    """Legacy BSL auth-code shape — login/password as direct fields."""

    login: str
    password: str
    redirect_uri: str
    code_challenge: str
    exp: datetime


@dataclass
class AccessTokenData:
    """Legacy BSL access-token shape."""

    login: str
    password: str
    exp: datetime


@dataclass
class RefreshTokenData:
    """Legacy BSL refresh-token shape with rotation counter."""

    login: str
    password: str
    exp: datetime
    rotation_counter: int = 0


class OAuth2Store(_GenericOAuth2Store):
    """BSL store — adds legacy `_task` suffix aliases."""

    async def start_cleanup_task(self, interval: int = 60) -> None:
        await self.start_cleanup(interval)

    async def stop_cleanup_task(self) -> None:
        await self.stop_cleanup()


class OAuth2Service(_GenericOAuth2Service):
    """BSL adapter: (login, password) packed into generic `user_data`."""

    async def generate_authorization_code(  # type: ignore[override]
        self,
        login: str,
        password: str,
        redirect_uri: str,
        code_challenge: str,
    ) -> str:
        return await super().generate_authorization_code(
            client_id="bsl-legacy",
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            user_data={"login": login, "password": password},
        )

    async def validate_access_token(  # type: ignore[override]
        self, token: str
    ) -> tuple[str, str] | None:
        data = await super().validate_access_token(token)
        if not data:
            return None
        return (data["login"], data["password"])
