---
name: 1c-mcp-crud
description: "1c-mcp-crud — MCP доступ к данным и метаданным 1С:Предприятие. ИСПОЛЬЗУЙ когда нужно выполнить запрос к базе 1С, получить метаданные конфигурации, выполнить код 1С, прочитать журнал регистрации, найти ссылки на объект, создать/обновить/провести объект. Триггеры: 'запрос к базе 1С', 'данные из 1С', 'execute_query', 'get_metadata', 'execute_code', 'журнал регистрации', 'навигационная ссылка', 'права доступа роли'. НЕ для написания BSL кода (→ bsl-development), НЕ для документации (→ 1c-doc-research)."
---

# 1c-mcp-crud — MCP доступ к данным и метаданным 1С:Предприятие

> **Историческая справка.** Раньше использовался MCP-сервер `1c-mcp-toolkit` (ROCTUP, .epf на порту 6003) — он **отключён** и удалён из активной конфигурации. На замену пришёл **`1c-mcp-crud`**: Python stdio-процесс, который ходит в 1С через IIS-публикацию `/hs/mcp/rpc` и расширение `MCP_Сервер`. Tool prefix в Claude Code: **`mcp__1c-mcp-crud__*`**.

## Обзор

MCP-сервер для работы с базой 1С:Предприятие через AI-агентов. Расширенный набор инструментов (17 tools) поверх HTTP-сервиса 1С:

| Возможность | Tools |
|---|---|
| Запросы и BSL-код | `execute_query`, `validate_query`, `execute_code`, `get_bsl_syntax_help` |
| Чтение метаданных | `get_metadata`, `get_metadata_structure`, `get_metadata_tree`, `list_metadata_objects` |
| Чтение форм | `get_form_structure` |
| Поиск по коду конфигурации | `search_code` |
| CRUD объектов | `create_object`, `update_object`, `post_document`, `mark_for_deletion` |
| Навигационные ссылки | `get_link_of_object`, `get_object_by_link` |
| Анализ зависимостей | `find_references_to_object` |
| Безопасность и аудит | `get_access_rights`, `get_event_log` |

## Триггеры

- 'запрос к базе 1С', 'данные из 1С', 'прочитать справочник', 'прочитать документ'
- 'execute_query', 'validate_query', 'get_metadata', 'execute_code'
- 'структура формы', 'get_form_structure'
- 'create_object', 'update_object', 'post_document', 'mark_for_deletion'
- 'журнал регистрации', 'get_event_log'
- 'навигационная ссылка', 'права доступа роли', 'ссылки на объект'

НЕ для анализа BSL-кода — используй `bsl-development`.
НЕ для справки по API платформы 8.3.27 — используй `1c-doc-research`.
НЕ для написания тестов — используй `va-bdd-testing` / YaXUnit.

## Архитектура

```
Claude Code ──MCP stdio──► Python entrypoint ──HTTP Basic──► IIS /hs/mcp/rpc ──► База 1С (TestDB)
                           mcp_entrypoint.py                  расширение MCP_Сервер
```

- Python-процесс стартует Claude Code как stdio MCP-server
- Каждый tool-call оборачивается в HTTP-запрос к публикации 1С (`MCP_ONEC_URL`)
- HTTP Basic-авторизация (`MCP_ONEC_USERNAME` / `MCP_ONEC_PASSWORD` в `env`)
- 1С отвечает синхронно: данные/ошибка/контекст вернутся в response

В отличие от старого toolkit:
- **Не нужна открытая 1С-сессия с .epf** — сервер работает через регулярную IIS-публикацию
- **Транспорт stdio**, а не HTTP :6003 — не требует отдельного прокси
- **Шире набор tools** — добавлены write-операции (`create_object`/`update_object`/`post_document`) и расширенный анализ метаданных

## Конфигурация (`.mcp.json`)

```json
"1c-mcp-crud": {
  "command": "D:\\1C-Enterprise_Framework\\src\\external\\1c_mcp\\venv\\Scripts\\python.exe",
  "args": ["D:\\1C-Enterprise_Framework\\src\\external\\1c_mcp\\mcp_entrypoint.py"],
  "env": {
    "PYTHONIOENCODING": "utf-8",
    "MCP_ONEC_URL": "http://localhost/TestDB",
    "MCP_ONEC_USERNAME": "<user>",
    "MCP_ONEC_PASSWORD": "<password>"
  },
  "timeout": 60000
}
```

В проекте дополнительно настроены экземпляры под другие базы: `1c-mcp-crud-infeeda`, `1c-mcp-crud-dev39144`, `1c-mcp-crud-daily` — отличаются `MCP_ONEC_URL`.

## Точные параметры API (общие c унаследованным toolkit)

### `execute_query` — запросы 1С

```json
{"query": "ВЫБРАТЬ ПЕРВЫЕ 10 Код, Наименование ИЗ Справочник.Номенклатура"}
```

С параметрами:
```json
{
  "query": "ВЫБРАТЬ * ИЗ Документ.Х ГДЕ Контрагент = &К",
  "params": {
    "К": {"_objectRef": true, "УникальныйИдентификатор": "uuid", "ТипОбъекта": "СправочникСсылка.Контрагенты"}
  }
}
```

Ссылки в результате — `{_objectRef: true, "УникальныйИдентификатор": "uuid", "ТипОбъекта": "..."}`.

### `validate_query` — синтаксическая проверка ДО исполнения

Принимает тот же `query`, не выполняет — возвращает ошибку компиляции либо OK. Использовать всегда **перед** `execute_query` на проде.

### `execute_code` — выполнение BSL

```json
{"code": "Результат = ТекущаяДатаСеанса();"}
```

Результат пишется в переменную `Результат`. Возвращается строка/JSON-сериализация.

### `get_metadata` / `get_metadata_structure` / `get_metadata_tree` / `list_metadata_objects`

- `get_metadata_tree` — полное дерево конфигурации (все типы объектов)
- `list_metadata_objects` — список объектов одного типа (все справочники, все документы)
- `get_metadata` — короткие реквизиты одного объекта
- `get_metadata_structure` — расширенная структура (ТЧ, формы, команды). Параметр `metaType` (английский enum) + `name`.

### `get_form_structure` — элементы формы

Возвращает имена и типы элементов формы (Button/InputField/Table и т.п.), DataPath, видимость/обязательность. Ключевой инструмент для написания VA BDD тестов.

### `search_code` — поиск по коду конфигурации

Текстовый поиск по BSL-модулям конфигурации (без LSP). Дополняет `bsl-semantic-search`.

### `get_bsl_syntax_help`

Локальная справка по синтаксису BSL — без обращения к платформенному `bsl-platform-context`.

### `create_object` / `update_object` / `post_document` / `mark_for_deletion`

Запись в базу. Использовать **только в TestDB** или с явного подтверждения пользователя. На проде предпочесть `execute_code` с серверной транзакцией.

### `get_link_of_object` / `get_object_by_link`

Конвертация между `{_objectRef: ...}` и навигационной ссылкой `e1cib/data/...?ref=...`. Ключевая пара для последовательных вызовов.

### `find_references_to_object`

Параметры:
- `target_object_description` — `{_objectRef: true, ...}` (обязательно)
- `search_scope` — массив **на английском**: `documents`, `catalogs`, `information_registers`, `accumulation_registers`, `accounting_registers`, `calculation_registers`
- `limit_hits` (default 200), `limit_per_meta` (default 20), `timeout_budget_sec` (default 30)

### `get_access_rights`

```json
{"metadata_object": "Справочник.гкс_ГруппыТС"}
```

Возвращает список ролей и их прав на объект — Чтение/Изменение/Просмотр и т.д.

### `get_event_log`

```json
{"count": 20}
```

Дополнительные параметры: `start_date`, `end_date`, `level` (Information/Error/Warning).

## Типичные цепочки вызовов

### Получить данные объекта по коду

```
1. execute_query("ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ Справочник.X ГДЕ Код = '1'")
   → _objectRef с UUID
2. get_link_of_object(object_description={_objectRef...})
   → навигационная ссылка
3. get_object_by_link(link="e1cib/data/...")
   → все реквизиты объекта
```

### Найти где используется объект

```
1. execute_query("ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ Справочник.X ГДЕ Код = '1'")
2. find_references_to_object(target_object_description={_objectRef...},
                             search_scope=["documents","information_registers"])
```

### Безопасный SQL на live-данных

```
1. validate_query(query="...")        # синтаксическая проверка
2. execute_query(query="...")         # с ПЕРВЫЕ N или ГДЕ
3. оценить результат
4. (опционально) execute_code         # для CRUD-цикла внутри транзакции
```

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `ВЫБРАТЬ * ИЗ Справочник.Номенклатура` без `ПЕРВЫЕ` | Тысячи записей, таймаут | Всегда `ВЫБРАТЬ ПЕРВЫЕ N` или фильтр `ГДЕ` |
| `execute_code` для простого чтения | Излишне, сложнее отладить | Использовать `execute_query` |
| Запись в продовую базу без подтверждения | Необратимые изменения | Сначала TestDB; для прода — явное согласие пользователя |
| Игнорировать `validate_query` перед `execute_query` | Падение на синтаксисе после долгого ожидания | Всегда `validate_query` сначала |
| Русские названия типов в `find_references_to_object.search_scope` | Сервер ждёт английский enum | `documents`, `catalogs`, `information_registers`, ... |
| Использовать `localhost` в `Srvr=` 1С-предприятия | "Определение принадлежности процессов" | Использовать hostname машины (`KOMPUTER` и т.п.) |

## Диагностика

| Проблема | Причина | Решение |
|----------|---------|---------|
| MCP-сервер не стартует | Питон-venv в `MCP_ONEC_*` нет / битый путь | Проверить `command`/`args` в `.mcp.json` |
| 401/403 от IIS | Неверный `MCP_ONEC_USERNAME` / `MCP_ONEC_PASSWORD` | Обновить env в `.mcp.json` |
| 404 на `/hs/mcp/rpc` | Не опубликована конфигурация на IIS, либо нет расширения `MCP_Сервер` | Опубликовать через `webinst.exe`, проверить расширение |
| Таймаут `execute_query` | Тяжёлый запрос | `ПЕРВЫЕ N`, оптимизация запроса, рост `timeout` в `.mcp.json` |
| Кракозябры в ответах | cp1251 stdout на Windows | `PYTHONIOENCODING=utf-8` в `env` (включено по умолчанию) |
| `object_description must contain '_objectRef'` | Неправильный формат для `get_link_of_object` / `find_references_to_object` | Обернуть в `{_objectRef: true, УникальныйИдентификатор: "uuid", ТипОбъекта: "..."}` |
| `Invalid search scope` в `find_references_to_object` | Русские названия | Использовать английский enum |
| `link required` в `get_object_by_link` | Параметр иначе | Параметр называется `link`, не `navigation_link` |

## Ссылки

- Регистрация в `.mcp.json` — [строки 1c-mcp-crud / 1c-mcp-crud-infeeda / 1c-mcp-crud-dev39144 / 1c-mcp-crud-daily](../../../.mcp.json)
- Подсистема памяти и токен-экономии — `mcp__memory-orchestrator__*`
- Тестирование через VA BDD — skill `va-bdd-testing`, использует `1c-mcp-crud` как источник проверок (Stage 4a)
- Анализ задачи — skill `analyze-1c-task-v2` (использует `1c-mcp-crud` для проверки реквизитов и валидации запросов)
- Реализация задачи — skill `implement-1c-task` (обязательные циклы `validate_query` → `execute_query` → запись через EDT-MCP)
