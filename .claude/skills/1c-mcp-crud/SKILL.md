---
name: 1c-mcp-crud
description: "1c-mcp-crud — MCP доступ к данным и метаданным 1С:Предприятие. ИСПОЛЬЗУЙ когда нужно выполнить запрос к базе 1С, получить метаданные конфигурации, выполнить код 1С, прочитать журнал регистрации, найти ссылки на объект, создать/обновить/провести объект. Триггеры: 'запрос к базе 1С', 'данные из 1С', 'execute_query', 'get_metadata', 'execute_code', 'журнал регистрации', 'навигационная ссылка', 'права доступа роли'. НЕ для написания BSL кода (→ bsl-development), НЕ для документации (→ 1c-doc-research)."
---

# 1c-mcp-crud — MCP доступ к данным и метаданным 1С:Предприятие

> **Историческая справка.** Раньше использовался MCP-сервер `1c-mcp-toolkit` (ROCTUP, .epf на порту 6003) — он **отключён** и удалён из активной конфигурации. На замену пришёл **`1c-mcp-crud`**: Python stdio-процесс, который ходит в 1С через IIS-публикацию `/hs/mcp/rpc` и расширение `MCP_Сервер`. Tool prefix в Claude Code: **`mcp__1c-mcp-crud__*`**.

## Обзор

MCP-сервер для работы с базой 1С:Предприятие через AI-агентов. **19 инструментов** поверх HTTP-сервиса 1С (эталон — live `tools/list`, проверено 2026-06-19 на базе `transport`):

| Возможность | Tools | Кол-во |
|---|---|---|
| Запросы и BSL-код | `execute_query`, `validate_query`, `execute_code`, `get_bsl_syntax_help` | 4 |
| Чтение метаданных | `get_metadata`, `get_metadata_structure`, `get_metadata_tree`, `list_metadata_objects` | 4 |
| Чтение форм | `get_form_structure` | 1 |
| Поиск по коду конфигурации | `search_code` | 1 |
| CRUD объектов | `create_object`, `update_object`, `post_document`, `mark_for_deletion` | 4 |
| Навигационные ссылки | `get_link_of_object`, `get_object_by_link` | 2 |
| Анализ зависимостей | `find_references_to_object` | 1 |
| Безопасность и аудит | `get_access_rights`, `get_event_log` | 2 |

> **Состав = 19** (live tools/list). `submit_for_deanonymization` фигурирует в некоторых сборках расширения, но в **текущей боевой сборке (`transport`) его НЕТ** — не закладываться на него. Полная боевая `.cfe` весит ~70 KB; копия `external/1c_mcp/build/MCP_Сервер.cfe` (~41 KB) **устарела** и отдаёт лишь 2 инструмента — для восстановления её НЕ использовать (см. Диагностику).

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
Claude Code ──MCP stdio──► Python launcher ──HTTP Basic──► веб-сервер (Apache/IIS) /<база>/hs/mcp/rpc ──► База 1С
                           mcp_1c_stdio_launcher.py          расширение MCP_Сервер
```

> Боевой инстанс смотрит на публикацию `transport` через **Apache** (`C:\Apache24`, см. `httpd.conf` → `Alias "/transport"` + `default.vrd`). Health-эндпоинт: `GET http://localhost/transport/hs/mcp/health` → `{"status":"ok"}`.

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
  "command": "C:\\1С-Framework\\external\\1c_mcp\\venv\\Scripts\\python.exe",
  "args": ["C:\\1С-Framework\\scripts\\mcp_1c_stdio_launcher.py"],
  "cwd": "C:\\1С-Framework\\external\\1c_mcp",
  "env": {
    "PYTHONPATH": "C:\\1С-Framework\\external\\1c_mcp",
    "PYTHONIOENCODING": "utf-8",
    "MCP_ONEC_URL": "http://localhost/transport",
    "MCP_ONEC_SERVICE_ROOT": "mcp",
    "MCP_ONEC_USERNAME": "<user>@sodru.com",
    "MCP_ONEC_PASSWORD": "<password>"
  },
  "timeout": 60000
}
```

- Entrypoint — **`scripts/mcp_1c_stdio_launcher.py`** (шим: parent-repo `src/` коллидирует с `external/1c_mcp/src/`; launcher делает `chdir` + `sys.path.insert` к сабмодулю). НЕ `mcp_entrypoint.py`.
- Домен логина — **`@sodru.com`** (НЕ `@sodrugestvo.ru`/`@sodrugestvo.by`; у разных пользователей базы домены различаются — см. [[feedback-1c-mcp-crud-login-domain]]).
- Прямой вызов сервиса в обход незарегистрированного MCP — его же клиентом `external/1c_mcp/src/py_server/onec_client.py` (`OneCClient` → Basic-auth → JSON-RPC `tools/call`/`tools/list`/`GET /health`).

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

Возвращает права по ролям на объект — Чтение/Добавление/Изменение/Удаление/Просмотр и т.д. С параметром `user_name` — эффективные права конкретного пользователя (а не список ролей): `{"metadata_object": "Справочник.Пользователи", "user_name": "o.karankevich@sodru.com"}`.

### `get_event_log`

```json
{"limit": 50, "levels": "Error,Warning"}
```

Параметры (live-схема): `limit` (default 50), `levels` (CSV: `Information,Warning,Error,Note`), `start_date`/`end_date` (ISO 8601, по умолчанию — последний час), `events` (CSV имён событий), `user` (CSV), `metadata_type` (FQN-фильтр). **NB:** параметр называется `limit`/`levels` (НЕ `count`/`level`).

> **Семантика лимитирования (важно при правке обработчика расширения).** В обработчике `ПолучитьЖурналРегистрации` журнал выгружается в `ТаблицаЗначений`, а у этой перегрузки `ВыгрузитьЖурналРегистрации(ТЗ, Отбор, КолонкиВыборки)` **параметра-количества НЕТ** (3-й позиционный = «КолонкиВыборки»; число молча игнорируется, строка → «Неправильное имя колонки»). Поэтому `limit` каплится **обрезкой BSL-цикла** (`Если Записи.Количество() >= Лимит Тогда Прервать`) + сортировкой `ТаблицаЖурнала.Сортировать("Дата Убыв")` (самые свежие N). Колонка уровня — `Уровень` (НЕ `УровеньЖурналаРегистрации`). Раньше инструмент был сломан (всегда `count:0` — отсутствовал `Записи.Добавить`; `limit` не работал) — **исправлено и развёрнуто 2026-06-19** (`MCP_Сервер_FIXED2.cfe`). Полный разбор + рецепт правки `.cfe` — cache [`vygruzit-zhurnal-registracii-limit`](../1c-doc-research/cache/vygruzit-zhurnal-registracii-limit.md).

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
| 404 на `/hs/mcp/rpc` | Не опубликована конфигурация на веб-сервере, либо нет расширения `MCP_Сервер` | Опубликовать через `webinst.exe`/`vrd`, проверить расширение |
| **`500` на ВСЕХ эндпоинтах (вкл. `/health`)**, тело пустое, в Apache `error.log` ничего | Расширение `MCP_Сервер` есть в базе, но его конфигурация **не применена к БД** (правки в Конфигураторе без «Обновить конфигурацию БД»). Сервер `1c-mcp-crud` из-за этого = `failed`. **NB:** `401`=логин/пароль, `500`=сам сервис | `1cv8 DESIGNER /S "<srv>\<ib>" /N <admin> /P <pwd> /LoadCfg "<MCP_Сервер.cfe>" -Extension "MCP_Сервер"` → `/UpdateDBCfg -Extension "MCP_Сервер"` → `/mcp reconnect`. Полную 19-tool `.cfe` брать из `DumpCfg -Extension` самой базы (build-копия устарела). Нужна учётка с правами конфигурирования (ПолныеПрава). Детали — память [[reference-1c-mcp-crud-extension-restore]] |
| Таймаут `execute_query` | Тяжёлый запрос | `ПЕРВЫЕ N`, оптимизация запроса, рост `timeout` в `.mcp.json` |
| Кракозябры в ответах | cp1251 stdout на Windows | `PYTHONIOENCODING=utf-8` в `env` (включено по умолчанию) |
| `object_description must contain '_objectRef'` | Неправильный формат для `get_link_of_object` / `find_references_to_object` | Обернуть в `{_objectRef: true, УникальныйИдентификатор: "uuid", ТипОбъекта: "..."}` |
| `Invalid search scope` в `find_references_to_object` | Русские названия | Использовать английский enum |
| `link required` в `get_object_by_link` | Параметр иначе | Параметр называется `link`, не `navigation_link` |
| `Метод объекта не обнаружен (УникальныйИдентификатор)` из `mcp_Сериализация.Модуль(142)` на `execute_query` | В результате есть колонка `ПеречислениеСсылка.*` — у ссылок перечислений НЕТ метода `УникальныйИдентификатор()`, сериализатор расширения падает. Коварство: проявляется ТОЛЬКО когда строки реально вернулись — пустой результат (`data: []`) не падает, поэтому тот же запрос «работал» на пустой выборке (live 2026-07-12, SVETLY) | Enum-колонки оборачивать в `ПРЕДСТАВЛЕНИЕ(...)` (и группировать по нему же), либо `execute_code` с ручной `Строка(...)`-сериализацией |

## Ссылки

- Регистрация в `.mcp.json` — [строки 1c-mcp-crud / **1c-mcp-crud-erp** / 1c-mcp-crud-infeeda / 1c-mcp-crud-dev39144 / 1c-mcp-crud-daily](../../../.mcp.json)
  - **Профиль `1c-mcp-crud-erp`** — те же 19 инструментов, но другая база: `MCP_ONEC_URL=http://localhost/erp` → **серверная** база `Srvr=DESKTOP-TNU600C;Ref=Enterprise20_2_5_27_52` (УправлениеПредприятием 2.5.27.52), публикация через **Apache** (`C:\Apache24\htdocs\erp\default.vrd`), tool-prefix `mcp__1c-mcp-crud-erp__*`. Методика API идентична. Деплой/правка расширения этой базы — память [[project-1c-mcp-erp-extension]]
- Подсистема памяти и токен-экономии — `mcp__memory-orchestrator__*`
- Тестирование через VA BDD — skill `va-bdd-testing`, использует `1c-mcp-crud` как источник проверок (Stage 4a)
- Анализ задачи — skill `analyze-1c-task-v2` (использует `1c-mcp-crud` для проверки реквизитов и валидации запросов)
- Реализация задачи — skill `implement-1c-task` (обязательные циклы `validate_query` → `execute_query` → запись через EDT-MCP)


## Незадокументированные bsl_tool

- `CallGraphStore` (src\bsl\call_graph\store.py)
- `BSLStyleProfile` (src\bsl\coding_assistant\style_extractor.py)
- `BSLStyleExtractor` (src\bsl\coding_assistant\style_extractor.py)
- `EvalResult` (src\bsl\evaluation\metrics.py)
- `ObjectInfo` (src\bsl\knowledge_graph\metadata_extractor.py)
- `MetadataExtractor` (src\bsl\knowledge_graph\metadata_extractor.py)
- `OAuth2BearerMiddleware` (src\bsl\mcp_server\http_server.py)
- `MCPHttpServer` (src\bsl\mcp_server\http_server.py)
- `MCPProxy` (src\bsl\mcp_server\mcp_server.py)
- `OneCClient` (src\bsl\mcp_server\onec_client.py)
- `BSLASTParser` (src\bsl\parser\bsl_ast_parser.py)
- `BSLChunk` (src\bsl\parser\bsl_chunker.py)
- `BSLChunker` (src\bsl\parser\bsl_chunker.py)
- `BSLContextEnricher` (src\bsl\parser\context_enricher.py)
- `SymbolType` (src\bsl\parser\models.py)
- `CompilationDirective` (src\bsl\parser\models.py)
- `ModuleType` (src\bsl\parser\models.py)
- `BSLParam` (src\bsl\parser\models.py)
- `BSLCall` (src\bsl\parser\models.py)
- `BSLSymbol` (src\bsl\parser\models.py)
- `BSLVariable` (src\bsl\parser\models.py)
- `BSLRegion` (src\bsl\parser\models.py)
- `BSLModule` (src\bsl\parser\models.py)
- `BSLSearchSettings` (src\bsl\semantic_search\config.py)
- `RouterResult` (src\bsl\semantic_search\hybrid_router.py)
- `SonarQubeConfig` (src\bsl\sonar\config_manager.py)
- `ConfigManager` (src\bsl\sonar\config_manager.py)
- `Issue` (src\bsl\sonar\report_generator.py)
- `AnalysisReport` (src\bsl\sonar\report_generator.py)
- `ReportGenerator` (src\bsl\sonar\report_generator.py)
- `BSLRule` (src\bsl\sonar\rules_manager.py)
- `RulesManager` (src\bsl\sonar\rules_manager.py)
