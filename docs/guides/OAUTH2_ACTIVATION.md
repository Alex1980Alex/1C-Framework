# Активация OAuth2 для MCP сервера

> ⚠ **Обновление 2026-07-24 (ADR-056):** гайд писался для BSL MCP-прокси `src/bsl/mcp_server` (ретирован). Живая реализация OAuth2 — `src/shared/mcp_oauth` + `build_oauth_router()` (FastAPI); для `pdf-vector-graph` активация через env `MCP_OAUTH_ENABLED=1` и `MCP_OAUTH_*` (см. [09.2 Авторизация](../framework%20documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.2_Авторизация.md)).

## 1. Предварительные условия

- MCP сервер работает (`MCP_AUTH_MODE=none`)
- Python 3.10+ с пакетами: `python-jose`, `cryptography`
- Доступ к `.env` и `src/shared/mcp_oauth/`

## 2. Шаги активации

### Шаг 1: Установить режим

```env
MCP_AUTH_MODE=oauth2
```

### Шаг 2: Настроить TTL токенов

```env
MCP_ACCESS_TOKEN_TTL=3600
MCP_REFRESH_TOKEN_TTL=1209600
MCP_CODE_TTL=120
MCP_ALLOWED_SCOPES=read:documents,write:documents,manage:indexes
```

### Шаг 3: Сгенерировать credentials

```bash
# скрипт-генератор входил в ретированный модуль; credentials генерируются стандартно:
python -c "import secrets; print('Client ID:    ', secrets.token_hex(16)); print('Client Secret:', secrets.token_hex(32))"
```

### Шаг 4: Тест PKCE flow

```bash
# Authorization
curl -X POST http://localhost:8889/oauth/authorize \
  -H "Content-Type: application/json" \
  -d '{"client_id": "ID", "code_challenge": "...", "code_challenge_method": "S256"}'

# Token exchange
curl -X POST http://localhost:8889/oauth/token \
  -H "Content-Type: application/json" \
  -d '{"grant_type": "authorization_code", "code": "CODE", "code_verifier": "..."}'
```

## 3. Полная конфигурация .env

```env
# === AUTH ===
MCP_AUTH_MODE=oauth2
MCP_OAUTH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MCP_OAUTH_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyy
MCP_OAUTH_REDIRECT_URI=http://localhost:8888/oauth/callback
MCP_ACCESS_TOKEN_TTL=3600
MCP_REFRESH_TOKEN_TTL=1209600
MCP_CODE_TTL=120
MCP_ALLOWED_SCOPES=read:documents,write:documents,manage:indexes
```

## 4. Подключение клиентов

### Claude Desktop

```json
{
  "mcpServers": {
    "1c-framework": {
      "url": "http://localhost:8889",
      "auth": { "type": "oauth2", "client_id": "ID", "client_secret": "SECRET" }
    }
  }
}
```

### Cursor / VS Code

Аналогично — указать `url`, `auth.type=oauth2`, credentials.

## 5. Откат

```env
MCP_AUTH_MODE=none
```

Перезапустить сервер. Токены станут невалидными.

## 6. Troubleshooting

| Проблема | Решение |
|----------|---------|
| 401 Unauthorized | Проверить `Authorization: Bearer TOKEN` |
| Token expired | Использовать refresh_token |
| Invalid code_challenge | Проверить S256 хэширование |
| CORS | Добавить redirect_uri в whitelist |
