---
title: OAuth 2.1 + PKCE — Setup & Integration Guide
unified_id: doc:wiki:auth:oauth-setup
status: current
tags:
  - auth
  - oauth
  - mcp
  - setup
  - guide
confidence: 1.0
created_at: '2026-05-15T00:00:00'
updated_at: '2026-05-15T00:00:00'
related:
  - '[[oauth2-service]]'
  - hermes-llm-wiki-Phase-6
---

# OAuth 2.1 + PKCE — Setup Guide

> Дополнение к [[oauth2-service]] (audit). Здесь — практические шаги.

## 1. Environment variables

| Variable | Default | Назначение |
|---|---|---|
| `MCP_OAUTH_ENABLED` | `false` | Feature flag — включает OAuth middleware на pdf-vector-graph MCP. При `false` сервер работает без авторизации (legacy) |
| `MCP_OAUTH_PUBLIC_URL` | `http://localhost:8000` | Публичный URL сервера. Используется в RFC 9728 PRM (`/.well-known/oauth-protected-resource`) для построения авторизационных endpoints |
| `MCP_OAUTH_CODE_TTL` | `600` | TTL authorization code в секундах (10 мин по умолчанию) |
| `MCP_OAUTH_ACCESS_TTL` | `3600` | TTL access token в секундах (1 час) |
| `MCP_OAUTH_REFRESH_TTL` | `86400` | TTL refresh token в секундах (24 часа, ротация инкрементирует counter) |

Конфиг в [.mcp.json](../../../.mcp.json) под `pdf-vector-graph` → `env`. Для BSL MCP (`src/bsl/mcp_server`) переменные читаются через [src/bsl/mcp_server/config.py](../../../src/bsl/mcp_server/config.py).

## 2. Quick start — auth flow с curl

### 2.1 Discovery (RFC 9728 PRM)

```bash
curl http://localhost:8000/.well-known/oauth-protected-resource
# {
#   "resource": "http://localhost:8000",
#   "authorization_servers": ["http://localhost:8000"],
#   "authorization_endpoint": "http://localhost:8000/authorize",
#   "token_endpoint": "http://localhost:8000/token",
#   "code_challenge_methods_supported": ["S256"]
# }
```

### 2.2 Authorization request (PKCE S256)

```bash
# Сгенерировать verifier + challenge
VERIFIER=$(openssl rand -base64 32 | tr -d '=+/' | head -c 43)
CHALLENGE=$(echo -n "$VERIFIER" | openssl dgst -sha256 -binary | base64 | tr -d '=+/' | tr '/+' '_-')

# Запросить code (BSL: GET /authorize, MCP: POST с login/password в форме)
curl "http://localhost:8000/authorize?client_id=mcp-client&redirect_uri=http://localhost/cb&code_challenge=$CHALLENGE&code_challenge_method=S256"
# → 302 Redirect: http://localhost/cb?code=<32-byte-base64url>
```

### 2.3 Token exchange

```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=authorization_code" \
  -d "code=$CODE" \
  -d "redirect_uri=http://localhost/cb" \
  -d "code_verifier=$VERIFIER"
# {
#   "access_token": "...",
#   "token_type": "Bearer",
#   "expires_in": 3600,
#   "refresh_token": "..."
# }
```

### 2.4 Token usage

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/mcp/tools/call
```

### 2.5 Refresh rotation

```bash
curl -X POST http://localhost:8000/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$REFRESH_TOKEN"
# Возвращает новые access + refresh; старый refresh инвалидируется (single-use)
```

## 3. Client integration — Python httpx

```python
import base64
import hashlib
import secrets
import httpx


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


async def acquire_token(base_url: str, client_id: str, redirect_uri: str) -> dict:
    verifier, challenge = pkce_pair()
    async with httpx.AsyncClient() as cli:
        # Step 1: get code (manual user step in real flow)
        r = await cli.get(
            f"{base_url}/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
            follow_redirects=False,
        )
        code = r.next_request.url.params["code"]

        # Step 2: exchange code
        r = await cli.post(
            f"{base_url}/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
        return r.json()
```

## 4. Migration path (BSL legacy → generic)

Legacy импорт продолжает работать через wrapper:

```python
# Старый код — продолжает работать
from src.bsl.mcp_server.auth.oauth2 import OAuth2Service, OAuth2Store

store = OAuth2Store()
service = OAuth2Service(store)
await store.start_cleanup_task(interval=60)
code = await service.generate_authorization_code(
    login="user", password="pw",
    redirect_uri="http://localhost/cb",
    code_challenge=challenge,
)
creds = await service.validate_access_token(token)  # → (login, password) | None
```

Новый код использует generic напрямую:

```python
from src.shared.mcp_oauth import OAuth2Service, OAuth2Store

store = OAuth2Store()
service = OAuth2Service(store)
await store.start_cleanup(interval=60)
code = await service.generate_authorization_code(
    client_id="mcp-client",
    redirect_uri="http://localhost/cb",
    code_challenge=challenge,
    user_data={"role": "admin", "tenant": "acme"},
)
data = await service.validate_access_token(token)  # → dict | None
```

## 5. Troubleshooting

| Симптом | Причина | Решение |
|---|---|---|
| `400 invalid_grant: PKCE validation failed` | `code_verifier` не соответствует `code_challenge` | Убедиться что challenge = `base64url(sha256(verifier))` без padding |
| `400 invalid_grant: Invalid or expired authorization code` | Code TTL истёк (default 600s) либо code уже использован (single-use) | Запросить новый code через `/authorize` |
| `401 invalid_token` | Access token истёк или некорректен | Использовать refresh token через `/token` с `grant_type=refresh_token` |
| `400 invalid_grant: redirect_uri mismatch` | URI на `/token` не совпадает с URI на `/authorize` | Использовать **точно** один и тот же URI на обоих шагах (exact-match) |
| Refresh token не работает после ротации | Каждый refresh — single-use, генерирует новую пару | После каждого refresh **сохранять** новый refresh_token |
| `code_challenge_methods_supported` пусто в PRM | Сервер не объявляет S256 | Проверить версию `src.shared.mcp_oauth` ≥ Phase 6 |

## 6. См. также

- [[oauth2-service]] — API reference + audit
- [RFC 7636 — PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 9728 — Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)
- [openspec hermes-llm-wiki Phase 6 tasks](../../../openspec/changes/hermes-llm-wiki/tasks.md#фаза-6-oauth-21-generalization-p2-m--параллельно)
