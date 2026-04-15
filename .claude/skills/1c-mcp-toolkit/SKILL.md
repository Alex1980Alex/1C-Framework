---
name: 1c-mcp-toolkit
description: "1c-mcp-toolkit — MCP доступ к данным и метаданным 1С:Предприятие. ИСПОЛЬЗУЙ когда нужно выполнить запрос к базе 1С, получить метаданные конфигурации, выполнить код 1С, прочитать журнал регистрации, найти ссылки на объект. Триггеры: 'запрос к базе 1С', 'данные из 1С', 'execute_query', 'get_metadata', 'execute_code', 'журнал регистрации', 'навигационная ссылка', 'права доступа роли'. НЕ для написания BSL кода (→ bsl-development), НЕ для документации (→ 1c-doc-research)."
---

# 1c-mcp-toolkit — MCP доступ к данным и метаданным 1С:Предприятие

## Обзор

MCP-сервер для работы с базой 1С:Предприятие через AI-агенты. 9 инструментов: запросы, выполнение кода, метаданные, журнал регистрации, навигационные ссылки, права доступа, анонимизация. Встроенный NativeAPI HTTP-сервер в .epf (без Docker). TOON-формат (экономия 30-60% токенов).

**Сервер:** ROCTUP/1c-mcp-toolkit v1.5.0 (Native HTTP)
**Репозиторий:** https://github.com/ROCTUP/1c-mcp-toolkit

## Триггеры

- 'запрос к базе 1С', 'данные из 1С', 'прочитать справочник', 'прочитать документ'
- 'execute_query', 'get_metadata', 'execute_code', '1c-mcp-toolkit'
- 'метаданные конфигурации', 'структура базы', 'журнал регистрации'
- 'навигационная ссылка', 'права доступа роли', 'ссылки на объект'
- 'создать документ в 1С', 'провести документ', 'записать справочник'

НЕ для анализа BSL-кода — используй `bsl-development`.
НЕ для справки по API платформы — используй `1c-doc-research`.
НЕ для тестирования — используй Vanessa/YaXUnit.

## Архитектура

```
Claude Code ──MCP (Streamable HTTP)──► .epf в 1С (NativeAPI HTTP-сервер :6003) ──► База данных
                                       Режим Предприятие, TOON-формат, анонимизация
```

- .epf запускает встроенный HTTP-сервер (NativeAPI MCPHttpTransport)
- Claude Code подключается напрямую по Streamable HTTP
- Обработка выполняет команду в контексте базы 1С
- Ответ в TOON-формате (экономия 30-60% токенов vs JSON)

## Установка и настройка

### Docker (прокси-сервер)

```bash
docker run -d -p 6003:6003 \
  -e ALLOW_DANGEROUS_WITH_APPROVAL=true \
  --restart unless-stopped \
  --name 1c-mcp-toolkit-proxy \
  roctup/1c-mcp-toolkit-proxy
```

Проверка: `docker logs 1c-mcp-toolkit-proxy` — должно быть `Uvicorn running on http://0.0.0.0:6003`.

### Обработка 1С (.epf)

1. Скачать `MCP_Toolkit.epf` из `build/` репозитория (или `tools/1c-mcp-toolkit/`)
2. Открыть в 1С в режиме **Предприятие** (НЕ конфигуратор)
3. Указать URL прокси: `http://localhost:6003`
4. Нажать **Подключить**
5. Должно появиться: "Успешное подключение к серверу"

Обработка должна быть **открыта всё время** работы. Закрыл — связь пропала.

### Конфигурация MCP

Добавить в `.mcp/bsl.json`:

```json
"1c-mcp-toolkit": {
  "url": "http://localhost:6003/mcp",
  "timeout": 180000
}
```

> **Доп. инструменты (не описаны ниже):** `get_metadata_structure`, `list_metadata_objects`. Контракт параметров отличается от `get_metadata` (требует `metaType` из английского enum + `name`). Точный API и антипаттерны — [cache/get_metadata_structure-api.md](cache/get_metadata_structure-api.md).

## 8 MCP-инструментов (все протестированы 2026-03-12)

| Tool | Назначение | Когда использовать | Статус |
|------|-----------|-------------------|--------|
| `execute_query` | Запросы на языке 1С | Чтение данных, отчёты, поиск | ✅ |
| `execute_code` | Выполнение произвольного BSL | Создание/проведение документов, сложные операции | ✅ |
| `get_metadata` | Структура конфигурации | Узнать какие объекты есть, их количество | ✅ |
| `get_event_log` | Журнал регистрации | Диагностика, аудит, поиск ошибок | ✅ |
| `get_object_by_link` | Объект по навигационной ссылке | Получить данные конкретного объекта | ✅ |
| `get_link_of_object` | Навигационная ссылка из описания | Сгенерировать ссылку для get_object_by_link | ✅ |
| `find_references_to_object` | Ссылки на объект в метаданных | Анализ зависимостей, impact analysis | ✅ |
| `get_access_rights` | Права ролей к объекту | Аудит безопасности, проверка доступа | ✅ |

## Точные параметры API (проверено тестированием)

### 1. execute_query

```json
{"query": "ВЫБРАТЬ ПЕРВЫЕ 10 Код, Наименование ИЗ Справочник.Номенклатура"}
```

С параметрами:
```json
{"query": "ВЫБРАТЬ * ИЗ Документ.Х ГДЕ Контрагент = &К", "params": {"К": {"_objectRef": true, "УникальныйИдентификатор": "uuid", "ТипОбъекта": "СправочникСсылка.Контрагенты"}}}
```

Результат: `{success: true, data: "[N]{колонки}:\n  строка1\n  строка2"}`. Ссылки возвращаются как `{_objectRef: true, "УникальныйИдентификатор": "uuid", "ТипОбъекта": "..."}`.

### 2. execute_code

```json
{"code": "Результат = ТекущаяДатаСеанса();"}
```

Результат записывается в переменную `Результат`. Возвращает: `{success: true, data: "\"2026-03-11T23:46:18Z\""}`.

### 3. get_metadata

```json
{}
```

Без параметров — вся конфигурация. Возвращает: типы объектов + количество + свойства конфигурации (имя, версия, режим запуска и т.д.).

### 4. get_event_log

```json
{"count": 20}
```

Параметры: `count`, `start_date`, `end_date`, `level` (Information/Error/Warning). Возвращает до 100 записей: date, level, event, comment, user, metadata, session, application, computer, transaction_status.

### 5. get_object_by_link

**Параметр: `link`** (НЕ `navigation_link`!)

```json
{"link": "e1cib/data/Справочник.гкс_ГруппыТС?ref=813500505694551b11f0bbeb6a935645"}
```

Возвращает все реквизиты объекта: код, наименование, все поля. Ссылку можно получить через execute_code + `ПолучитьНавигационнуюСсылку()` или через `get_link_of_object`.

### 6. get_link_of_object

**Параметр: `object_description`** (object с обязательным `_objectRef: true`)

```json
{"object_description": {"_objectRef": true, "УникальныйИдентификатор": "6a935645-bbeb-11f0-8135-00505694551b", "ТипОбъекта": "СправочникСсылка.гкс_ГруппыТС"}}
```

Возвращает навигационную ссылку `e1cib/data/...?ref=...` для использования в `get_object_by_link`.

### 7. get_access_rights

```json
{"metadata_object": "Справочник.гкс_ГруппыТС"}
```

Возвращает: тип метаданных, список применимых прав (Чтение, Добавление, Изменение, Удаление, Просмотр, ИнтерактивноеДобавление, Редактирование, и т.д.), роли и их настройки.

### 8. find_references_to_object

**Параметры:**
- `target_object_description` — объект с `_objectRef: true` (обязательно)
- `search_scope` — массив строк **на английском**: `documents`, `catalogs`, `information_registers`, `accumulation_registers`, `accounting_registers`, `calculation_registers`

```json
{
  "target_object_description": {"_objectRef": true, "УникальныйИдентификатор": "uuid", "ТипОбъекта": "СправочникСсылка.гкс_ГруппыТС"},
  "search_scope": ["documents", "catalogs", "information_registers"]
}
```

Дополнительные параметры: `limit_hits` (default 200), `limit_per_meta` (default 20), `timeout_budget_sec` (default 30).

## Типичные цепочки вызовов

### Получить данные объекта по коду

```
1. execute_query("ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ Справочник.X ГДЕ Код = '1'")
   → получаем _objectRef с UUID
2. get_link_of_object(object_description={_objectRef...})
   → получаем навигационную ссылку
3. get_object_by_link(link="e1cib/data/...")
   → получаем все реквизиты объекта
```

### Найти где используется объект

```
1. execute_query("ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ Справочник.X ГДЕ Код = '1'")
   → получаем _objectRef
2. find_references_to_object(target_object_description={_objectRef...}, search_scope=["documents","information_registers"])
   → список всех ссылающихся объектов
```

### Получить дату сервера

```
execute_code(code="Результат = ТекущаяДатаСеанса();")
→ "2026-03-11T23:46:18Z"
```

## Каналы изоляции

При подключении нескольких баз 1С к одному прокси — используй каналы:

- Обработка в 1С: указать channel в URL прокси `http://localhost:6003?channel=dev`
- REST API: добавить `?channel=dev` к запросам

Это позволяет разделить dev/prod потоки через один Docker-контейнер.

## Запуск 1С:Предприятие

**ВАЖНО:** Использовать hostname `KOMPUTER`, НЕ `localhost` (иначе ошибка "определение принадлежности клиентского и серверного процессов").

```bash
"C:/Program Files/1cv8/8.3.27.1859/bin/1cv8.exe" ENTERPRISE /S"KOMPUTER/TestDB" /N"a.novozhenin.da@sodrugestvo.local" /P"Alex1980Alex"
```

## Текущее окружение

| Параметр | Значение |
|----------|----------|
| Режим | **Встроенный NativeAPI HTTP-сервер** (без Docker) на порту 6003 |
| Обработка .epf | `D:\1С-Framework\tools\1c-mcp-toolkit\MCP_Toolkit_v1.5.0.epf` |
| База | TestDB (`Srvr="KOMPUTER";Ref="TestDB"`) |
| Конфигурация | УправлениеТранспортомНаПЛК v2026.3.1.0 |
| Платформа | 8.3.27.1859 |
| Объекты | 91 справочник, 27 документов, 191 РС, 1 РН, 710 общих модулей, 105 перечислений |
| MCP конфиг | `.mcp.json` → `1c-mcp-toolkit` (Streamable HTTP) |
| Формат ответов | TOON (экономия 30-60% токенов) |
| Анонимизация | Включена (779 правил по умолчанию) |
| Все 9 tools | ✅ протестированы 2026-04-01 |

## Диагностика

| Проблема | Причина | Решение |
|----------|---------|---------|
| Docker error "pipe not found" | Docker Desktop не запущен | Запустить Docker Desktop, подождать 30 сек |
| "Not Acceptable" на /mcp | Неправильный Accept header | Нужен `Accept: application/json, text/event-stream` |
| "Missing session ID" | Повторный запрос без ID сессии | Сохранять `Mcp-Session-Id` из response headers |
| Кракозябры в ответах | cp1251 stdout на Windows | `PYTHONIOENCODING=utf-8` + `io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` |
| curl UTF-8 ошибки с кириллицей | Windows curl не передаёт UTF-8 JSON | Использовать Python `requests` вместо curl |
| "204 No Content" на /1c/poll | Нормально — нет команд в очереди | Обработка ждёт команду, всё ok |
| Обработка не подключается | Неверный URL прокси | Проверить `http://localhost:6003` в .epf |
| Контейнер не стартует | Порт 6003 занят | `docker ps` проверить, `docker rm -f` старый |
| Таймаут execute_query | Тяжёлый запрос | Добавить `ПЕРВЫЕ N`, оптимизировать запрос |
| "object_description must contain '_objectRef'" | Неправильный формат для get_link/find_refs | Нужен `{_objectRef: true, УникальныйИдентификатор: "uuid", ТипОбъекта: "..."}` |
| "Invalid search scope" в find_references | Русские названия типов | Использовать **английские**: `documents`, `catalogs`, `information_registers` |
| "определение принадлежности процессов" при запуске 1С | `localhost` не резолвится корректно | Использовать hostname `KOMPUTER` вместо `localhost` |
| Ошибка validation `link` required | Параметр назван иначе | `get_object_by_link` → param `link`, НЕ `navigation_link` |

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `ВЫБРАТЬ * ИЗ Справочник.Номенклатура` без ПЕРВЫЕ | Вернёт тысячи записей, таймаут | Всегда `ВЫБРАТЬ ПЕРВЫЕ N` или фильтр ГДЕ |
| Закрыть обработку в 1С | Связь с прокси пропадёт | Держать .epf открытым всё время |
| Менять конфигурацию для MCP | Не нужно, .epf работает без этого | Использовать внешнюю обработку |
| execute_code для простого чтения | Излишне, сложнее отладить | Использовать execute_query |
| Игнорировать include_schema | Не знаешь типы колонок | Добавить `include_schema=true` при первом запросе |
