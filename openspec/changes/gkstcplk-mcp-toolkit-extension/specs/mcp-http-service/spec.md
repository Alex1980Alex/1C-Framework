## ADDED Requirements

### Requirement: HTTP-сервис принимает MCP JSON-RPC запросы

HTTP-сервис `гкс_MCP` MUST принимать MCP JSON-RPC запросы с корневым URL `/mcp`.

- Шаблон URL: `/endpoint` (полный путь: `/hs/mcp/endpoint`)
- Метод: POST
- Content-Type: application/json
- Accept: application/json, text/event-stream

#### Scenario: валидный MCP запрос

- **WHEN** клиент шлёт POST `/hs/mcp/endpoint` с `Content-Type: application/json` и валидным JSON-RPC payload
- **THEN** сервис принимает запрос и передаёт его в маршрутизатор методов

### REQ-2: Маршрутизация по MCP-протоколу
- `method: "initialize"` → возвращает capabilities сервера
- `method: "tools/list"` → возвращает список 9 инструментов
- `method: "tools/call"` → маршрутизирует по `params.name` к обработчику
- Неизвестный метод → JSON-RPC error -32601 (Method not found)

### REQ-3: Защита доступа
- Проверка константы `гкс_РазрешитьMCPToolkit` перед выполнением
- Если `Ложь` → HTTP 403 Forbidden
- Роль `гкс_МСPToolkit` для доступа к HTTP-сервису

### REQ-4: Совместимость с Claude Code
- Ответ в формате MCP JSON-RPC 2.0
- Поддержка `Mcp-Session-Id` header для stateful сессий
- TOON-формат в `content[].text` для экономии токенов
