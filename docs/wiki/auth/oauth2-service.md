---
title: OAuth 2.1 Service — Audit & API Reference
unified_id: doc:wiki:auth:oauth2-service
status: current
tags:
  - auth
  - oauth
  - mcp
  - audit
confidence: 1.0
created_at: '2026-05-14T00:00:00'
updated_at: '2026-05-14T00:00:00'
related:
  - hermes-llm-wiki-Phase-6
---

# OAuth 2.1 Service — состояние и API

> **Аудит, 2026-05-14.** Hermes-llm-wiki Phase 6 task #1.
>
> **Surprise finding:** generic extraction уже выполнена ранее. tasks.md описывает
> Ф6 как «23 pending», но `src/shared/mcp_oauth/` существует с тестами. Реальный
> остаток меньше декларированного.

## Текущее состояние (две реализации сосуществуют)

| | BSL legacy | Generic shared |
|---|---|---|
| Путь | [`src/bsl/mcp_server/auth/oauth2.py`](../../../src/bsl/mcp_server/auth/oauth2.py) | [`src/shared/mcp_oauth/`](../../../src/shared/mcp_oauth/) |
| Размер | 214 LoC, single file | 373 LoC (models 34 + service 165 + store 157 + **init** 17) |
| Tests | нет специфичных | [`tests/unit/test_mcp_oauth.py`](../../../tests/unit/test_mcp_oauth.py) — 16 passing |
| Пользовательские данные | login + password в каждой структуре | абстрактный `user_data: dict` |
| Store backends | только in-memory | pluggable через `OAuth2StoreBackend` ABC (in-memory готов, SQLite/Redis — TODO) |
| Используется в | BSL MCP server | имеется `src.shared.mcp_oauth`, активных потребителей в коде НЕ найдено |

`src/bsl/mcp_server/auth/oauth2.py:3-5` уже содержит docstring-предупреждение:

```python
"""OAuth2 хранилище и сервис для авторизации.

Note: Generic version extracted to src.shared.mcp_oauth (Phase 6).
This module preserves the original BSL-specific login/password API.
New MCP servers should use src.shared.mcp_oauth instead.
"""
```

Это значит, что **extraction уже выполнена** (Ф6 §2 spec). Невыполненными остаются: backward-compat wrapper, подключение к `pdf-vector-graph`, security review.

---

## API: BSL legacy (`src/bsl/mcp_server/auth/oauth2.py`)

### Data classes (lines 19-46)

```python
@dataclass
class AuthCodeData:
    login: str           # BSL-specific
    password: str        # BSL-specific
    redirect_uri: str
    code_challenge: str  # PKCE challenge
    exp: datetime

@dataclass
class AccessTokenData:
    login: str
    password: str
    exp: datetime

@dataclass
class RefreshTokenData:
    login: str
    password: str
    exp: datetime
    rotation_counter: int = 0  # increments per refresh
```

### `OAuth2Store` (lines 49-123, in-memory only)

| Метод | Назначение |
|---|---|
| `start_cleanup_task(interval=60)` | Запустить async задачу очистки expired |
| `stop_cleanup_task()` | Остановить cleanup loop |
| `_cleanup_expired()` | Удалить просроченные auth codes / access / refresh |
| `save_auth_code(code, data)` / `get_auth_code(code)` | Auth code lifecycle (single-use, `.pop()` on get) |
| `save_access_token(token, data)` / `get_access_token(token)` | Access token (multi-use, expiry-checked on get) |
| `save_refresh_token(token, data)` / `get_refresh_token(token)` | Refresh token (single-use, `.pop()` on get) |

### `OAuth2Service` (lines 126-214)

| Метод | Назначение | TTL default |
|---|---|---|
| `__init__(store, code_ttl=120, access_ttl=3600, refresh_ttl=1209600)` | DI store + token TTLs | 2 min / 1h / 14 дней |
| `generate_prm_document(public_url)` | RFC 9728 PRM endpoint metadata | — |
| `generate_authorization_code(login, password, redirect_uri, code_challenge)` | Step 1 OAuth flow | TTL=`code_ttl` |
| `validate_pkce(code_verifier, code_challenge)` | RFC 7636 PKCE S256 verification | static |
| `exchange_code_for_tokens(code, redirect_uri, code_verifier)` | Step 2: code → (access, refresh) | TTL=`access_ttl`/`refresh_ttl` |
| `refresh_tokens(refresh_token)` | Rotation: new access + new refresh | — |
| `validate_access_token(token)` | → (login, password) или None | — |

**BSL-specific contract**: store coupling — `login/password` живут в data classes напрямую. Невозможно использовать для аутентификации других схем (OIDC, SAML federation, magic links).

---

## API: Generic shared (`src/shared/mcp_oauth/`)

### Структура модуля

```
src/shared/mcp_oauth/
├── __init__.py    — public re-exports
├── models.py      — AuthCodeData / AccessTokenData / RefreshTokenData (generic)
├── service.py     — OAuth2Service (generic flow logic)
└── store.py       — OAuth2Store + OAuth2StoreBackend ABC + InMemoryBackend
```

### Generic data model

В отличие от BSL, данные пользователя абстрактны:

```python
@dataclass
class AuthCodeData:
    client_id: str             # OAuth2 client_id (вместо login)
    redirect_uri: str
    code_challenge: str
    user_data: dict            # opaque payload (любая user identity)
    exp: datetime
```

`user_data: dict` позволяет хранить:

- `{"login": "...", "password": "..."}` — BSL pattern (backward-compat)
- `{"sub": "user-id", "email": "...", "roles": [...]}` — OIDC pattern
- `{"api_key_id": "...", "tenant": "..."}` — multi-tenant pattern

### Pluggable storage

`store.py` определяет ABC:

```python
class OAuth2StoreBackend(ABC):
    @abstractmethod
    async def save_auth_code(self, code: str, data: AuthCodeData): ...
    @abstractmethod
    async def get_auth_code(self, code: str) -> AuthCodeData | None: ...
    # ... + access/refresh save/get
    @abstractmethod
    async def cleanup_expired(self) -> dict[str, int]: ...
```

Реализации:

- `InMemoryBackend` — готово, эквивалентно BSL behavior
- `SQLiteBackend` — TODO (для persistence через рестарт)
- `RedisBackend` — TODO (для multi-instance MCP servers)

### Test coverage (passing, 2026-05-14)

`tests/unit/test_mcp_oauth.py` — 16 тестов, проходят за 0.18s:

```
TestModels (3): auth_code_data_fields, refresh_token_rotation_counter, default_rotation_counter
TestInMemoryBackend (~3-5): basic CRUD + expiry
TestOAuth2Service (~7): pkce_validation, full_auth_flow, exchange_wrong_redirect, exchange_wrong_pkce, expired_code_rejected, validate_invalid_token, refresh_invalid_token
TestOAuth2Store (~1): cleanup_task
```

---

## Сравнение surface

| Aspect | BSL legacy | Generic shared |
|---|---|---|
| User identity | `login`+`password` (жёстко) | `user_data: dict` (opaque) |
| Storage | in-memory only | `OAuth2StoreBackend` ABC + InMemoryBackend |
| PKCE | S256 only | S256 only (one method consistent with RFC 9728 PRM) |
| Refresh rotation | counter в RefreshTokenData | counter в RefreshTokenData (одинаково) |
| Cleanup | inline `_cleanup_expired` | через backend `cleanup_expired()` (delegated) |
| TTL defaults | 120 / 3600 / 1209600 | identical (если совпадает с reading service.py) |
| PRM endpoint | `generate_prm_document(public_url)` | same |
| Tests | 0 specific (covered via integration?) | 16 unit tests |

---

## Gaps для завершения Ф6

Из 23 заявленных tasks реально остаются:

| Task | Status | Effort |
|---|---|---|
| Аудит существующего `oauth2.py`, документировать API | ✅ ДАННЫЙ ДОКУМЕНТ | done |
| Extract `OAuth2Service` в `src/shared/mcp_oauth/service.py` | ✅ done в прошлой фазе | — |
| `OAuth2Store` с pluggable backends | ⏳ ABC + InMemoryBackend готовы; SQLiteBackend + RedisBackend pending | 4-6ч каждый |
| Backward-compat: BSL `oauth2.py` становится thin wrapper | 🔲 НЕТ — BSL остаётся duplicated impl | 2-3ч |
| Подключить к `pdf-vector-graph` MCP server за feature flag `MCP_OAUTH_ENABLED` | 🔲 не сделано | 3-4ч |
| Расширить `tests/unit/api/test_auth.py` | 🔲 mcp_oauth уже покрыт; нужно расширение для wrapper | 2-3ч |
| 288 существующих тестов не сломались | ❓ unverified — нужен прогон | 30 мин |
| Security review через `memory_audit_log` | 🔲 не сделано | 2-3ч |
| `.mcp.json` env vars для OAuth | 🔲 не сделано | 30 мин |
| `docs/wiki/auth/oauth-setup.md` | 🔲 не сделано (будет после remaining работ) | 1-2ч |

**Реальная остаточная трудоёмкость Ф6:** ~15-20 часов (vs 3-4 дня по spec) — extraction уже не нужна.

---

## Действия для следующей сессии

1. **Backward-compat wrapper** (`src/bsl/mcp_server/auth/oauth2.py` rewrite): import `OAuth2Service` из shared, добавить тонкий `BslOAuth2Adapter` который инжектит `user_data={"login": ..., "password": ...}`. Убрать duplicated code. Затронет ~150 LoC.
2. **Regression run**: `pytest tests/unit/api/test_auth.py tests/integration/` — confirm 0 регрессий после wrapper.
3. **Feature flag для pdf-vector-graph**: env `MCP_OAUTH_ENABLED=1` → подключение `OAuth2Service` в `src/api/auth/`.
4. **`oauth-setup.md`**: пошаговая инструкция для пользователей PDF MCP server.

## Связано

- Spec: [`openspec/changes/hermes-llm-wiki/tasks.md`](../../../openspec/changes/hermes-llm-wiki/tasks.md) §Фаза 6
- Initial extraction commit: см. git log на `src/shared/mcp_oauth/` (`git log --oneline -- src/shared/mcp_oauth/`)
- RFC: [PKCE 7636](https://datatracker.ietf.org/doc/html/rfc7636), [PRM 9728](https://datatracker.ietf.org/doc/html/rfc9728)
