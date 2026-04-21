"""OAuth2 хранилище и сервис для авторизации.

Note: Generic version extracted to src.shared.mcp_oauth (Phase 6).
This module preserves the original BSL-specific login/password API.
New MCP servers should use src.shared.mcp_oauth instead.
"""

import asyncio
import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class AuthCodeData:
    """Данные authorization code."""

    login: str
    password: str
    redirect_uri: str
    code_challenge: str
    exp: datetime


@dataclass
class AccessTokenData:
    """Данные access token."""

    login: str
    password: str
    exp: datetime


@dataclass
class RefreshTokenData:
    """Данные refresh token."""

    login: str
    password: str
    exp: datetime
    rotation_counter: int = 0


class OAuth2Store:
    """In-memory хранилище для OAuth2 токенов и кодов."""

    def __init__(self):
        self.auth_codes: dict[str, AuthCodeData] = {}
        self.access_tokens: dict[str, AccessTokenData] = {}
        self.refresh_tokens: dict[str, RefreshTokenData] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self, interval: int = 60):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
        logger.debug(f"Запущена задача очистки OAuth2 токенов (интервал: {interval}s)")

    async def stop_cleanup_task(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.debug("Задача очистки OAuth2 токенов остановлена")

    async def _cleanup_loop(self, interval: int):
        while True:
            try:
                await asyncio.sleep(interval)
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка при очистке токенов: {e}")

    def _cleanup_expired(self):
        now = datetime.now()
        expired_codes = [code for code, data in self.auth_codes.items() if data.exp < now]
        for code in expired_codes:
            del self.auth_codes[code]
        expired_access = [token for token, data in self.access_tokens.items() if data.exp < now]
        for token in expired_access:
            del self.access_tokens[token]
        expired_refresh = [token for token, data in self.refresh_tokens.items() if data.exp < now]
        for token in expired_refresh:
            del self.refresh_tokens[token]
        if expired_codes or expired_access or expired_refresh:
            logger.debug(
                f"Очищено токенов: codes={len(expired_codes)}, access={len(expired_access)}, refresh={len(expired_refresh)}"
            )

    def save_auth_code(self, code: str, data: AuthCodeData):
        self.auth_codes[code] = data

    def get_auth_code(self, code: str) -> AuthCodeData | None:
        data = self.auth_codes.pop(code, None)
        if data and data.exp < datetime.now():
            return None
        return data

    def save_access_token(self, token: str, data: AccessTokenData):
        self.access_tokens[token] = data

    def get_access_token(self, token: str) -> AccessTokenData | None:
        data = self.access_tokens.get(token)
        if data and data.exp < datetime.now():
            del self.access_tokens[token]
            return None
        return data

    def save_refresh_token(self, token: str, data: RefreshTokenData):
        self.refresh_tokens[token] = data

    def get_refresh_token(self, token: str) -> RefreshTokenData | None:
        data = self.refresh_tokens.pop(token, None)
        if data and data.exp < datetime.now():
            return None
        return data


class OAuth2Service:
    """Сервис OAuth2 для авторизации (BSL-specific, login/password)."""

    def __init__(self, store: OAuth2Store, code_ttl: int = 120,
                 access_ttl: int = 3600, refresh_ttl: int = 1209600):
        self.store = store
        self.code_ttl = code_ttl
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl

    def generate_prm_document(self, public_url: str) -> dict:
        public_url = public_url.rstrip("/")
        return {
            "resource": public_url,
            "authorization_servers": [public_url],
            "authorization_endpoint": f"{public_url}/authorize",
            "token_endpoint": f"{public_url}/token",
            "code_challenge_methods_supported": ["S256"],
        }

    def generate_authorization_code(self, login: str, password: str,
                                    redirect_uri: str, code_challenge: str) -> str:
        code = secrets.token_urlsafe(32)
        exp = datetime.now() + timedelta(seconds=self.code_ttl)
        self.store.save_auth_code(code, AuthCodeData(
            login=login, password=password,
            redirect_uri=redirect_uri, code_challenge=code_challenge, exp=exp,
        ))
        return code

    @staticmethod
    def validate_pkce(code_verifier: str, code_challenge: str) -> bool:
        verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
        computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode("ascii").rstrip("=")
        return computed_challenge == code_challenge

    def exchange_code_for_tokens(self, code: str, redirect_uri: str,
                                 code_verifier: str) -> tuple[str, str, int, str] | None:
        code_data = self.store.get_auth_code(code)
        if not code_data:
            logger.warning("Недействительный или истёкший authorization code")
            return None
        if code_data.redirect_uri != redirect_uri:
            logger.warning("Несовпадение redirect_uri")
            return None
        if not self.validate_pkce(code_verifier, code_data.code_challenge):
            logger.warning("PKCE валидация не прошла")
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
        logger.debug(f"Выданы токены для пользователя {code_data.login}")
        return (access_token, "Bearer", self.access_ttl, refresh_token)

    def refresh_tokens(self, refresh_token: str) -> tuple[str, str, int, str] | None:
        refresh_data = self.store.get_refresh_token(refresh_token)
        if not refresh_data:
            logger.warning("Недействительный или истёкший refresh token")
            return None

        new_access_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        now = datetime.now()
        self.store.save_access_token(new_access_token, AccessTokenData(
            login=refresh_data.login, password=refresh_data.password,
            exp=now + timedelta(seconds=self.access_ttl),
        ))
        self.store.save_refresh_token(new_refresh_token, RefreshTokenData(
            login=refresh_data.login, password=refresh_data.password,
            exp=now + timedelta(seconds=self.refresh_ttl),
            rotation_counter=refresh_data.rotation_counter + 1,
        ))
        logger.debug(f"Обновлены токены для {refresh_data.login} (rotation #{refresh_data.rotation_counter + 1})")
        return (new_access_token, "Bearer", self.access_ttl, new_refresh_token)

    def validate_access_token(self, token: str) -> tuple[str, str] | None:
        token_data = self.store.get_access_token(token)
        if not token_data:
            return None
        return (token_data.login, token_data.password)
