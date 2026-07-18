---
name: implement-1c-task
description: "Реализация задачи 1С по готовому ANALYSIS-REPORT.md (BSL/XML через EDT-MCP). ТОЛЬКО после /analyze-1c-task-v2, когда есть ANALYSIS-REPORT с точками модификации. НЕ для анализа задач (→ analyze-1c-task-v2), НЕ для Claude Code, НЕ для LangChain."
version: 2.9.0
updated: 2026-07-13
tags: [1c, implementation, bsl, configuration, edt-mcp, 1c-mcp-crud, bsl-debugger, 1c-debug-hmr]
triggers:
  - реализовать задачу 1С
  - implement 1c task
  - внести изменения по анализу
  - реализация по ANALYSIS-REPORT
commands:
  - /implement-1c-task
---

> **4-этапная парадигма (ADR-019 B′, G5/G2):** этот skill реализует **Этап 3 «Кодирование»** (Этапы 0–3:
> preflight→подготовка→валидация→BSL-write) и **Этап 4 «Тестирование»** (Этапы 4–6 + `/write-1c-tests`/`/run-1c-tests`).
> **Sonar обязателен (ADR-037):** после BSL-правок — `scripts/run-sonar-analysis.ps1` → `python scripts/sonar_rescan_verify.py`; Stop-гейт `onec-task-completion-stop` блокирует завершение, если изменённый/добавленный `.bsl` под `/src/` не прошёл Sonar с чистой дельтой (0 BLOCKER/CRITICAL). Sonar-down→skip; opt-out `ONEC_SONAR_GATE_DISABLE=1`. **С 2026-07-03 verify — `mode=changed-lines`:** дельта = пересечение issue-строк с `git diff -w` изменённых файлов (сервер-независимый Clean-as-You-Code; вырожденный server-baseline [первый скан → new≈total] детектится и репортится, но не гейтит). **Норма — ОДИН скан на задачу:** собрать ВСЕ контент-правки (код + док-комменты) → формат → `bsl_lint --fail-on-error` локально → один скан → один verify; каждая правка ПОСЛЕ скана делает его stale (гейт потребует пересканирования, скан — минуты).
> Артефакт — `IMPLEMENTATION-PROGRESS.md`. `pipeline/<slug>/.pipeline-state.json` ведётся **автоматически** (preflight-мост
> F-1, advance F-1.5). **Гейт (F-2):** запуск БЛОКИРУЕТСЯ, пока дизайн (этап 2, ANALYSIS-REPORT) не одобрен —
> `pipeline_state.py approve <slug>`. См. [roadmap 260614](../../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md).

# Реализация задачи 1С — 8-этапный pipeline (v2.9)

> **История версий:** полный список изменений v2.0.0 → v2.8.1 — [references/tools-reference.md#история-версий-implement-1c-task](references/tools-reference.md#история-версий-implement-1c-task). Текущая версия - **2.9.0 (2026-07-13)**: Этапы 5.x/6 - верификация и тестирование ОБЯЗАТЕЛЬНО на **реальных данных** живой базы + обязательная глава **«Тестирование на реальных данных»** в IMPLEMENTATION-PROGRESS.md (мандат пользователя, ADR-050; advisory-контроль `lint_1c_artifacts`). Предыдущая - 2.8.1 (2026-06-15): Этап 4, опциональный шаг 0 «автоформат» (`bsl_lint.py --format`).

## Overview

Skill для реализации задачи по конфигурации 1С:Предприятие.
На входе — готовый ANALYSIS-REPORT.md (от analyze-1c-task-v2).
На выходе — внесённые BSL/XML изменения, верифицированные на живых данных и закоммиченные.

**Отличия v2 от v1:**
- EDT-MCP: чтение/запись BSL-модулей прямо в проект EDT, валидация запросов, проверка ошибок
- **codepilot1c (1С Copilot): мутации форм / DCS / прав ролей / макетов — то, что EDT-MCP НЕ делает**
- 1c-mcp-crud: верификация SQL на живых данных ДО записи, подготовка тестовых данных, проверка результатов ПОСЛЕ
- bsl-debugger: статический анализ BSL-кода, отладка чистой логики в OneScript

## Входные данные

Из аргументов команды:
1. **Путь к docs/** — папка с ANALYSIS-REPORT.md
2. **Путь к src/** — корень исходников конфигурации (опционально, определяется автоматически)

## Инструменты (4 MCP-сервера + вспомогательные)

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

**Полный набор EDT-MCP по этапам** (~36 из 70 тулов, дополняет hot-path таблицу выше): [references/tools-reference.md#полный-набор-edt-mcp-по-этапам](references/tools-reference.md#полный-набор-edt-mcp-по-этапам).

### codepilot1c (1С Copilot) — мутации, которые EDT-MCP НЕ делает (форма/DCS/роли/макеты)

> EDT-MCP **не мутирует формы** (только `get_form_screenshot`/`get_form_layout_snapshot`), не трогает DCS, права ролей, макеты печатных форм. Для этих правок — **codepilot1c** (тот же EDT-проект, модельная валидированная правка). **Все мутации требуют `edt_validate_request` → `validation_token` ПЕРЕД** `mutate_*`/`apply_*`/`dcs_manage` (обязательный гейт сервера). Скилл: [`codepilot1c`](../codepilot1c/SKILL.md).

| Инструмент | Когда использовать |
|---|---|
| `inspect_form_layout` | Этап 3: прочитать дерево формы (id/dataPath/тип) ПЕРЕД мутацией |
| `mutate_form_model` | Этап 3: добавить/изменить элемент формы (`add_field` виджет `CHECK_BOX_FIELD`/`INPUT_FIELD` + `data_path`, **вкл. привязку к члену `ConstantsSet` — EDT-MCP это НЕ умеет**) |
| `apply_form_recipe` | Этап 3: форма + реквизиты формы + layout пакетно |
| `create_form` | Этап 3: новая управляемая форма для объекта |
| `dcs_manage` | Этап 3: схема компоновки данных (наборы/параметры/вычисляемые поля) — у EDT-MCP нет |
| `inspect_role_rights` / `mutate_role_rights` | Этап 3/5: права роли по объектам/флаги (напр. право на новую константу — R-1 из ANALYSIS-REPORT) |
| `inspect_template` / `render_template` | Этап 3: макет печатной формы (.mxl из секционного JSON) |
| `qa_plan_scenario`/`qa_generate`/`qa_validate_feature`/`qa_run` · `author_yaxunit_tests` | Этап 6: Vanessa BDD / YAxUnit через MCP-модель (альтернатива va-bdd/yaxunit-скиллам) |

**Правило выбора (форма/DCS/роль/макет):** `inspect_*` → `edt_validate_request` → `mutate_*`/`apply_*`/`dcs_manage`. **НЕ править `Form.form`/`.mxl`/`.dcs` руками** — codepilot1c даёт валидированную модельную правку; ручной XML — только фолбэк при недоступности codepilot1c (тогда кросс-проверять `inspect_form_layout`). Урок GKSTCPLK-2640: флажок на форму набора констант EDT-MCP не привязал (dotted `dataPath` к `ConstantsSet` он трактует как колонку динсписка), нативный путь — `mutate_form_model add_field CHECK_BOX_FIELD data_path=НаборКонстант.<константа>`.

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

### bsl-debugger — статический анализ и отладка

| Инструмент | Когда использовать |
|---|---|
| `bsl_analyze` | Этап 4: статический анализ написанного BSL-кода (линтер) |
| `bsl_execute` | Этап 4: запустить фрагмент BSL-логики в OneScript (без базы) |
| `bsl_debug_start` | Этап 4: пошаговая отладка алгоритма (breakpoints, step) |
| `bsl_debug_variables` | Этап 4: проверить значения переменных в точке останова |

**Ограничение bsl-debugger:** Работает через OneScript, НЕ через 1С:Предприятие.
Нет доступа к объектам 1С (Документы, Регистры, Справочники). Подходит ТОЛЬКО для:
- Проверки чистой логики (условия, циклы, формирование массивов)
- Статического анализа (bsl_analyze) — но **с известными false-positive'ами на стандартных 1С-конструкциях** (директивы препроцессора `#Если ... Тогда`, chained `Запрос.Выполнить().Пустой()`). См. Этап 4 → graceful skip.
- НЕ подходит для запросов к базе — для этого используй 1c-mcp-crud

### 1c-debug-hmr — live отладка через RDBG (HMR wrapper, default since 2026-05-10)

`1c-debug-hmr` обёрнут HMR subprocess'ом (`mcp_hmr_proc.py`) — wrapper reload'ит сервер при изменении `mcp_debug_server.py` / `bsl_locals.py` / `uuid_index.py` без потери session к dbgs (persistence через `data/debug_sessions/.active.json`). Используется по умолчанию в Этапе 0 (`debug_health_check`) и Этапе 5.x (BP-verification).

Plain `1c-debug` (без HMR) — оставлен как CI/production-вариант (нет watcher overhead'а); переключение через env-флаг `IMPLEMENT_1C_USE_PLAIN_DEBUG=true`.

Ключевые инструменты: `debug_health_check` (Этап 0 probe), `debug_connect`/`debug_set_breakpoint`/`debug_get_breakpoints` (установка BP), `debug_ping`/`debug_stack_trace`/`debug_variables`/`debug_step` (Этап 5.x цикл), `debug_session_diff` (Этап 5.y regression). Полная таблица 13 тулов + режимы применения: [references/tools-reference.md#1c-debug-hmr--полная-таблица-инструментов-этап-5x-bp-verification](references/tools-reference.md#1c-debug-hmr--полная-таблица-инструментов-этап-5x-bp-verification). Skill: [1c-debug-hmr](../1c-debug-hmr/SKILL.md).

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
   | `bsl-debugger` | `mcp__bsl-debugger__bsl_analyze` или `mcp__1c-debug__debug_targets` | tool существует |

2-6. TCP-probe портов (`:8765` edt-mcp, `:1550` debug agent, либо `python scripts/smoke_test_implement_1c_task.py`), debug environment health через `debug_health_check(mode="probe")`, сопоставление с матрицей капабилити (Full / Full (no-BP) / Code-only / Read-only verify / Read-only research), сообщение пользователю о деградации, сохранение режима + `debug_session_id` в IMPLEMENTATION-PROGRESS.md footer — полный текст шагов и таблица капабилити: [references/stage-details.md#этап-0-preflight--детали-шаги-2-6](references/stage-details.md#этап-0-preflight--детали-шаги-2-6).

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

   **Path-fallback при File-not-found (Designer→EDT flatten)** и **fallback без edt-mcp** (`bsl-code-search`/`bsl-semantic-search`/`Read`, с перечнем ограничений) — полный текст: [references/stage-details.md#этап-1-подготовка--детали-fallbackов-шаг-3](references/stage-details.md#этап-1-подготовка--детали-fallbackов-шаг-3).

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

> **⚠ Правки `.bsl` — батчем, одним вызовом (2026-07-03).** PostToolUse-хук авто-формата (`bsl_lint --format`, ADR-036) срабатывает после каждого Write/Edit и переписывает файл на диске → серия последовательных Edit по одному файлу гоняется с форматером (stale-read, упавшие old_string). Все правки одного модуля собирать в ОДИН вызов: один `write_module_source` ИЛИ один python-скрипт (string-replace + assert-счётчики вхождений). Формат теперь селективный (только строки, изменённые vs HEAD; EOL сохраняется), но гонку Edit-серии это не отменяет.
>
> **Док-комментарии — сразу.** Каждый новый/извлечённый метод получает док-коммент (описание, `Параметры:`, `Возвращаемое значение:`) в момент написания, НЕ «потом»: Sonar-правила `MissingParameterDescription`/`MissingReturnedValueDescription` (MAJOR) на новом коде = лишняя итерация правка→скан (скан — минуты).

> **⚠ Impact-чек перед правкой ЭКСПОРТНОГО метода (обязательно, В2 260718).** Если точка модификации — правка/удаление СУЩЕСТВУЮЩЕГО экспортного метода (`Процедура/Функция … Экспорт`), ПЕРЕД изменением запусти `mcp__bsl-semantic-search__bsl_impact_analysis` (кто вызывает эту точку) и зафиксируй затронутых вызывающих в IMPLEMENTATION-PROGRESS (проверить их на регресс в тестировании). Экспортная точка = внешний контракт: правка без impact-анализа = регрессия «кто сломается» ловится тестами/пользователем, а не ДО правки. Presence impact замерялась **1.8%** (W1 аудита 260718); условие применимости детектится `shared/onec_change_scope.edits_exported_method` (честный applicable-знаменатель, [ADR-035 §19](../architecture-research/adr/035-mandatory-high-leverage-1c-tools.md)). **Добавление НОВОГО** экспортного метода impact не требует (вызывающих ещё нет).

#### Decision gate: рефакторинг или новый функционал?

Перед началом Этапа 3 для каждой точки модификации определить тип операции:

| Тип операции | Признак | Путь |
|---|---|---|
| **Новый функционал** | Добавление новой процедуры/реквизита/формы/подсистемы; вставка строк в существующий метод | **Стандартный Этап 3** (EDT-MCP `write_module_source`) |
| **Рефакторинг** | Переименование процедуры/переменной/параметра; замена тела существующего метода целиком; safe delete с проверкой references | **Этап 3R** (см. ниже) — активировать [bsl-refactoring-workflow](../bsl-refactoring-workflow/SKILL.md) |
| **Гибрид** | Новый функционал + попутное переименование существующих символов | Сначала Этап 3R (рефакторинг), потом Этап 3 (новый код) |

**Критерий однозначный:** если существующий символ меняет имя/удаляется/заменяется тело — это рефакторинг, `bsl_rename_symbol` / `bsl_replace_method_body` / `bsl_safe_delete_symbol`. Если только добавляются новые символы или строки внутри метода — это не рефакторинг, стандартный путь.

#### Этап 3R: Рефакторинг через bsl-semantic-search refactor (условный)

**Применяется только если decision gate определил операцию как рефакторинг.** Классификация символа → routing matrix, `bsl_rename_symbol`/`bsl_replace_method_body` с `dry_run: true` → проверка плана → confirm → верификация `get_project_errors` → лог в IMPLEMENTATION-PROGRESS.md. Полный 6-шаговый протокол: [references/stage-details.md#этап-3r-рефакторинг-через-bsl-semantic-search-refactor-условный](references/stage-details.md#этап-3r-рефакторинг-через-bsl-semantic-search-refactor-условный); workflow: [bsl-refactoring-workflow/SKILL.md](../bsl-refactoring-workflow/SKILL.md).

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

0. **(Опционально) Автоформат изменённого модуля через bsl-ls** ПЕРЕД диагностикой — единый стиль (отступы/пробелы) по стандартам 1С:
   ```
   python scripts/bsl_lint.py <module.bsl> --format
     → bsl-ls `--format` правит файл in-place; write-back ТОЛЬКО при изменении (сохраняет BOM/кодировку).
       Селективно (2026-07-03): формат применяется ТОЛЬКО к строкам, изменённым vs HEAD; легаси-строки
       и EOL-стиль файла не трогаются (churn-guard: дифф не раздувается, SCM-атрибуция Sonar не ломается).
       Идемпотентно (2-й прогон = «без изменений»). Снимает косметические замечания (MissingSpace и т.п.) до lint.
   ```
   После записи через EDT-MCP — перечитать модуль (`read_module_source`), т.к. файл переписан на диске.

1. **Для каждого изменённого модуля — точная BSL-диагностика через bsl-language-server** (ADR-020, предпочтительно):
   ```
   python scripts/bsl_lint.py <module.bsl> --severity error --fail-on-error
     → bsl-ls (128+ диагностик): точнее OneScript bsl_analyze (нет false-positive на #Если/chained-call;
       ловит InvalidCharacterInFile / IfElseIfEndsWithElse / Typo). Java auto-discovery (1C:EDT Axiom JDK 17).
   ```
   Реализация — [`scripts/bsl_lint.py`](../../../scripts/bsl_lint.py) (foundation «своей bsl-ls обвязки», ADR-020).

   **Fallback** (Java/bsl-ls недоступны — bundled JRE = невыгруженный LFS-указатель / EDT не запущен):
   ```
   bsl-debugger: bsl_analyze(file=<absolute_path>)
     → OneScript-линтер (известные false-positive'ы — см. ниже)
   ```

2. **Если `bsl_analyze` падает с parse error** — проверить, попадает ли ошибка в список known false-positive'ов (см. ниже). Если да — фиксируем как tool-limitation и считаем этап пройденным (EDT-валидация в Этапе 3 уже подтвердила корректность кода). Если нет — есть реальная ошибка, исправлять через Этап 3.

3-6. Опционально — `bsl_execute` на чистой логике, пошаговая `bsl_debug_start`/`bsl_debug_step`, экспериментальный live runtime debug через `1c-debug-hmr` (НЕ путать с обязательной Этап 5.x BP-verification), исправление реальных проблем (повтор Этапа 3). Known false-positive'ы `bsl_analyze` (директивы препроцессора, chained-call), workaround и правила логирования в IMPLEMENTATION-PROGRESS.md — полный текст: [references/stage-details.md#этап-4-статический-анализ--детали-шаги-3-5-false-positives-логирование](references/stage-details.md#этап-4-статический-анализ--детали-шаги-3-5-false-positives-логирование).

**Контрольная точка:**
- EDT `get_project_errors(severity="ERRORS") = 0` (авторитетный источник для 1С) — ОБЯЗАТЕЛЬНО
- `bsl_lint.py --severity error` = 0 (предпочтительно, bsl-ls) ИЛИ `bsl_analyze` = 0 / только known false-positive'ы (fallback, см. reference)

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

#### Этап 5.x: Live BP verification (ОБЯЗАТЕЛЬНО при режиме Full, SKIP при Full (no-BP))

**Цель:** доказать live-trace'ом что новый код действительно исполняется по ожидаемому пути. EDT `get_project_errors=0` означает «компилируется», но НЕ означает «вызывается». Без BP-trace pipeline может пропустить случай, когда `[MODIFIED]` точка изменена в другом месте, чем планировалось (например, реализация изменила процедуру Б случайно вместо процедуры А из ANALYSIS-REPORT).

**Когда применяется:** для КАЖДОЙ `[ADDED]`/`[MODIFIED]` точки модификации из ANALYSIS-REPORT. Точки `[REFACTOR]` (rename / replace body / safe delete) — BP не требуется (изменение тождественно по поведению).

**Данные триггера - реальные (v2.9.0, ADR-050):** trigger-harness (`execute_code`/`execute_query`) вызывает изменённый код с **реальными данными живой базы** - кандидатов подбирать `execute_query` по фактическому наличию, параметры воспроизводить функциями ВЫЗЫВАЮЩЕГО (Шаблон 7 skill [1c-debug-hmr](../1c-debug-hmr/SKILL.md)), НЕ выдуманными значениями; синтетика - только при пустой базе, с явной пометкой. Идентификаторы использованных данных (номер/код/дата, ссылка) фиксировать по ходу - они обязаны попасть в главу «Тестирование на реальных данных» (Этап 7).

**Шаг 0 — авто-калибровка строк (ОБЯЗАТЕЛЬНО, 2026-07-07):** номера строк локальных исходников (repo/EDT) систематически смещены относительно deployed-конфигурации — BP по строке из src молча не fire'ит (live-кейс: сдвиг +3). Перед первым точечным BP модуля: `debug_calibrate_lines(object_id, line_из_src)` → триггер фоновым заданием (`ФоновыеЗадания.Выполнить` через `execute_code` — прямой execute_code через HTTP-service НЕ ловится, RC2) → `debug_ping` ×2-3 → `debug_calibrate_result` → реальная строка + `offset` (применим ко всем BP этого модуля; на nearest уже стоит обычный BP). Детали — skill [1c-debug-hmr](../1c-debug-hmr/SKILL.md) Шаблон 5a.

**Полный 8-шаговый протокол** (`debug_connect`→`debug_set_breakpoint`→`debug_get_breakpoints`→триггер `execute_code`/`execute_query`→`debug_ping`→`debug_stack_trace` assert→`debug_variables`→`debug_step(Continue)`), fallback при не-fire (`debug_break_on_next` → `force_recycle_rphost` / thin client Solution C), 15-минутный timeout user-in-the-loop ветки, success criterion, шаблон логирования в IMPLEMENTATION-PROGRESS.md, и **Этап 5.y Regression diff** (`debug_session_diff` verdict-гейт) — полный текст: [references/stage-details.md#этап-5x-live-bp-verification--8-шаговый-протокол--fallback](references/stage-details.md#этап-5x-live-bp-verification--8-шаговый-протокол--fallback).

**⚠ Окно останова эфемерного JOB ≈ 1–2 с** (платформа принудительно возобновляет halt): `debug_variables`/`debug_evaluate` — сразу после ping с `stopByBP=true`; «Предмет отладки не зарегистрирован» = target уже завершился (не баг attach) → повторить прогон или читать переменные через `debug_set_logpoint` (JSONL, без гонки).

**Контрольная точка:** Нет новых ошибок, все ссылки на изменённые методы корректны, ВСЕ `[ADDED]`/`[MODIFIED]` точки покрыты BP-trace'ом (или обоснованно SKIP), regression verdict ≠ REGRESSION (если baseline есть).

---

### Этап 6: Тестирование на живых данных

**Цель:** Выполнить тест-план из ANALYSIS-REPORT на реальной базе - на **реальных данных** (существующие документы/записи, подобранные `execute_query`; каждые использованные данные фиксируются с идентификаторами для главы «Тестирование на реальных данных» Этапа 7).

**КРИТИЧНО — почему этот этап имеет ОБЯЗАТЕЛЬНЫЙ шаг 0:**

EDT-MCP `write_module_source` правит **исходники** проекта (`src/...`) и помечает изменения для последующей сборки. Запущенная инфобаза 1С работает с **уже скомпилированной** конфигурацией БД. Пока конфигурация БД не обновлена, любой `1c-mcp-crud: execute_code(...)` или проведение документа выполняет **СТАРУЮ** версию изменённой функции. Без шага 0 Этап 6 даёт ложно-отрицательный результат: «фикс не сработал» — потому что live-инфобаза не видит изменений.

**Шаги 0-5** (обновление конфигурации БД через `update_database` с программным gate на активные подключения → подготовка тестовых данных → пользователь проводит документ → проверка результата → очистка → фиксация в PROGRESS), альтернатива SQL-симуляции без обновления БД, и **YAxUnit unit-тесты** (`/write-1c-unit-tests` → `yaxunit-unit-testing`, деплой расширения, smoke `run_module_tests`) — полный текст: [references/stage-details.md#этап-6-тестирование-на-живых-данных--детали-шаги-0-5](references/stage-details.md#этап-6-тестирование-на-живых-данных--детали-шаги-0-5).

---

### Этап 7: Документация

**Цель:** Зафиксировать что было сделано.

**Создать/обновить файл IMPLEMENTATION-PROGRESS.md** в той же папке docs/ (статус, pipeline mode, точки модификации, debug session, результаты тестирования, footer `debug_session_id`) — полный шаблон + правила footer'а: [references/stage-details.md#этап-7-документация--шаблон-implementation-progressmd](references/stage-details.md#этап-7-документация--шаблон-implementation-progressmd).

**ОБЯЗАТЕЛЬНО — секция `## Сообщение коммита`** (в конце файла, НИКОГДА не пропускать): готовое сообщение git-коммита, сформированное по скиллу [`git-commit-message`](../git-commit-message/SKILL.md) — формат **«Как было / Как стало/список результатов»** + `Изменённые/добавленные объекты` (термины 1С: «Общий модуль», «Документ», «Регистр сведений», «Запрос» — НЕ имена файлов) + футер `МЕТАДАННЫЕ: GKSTCPLK-XXXX`. Это **то же самое** сообщение, которым коммитится Этап 8 — пользователь копирует его прямо из файла, без переспроса. Наличие секции проверяет advisory-хук `pipeline-1c-advance` (через `scripts/lint_1c_artifacts.py`).

**ОБЯЗАТЕЛЬНО - глава `## Тестирование на реальных данных`** (v2.9.0, мандат пользователя 2026-07-13, ADR-050): на каких данных тестировалось и какие результаты. Структура:
- **База:** `Srvr=...;Ref=...` / MCP-профиль, на которых шли Этапы 5.x/6.
- **Таблица данных:** `Объект | Идентификатор (номер/код/ссылка) | Дата | Сценарий` - конкретные реальные документы/записи, использованные BP-триггерами и тест-планом.
- **Инструменты:** BP-trace `1c-debug-hmr` (модуль:строка, стек frames[-1], значения переменных), `execute_query`/`execute_code`, YAxUnit/VA BDD - что применялось.
- **Результаты:** per-сценарий PASS/FAIL + итоговый вердикт; синтетические данные/SKIP - явно, с причиной.

Наличие главы проверяет `lint_1c_artifacts` (advisory) через `pipeline-1c-advance`.

---

### Этап 8: Git commit

**Цель:** Закоммитить изменения, аккуратно работая с многоуровневой структурой репозиториев (main repo → level-2 обычная директория → level-3 submodule/gitlink).

**Сообщение коммита — строго по скиллу [`git-commit-message`](../git-commit-message/SKILL.md)** (формат «Как было / Как стало», термины 1С, футер `МЕТАДАННЫЕ: GKSTCPLK-XXXX`). Это **ровно то же** сообщение, что вписано секцией `## Сообщение коммита` в IMPLEMENTATION-PROGRESS.md (Этап 7) — единый источник, не переформулировать заново. Коммитить через файл: `git commit -F <msg-файл>` (кириллица UTF-8; НЕ `-m` из PowerShell — портит кодировку, [[feedback-powershell-git-commit-utf8]]).

**Кратко:** submodule с BSL-кодом коммитится отдельно (`git -C "<submodule>" add <file> && commit`), submodule с документацией — отдельно, затем main repo bump'ит оба gitlink'а (`git add "<submodule-path>"` — не `-A`, не голая директория). Identity без `git config` — через per-command `-c user.name=... -c user.email=...`. Кириллические пути — через `-c core.quotepath=false`.

**⚠ НЕ использовать** `git add -A` в submodule и `git add <submodule-dir>` в родителе (индексирует untracked внутри, `fatal: filename too long` на Windows).

Полная структура репозиториев (3-уровневая диаграмма), пошаговый git-flow, git identity workaround и diagnostic-команды для подтверждения layout перед коммитом: [references/git-workflow.md](references/git-workflow.md).

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

Сервер `1c-mcp-crud` подключается к live-инфобазе через HTTP-сервис расширения `MCP_Сервер`. Три известных артефакта на Этапах 2, 5, 6: (1) `get_metadata` для РС возвращает пустой `attributes:[]` — workaround `execute_query` ПЕРВЫЕ 5; (2) `execute_query` падает на сериализации композитных ссылочных типов — workaround `ПРЕДСТАВЛЕНИЕ()`; (3) `execute_code` запрещает `Возврат` вне процедуры/функции — workaround `Если/Иначе` (кроме случаев с side-effects между early-exit точками — тогда named procedure). Полное описание с примерами: [references/gotchas.md#известные-ограничения-1c-mcp-crud](references/gotchas.md#известные-ограничения-1c-mcp-crud).

---

## Обработка ошибок

Стандартные рецепты триажа: `get_project_errors` (максимум 3 попытки исправления), `validate_query` (проверить имена полей/синтаксис), `execute_query` пустой результат (не ошибка сама по себе), `bsl_analyze` предупреждения (Error обязательно / Warning по ситуации / Info игнор). Полный текст: [references/gotchas.md#обработка-ошибок](references/gotchas.md#обработка-ошибок).

---

## Чеклист завершения (проверить перед Этапом 8)

- [ ] Все точки модификации из ANALYSIS-REPORT реализованы
- [ ] Каждый блок кода имеет комментарий с номером задачи
- [ ] EDT-MCP: `get_project_errors(severity="ERRORS") = 0`
- [ ] Все SQL-запросы прошли `validate_query`
- [ ] Все SQL-запросы проверены на живых данных (`execute_query`) — с workaround `ПРЕДСТАВЛЕНИЕ()` для ссылок (см. Известные ограничения 1c-mcp-crud)
- [ ] `bsl_analyze`: 0 ошибок ИЛИ только known false-positive'ы (chained call / препроцессор) — зафиксировано в IMPLEMENTATION-PROGRESS.md
- [ ] **Этап 6 → шаг 0**: конфигурация БД обновлена (`update_database` или ручной EDT) — без этого live-вызовы возвращают старое поведение
- [ ] **Этап 5.x BP-verification (режим Full)**: ВСЕ `[ADDED]`/`[MODIFIED]` точки покрыты BP-trace'ом (frames[0].lineNo соответствует MODIFIED_LINE), либо обоснованно помечены SKIP в IMPLEMENTATION-PROGRESS. Точки `[REFACTOR]` — освобождены.
- [ ] **Этап 5.y Regression diff (если есть baseline session_id в footer)**: `debug_session_diff` verdict ∈ {NO_REGRESSION, IMPROVEMENT, NEUTRAL}; при REGRESSION pipeline блокируется.
- [ ] **Footer IMPLEMENTATION-PROGRESS.md**: `<!-- debug_session_id: <UUID> -->` записан (если режим Full и BP-verification PASS) — для regression diff на следующем прогоне
- [ ] Тест-план из ANALYSIS-REPORT: все тесты PASS или помечены SKIP с причиной (минимум — SQL-симуляция, если БД не обновлена)
- [ ] **Рефакторинг (если применимо):** все `bsl_rename_symbol` / `bsl_replace_method_body` прошли `dry_run` → `apply`, `manual_required` обработаны вручную, routing backend + confidence зафиксированы в IMPLEMENTATION-PROGRESS.md
- [ ] **Sonar-дельта (ADR-037):** ВСЕ контент-правки собраны (вкл. док-комментарии новых методов) → ОДИН `run-sonar-analysis.ps1` → `sonar_rescan_verify.py` PASS (0 BLOCKER/CRITICAL на изменённых строках)
- [ ] **Глава `## Тестирование на реальных данных`** в IMPLEMENTATION-PROGRESS.md: база + таблица реальных данных (идентификаторы) + инструменты + результаты PASS/FAIL (v2.9.0, ADR-050; проверяет `lint_1c_artifacts`)
- [ ] IMPLEMENTATION-PROGRESS.md создан/обновлён
- [ ] **IMPLEMENTATION-PROGRESS.md содержит секцию `## Сообщение коммита`** (git-commit-message формат: Как было / Как стало + `МЕТАДАННЫЕ: GKSTCPLK-XXXX`) — то же сообщение, что и git-коммит Этапа 8 (проверяет `lint_1c_artifacts` через `pipeline-1c-advance`)
- [ ] Отклонения от ANALYSIS-REPORT зафиксированы
- [ ] **Git commit:**
  - [ ] Коммит во внутреннем repo с BSL (без `git add -A`, без `git add <submodule-dir>`)
  - [ ] Промежуточный repo обновил gitlink (если есть вложенный submodule)
  - [ ] Documentation submodule (`configuration/<TaskFolder>`) закоммичен с PROGRESS-файлом
  - [ ] Main repo обновил gitlink на documentation submodule
  - [ ] Submodule без identity → коммит через `git -c user.name=... -c user.email=...`
