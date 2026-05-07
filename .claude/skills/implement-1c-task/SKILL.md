---
name: implement-1c-task
description: "Реализация задачи 1С по готовому ANALYSIS-REPORT.md (BSL/XML через EDT-MCP). ТОЛЬКО после /analyze-1c-task-v2, когда есть ANALYSIS-REPORT с точками модификации. НЕ для анализа задач (→ analyze-1c-task-v2), НЕ для Claude Code, НЕ для LangChain."
version: 2.6.1
updated: 2026-05-07
tags: [1c, implementation, bsl, configuration, edt-mcp, 1c-mcp-crud, bsl-debugger]
triggers:
  - реализовать задачу 1С
  - implement 1c task
  - внести изменения по анализу
  - реализация по ANALYSIS-REPORT
---

# Реализация задачи 1С — 8-этапный pipeline (v2)

> **История версий:**
> - **v2.6.1 (2026-05-07):** follow-up к v2.6.0 после повторного e2e на той же сессии. **Этап 8 — переписан layout-блок** под точную 3-уровневую структуру. v2.6.0 описывала main как «tracks два submodule напрямую», но фактически **оба** submodule-пути проходят через обычную (не-git) подпапку: `configuration/` и `ИБTransportManagementDevelop/` — это level 2, регулярные директории main repo без своего `.git/`; submodule (gitlink) сидит на level 3 (`configuration/<TaskFolder>/`, `ИБTransportManagementDevelop/Конфигурация/`). Уточнено что path в индексе main хранится цельным (`"configuration/260304_GKSTCPLK-2182…"`, `"ИБTransportManagementDevelop/Конфигурация"`) и что `git add <subfolder>` без слеша/подсуба родителя — это **другая операция** (модификация level-2 директории), а не bump submodule. Diagnostic-пример обновлён ровно под этот layout. Никакого нового кода / нового decision gate / новых tools — только формулировка Этапа 8.
> - **v2.6.0 (2026-05-07):** калибровка после end-to-end прогона на GKSTCPLK-2182-A (АРМ «Композитные пробы»). Две правки. **Этап 1 — path-fallback:** ANALYSIS-REPORT'ы пишут Designer-style пути (`Documents/<Имя>/Ext/ManagerModule.bsl`, `DataProcessors/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl`); EDT в проекте flatten'ит их до своих абсолютных путей (напр. `DataProcessors/гкс_АРМКомпозитныеПробы/Forms/Форма/Module.bsl`). При этом `read_method_source(project, <designer_path>, ...)` падает с `File not found`. Добавлен явный шаг-fallback: при File-not-found → `list_modules(project, objectName=<ИмяОбъектаКонфигурации>)` → перебрать возвращённые `module_path`, выбрать совпадающий по типу модуля (Manager / Object / Form), повторить `read_method_source` с EDT-путём. Зафиксировать соответствие Designer→EDT в IMPLEMENTATION-PROGRESS.md (для будущих правок этой же задачи). **Этап 8 — layout:** диаграмма «трёх уровней вложенности» в v2.5.0 описывала `ИБTransportManagementDevelop/` как отдельный standalone-репо (НЕ submodule main). E2e-валидация 2026-05-07 (4 коммита в 3 репозиториях: `d3db501` BSL → `71a9ba481` main gitlink Конфигурация → `c6616817` docs submodule PROGRESS → `907b89ce1` main gitlink configuration) показала: фактически main repo tracks **два submodule напрямую** — `configuration/<TaskFolder>` (документация) и `ИБTransportManagementDevelop/Конфигурация` (BSL-исходники). Папка `ИБTransportManagementDevelop/` сама — обычная подпапка main repo, не отдельный git-репозиторий. Промежуточного «middle repo» с собственным `.git` нет; шаг 2 v2.5.0 (commit gitlink в `ИБTransportManagementDevelop`) удалён. Diagnostic-блок переписан под new-layout (`git ls-files --stage ИБTransportManagementDevelop/Конфигурация` ожидает entry с mode 160000).
> - **v2.5.0 (2026-05-07):** калибровка после end-to-end прогона на GKSTCPLK-2335. **Этап 4** — явный graceful-skip для `bsl_analyze` на production BSL: OneScript-парсер падает на директивах препроцессора `#Если ... Тогда` и chained-вызовах вида `Запрос.Выполнить().Пустой()` (стандартные 1С-конструкции). Если EDT `get_project_errors` = 0, ошибки `bsl_analyze` на этих паттернах фиксируем как tool-limitation и идём дальше. **Этап 6** — добавлен ОБЯЗАТЕЛЬНЫЙ шаг 0 «Обновление БД» через `mcp__edt-mcp__update_database` (или ручной EDT → Update Database) ПЕРЕД любым `execute_code`-вызовом изменённой функции; без этого live-инфобаза работает на старой скомпилированной конфигурации и `execute_code` возвращает старое поведение. **Этап 8** — переписан раздел git: 3-уровневая структура repo (main / submodule / nested standalone), запрет `git add <submodule-dir>` (подцепляет untracked), pattern `git -c user.name=... -c user.email=...` для submodule без локальной identity (CLAUDE.md запрещает `git config`). Добавлен раздел [Известные ограничения 1c-mcp-crud](#известные-ограничения-1c-mcp-crud) с workaround'ами для сериализации ссылок (`ПРЕДСТАВЛЕНИЕ()`) и пустого `attributes:[]` для регистров.
> - **v2.4.0 (2026-05-07):** в Preflight добавлен **TCP-probe** портов `:8765` (edt-mcp) и `:1550` (1С debug agent) — отдельный сигнал от наличия MCP-tool в сессии. Добавлен **fallback для Этапа 5** (`find_references` через `bsl-code-search:find_callers` + `bsl-semantic-search:bsl_call_graph`; `get_project_errors` через `bsl-debugger:bsl_analyze` per-file). Кросс-ссылки на новый раздел [16.6 EDT-MCP setup](../../../docs/framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md) и smoke-test `scripts/smoke_test_implement_1c_task.py`. Триггер изменений — выполнение Phase 4 + 5 [roadmap'а 260505](../../../docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md).
> - **v2.3.0 (2026-05-05):** добавлен **Preflight** — обязательная проверка доступности `edt-mcp` / `1c-mcp-crud` / `bsl-debug-server` перед стартом Этапа 1. Добавлен **fallback для Этапа 1** через `bsl-semantic-search` + `bsl-code-search` + `Read` (когда `edt-mcp` не зарегистрирован). Этапы 2, 3 (write), 5, 6 объявлены **hard-fail без edt-mcp/1c-mcp-crud** — частичный read-only режим возможен, запись кода и валидация на живых данных — нет. Триггер изменения — smoke-test 2026-05-05, в котором обнаружено что `mcp__edt-mcp__*` и `mcp__1c-mcp-crud__*` могут отсутствовать в сессии при проблемах с EDT (порт 8765) или с путями `.mcp.json`.
> - **v2.2.0 (2026-04-19):** добавлен conditional gate на рефакторинг в Этапе 3 после [Serena Audit Phases 0-7](../../../docs/roadmap/260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md). Новые MCP-инструменты `bsl_rename_symbol`, `bsl_replace_method_body`, `bsl_insert_after_method` (bsl-semantic-search refactor) применяются через [bsl-refactoring-workflow](../bsl-refactoring-workflow/SKILL.md) и [bsl-symbol-editing](../bsl-symbol-editing/SKILL.md) — только для refactoring-задач (rename / замена тела / safe delete). Для нового функционала — текущий путь EDT-MCP без изменений.
> - **v2.1.1 (2026-04-14):** откат Этапа 0 «Активация проекта в Serena» после [углублённого аудита](../../../docs/roadmap/260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md) — `language: bsl` в `.serena/project.yml` невалиден, LSP на BSL не работает, хук `serena-index-checker.py` не существует. Serena оставлена как опциональный вспомогательный инструмент.
> - **v2.1.0 (2026-04-14):** добавлен Этап 0 (откачен).
> - **v2.0.0 (2026-03-13):** 8-этапный pipeline с EDT-MCP + 1c-mcp-crud + bsl-debug-server.

## Overview

Skill для реализации задачи по конфигурации 1С:Предприятие.
На входе — готовый ANALYSIS-REPORT.md (от analyze-1c-task-v2).
На выходе — внесённые BSL/XML изменения, верифицированные на живых данных и закоммиченные.

**Отличия v2 от v1:**
- EDT-MCP: чтение/запись BSL-модулей прямо в проект EDT, валидация запросов, проверка ошибок
- 1c-mcp-crud: верификация SQL на живых данных ДО записи, подготовка тестовых данных, проверка результатов ПОСЛЕ
- bsl-debug-server: статический анализ BSL-кода, отладка чистой логики в OneScript

## Входные данные

Из аргументов команды:
1. **Путь к docs/** — папка с ANALYSIS-REPORT.md
2. **Путь к src/** — корень исходников конфигурации (опционально, определяется автоматически)

## Инструменты (3 MCP-сервера + вспомогательные)

### EDT-MCP — основной инструмент записи кода

| Инструмент | Когда использовать |
|---|---|
| `list_projects` | Этап 1: получить имя проекта EDT (ОБЯЗАТЕЛЬНО первым) |
| `list_modules` | Этап 1: найти модули объекта конфигурации |
| `get_module_structure` | Этап 1: обзор методов модуля (имена, строки, сигнатуры) |
| `read_method_source` | Этап 1, 3: прочитать тело конкретного метода перед модификацией |
| `read_module_source` | Этап 1: прочитать весь модуль (если нужен полный контекст) |
| `validate_query` | Этап 2: проверить синтаксис SQL-запроса ДО записи |
| `write_module_source` | Этап 3: записать изменённый BSL-код в модуль |
| `get_project_errors` | Этап 3: проверить ошибки EDT ПОСЛЕ каждой записи |
| `find_references` | Этап 5: найти все вызовы изменённого метода |
| `get_content_assist` | Этап 3: автодополнение имён (перечисления, регистры, методы) |
| `search_in_code` | Этап 1, 5: поиск паттернов в коде проекта |
| `get_symbol_info` | Этап 1: информация о символе (тип, параметры) |
| `get_applications` | Этап 6: получить applicationId работающего инфобейса (вход для update_database) |
| `update_database` | Этап 6: обновить конфигурацию БД ПЕРЕД live-вызовом изменённой функции (shared-state action — спросить пользователя) |

### 1c-mcp-crud — верификация на живых данных

| Инструмент | Когда использовать |
|---|---|
| `get_metadata` | Этап 1, 2: проверить имена полей, типы реквизитов, структуру |
| `execute_query` | Этап 2: прогнать SQL на живой базе ДО записи в код |
| `execute_query` | Этап 6: проверить результат ПОСЛЕ проведения документа |
| `execute_code` | Этап 6: подготовить тестовые данные (из тест-плана ANALYSIS-REPORT) |
| `execute_code` | Этап 6: очистить тестовые данные после тестирования |
| `get_object_by_link` | Этап 6: посмотреть конкретный объект по ссылке |
| `find_references_to_object` | Этап 5: найти ссылки на объект в базе данных |

### bsl-debug-server — статический анализ и отладка

| Инструмент | Когда использовать |
|---|---|
| `bsl_analyze` | Этап 4: статический анализ написанного BSL-кода (линтер) |
| `bsl_execute` | Этап 4: запустить фрагмент BSL-логики в OneScript (без базы) |
| `bsl_debug_start` | Этап 4: пошаговая отладка алгоритма (breakpoints, step) |
| `bsl_debug_variables` | Этап 4: проверить значения переменных в точке останова |

**Ограничение bsl-debug-server:** Работает через OneScript, НЕ через 1С:Предприятие.
Нет доступа к объектам 1С (Документы, Регистры, Справочники). Подходит ТОЛЬКО для:
- Проверки чистой логики (условия, циклы, формирование массивов)
- Статического анализа (bsl_analyze) — но **с известными false-positive'ами на стандартных 1С-конструкциях** (директивы препроцессора `#Если ... Тогда`, chained `Запрос.Выполнить().Пустой()`). См. Этап 4 → graceful skip.
- НЕ подходит для запросов к базе — для этого используй 1c-mcp-crud

### Вспомогательные

| Инструмент | Когда использовать |
|---|---|
| `bsl-semantic-search` | Этап 1: поиск похожего кода в конфигурации |
| `bsl-semantic-search` (refactor) | Этап 3: `bsl_rename_symbol`, `bsl_replace_method_body`, `bsl_insert_after/before_method` — **только для refactoring-задач** (см. условный этап 3R ниже) |
| `bsl-platform-context` | Этап 3: API платформы 1С (методы, свойства, типы) |
| `Grep/Glob` | Этап 1: поиск файлов и паттернов на диске |

---

## 8 этапов реализации

### Этап 0: Preflight — проверка доступности MCP-серверов (ОБЯЗАТЕЛЬНО)

**Цель:** До чтения ANALYSIS-REPORT убедиться, что инструменты pipeline зарегистрированы в текущей сессии. Без этой проверки skill уходит в этапы, где нужные tool-вызовы просто не существуют, и тратит итерации впустую.

**Шаги:**

1. Проверить три ключевых сервера через `ToolSearch` (или прямой вызов любого ping-tool сервера):

   | Сервер | Probe-вызов | Ожидание |
   |---|---|---|
   | `edt-mcp` | `mcp__edt-mcp__list_projects` (или `ToolSearch query: "edt"`) | в результатах есть `mcp__edt-mcp__*` |
   | `1c-mcp-crud` | `mcp__1c-mcp-crud__get_metadata` (или `ToolSearch query: "+1c crud"`) | в результатах есть `mcp__1c-mcp-crud__*` |
   | `bsl-debug-server` | `mcp__bsl-debugger__bsl_analyze` или `mcp__1c-debug__debug_targets` | tool существует |

2. **TCP-probe ключевых портов** — отдельный сигнал от наличия MCP-tool в сессии (tool может быть зарегистрирован, но HTTP-bridge упасть):

   | Порт | Сервис | Команда | Ожидание |
   |---|---|---|---|
   | `:8765` | EDT-MCP HTTP-bridge | `Test-NetConnection -ComputerName localhost -Port 8765 -InformationLevel Quiet` | `True` для режимов **Full** и **Code-only** |
   | `:1550` | 1С debug agent (`ragent.exe -debug`) | `Test-NetConnection -ComputerName localhost -Port 1550 -InformationLevel Quiet` | `True` только если нужна runtime-отладка в Этапе 4 |

   Альтернатива одной командой:
   ```powershell
   python scripts/smoke_test_implement_1c_task.py
   ```
   Скрипт парсит [.mcp.json](../../../.mcp.json), TCP-probe + MCP-handshake, возвращает exit-code `0` (Full) / `1` (degraded) / `2` (unusable). Подробности: [16.6 EDT-MCP setup](../../../docs/framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md).

3. Сопоставить результат с матрицей капабилити:

   | edt-mcp | 1c-mcp-crud | bsl-debug-server | Режим pipeline |
   |---|---|---|---|
   | ✓ | ✓ | ✓ | **Full** — все 8 этапов работают как описано |
   | ✓ | ✗ | * | **Code-only** — Этапы 1, 3 (write), 4, 5, 7, 8. Этап 2 — только `validate_query` (синтаксис), без `execute_query`. Этап 6 — SKIP с пометкой "ожидает ручного тестирования" |
   | ✗ | ✓ | * | **Read-only verify** — Этап 2 на данных, Этап 6 на данных. Запись кода невозможна (нет `write_module_source`) → STOP с просьбой запустить EDT |
   | ✗ | ✗ | * | **Read-only research** — только Этап 1 через fallback (см. ниже), сбор контекста. Запись и валидация невозможны → STOP перед Этапом 2 |

4. Если режим не **Full** — сообщить пользователю явно: какие серверы отсутствуют, какие этапы будут пропущены, что нужно поднять (EDT на `localhost:8765`, путь к `1c-mcp-crud` в `.mcp.json`, см. [16.6](../../../docs/framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md)). Дождаться решения: продолжить в деградированном режиме или прервать.

5. Сохранить выбранный режим в IMPLEMENTATION-PROGRESS.md под заголовком `Pipeline mode: Full | Code-only | Read-only verify | Read-only research`.

**Контрольная точка:** Известен режим pipeline. Все последующие этапы выполняются с учётом ограничений режима.

---

### Этап 1: Подготовка

**Цель:** Собрать актуальный контекст кода для всех точек модификации.

**Шаги:**

1. Прочитать ANALYSIS-REPORT.md — извлечь:
   - Номер задачи (GKSTCPLK-XXXX)
   - Точки модификации (пронумерованные)
   - Порядок выполнения
   - Зависимости между точками

2. Определить проект EDT (**режим Full / Code-only**):
   ```
   EDT-MCP: list_projects → получить имя проекта (напр. "УправлениеТранспортомНаПЛК")
   ```

   **Fallback (режим Read-only research, edt-mcp недоступен):** имя проекта берётся из пути src/ в ANALYSIS-REPORT (обычно `<repo>/configuration/<TaskFolder>/src/` или `ИБTransportManagementDevelop/src/`). Имя «проекта EDT» в этом режиме не используется как идентификатор — все обращения идут к файлам напрямую.

3. Для КАЖДОЙ точки модификации:

   **Основной путь (edt-mcp доступен):**
   ```
   EDT-MCP: get_module_structure(project, module_path)
     → получить актуальные номера строк методов
   EDT-MCP: read_method_source(project, module_path, method_name)
     → получить текущий код точки вставки
   ```

   **Path-fallback при File-not-found (Designer→EDT flatten):**

   ANALYSIS-REPORT'ы используют Designer-style пути из выгрузки конфигурации (например `Documents/<Имя>/Ext/ManagerModule.bsl`, `DataProcessors/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl`). EDT в открытом проекте хранит модули по своему layout'у (`DataProcessors/<Имя>/Forms/<Форма>/Module.bsl` без `Ext/Form/`). При расхождении `read_method_source(project, <designer_path>, ...)` падает с `File not found`.

   ```
   EDT-MCP: list_modules(project, objectName="<ИмяОбъектаКонфигурации>")
     → массив { module_path, module_type } для всех модулей объекта
   ```

   Из массива выбрать `module_path` совпадающий по типу (`ManagerModule` / `ObjectModule` / `FormModule` / `CommandModule`) и повторить `read_method_source` с EDT-путём. Соответствие Designer→EDT зафиксировать в IMPLEMENTATION-PROGRESS.md, чтобы последующие точки той же задачи использовали уже разрешённый путь без повторного fallback'а.

   **Fallback (edt-mcp недоступен):** структура модуля и тело метода читаются без EDT.
   ```
   bsl-code-search: get_module_ast(file_path)
     → процедуры/функции в модуле (имена + диапазоны строк)
   ИЛИ
   bsl-semantic-search: bsl_object_info(object_name)
     → метаданные объекта + список модулей + call graph stats
   bsl-semantic-search: bsl_coding_context(object_name, task_description)
     → агрегированный контекст: object info + dependencies + style + similar code

   Read(file_path, offset=method_start_line, limit=method_length)
     → текущий код точки вставки (через стандартный Read)
   ```

   **Ограничения fallback'а** (зафиксировать в IMPLEMENTATION-PROGRESS.md):
   - Нет `get_content_assist` — автодополнение имён перечислений/регистров недоступно, проверять вручную через `bsl-platform-context` или `Grep` по конфигурации.
   - Нет `get_symbol_info` — типы параметров/возвращаемых значений выводить из сигнатуры в `get_module_ast` или из аннотаций кода.
   - Нет `search_in_code` по проекту EDT — заменяется на `Grep` + `bsl_search` (семантический).

4. Сверить номера строк из ANALYSIS-REPORT с актуальными.
   - **Full / Code-only:** актуальные = из EDT-MCP.
   - **Read-only research:** актуальные = из `get_module_ast`.
   Если расхождение — использовать актуальные номера и зафиксировать в IMPLEMENTATION-PROGRESS.md.

**Контрольная точка:** Для каждой точки модификации известны актуальные строки и текущий код. Источник (EDT-MCP / bsl-code-search) задокументирован.

---

### Этап 2: Предварительная валидация запросов

**Цель:** Проверить ВСЕ SQL-запросы из плана ДО записи в код.

**Шаги:**

1. Извлечь все SQL-запросы из ANALYSIS-REPORT (из кода точек модификации).

2. Для КАЖДОГО запроса:
   ```
   EDT-MCP: validate_query(project, query_text)
     → синтаксическая проверка (поля, таблицы, типы)
   ```

3. Если validate_query прошёл — проверить на живых данных:
   ```
   1c-mcp-crud: execute_query(query_text_with_test_params)
     → убедиться что запрос возвращает ожидаемые данные
   ```

4. Если запрос содержит параметры (&Параметр) — подставить реальные значения из базы для теста.

5. Проверить имена полей:
   ```
   1c-mcp-crud: get_metadata(object_type, object_name)
     → сверить имена полей в запросе с метаданными
   ```

**Контрольная точка:** Все SQL-запросы валидны и возвращают ожидаемые данные.

**Если запрос не прошёл валидацию:**
- Исправить запрос
- Повторить validate_query + execute_query
- Обновить код точки модификации с исправленным запросом
- Зафиксировать отклонение от ANALYSIS-REPORT в IMPLEMENTATION-PROGRESS.md

---

### Этап 3: BSL-изменения

**Цель:** Внести код в модули **строго в порядке** из ANALYSIS-REPORT.

#### Decision gate: рефакторинг или новый функционал?

Перед началом Этапа 3 для каждой точки модификации определить тип операции:

| Тип операции | Признак | Путь |
|---|---|---|
| **Новый функционал** | Добавление новой процедуры/реквизита/формы/подсистемы; вставка строк в существующий метод | **Стандартный Этап 3** (EDT-MCP `write_module_source`) |
| **Рефакторинг** | Переименование процедуры/переменной/параметра; замена тела существующего метода целиком; safe delete с проверкой references | **Этап 3R** (см. ниже) — активировать [bsl-refactoring-workflow](../bsl-refactoring-workflow/SKILL.md) |
| **Гибрид** | Новый функционал + попутное переименование существующих символов | Сначала Этап 3R (рефакторинг), потом Этап 3 (новый код) |

**Критерий однозначный:** если существующий символ меняет имя/удаляется/заменяется тело — это рефакторинг, `bsl_rename_symbol` / `bsl_replace_method_body` / `bsl_safe_delete_symbol`. Если только добавляются новые символы или строки внутри метода — это не рефакторинг, стандартный путь.

#### Этап 3R: Рефакторинг через bsl-semantic-search refactor (условный)

**Применяется только если decision gate определил операцию как рефакторинг.**

1. **Классифицировать символ** (routing matrix v2 — `src/bsl/semantic_search/refactor/routing_matrix.yaml`):
   - `local_variable` / `parameter` / `module_local_proc` → ast-grep in-file (confidence 0.95)
   - `module_export_proc` → ast-grep cross-file через Neo4j граф (confidence 0.85)
   - `form_handler` → ast-grep + XML (confidence 0.95 после R5.5 calibration)
   - `unknown` / динамические вызовы (`Выполнить()`) → **manual tier**

2. **Вызвать нужный инструмент** (ВСЕГДА сначала `dry_run: true`):
   ```
   mcp__bsl-semantic-search__bsl_rename_symbol(
       uri: "file:///path/to/Module.bsl",
       line: N, character: M,
       new_name: "НовоеИмя",
       dry_run: true
   )
   ```
   Или `bsl_replace_method_body` / `bsl_insert_after_method` — см. [bsl-symbol-editing](../bsl-symbol-editing/SKILL.md).

3. **Проверить план** (dry_run response):
   - `status: "plan"` → показать `files_affected` + `edits`
   - `status: "manual_required"` → переключиться на manual tier (Grep + Edit)

4. **Подтвердить изменения** (`dry_run: false` с `confirm_token` из plan).

5. **Верифицировать через EDT-MCP:**
   ```
   EDT-MCP: get_project_errors(project, severity="ERROR") → 0 ошибок
   ```

6. **Логировать в IMPLEMENTATION-PROGRESS.md:** backend (ast-grep/multilspy/manual), confidence, N файлов изменено.

Полный workflow: [bsl-refactoring-workflow/SKILL.md](../bsl-refactoring-workflow/SKILL.md).

#### Стандартный Этап 3: Новый функционал (EDT-MCP)

**Цикл для КАЖДОЙ точки модификации (в порядке выполнения):**

```
ПОВТОРИТЬ для каждой точки:

  1. ПРОЧИТАТЬ текущий код:
     EDT-MCP: read_method_source(project, module, method)
       или read_module_source(project, module, startLine, endLine)

  2. ПОДГОТОВИТЬ изменённый код:
     - Взять код из ANALYSIS-REPORT
     - Добавить комментарии с номером задачи (Правило 1)
     - Если нужен API платформы:
       bsl-platform-context: getMembers / getMember / search

  3. ЗАПИСАТЬ код:
     EDT-MCP: write_module_source(project, module, code, startLine, endLine)

  4. ПРОВЕРИТЬ ошибки:
     EDT-MCP: get_project_errors(project, severity="ERROR")
       → ЕСЛИ есть ошибки → исправить и повторить шаги 2-4
       → ЕСЛИ ошибок нет → перейти к следующей точке

  5. ВЕРИФИЦИРОВАТЬ запись:
     EDT-MCP: read_method_source(project, module, method)
       → убедиться что код записан корректно
```

**Правила записи:**
- Новые процедуры/функции: `write_module_source` с `insertAfterLine`
- Модификация существующих: `write_module_source` с `startLine`/`endLine`
- После КАЖДОЙ записи — обязательный `get_project_errors`
- При ошибке — НЕ переходить к следующей точке, сначала исправить

---

### Этап 4: Статический анализ

**Цель:** Проверить качество написанного BSL-кода.

**Шаги:**

1. Для каждого изменённого модуля:
   ```
   bsl-debug-server: bsl_analyze(file=<absolute_path>)
     → получить предупреждения и ошибки линтера
   ```

2. **Если `bsl_analyze` падает с parse error** — проверить, попадает ли ошибка в список known false-positive'ов (см. ниже). Если да — фиксируем как tool-limitation и считаем этап пройденным (EDT-валидация в Этапе 3 уже подтвердила корректность кода). Если нет — есть реальная ошибка, исправлять через Этап 3.

3. Для новых процедур с чистой логикой (без обращений к базе):
   ```
   bsl-debug-server: bsl_execute(code_fragment)
     → проверить что логика работает (условия, циклы, массивы)
   ```

4. При сложной логике (вложенные циклы, условия) — пошаговая отладка:
   ```
   bsl-debug-server: bsl_debug_start(file, breakpoints)
   bsl-debug-server: bsl_debug_step(session, "stepInto")
   bsl-debug-server: bsl_debug_variables(session)
     → проверить значения на каждом шаге
   bsl-debug-server: bsl_debug_stop(session)
   ```

5. Исправить найденные **реальные** проблемы (повторить Этап 3 для исправлений).

**Контрольная точка:**
- EDT `get_project_errors(severity="ERRORS") = 0` (авторитетный источник для 1С) — ОБЯЗАТЕЛЬНО
- `bsl_analyze` = 0 ошибок ИЛИ все ошибки попадают в known false-positive'ы

**Known false-positive'ы `bsl_analyze` (OneScript-парсер ≠ 1С-компилятор):**

| Паттерн | Сообщение парсера | Корректное поведение |
|---|---|---|
| `#Если ТолстыйКлиентОбычноеПриложение Или Сервер ... Тогда` (директива препроцессора в строке 1) | `Неожиданный токен: Тогда` | Стандартная BSL-директива препроцессора. EDT компилирует. Игнорировать. |
| `Запрос.Выполнить().Пустой()` (chained method call) | `Ожидается имя свойства` | Стандартный паттерн 1С. Игнорировать. |
| `НовыйОбъект.Записать(РежимЗаписиДокумента.Проведение)` (composite ref в аргументе) | разные | Если EDT принимает — игнорировать. |

**Workaround при padении на препроцессоре:** передавать в `bsl_analyze(source=<тело_метода>)` только тело новой функции (без директив препроцессора), а не весь файл через `file=...`.

**Когда ПРОПУСТИТЬ bsl_execute/bsl_debug (но НЕ bsl_analyze):**
- Код состоит только из вызовов методов 1С (РегистрыСведений, Документы)
- Код — простой SQL-запрос + проверка результата
- В этих случаях достаточно bsl_analyze (или его graceful-skip)

**Логирование в IMPLEMENTATION-PROGRESS.md:**
- `bsl_analyze: 0 errors / N warnings` — успех
- `bsl_analyze: SKIP (OneScript false-positive on <pattern>); EDT errors = 0` — tool-limitation, проверка через EDT

---

### Этап 5: Верификация кросс-зависимостей

**Цель:** Убедиться что изменения не сломали существующий код.

**Шаги:**

1. Для каждого изменённого/нового метода:

   **Основной путь (edt-mcp доступен):**
   ```
   EDT-MCP: find_references(project, module, symbol)
     → найти все места вызова
   ```

   **Fallback (edt-mcp недоступен, режим Read-only research):**
   ```
   bsl-code-search: find_callers(symbol_name)
     → AST-уровень: прямые вызовы по конфигурации
   bsl-semantic-search: bsl_call_graph(object_name, depth=2)
     → семантический граф зависимостей через Neo4j
   ```
   Ограничение: оба fallback'а работают по индексу, не учитывают live-проект EDT — могут пропустить недавно добавленные вызовы (до переиндексации). Зафиксировать в IMPLEMENTATION-PROGRESS.md.

2. Проверить общие ошибки проекта:

   **Основной путь (edt-mcp доступен):**
   ```
   EDT-MCP: get_project_errors(project, severity="ERROR")
   EDT-MCP: get_project_errors(project, severity="WARNING")
     → убедиться что новых ошибок/предупреждений не появилось
   ```

   **Fallback (edt-mcp недоступен):**
   ```
   bsl-debugger: bsl_analyze(file_path) для каждого изменённого .bsl
     → статический линтер по локальному файлу (без cross-module проверки)
   ```
   В режиме без EDT cross-module ошибки (несовпадение сигнатур, отсутствующие модули) обнаружить нельзя — отметить как «требует EDT-валидации перед merge».

3. Если в ANALYSIS-REPORT указаны объекты-источники данных:
   ```
   1c-mcp-crud: get_metadata(object_type, object_name)
     → финальная проверка что все используемые поля существуют
   ```

**Контрольная точка:** Нет новых ошибок, все ссылки на изменённые методы корректны.

---

### Этап 6: Тестирование на живых данных

**Цель:** Выполнить тест-план из ANALYSIS-REPORT на реальной базе.

**КРИТИЧНО — почему этот этап имеет ОБЯЗАТЕЛЬНЫЙ шаг 0:**

EDT-MCP `write_module_source` правит **исходники** проекта (`src/...`) и помечает изменения для последующей сборки. Запущенная инфобаза 1С работает с **уже скомпилированной** конфигурацией БД. Пока конфигурация БД не обновлена, любой `1c-mcp-crud: execute_code(...)` или проведение документа выполняет **СТАРУЮ** версию изменённой функции. Без шага 0 Этап 6 даёт ложно-отрицательный результат: «фикс не сработал» — потому что live-инфобаза не видит изменений.

**Шаги:**

0. **ОБНОВЛЕНИЕ КОНФИГУРАЦИИ БД** (ОБЯЗАТЕЛЬНО, никогда не пропускать):

   **Основной путь (автоматически):**
   ```
   EDT-MCP: get_applications(projectName)
     → найти applicationId работающего инфобейса
   EDT-MCP: update_database(projectName, applicationId, fullUpdate=false, autoRestructure=true)
     → инкрементальное обновление; полное (fullUpdate=true) — если меняется структура хранения
   ```
   Примечание: `update_database` модифицирует live-инфобазу — это **shared-state action** (CLAUDE.md). Если в инфобазе работают другие пользователи или это production — ОСТАНОВИТЬСЯ и спросить у пользователя.

   **Ручной путь (когда `update_database` отсутствует или нужна ручная проверка):**
   - Сообщить пользователю: «Обнови конфигурацию БД через EDT (Project → Update Database) или через Конфигуратор (F7 → Обновить конфигурацию базы данных). После обновления скажи 'готово'.»
   - Дождаться подтверждения.

   **Smoke-test что обновление прошло:** вызвать изменённую функцию через `execute_code` на одном тестовом объекте; результат должен соответствовать новой логике.

1. **Подготовка тестовых данных** (если требуется в тест-плане):
   ```
   1c-mcp-crud: execute_query(find_test_candidates)
     → найти подходящие объекты для тестирования
   1c-mcp-crud: execute_code(create_test_data)
     → создать тестовые записи согласно тест-плану
   1c-mcp-crud: execute_query(verify_test_data)
     → убедиться что тестовые данные созданы
   ```

2. **Проведение документа** — ПОЛЬЗОВАТЕЛЬ проводит документ вручную в 1С.
   Claude НЕ МОЖЕТ провести документ (нет GUI). Сообщить пользователю:
   ```
   "Проведи документ [ссылка/описание] в 1С:Предприятие.
   После проведения скажи 'готово' — я проверю результат."
   ```

3. **Проверка результата**:
   ```
   1c-mcp-crud: execute_query(verification_query)
     → проверить что данные изменились как ожидалось
   ```

4. **Очистка тестовых данных** (если создавались):
   ```
   1c-mcp-crud: execute_code(cleanup_test_data)
     → вернуть данные к исходному состоянию
   ```

5. Зафиксировать результаты в IMPLEMENTATION-PROGRESS.md, включая:
   - Способ обновления БД (auto через update_database / manual через EDT)
   - Подтверждение что live-вызов изменённой функции вернул новое значение

**Альтернатива при невозможности обновить БД** (production-окружение, другие пользователи в БД, отсутствие applicationId):
- **SQL-симуляция новой логики** через `execute_query` — построить запрос, повторяющий поведение изменённой функции на тех же данных. Сравнить старое vs новое поведение на репрезентативных кейсах из тест-плана. Зафиксировать как `Тест: симуляция через SQL (без обновления БД)` — это НЕ полная live-валидация, требует пометки в IMPLEMENTATION-PROGRESS.md.

**ВАЖНО:** Этот этап ИНТЕРАКТИВНЫЙ — требует участия пользователя для проведения документов и (часто) для обновления БД.
Если пользователь не может провести сейчас — пометить как "ожидает ручного тестирования", при этом SQL-симуляция должна быть выполнена в любом случае.

---

### Этап 7: Документация

**Цель:** Зафиксировать что было сделано.

**Создать/обновить файл IMPLEMENTATION-PROGRESS.md** в той же папке docs/:

```markdown
# НОМЕР-ЗАДАЧИ — Прогресс реализации

## Статус: В работе / Завершено / Ожидает тестирования

## Выполненные точки модификации

### Точка N: Описание
- **Файл:** путь
- **Действие:** что сделано
- **Строки:** актуальные (из EDT-MCP)
- **Валидация запросов:** validate_query OK / исправлен (описание)
- **Ошибки EDT:** 0 / исправлены (описание)
- **bsl_analyze:** 0 ошибок / N предупреждений (список)
- **Тест на данных:** пройден / ожидает / не требуется
- **Отклонения от ANALYSIS-REPORT:** нет / описание

## Результаты тестирования
- Тест X.Y: PASS / FAIL / SKIP (причина)

## Открытые вопросы (если есть)
```

---

### Этап 8: Git commit

**Цель:** Закоммитить изменения, аккуратно работая с многоуровневой структурой репозиториев.

#### Структура репозиториев

Layout — **трёхуровневый**, при этом level 2 это **обычная директория** main repo (не git-репо, не submodule). Подтверждено 2026-05-07 через `git ls-files --stage` и инспекцию `.git/` в каждой папке цепочки.

```
Level 1 — MAIN repo (.git здесь)
C:\1С-Framework\
│
├── configuration/                                 ← Level 2: обычная подпапка main, БЕЗ своего .git/
│   ├── 260304_GKSTCPLK-2182…/                     ← Level 3: SUBMODULE (gitlink in main)
│   │   ├── .git                                   ← gitlink-файл (содержимое = "gitdir: ...")
│   │   └── docs/<task>/IMPLEMENTATION-PROGRESS.md
│   └── 260416_GKSTCPLK-2368…/                     ← Level 3: SUBMODULE (gitlink in main)
│
├── ИБTransportManagementDevelop/                  ← Level 2: обычная подпапка main, БЕЗ своего .git/
│   └── Конфигурация/                              ← Level 3: SUBMODULE (gitlink in main)
│       ├── .git                                   ← gitlink-файл
│       └── src/.../*.bsl                          ← BSL-исходники (правит EDT-MCP)
│
├── external/1c_mcp/                               ← обычно untracked в main
└── …
```

**Ключевые факты:**
- **Level 1 (main repo):** единственный репозиторий с настоящим каталогом `.git/` в корне. Все gitlink'и хранятся в индексе main.
- **Level 2 (`configuration/`, `ИБTransportManagementDevelop/`):** просто директории — `git rev-parse --is-inside-work-tree` внутри них всё ещё показывает main, своего `.git/` НЕТ. Сюда нельзя `cd` и сделать локальный коммит — это будет коммит в main.
- **Level 3 (`configuration/<TaskFolder>/`, `ИБTransportManagementDevelop/Конфигурация/`):** submodule'ы — отдельные git-репозитории со своим `.git`-указателем (gitfile), своей историей и своим `HEAD`.
- В индексе main путь submodule хранится **цельным** (со слешем): `"configuration/<TaskFolder>"` и `"ИБTransportManagementDevelop/Конфигурация"`. Это и есть аргумент для `git add` при bump'е gitlink'а.
- `git add ИБTransportManagementDevelop` (без `/Конфигурация`) — **другая** операция: индексирует level-2 директорию как контент main, что обычно нежелательно (см. Diagnostic ниже).
- Промежуточного git-репо между level 1 и level 3 нет (в отличие от ошибочного описания v2.5.0). Поэтому шага «commit gitlink в middle repo» в этом pipeline не существует.

#### Шаги

1. **Submodule с BSL-кодом** (`ИБTransportManagementDevelop/Конфигурация`):
   ```bash
   git -C "ИБTransportManagementDevelop/Конфигурация" add <specific_file_path>
   git -C "ИБTransportManagementDevelop/Конфигурация" commit -m "feat(НОМЕР-ЗАДАЧИ): краткое описание"
   ```
   ⚠ **НЕ использовать `git add -A`** — submodule может содержать чужой dirty state.
   ⚠ **НЕ использовать `git add <submodule-dir>`** в родителе — git попытается проиндексировать **untracked файлы внутри** (включая длинные пути Windows → fatal: filename too long).

2. **Submodule с документацией** (`configuration/<TaskFolder>`) — закоммитить IMPLEMENTATION-PROGRESS.md:
   ```bash
   git -C "configuration/<TaskFolder>" add "docs/<task>/IMPLEMENTATION-PROGRESS.md"
   git -C "configuration/<TaskFolder>" commit -m "docs(НОМЕР-ЗАДАЧИ): add implementation progress"
   ```

3. **Main repo** — обновить оба gitlink'а (по одному коммиту на submodule или одним коммитом сразу):
   ```bash
   git add "ИБTransportManagementDevelop/Конфигурация"
   git commit -m "chore(НОМЕР-ЗАДАЧИ): bump Конфигурация submodule ref"

   git add "configuration/<TaskFolder>"
   git commit -m "chore(НОМЕР-ЗАДАЧИ): bump configuration submodule ref"
   ```
   Здесь `git add <submodule_path>` — **корректно**: git распознаёт submodule entry и обновляет только gitlink, не содержимое.

**Итого:** одна задача = до 4 коммитов в 3 репозиториях (BSL submodule, docs submodule, main ×2 gitlink). Если правка только в одном из submodule — соответствующая половина пропускается.

#### Git identity без `git config`

CLAUDE.md запрещает `git config` (включая локальный). Если submodule наследует identity от родителя — коммит проходит. Если в submodule пусто — коммит падает с `fatal: unable to auto-detect email address`. Решение — **per-command override**:

```bash
git -c user.name="Имя" -c user.email="email@example.com" commit -m "..."
```

Эти `-c` действуют только в рамках одной команды и **не пишутся** в `.git/config`. Identity берётся из main repo (`git config user.name` + `git config user.email`).

#### Diagnostic: подтвердить 3-уровневый layout перед коммитом

Шаг 1 — убедиться что **level 3** (submodule) действительно зарегистрирован в индексе **level 1** (main):

```bash
git ls-files --stage "ИБTransportManagementDevelop/Конфигурация"
# ожидается: 160000 <hash> 0  ИБTransportManagementDevelop/Конфигурация
git ls-files --stage "configuration/<TaskFolder>"
# ожидается: 160000 <hash> 0  configuration/<TaskFolder>
```

Mode `160000` = gitlink (submodule). Если строка пуста или mode ≠ `160000` — submodule не зарегистрирован, остановиться и сверить с пользователем (вероятно сломан `.gitmodules` или рабочий tree разошёлся с индексом).

Шаг 2 — убедиться что **level 2** (`configuration/`, `ИБTransportManagementDevelop/`) — действительно простая директория, а не самозванец:

```bash
test -d "ИБTransportManagementDevelop/.git" && echo "АНОМАЛИЯ: level 2 имеет свой .git" || echo "OK: level 2 — обычная директория"
test -d "configuration/.git" && echo "АНОМАЛИЯ: level 2 имеет свой .git" || echo "OK: level 2 — обычная директория"
```

Ожидание: `OK` для обоих. Если у level-2 директории появился собственный `.git/` — это другой layout (как ошибочно описывала v2.5.0), и git-flow из шагов 1-3 надо переcмотреть отдельно.

Шаг 3 — `git status` в main: типичный `m configuration/<TaskFolder>` или `m ИБTransportManagementDevelop/Конфигурация` (lowercase `m` = submodule modified content) — **нормально**, ожидается перед bump'ом gitlink'а. А вот `M ИБTransportManagementDevelop` (uppercase, без `/Конфигурация`) — **аномалия**: значит внутри level-2 директории появились трекаемые main'ом файлы вне зарегистрированного submodule. Не bump'ить, разобраться сначала.

---

## ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА

### Правило 1: Комментарии с номером задачи (НИКОГДА НЕ ПРОПУСКАТЬ)

Каждый блок нового/изменённого кода ОБЯЗАТЕЛЬНО оборачивается комментариями:

```bsl
// GKSTCPLK-XXXX Начало
<новый код>
// GKSTCPLK-XXXX Конец
```

Каждая строка вызова, добавленная в существующую процедуру:
```bsl
	ВызовНовойПроцедуры(); // GKSTCPLK-XXXX
```

Где `GKSTCPLK-XXXX` — номер задачи из ANALYSIS-REPORT (заголовок или имя папки).

**Формат комментариев по правилам 1С:**
- Однострочные вставки: `// НОМЕР-ЗАДАЧИ` в конце строки
- Блоки кода (новые функции, процедуры, области): `// НОМЕР-ЗАДАЧИ Начало` перед блоком, `// НОМЕР-ЗАДАЧИ Конец` после блока
- Это позволяет при code review и merge видеть, какой код относится к какой задаче

### Правило 2: Следовать паттернам конфигурации

Перед написанием нового кода:
1. **Найти аналогичный функционал** в конфигурации (через bsl-semantic-search или EDT-MCP search_in_code)
2. **Использовать существующие функции** если они подходят (не дублировать)
3. **Следовать стилю** именования, форматирования, структуры запросов из существующего кода
4. **Копировать паттерны** — если в конфигурации есть похожая реализация, брать её как шаблон

### Правило 3: Не модифицировать файлы вне списка

Изменять ТОЛЬКО файлы, перечисленные в ANALYSIS-REPORT. Если обнаружена необходимость менять другие файлы — остановиться и сообщить пользователю.

### Правило 4: Проверять имена полей

Перед использованием имён полей в SQL-запросах — проверять через `get_metadata` И `validate_query`. Частые ошибки:
- Поля с/без префикса `гкс_`
- Разные имена в разных регистрах (например `РегистрацияТранспорта` vs `ДокументРегистрации`)
- `ПустаяСсылка` без скобок в SQL: `ЗНАЧЕНИЕ(Перечисление.xxx.ПустаяСсылка)` — БЕЗ `()`

### Правило 5: Цикл записи EDT-MCP (НИКОГДА НЕ ПРОПУСКАТЬ)

```
write_module_source → get_project_errors → [fix if needed] → read_method_source (verify)
```

КАЖДАЯ запись кода ОБЯЗАТЕЛЬНО проходит этот цикл. Не переходить к следующей точке при наличии ошибок.

### Правило 6: Валидация запросов ДО записи (НИКОГДА НЕ ПРОПУСКАТЬ)

```
validate_query → execute_query (с тестовыми параметрами) → [fix if needed] → write
```

КАЖДЫЙ SQL-запрос в новом коде ОБЯЗАТЕЛЬНО проверяется на Этапе 2 ДО записи в модуль.

### Правило 7: Пользователь проводит документы

Claude НЕ МОЖЕТ проводить документы, нажимать кнопки, открывать формы.
Для тестов, требующих проведения — запрашивать действие у пользователя.
Для проверки результатов — использовать execute_query/execute_code.

---

## Известные ограничения 1c-mcp-crud

Сервер `1c-mcp-crud` подключается к live-инфобазе через HTTP-сервис расширения `MCP_Сервер`. У текущей версии расширения есть два известных артефакта, которые проявляются на Этапах 2, 5 и 6.

### Ограничение 1: `get_metadata` для регистра сведений возвращает пустой `attributes:[]`

**Проявление:**
```json
{"success": true, "data": {
  "fullName": "РегистрСведений.<имя>",
  "name": "<имя>",
  "synonym": "...",
  "attributes": []
}}
```

Поля `Измерения` / `Ресурсы` / `Реквизиты` отсутствуют, хотя в конфигурации они есть.

**Workaround:** проверять имена полей через `execute_query` (выбрать первые 5 строк со всеми ожидаемыми колонками — если запрос не падает, поля существуют):
```sql
ВЫБРАТЬ ПЕРВЫЕ 5
    Регистр.<Поле1>, Регистр.<Поле2>, ...
ИЗ РегистрСведений.<имя> КАК Регистр
```

Альтернатива — `EDT-MCP: get_metadata_details(fqn)` (если EDT доступен — даёт полную структуру).

### Ограничение 2: `execute_query` падает на сериализации композитных ссылочных типов

**Проявление:**
```
{"success": false, "error":
  "{MCP_Сервер ОбщийМодуль.mcp_Сериализация.Модуль(142)}:
   Метод объекта не обнаружен (УникальныйИдентификатор)"}
```

Возникает при возврате полей с композитным ссылочным типом (например, `ДокументСсылка.X, ДокументСсылка.Y` в одном поле — типично для реквизитов вида `гкс_ДокументРегистрации`).

**Workaround:** оборачивать такие поля в `ПРЕДСТАВЛЕНИЕ()`:
```sql
ВЫБРАТЬ
    ПРЕДСТАВЛЕНИЕ(ЛА.гкс_ДокументРегистрации) КАК ДокументРегистрации,
    ПРЕДСТАВЛЕНИЕ(ЛА.Ссылка) КАК ЛабораторныйАнализ
ИЗ Документ.гкс_ЛабораторныйАнализ КАК ЛА
```

`ПРЕДСТАВЛЕНИЕ()` возвращает строку, сериализация не ломается. Если нужна именно ссылка для дальнейшего использования (например, передать как параметр) — использовать `execute_code` с явным присваиванием в `Результат`, обходя сериализацию query-результата:
```bsl
Результат = РегистрыСведений.<имя>.СоздатьМенеджерЗаписи();
```

### Когда workaround'ы недостаточны

Если задача требует получить именно ссылочные значения через query (без `execute_code`-обхода) — отметить в IMPLEMENTATION-PROGRESS.md как `требует доработки расширения MCP_Сервер` и провалидировать алгоритм через `execute_code` или EDT-симуляцию.

---

## Обработка ошибок

### EDT-MCP: get_project_errors вернул ошибки

1. Прочитать текст ошибки
2. Определить причину (опечатка, несуществующий метод, неправильный тип)
3. Исправить код
4. Повторить write_module_source → get_project_errors
5. Максимум 3 попытки. После 3-й — сообщить пользователю с текстом ошибки

### EDT-MCP: validate_query вернул ошибку

1. Проверить имена полей через get_metadata
2. Проверить синтаксис (скобки, кавычки, ЗНАЧЕНИЕ())
3. Исправить запрос
4. Повторить validate_query
5. Если поле не найдено — возможно, нужен другой алиас или полное имя

### 1c-mcp-crud: execute_query вернул пустой результат

1. Проверить параметры запроса (правильные ссылки?)
2. Проверить условия WHERE (слишком строгие?)
3. Если данных действительно нет — это НЕ ошибка для превентивных проверок
4. Зафиксировать в IMPLEMENTATION-PROGRESS.md

### bsl-debug-server: bsl_analyze вернул предупреждения

1. Критичные (Error) — исправить обязательно
2. Warning — оценить, исправить если разумно
3. Info — игнорировать
4. Зафиксировать количество в IMPLEMENTATION-PROGRESS.md

---

## Чеклист завершения (проверить перед Этапом 8)

- [ ] Все точки модификации из ANALYSIS-REPORT реализованы
- [ ] Каждый блок кода имеет комментарий с номером задачи
- [ ] EDT-MCP: `get_project_errors(severity="ERRORS") = 0`
- [ ] Все SQL-запросы прошли `validate_query`
- [ ] Все SQL-запросы проверены на живых данных (`execute_query`) — с workaround `ПРЕДСТАВЛЕНИЕ()` для ссылок (см. Известные ограничения 1c-mcp-crud)
- [ ] `bsl_analyze`: 0 ошибок ИЛИ только known false-positive'ы (chained call / препроцессор) — зафиксировано в IMPLEMENTATION-PROGRESS.md
- [ ] **Этап 6 → шаг 0**: конфигурация БД обновлена (`update_database` или ручной EDT) — без этого live-вызовы возвращают старое поведение
- [ ] Тест-план из ANALYSIS-REPORT: все тесты PASS или помечены SKIP с причиной (минимум — SQL-симуляция, если БД не обновлена)
- [ ] **Рефакторинг (если применимо):** все `bsl_rename_symbol` / `bsl_replace_method_body` прошли `dry_run` → `apply`, `manual_required` обработаны вручную, routing backend + confidence зафиксированы в IMPLEMENTATION-PROGRESS.md
- [ ] IMPLEMENTATION-PROGRESS.md создан/обновлён
- [ ] Отклонения от ANALYSIS-REPORT зафиксированы
- [ ] **Git commit:**
  - [ ] Коммит во внутреннем repo с BSL (без `git add -A`, без `git add <submodule-dir>`)
  - [ ] Промежуточный repo обновил gitlink (если есть вложенный submodule)
  - [ ] Documentation submodule (`configuration/<TaskFolder>`) закоммичен с PROGRESS-файлом
  - [ ] Main repo обновил gitlink на documentation submodule
  - [ ] Submodule без identity → коммит через `git -c user.name=... -c user.email=...`
