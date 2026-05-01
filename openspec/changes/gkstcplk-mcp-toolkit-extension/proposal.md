## Why

MCP-toolkit (ROCTUP/1c-mcp-crud v1.5.0) сейчас работает как внешняя обработка (.epf) которую нужно вручную открывать в 1С каждый раз. Это создаёт проблемы: обработка может быть случайно закрыта, нужно помнить о её запуске, и она недоступна для автоматических сценариев (CI/CD, VA BDD тесты). Расширение конфигурации решает эти проблемы — HTTP-сервис запускается автоматически вместе с базой и доступен постоянно.

## What Changes

- Создание расширения конфигурации `гкс_MCPToolkit` (.cfe) с HTTP-сервисом
- HTTP-сервис обрабатывает MCP JSON-RPC запросы (Streamable HTTP transport)
- Перенос серверной логики из модуля формы .epf (12,441 строк) в общие модули расширения
- 9 MCP-инструментов: execute_query, execute_code, get_metadata, get_event_log, get_object_by_link, get_link_of_object, find_references_to_object, get_access_rights, submit_for_deanonymization
- TOON-формат ответов (экономия 30-60% токенов)
- Без NativeAPI компоненты — стандартный HTTP-сервис 1С через веб-сервер (IIS/Apache)
- **Scope OUT**: анонимизация (779 правил) — оставить в .epf для первой версии
- **Scope OUT**: форма подтверждения опасных операций — в расширении автоматически разрешать (или конфигурировать через константу)

## Capabilities

### New Capabilities
- `mcp-http-service`: HTTP-сервис расширения для приёма MCP JSON-RPC запросов. Маршрутизация по method name → обработчик. Streamable HTTP transport (POST /mcp).
- `mcp-query-executor`: Серверный модуль выполнения запросов 1С (execute_query) и произвольного BSL-кода (execute_code) с сериализацией результатов в TOON-формат.
- `mcp-metadata-provider`: Серверный модуль получения метаданных конфигурации (get_metadata), навигационных ссылок, поиска ссылок на объект, прав доступа.

### Modified Capabilities

## Impact

- **Конфигурация**: расширение `гкс_MCPToolkit.cfe` подключается к базе TestDB
- **Веб-сервер**: требуется публикация HTTP-сервиса через IIS (или встроенный веб-сервер 1С 8.3.27)
- **Клиент Claude Code**: `.mcp.json` → URL меняется с `http://localhost:6003/mcp` на `http://KOMPUTER/TestDB/hs/mcp/endpoint`
- **Существующий .epf**: продолжает работать параллельно (обратная совместимость)
- **Безопасность**: execute_code выполняет произвольный BSL — ограничить ролью или константой `гкс_РазрешитьMCPToolkit`
