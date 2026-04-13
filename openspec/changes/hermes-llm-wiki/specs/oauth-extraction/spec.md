# Spec: oauth-extraction

**Change:** hermes-llm-wiki
**Phase:** 6
**Profile:** python-framework

## Контекст

OAuth 2.1 + PKCE **уже реализован** для BSL MCP server (Phase 12.3, обнаружено в v1.3.1 audit). Существующие компоненты:

| Файл | LoC | Что содержит |
|------|-----|--------------|
| [`src/bsl/mcp_server/auth/oauth2.py`](../../../../src/bsl/mcp_server/auth/oauth2.py) | 350 | `OAuth2Service`, `OAuth2Store`, `AuthCodeData`, `AccessTokenData`, `RefreshTokenData`, PKCE validation, RFC 9728 PRM document, TTL cleanup task |
| [`src/api/auth/jwt_handler.py`](../../../../src/api/auth/jwt_handler.py) | 159 | `JWTHandler` для REST API с multi-tenant (tenant_id, role, HS256) |
| [`src/api/auth/dependencies.py`](../../../../src/api/auth/dependencies.py) | 179 | FastAPI DI для auth |
| [`src/api/routes/auth.py`](../../../../src/api/routes/auth.py) | 95 | `/auth/token` endpoint |
| [`tests/unit/api/test_auth.py`](../../../../tests/unit/api/test_auth.py) | 288 | Полный unit test suite |

**В v1.0-1.2 roadmap это было ошибочно отнесено к "defer P3" — реально Phase 12.3 DONE.** Фаза 6 v1.3.4 переформулирована в **экстракцию** существующего кода в `src/shared/mcp_oauth/` как reusable module, **без** breaking changes для BSL MCP server.

Цель: после экстракции подключить тот же OAuth2Service к другим MCP-серверам (начиная с `pdf-vector-graph`) опционально за feature flag `MCP_OAUTH_ENABLED=true`. Single-user локальная разработка остаётся с flag=false по умолчанию.

---

## ## ADDED REQ-1: src/shared/mcp_oauth/ модуль

**Файлы:**
- `src/shared/mcp_oauth/__init__.py` (новый)
- `src/shared/mcp_oauth/service.py` (новый, экстрагирован из `bsl/mcp_server/auth/oauth2.py`)
- `src/shared/mcp_oauth/store.py` (новый, `OAuth2Store` + pluggable backends)
- `src/shared/mcp_oauth/models.py` (новый, dataclasses)
- `src/shared/mcp_oauth/prm.py` (новый, RFC 9728 PRM document generation)

Generic reusable OAuth 2.1 service, не зависящий от BSL или FastAPI specifics.

### API

```python
# src/shared/mcp_oauth/__init__.py
from src.shared.mcp_oauth.service import OAuth2Service
from src.shared.mcp_oauth.store import OAuth2Store, InMemoryBackend, SQLiteBackend
from src.shared.mcp_oauth.models import (
    AuthCodeData,
    AccessTokenData,
    RefreshTokenData,
    OAuth2Config,
)

__all__ = [
    "OAuth2Service",
    "OAuth2Store",
    "InMemoryBackend",
    "SQLiteBackend",
    "AuthCodeData",
    "AccessTokenData",
    "RefreshTokenData",
    "OAuth2Config",
]


# src/shared/mcp_oauth/models.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class OAuth2Config:
    client_id: str
    client_secret: str | None  # None для PKCE public clients
    code_ttl_s: int = 600       # 10 минут
    access_ttl_s: int = 3600    # 1 час
    refresh_ttl_s: int = 86400  # 24 часа
    require_pkce: bool = True
    allowed_redirect_uris: list[str] = None


@dataclass
class AuthCodeData:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: str          # PKCE
    code_challenge_method: str   # "S256"
    scope: list[str]
    exp: datetime


@dataclass
class AccessTokenData:
    token: str
    client_id: str
    scope: list[str]
    exp: datetime
    token_type: str = "Bearer"


@dataclass
class RefreshTokenData:
    token: str
    access_token: str
    client_id: str
    exp: datetime
```

### OAuth2Service

```python
# src/shared/mcp_oauth/service.py
import secrets
from datetime import datetime, timedelta, timezone

from src.shared.mcp_oauth.models import (
    AuthCodeData,
    AccessTokenData,
    RefreshTokenData,
    OAuth2Config,
)
from src.shared.mcp_oauth.store import OAuth2Store


class OAuth2Service:
    """Generic OAuth 2.1 + PKCE service, extracted from BSL MCP server.

    Reusable across MCP servers via Store backend abstraction.
    """

    def __init__(self, config: OAuth2Config, store: OAuth2Store) -> None:
        self.config = config
        self.store = store

    def generate_authorization_code(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: list[str],
    ) -> str:
        """Generate OAuth auth code. PKCE required if config.require_pkce."""

    def validate_pkce(self, code_verifier: str, code_challenge: str) -> bool:
        """RFC 7636: S256(code_verifier) == code_challenge."""

    async def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
        client_id: str,
    ) -> tuple[str, str, int, str] | None:
        """Returns (access_token, token_type, expires_in, refresh_token) or None."""

    async def refresh_access_token(
        self, refresh_token: str
    ) -> tuple[str, int] | None:
        """Returns (new_access_token, expires_in) or None if invalid/expired."""

    async def revoke_token(self, token: str, token_type: str) -> None:
        """Revoke access or refresh token."""

    def generate_prm_document(self, public_url: str) -> dict:
        """RFC 9728: Protected Resource Metadata for MCP discovery."""
```

### Сценарий 1: Экстракция сохраняет семантику

**Given** existing `src/bsl/mcp_server/auth/oauth2.py` с `OAuth2Service`
**When** код перемещён в `src/shared/mcp_oauth/service.py` с удалением BSL-specific деталей
**Then** все публичные методы сохраняют сигнатуры
**And** `validate_pkce`, `exchange_code_for_tokens`, `generate_prm_document` работают идентично
**And** existing BSL MCP server продолжает работать через backward-compat wrapper (REQ-2)

### Сценарий 2: Pluggable store backend

**Given** `OAuth2Service(config, store=InMemoryBackend())`
**When** вызывается `exchange_code_for_tokens(code, verifier, client_id)`
**Then** auth code сохраняется через `store.save_auth_code(code, data)`
**And** access + refresh tokens через `store.save_access_token()` / `save_refresh_token()`
**And** cleanup expired через `store.cleanup_expired()`

### Граничные условия

- PKCE `code_challenge_method != "S256"` → `ValueError("Only S256 supported")`
- `require_pkce=True` и `code_challenge` отсутствует → error на `generate_authorization_code`
- Expired auth code → `exchange_code_for_tokens` возвращает `None`, не crash
- Concurrent `refresh_access_token` для одного refresh_token → store enforces atomic swap (old invalidated)
- `generate_prm_document(public_url="")` → `ValueError`

### Ссылки

- [`src/bsl/mcp_server/auth/oauth2.py`](../../../../src/bsl/mcp_server/auth/oauth2.py) — source (Phase 12.3)
- [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636) — PKCE
- [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728) — OAuth 2.0 Protected Resource Metadata

---

## ## ADDED REQ-2: Pluggable OAuth2Store backends

**Файл:** `src/shared/mcp_oauth/store.py` (новый)

`OAuth2Store` — abstract base с тремя implementations: `InMemoryBackend` (для тестов и single-user), `SQLiteBackend` (persistent local), `RedisBackend` (optional, для multi-server deployments).

### API

```python
# src/shared/mcp_oauth/store.py
from abc import ABC, abstractmethod
from typing import Optional

from src.shared.mcp_oauth.models import (
    AuthCodeData,
    AccessTokenData,
    RefreshTokenData,
)


class OAuth2Store(ABC):
    """Abstract storage для OAuth tokens."""

    @abstractmethod
    async def start_cleanup_task(self, interval_s: int = 60) -> None: ...

    @abstractmethod
    async def stop_cleanup_task(self) -> None: ...

    @abstractmethod
    async def save_auth_code(self, code: str, data: AuthCodeData) -> None: ...

    @abstractmethod
    async def get_auth_code(self, code: str) -> Optional[AuthCodeData]: ...

    @abstractmethod
    async def save_access_token(self, token: str, data: AccessTokenData) -> None: ...

    @abstractmethod
    async def get_access_token(self, token: str) -> Optional[AccessTokenData]: ...

    @abstractmethod
    async def save_refresh_token(self, token: str, data: RefreshTokenData) -> None: ...

    @abstractmethod
    async def get_refresh_token(self, token: str) -> Optional[RefreshTokenData]: ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Returns count of removed items."""


class InMemoryBackend(OAuth2Store):
    """In-memory implementation (текущий default в BSL MCP)."""

    def __init__(self) -> None:
        self.auth_codes: dict[str, AuthCodeData] = {}
        self.access_tokens: dict[str, AccessTokenData] = {}
        self.refresh_tokens: dict[str, RefreshTokenData] = {}
        self._cleanup_task = None


class SQLiteBackend(OAuth2Store):
    """Persistent SQLite storage для local single-server."""

    def __init__(self, db_path: str = "data/oauth_store.db") -> None: ...
    # Table schema: auth_codes(code, client_id, ..., exp),
    #               access_tokens(token, client_id, ..., exp),
    #               refresh_tokens(token, access_token, client_id, exp)
    # Cleanup: DELETE WHERE exp < NOW() periodically
```

### Сценарий 1: InMemory roundtrip

**Given** `store = InMemoryBackend()`
**And** `auth_code = AuthCodeData(code="abc", ...)` с `exp=now+600s`
**When** `await store.save_auth_code("abc", auth_code)` и потом `await store.get_auth_code("abc")`
**Then** возвращается тот же `auth_code`
**And** после 601 секунд `get_auth_code("abc")` возвращает `None` (expired)

### Сценарий 2: SQLite persistence across restarts

**Given** `store = SQLiteBackend("test.db")` и сохранён access token
**When** процесс перезапускается и `store = SQLiteBackend("test.db")` создаётся заново
**Then** `get_access_token(token)` возвращает тот же data (persistence works)

### Граничные условия

- Concurrent writes на один код/токен → последний wins (`put` semantics)
- SQLite database locked → retry с backoff (через existing `src/memory/infrastructure/retry.py`)
- Cleanup task фейлится → log error, продолжается до next tick
- `db_path` parent не существует → `mkdir(parents=True, exist_ok=True)`

### Ссылки

- [`src/memory/infrastructure/retry.py`](../../../../src/memory/infrastructure/retry.py) — retry logic для SQLite
- Существующий `OAuth2Store` в [`src/bsl/mcp_server/auth/oauth2.py:44-148`](../../../../src/bsl/mcp_server/auth/oauth2.py) — source для InMemoryBackend

---

## ## MODIFIED REQ-3: BSL MCP server использует shared module

**Файл:** [`src/bsl/mcp_server/auth/oauth2.py`](../../../../src/bsl/mcp_server/auth/oauth2.py)
**Было:** 350 LoC с полной собственной реализацией `OAuth2Service`, `OAuth2Store`, dataclasses
**Стало:** thin wrapper (~50 LoC) re-exporting из `src/shared/mcp_oauth/`

### Backward-compat стратегия

```python
# src/bsl/mcp_server/auth/oauth2.py (после экстракции)
"""DEPRECATED: thin wrapper over src.shared.mcp_oauth.

Imports from shared module for backward-compat with existing callers.
New code should import directly from src.shared.mcp_oauth.
"""

# Re-export всех публичных классов
from src.shared.mcp_oauth import (
    OAuth2Service,
    OAuth2Store,
    InMemoryBackend,
    AuthCodeData,
    AccessTokenData,
    RefreshTokenData,
    OAuth2Config,
)

# BSL-specific default factory (сохраняет existing инициализацию)
def create_bsl_oauth_service() -> OAuth2Service:
    """Factory with BSL-specific defaults."""
    config = OAuth2Config(
        client_id=os.environ.get("BSL_MCP_CLIENT_ID", "bsl-mcp-default"),
        client_secret=None,  # PKCE-only для BSL MCP
        code_ttl_s=600,
        access_ttl_s=3600,
        refresh_ttl_s=86400,
        require_pkce=True,
    )
    return OAuth2Service(config, store=InMemoryBackend())


__all__ = [
    "OAuth2Service",
    "OAuth2Store",
    "InMemoryBackend",
    "AuthCodeData",
    "AccessTokenData",
    "RefreshTokenData",
    "OAuth2Config",
    "create_bsl_oauth_service",
]
```

### Сценарий 1: Existing BSL MCP server callers работают без изменений

**Given** существующий импорт `from src.bsl.mcp_server.auth.oauth2 import OAuth2Service`
**When** код запускается после экстракции
**Then** import работает (re-export из shared)
**And** поведение идентично pre-extraction (use the same underlying class)
**And** все 288 тестов из [`test_auth.py`](../../../../tests/unit/api/test_auth.py) проходят без изменений

### Сценарий 2: Deprecated warning для старого пути

**Given** новый код импортирует `from src.bsl.mcp_server.auth.oauth2 import OAuth2Service`
**When** module загружается
**Then** deprecation warning в logs: `"Importing from bsl.mcp_server.auth.oauth2 is deprecated, use src.shared.mcp_oauth instead"`
**And** код продолжает работать (soft deprecation)

### Граничные условия

- Импорт из `src.bsl.mcp_server.auth.oauth2.OAuth2Store.auth_codes` (internal attribute) → работает через re-export
- Subclassing old `OAuth2Service` → продолжает работать (same class)
- Third-party extension использует deprecated path → гибкая деград через warning, не breaking

### Ссылки

- [`src/bsl/mcp_server/auth/oauth2.py`](../../../../src/bsl/mcp_server/auth/oauth2.py) — target file
- [`tests/unit/api/test_auth.py`](../../../../tests/unit/api/test_auth.py) — regression protection (288 тестов)

---

## ## ADDED REQ-4: pdf-vector-graph MCP server OAuth integration (за feature flag)

**Файл:** `src/mcp_server/auth.py` (или аналогичный путь для pdf-vector-graph MCP)
**Feature flag:** `MCP_OAUTH_ENABLED` env var (default `false`)

Подключение существующего `OAuth2Service` к `pdf-vector-graph` MCP серверу. **НЕ блокирует single-user режим** — активируется только для multi-tenant production deployments.

### Integration

```python
# src/mcp_server/auth.py (новый или расширение)
import os
from src.shared.mcp_oauth import OAuth2Service, OAuth2Config, InMemoryBackend, SQLiteBackend


def get_mcp_oauth_service() -> OAuth2Service | None:
    """Returns OAuth2Service if MCP_OAUTH_ENABLED=true, else None."""
    if not os.environ.get("MCP_OAUTH_ENABLED", "false").lower() == "true":
        return None

    config = OAuth2Config(
        client_id=os.environ["PDF_MCP_CLIENT_ID"],
        client_secret=None,
        require_pkce=True,
    )

    # Persistent store для production
    store = SQLiteBackend(
        db_path=os.environ.get("MCP_OAUTH_DB_PATH", "data/mcp_oauth.db")
    )
    return OAuth2Service(config, store)


async def auth_middleware(request, call_next):
    """Async middleware: validate Bearer token if OAuth enabled."""
    oauth = get_mcp_oauth_service()
    if oauth is None:
        return await call_next(request)  # passthrough

    token = _extract_bearer(request.headers.get("Authorization", ""))
    if not token:
        return _401_response("Missing token")

    token_data = await oauth.store.get_access_token(token)
    if token_data is None or token_data.exp < datetime.now(timezone.utc):
        return _401_response("Invalid or expired token")

    request.state.client_id = token_data.client_id
    request.state.scope = token_data.scope
    return await call_next(request)
```

### Сценарий 1: Single-user local (default)

**Given** `.env` не содержит `MCP_OAUTH_ENABLED` (default `false`)
**When** `pdf-vector-graph` MCP server стартует
**Then** `get_mcp_oauth_service()` возвращает `None`
**And** `auth_middleware` passthrough'ит все запросы
**And** поведение **идентично** текущему (не трогаем local workflow)

### Сценарий 2: Multi-tenant production

**Given** `.env: MCP_OAUTH_ENABLED=true`, `PDF_MCP_CLIENT_ID=prod-client`
**When** MCP server стартует
**Then** `OAuth2Service` инициализирован с `SQLiteBackend`
**And** без Bearer token → 401 response
**And** с valid token → request обрабатывается + `client_id` + `scope` доступны через `request.state`

### Сценарий 3: Expired token handling

**Given** `MCP_OAUTH_ENABLED=true`
**And** Client имеет expired access token
**When** Client делает request с expired token
**Then** 401 response с `WWW-Authenticate: Bearer error="invalid_token"`
**And** client использует refresh token → `oauth.refresh_access_token()` → получает new access token

### Граничные условия

- `MCP_OAUTH_ENABLED=true` но `PDF_MCP_CLIENT_ID` не установлен → `RuntimeError` на startup (fail-fast)
- Malformed `Authorization` header → 400 response
- SQLite store недоступен → 503 response (service unavailable), не crash
- Feature flag toggled runtime (не recommended) → требует restart для consistency

### Ссылки

- [`src/mcp_server/`](../../../../src/mcp_server/) — pdf-vector-graph MCP target
- [`.mcp.json`](../../../../.mcp.json) — конфиг для MCP clients
- `docs/wiki/auth/oauth-setup.md` — будет создан в Фазе 1 migration (wiki docs)

---

## ## ADDED REQ-5: Integration с memory_audit_log

**Файлы:** `src/shared/mcp_oauth/service.py` (extension через hook)

Каждая token operation (issue, refresh, revoke, invalid) логируется в existing `memory_audit_log` tool (P4, `src/memory/orchestrator/memory_orchestrator.py`). Security audit trail готов из коробки.

### Event types

| Event | Когда | Payload |
|-------|-------|---------|
| `oauth.code.issued` | `generate_authorization_code()` успешен | `{client_id, scope, exp}` |
| `oauth.token.issued` | `exchange_code_for_tokens()` успешен | `{client_id, access_exp, refresh_exp}` |
| `oauth.token.refreshed` | `refresh_access_token()` успешен | `{client_id, new_exp}` |
| `oauth.token.revoked` | `revoke_token()` | `{client_id, token_type}` |
| `oauth.auth.failed` | Invalid token / expired / PKCE fail | `{client_id, reason}` |

### Integration

```python
# src/shared/mcp_oauth/service.py

class OAuth2Service:
    def __init__(
        self,
        config: OAuth2Config,
        store: OAuth2Store,
        audit_callback: Callable[[str, dict], Awaitable[None]] | None = None,
    ) -> None:
        ...
        self._audit = audit_callback

    async def _publish_audit(self, event_type: str, payload: dict) -> None:
        if self._audit:
            try:
                await self._audit(event_type, payload)
            except Exception as e:
                logger.warning(f"[OAUTH-AUDIT] Failed to log {event_type}: {e}")
```

### Сценарий 1: Successful token issuance logged

**Given** `OAuth2Service(audit_callback=memory_orchestrator.memory_audit_log)`
**When** `exchange_code_for_tokens()` succeeds
**Then** `memory_audit_log` получает `event_type="oauth.token.issued"` с payload
**And** audit запись доступна через `memory_orchestrator.memory_audit_stats` (existing P4 tool)

### Сценарий 2: Failed auth logged для security analysis

**Given** 5 неудачных попыток с invalid tokens в течение минуты
**When** audit log запрашивается
**Then** `memory_audit_stats()` возвращает `{oauth.auth.failed: 5, time_window: "1min"}`
**And** security analyst может использовать для rate limiting / alerting

### Граничные условия

- `audit_callback=None` (default) → silent, no audit, существующее поведение
- Audit callback выбрасывает exception → log warning, OAuth operation не прерывается (fail-open for availability)
- Audit payload содержит sensitive data (access token) → **НЕ включать в payload**, только metadata

### Ссылки

- `memory_orchestrator.memory_audit_log` (P4 tool) — existing audit infrastructure
- `memory_orchestrator.memory_audit_stats` (P4 tool) — audit queries

---

## ## ADDED REQ-6: .mcp.json OAuth configuration documentation

**Файл:** `.mcp.json` (обновление документации и env-переменных)

Документация конфигурации для OAuth-enabled MCP servers. Не включает реальные secrets — только примеры.

### Обновление

```json
{
  "mcpServers": {
    "pdf-vector-graph": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "env": {
        "MCP_OAUTH_ENABLED": "false",
        "PDF_MCP_CLIENT_ID": "pdf-mcp-default",
        "MCP_OAUTH_DB_PATH": "data/mcp_oauth.db"
      }
    }
  }
}
```

### Env переменные (новые)

| Variable | Default | Описание |
|----------|---------|----------|
| `MCP_OAUTH_ENABLED` | `false` | Включает OAuth 2.1 для pdf-vector-graph MCP server |
| `PDF_MCP_CLIENT_ID` | `pdf-mcp-default` | OAuth client ID для PDF MCP server |
| `MCP_OAUTH_DB_PATH` | `data/mcp_oauth.db` | SQLite store path (только если OAuth enabled) |
| `BSL_MCP_CLIENT_ID` | `bsl-mcp-default` | OAuth client ID для BSL MCP (existing, не новое) |

### Сценарий 1: Default single-user config работает

**Given** `.env` без новых переменных
**When** Claude Code запускает pdf-vector-graph MCP
**Then** MCP стартует с `MCP_OAUTH_ENABLED=false`
**And** все MCP tools доступны без Bearer token
**And** existing workflow не меняется

### Сценарий 2: Multi-tenant setup

**Given** `.env: MCP_OAUTH_ENABLED=true`, `PDF_MCP_CLIENT_ID=prod`, `MCP_OAUTH_DB_PATH=/data/oauth.db`
**When** MCP server стартует
**Then** SQLiteBackend инициализируется на `/data/oauth.db`
**And** Bearer token required для всех requests
**And** existing BSL MCP не затронут (отдельный конфиг)

### Граничные условия

- `.mcp.json` содержит secrets → **ошибка**, использовать только env vars
- Invalid JSON в `.mcp.json` → Claude Code fail on startup с четким error message
- Conflict между BSL OAuth и PDF OAuth configs → независимые (separate client IDs)

### Ссылки

- [`.mcp.json`](../../../../.mcp.json) — project MCP config
- [`.env.example`](../../../../.env.example) — нужно обновить с новыми env vars

---

## Регрессия

Фаза 6 **НЕ ДОЛЖНА** ломать:

- [ ] **288 тестов** [`tests/unit/api/test_auth.py`](../../../../tests/unit/api/test_auth.py) — все должны проходить без изменений
- [ ] Existing BSL MCP server — `/auth/token` endpoint работает как раньше
- [ ] Existing `JWTHandler` для REST API — не трогается, остаётся в `src/api/auth/jwt_handler.py`
- [ ] Existing `src/api/routes/auth.py` — endpoint signatures неизменны
- [ ] CLI команда `python -m src.cli.main auth token --tenant <id> --role <role>` — работает
- [ ] Single-user workflow (default `MCP_OAUTH_ENABLED=false`) — полностью **passthrough**, никакого overhead
- [ ] Existing `src/bsl/mcp_server/auth/oauth2.py` imports — работают через re-export

## Новые тесты

```
tests/unit/shared/mcp_oauth/
  __init__.py
  test_service.py                 — OAuth2Service methods (issue, exchange, refresh, revoke, PKCE)
  test_store_in_memory.py         — InMemoryBackend roundtrip + cleanup
  test_store_sqlite.py            — SQLiteBackend persistence + cleanup + concurrent access
  test_prm.py                     — RFC 9728 PRM document generation
  test_backward_compat.py         — BSL MCP re-export works

tests/integration/
  test_pdf_mcp_oauth_enabled.py   — pdf-vector-graph с MCP_OAUTH_ENABLED=true
  test_pdf_mcp_oauth_disabled.py  — default passthrough поведение
  test_oauth_audit_integration.py — memory_audit_log integration

tests/regression/
  test_bsl_oauth_288_no_regression.py — re-run всех 288 BSL auth тестов
```

**Coverage target:**
- `src/shared/mcp_oauth/` — ≥95% (critical security code)
- Backward-compat wrapper — ≥100% (no branches, just re-exports)
- 288 existing tests — **100% pass** (regression blocker)

**Security review checklist (перед merge):**
- [ ] Нет секретов в логах / events / audit payload
- [ ] PKCE S256 обязателен для public clients
- [ ] TTL ≤ 1h access, ≤ 24h refresh, ≤ 10min auth code
- [ ] Token rotation корректно работает (old refresh invalidated after use)
- [ ] Rate limiting на `/auth/token` endpoint (existing или новое)
- [ ] SQLite store права доступа (0600, chmod на создание)
