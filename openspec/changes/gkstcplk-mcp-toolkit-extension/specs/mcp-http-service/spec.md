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

### Requirement: Маршрутизация по MCP-протоколу

Сервис MUST маршрутизировать JSON-RPC методы по следующим правилам:

- `method: "initialize"` → возвращает capabilities сервера
- `method: "tools/list"` → возвращает список 9 инструментов
- `method: "tools/call"` → маршрутизирует по `params.name` к обработчику
- Неизвестный метод → JSON-RPC error `-32601` (Method not found)

#### Scenario: tools/list возвращает инструменты

- **WHEN** клиент шлёт `{"method": "tools/list"}`
- **THEN** ответ содержит массив `tools[]` с 9 элементами

#### Scenario: неизвестный метод

- **WHEN** клиент шлёт `{"method": "unknown/foo"}`
- **THEN** ответ содержит `error.code = -32601` и `error.message = "Method not found"`

### Requirement: Защита доступа

Сервис MUST проверять авторизацию перед обработкой каждого запроса:

- Проверка константы `гкс_РазрешитьMCPToolkit` перед выполнением
- Если `Ложь` → HTTP 403 Forbidden
- Роль `гкс_МСPToolkit` для доступа к HTTP-сервису

#### Scenario: kill switch выключен

- **WHEN** константа `гкс_РазрешитьMCPToolkit = Ложь`, клиент шлёт валидный запрос
- **THEN** сервис возвращает HTTP 403 Forbidden, запрос не обрабатывается

#### Scenario: пользователь без роли

- **WHEN** клиент аутентифицирован, но не имеет роль `гкс_МСPToolkit`
- **THEN** сервис возвращает HTTP 403 Forbidden

### Requirement: Совместимость с Claude Code

Ответы сервиса MUST соответствовать MCP-протоколу Claude Code:

- Ответ в формате MCP JSON-RPC 2.0
- Поддержка `Mcp-Session-Id` header для stateful сессий
- TOON-формат в `content[].text` для экономии токенов

#### Scenario: stateful сессия

- **WHEN** клиент шлёт второй запрос с тем же `Mcp-Session-Id`
- **THEN** сервис восстанавливает контекст сессии (например, ранее открытую транзакцию)

#### Scenario: TOON-формат в content

- **WHEN** инструмент возвращает структурированные данные (массив объектов)
- **THEN** `content[].text` содержит TOON-сериализацию (column-major табличный формат для экономии токенов)
