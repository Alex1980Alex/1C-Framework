# Пайплайн (trivial): Fix codepilot1c MCP `-32000`

Дата: 2026-06-21 · Тип: trivial (1 файл config + 1 GUI-действие пользователя в EDT)

## План
MCP-сервер `codepilot1c` не переподключался (`/mcp` → `-32000`). Цель — восстановить подключение Claude Code к встроенному MCP-хосту плагина EDT `com.codepilot1c` (1C Copilot) на `http://127.0.0.1:8766/mcp`.

## Дизайн
Диагностика показала ДВЕ причины:
1. **Хост не запущен** — порт 8766 без слушателя (`Get-NetTCPConnection`), плагин установлен (p2 pool + `bundles.info`), но MCP Host opt-in и не включён в workspace (нет prefs/лога). Авторег `org.eclipse.ui.startup → McpHostStartup` не стартует выключенный хост.
2. **Рассинхрон токена** — режим «OAuth 2.1 + Bearer»; статичный Bearer в [.mcp.json](file:///C:/1С-Framework/.mcp.json) (`cpedt-local-8766-tkn`) ≠ реальному резервному токену плагина → 401. Токен плагина хранится в Eclipse secure storage (`TOKEN_SECURE_KEY`) — извне не задаётся.

Решение: (1) пользователь включает MCP Host в *Preferences → 1C Copilot → MCP Хост* (порт 8766); (2) синхронизировать Bearer-токен в `.mcp.json` с тем, что в поле плагина. Альтернатива (отклонена как более тяжёлая): OAuth-режим без `--header` → браузерный флоу.

## Реализация
- Пользователь включил «Включить MCP-хост» + «Включить HTTP-эндпоинт», порт 8766 → статус «● Сервер запущен и отвечает по HTTP».
- Правка [.mcp.json](file:///C:/1С-Framework/.mcp.json): Bearer `cpedt-local-8766-tkn` → `1eb53fe74a9ab743a335159b81572b53c6a399f4c9b82584` (реальный токен плагина).
- Рецепт сохранён в память: `reference_codepilot1c_mcp_host.md` + строка в `MEMORY.md`.

## Тест
- Live-probe `POST /mcp` initialize:
  - токен `1eb53…` → **HTTP 200**, `serverInfo: CodePilot1C MCP Host v1.3.0` (tools/prompts/resources). ✅
  - старый `cpedt-local-8766-tkn` → **401 Unauthorized** (подтверждает корень). ✅
- `.mcp.json` валиден (`ConvertFrom-Json` OK). ✅
- Остаётся пользователю: `/mcp reconnect` (Claude Code перечитает конфиг). Caveat: ротация токена в EDT / закрытие EDT → повторный `-32000`.

## Доп-итерация: токен верный, а reconnect всё равно -32000
Корень №3 — **mcp-remote игнорирует статичный Bearer и принудительно идёт в OAuth**: сервер анонсирует OAuth-discovery (`.well-known/oauth-protected-resource` + `oauth-authorization-server` → 200), mcp-remote делает dynamic client registration + token-flow (пишет `~/.mcp-auth/mcp-remote-0.1.37/<hash>_{client_info,code_verifier,tokens}.json`), который headless'но не доводится → `-32000`. Чистка кэша не помогает — mcp-remote пересоздаёт его при каждом старте (метки времени подтвердили).

**Финальное решение:** убрать mcp-remote из цепочки — перевести `codepilot1c` на нативный HTTP-транспорт Claude Code с Bearer-заголовком:
```json
"codepilot1c": { "type": "http", "url": "http://127.0.0.1:8766/mcp", "headers": { "Authorization": "Bearer <token>" } }
```
Нативный клиент шлёт заголовок напрямую; OAuth-дискавери mcp-remote не запускается. `~/.mcp-auth`-кэш вычищен (не используется).

**Fallback** (если нативный HTTP-клиент тоже уйдёт в OAuth): сменить в EDT *1C Copilot → MCP Хост → Режим авторизации* на **«Только Bearer»** (сервер перестанет анонсировать OAuth) — server-side, надёжнее всего.
