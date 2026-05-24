"""OAuth2 token store with pluggable backends.

Default: in-memory dicts. Extend with SQLite/Redis by subclassing OAuth2StoreBackend.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from .models import AccessTokenData, AuthCodeData, RefreshTokenData

logger = logging.getLogger(__name__)


class OAuth2StoreBackend(ABC):
    """Abstract backend for OAuth2 token storage."""

    @abstractmethod
    async def save_auth_code(self, code: str, data: AuthCodeData) -> None: ...

    @abstractmethod
    async def get_auth_code(self, code: str) -> AuthCodeData | None: ...

    @abstractmethod
    async def save_access_token(self, token: str, data: AccessTokenData) -> None: ...

    @abstractmethod
    async def get_access_token(self, token: str) -> AccessTokenData | None: ...

    @abstractmethod
    async def delete_access_token(self, token: str) -> None: ...

    @abstractmethod
    async def save_refresh_token(self, token: str, data: RefreshTokenData) -> None: ...

    @abstractmethod
    async def get_refresh_token(self, token: str) -> RefreshTokenData | None: ...

    @abstractmethod
    async def delete_refresh_token(self, token: str) -> None: ...

    @abstractmethod
    async def cleanup_expired(self) -> tuple[int, int, int]:
        """Remove expired entries. Returns (codes_removed, access_removed, refresh_removed)."""
        ...


class InMemoryBackend(OAuth2StoreBackend):
    """In-memory dict-based storage. Suitable for single-process deployments."""

    def __init__(self) -> None:
        self._auth_codes: dict[str, AuthCodeData] = {}
        self._access_tokens: dict[str, AccessTokenData] = {}
        self._refresh_tokens: dict[str, RefreshTokenData] = {}

    async def save_auth_code(self, code: str, data: AuthCodeData) -> None:
        self._auth_codes[code] = data

    async def get_auth_code(self, code: str) -> AuthCodeData | None:
        data = self._auth_codes.pop(code, None)
        if data and data.exp < datetime.now():
            return None
        return data

    async def save_access_token(self, token: str, data: AccessTokenData) -> None:
        self._access_tokens[token] = data

    async def get_access_token(self, token: str) -> AccessTokenData | None:
        data = self._access_tokens.get(token)
        if data and data.exp < datetime.now():
            del self._access_tokens[token]
            return None
        return data

    async def delete_access_token(self, token: str) -> None:
        self._access_tokens.pop(token, None)

    async def save_refresh_token(self, token: str, data: RefreshTokenData) -> None:
        self._refresh_tokens[token] = data

    async def get_refresh_token(self, token: str) -> RefreshTokenData | None:
        data = self._refresh_tokens.pop(token, None)
        if data and data.exp < datetime.now():
            return None
        return data

    async def delete_refresh_token(self, token: str) -> None:
        self._refresh_tokens.pop(token, None)

    async def cleanup_expired(self) -> tuple[int, int, int]:
        now = datetime.now()
        expired_codes = [k for k, v in self._auth_codes.items() if v.exp < now]
        for k in expired_codes:
            del self._auth_codes[k]

        expired_access = [k for k, v in self._access_tokens.items() if v.exp < now]
        for k in expired_access:
            del self._access_tokens[k]

        expired_refresh = [k for k, v in self._refresh_tokens.items() if v.exp < now]
        for k in expired_refresh:
            del self._refresh_tokens[k]

        return len(expired_codes), len(expired_access), len(expired_refresh)


class OAuth2Store:
    """OAuth2 token store with configurable backend and automatic cleanup."""

    def __init__(self, backend: OAuth2StoreBackend | None = None) -> None:
        self.backend = backend or InMemoryBackend()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup(self, interval: int = 60) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))

    async def stop_cleanup(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self, interval: int) -> None:
        while True:
            try:
                await asyncio.sleep(interval)
                codes, access, refresh = await self.backend.cleanup_expired()
                if codes or access or refresh:
                    logger.debug(
                        "Cleaned expired tokens: codes=%d, access=%d, refresh=%d",
                        codes,
                        access,
                        refresh,
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Token cleanup error: %s", e)

    async def save_auth_code(self, code: str, data: AuthCodeData) -> None:
        await self.backend.save_auth_code(code, data)

    async def get_auth_code(self, code: str) -> AuthCodeData | None:
        return await self.backend.get_auth_code(code)

    async def save_access_token(self, token: str, data: AccessTokenData) -> None:
        await self.backend.save_access_token(token, data)

    async def get_access_token(self, token: str) -> AccessTokenData | None:
        return await self.backend.get_access_token(token)

    async def save_refresh_token(self, token: str, data: RefreshTokenData) -> None:
        await self.backend.save_refresh_token(token, data)

    async def get_refresh_token(self, token: str) -> RefreshTokenData | None:
        return await self.backend.get_refresh_token(token)
