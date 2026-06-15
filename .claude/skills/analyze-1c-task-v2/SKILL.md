---
name: analyze-1c-task-v2
description: >
  5-фазная методология анализа задачи 1С:Предприятие.
  Требования -> Объекты -> Алгоритм -> План -> Верификация.
  v4.0: SDD-интеграция (OpenSpec delta-specs, approval gate, brownfield validation).
version: 4.2.0
updated: 2026-05-11
tags: [1c, analysis, bsl, configuration, methodology, semantic-search, autoresearch, three-agent, 1c-debug-hmr]
ultrathink: true
commands:
  - /analyze-1c-task
---

> **4-этапная парадигма (ADR-019 B′, G5/G2):** этот skill реализует **Этап 1 «Планирование архитектуры»** (Фазы 1–3:
> Требования→Объекты→Алгоритм, +2.5 Trace) и **Этап 2 «Дизайн реализации»** (Фазы 4–5: План модификаций + тест-стратегия,
> +опц. OpenSpec). Артефакт обоих этапов — `ANALYSIS-REPORT.md`. `pipeline/<slug>/.pipeline-state.json` ведётся
> **автоматически** (preflight-мост F-1) и двигается по записи отчёта (F-1.5). **Гейт (F-2):** дизайн (этап 2) одобряется
> человеком (`pipeline_state.py approve <slug>`) перед `/implement-1c-task`. См. [roadmap 260614](../../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md).

# Анализ задачи 1С — 5-фазная методология (v4.2)

## Overview

Skill для комплексного анализа задачи по конфигурации 1С:Предприятие.
На входе — ТЗ (описание задачи). На выходе — ANALYSIS-REPORT.md с пронумерованными
точками модификации, готовый для передачи в implement-1c-task.

**Улучшения v2 (C:\1С-Framework):**
- Семантический поиск по 3,900+ BSL-модулям (bsl-semantic-search)
- Поиск в индексированной документации 1С:8.3.27 (pdf-vector-graph)
- API платформы 1С (bsl-platform-context) — типы, методы, свойства
- Дешёвый LLM для подзадач анализа (llm-rotation)
- 3 слоя памяти для накопления опыта

**Улучшения v2.1:**
- Обязательный поиск паттернов и существующего функционала в конфигурации
- Верификация имён полей через get_metadata
- Подготовка комментариев с номером задачи в плане

**Улучшения v4.0 (SDD-интеграция):**
- Delta-spec маркеры `[ADDED]`/`[MODIFIED]` для каждого объекта (проверка через get_metadata)
- Маршрутизация на OpenSpec после анализа: ANALYSIS-REPORT → `/opsx:propose` → approval → apply
- Brownfield validation: после реализации → `brownfield-validate` (Gap+Design+Impl)
- Approval gate: `approval-gate.py` блокирует реализацию без одобрения спецификации

**Улучшения v4.1 (2026-04-19, bsl-semantic-search refactor integration):**
- Фаза 2 расширена вопросом `[REFACTOR]`: определение, является ли точка модификации рефакторингом существующего символа (rename/replace body/safe delete)
- Для `[REFACTOR]` точек в плане ОБЯЗАТЕЛЬНО: тип символа (local_variable/parameter/module_local_proc/module_export_proc/form_handler), ожидаемый backend (ast-grep/multilspy/manual), confidence из routing matrix
- Новый маркер `[REFACTOR]` дополняет `[ADDED]`/`[MODIFIED]` (может сочетаться: `[MODIFIED] [REFACTOR]` — существующий объект, операция — переименование/замена тела)

**Улучшения v4.2 (2026-05-11, 1c-debug-hmr integration):**
- Опциональная **Фаза 2.5 Runtime Trace** между «Объекты» и «Алгоритм» — live BP-trace через `mcp__1c-debug-hmr__*` для сложных runtime-алгоритмов (≥3 ветвлений по runtime-данным)
- Триггер: флаг `--trace` или skill self-decision при наличии условий по `Пользователи.ТекущийПользователь()`, `ПолучитьФункциональнуюОпцию`, `Тип(Параметр)`, режимам проведения
- Output: новая секция «3.Y Runtime Trace» в ANALYSIS-REPORT.md с Entry / Stack-JSON / Variables snapshot / Branch evaluation / **Discrepancies** (static vs runtime — load-bearing для Фазы 4)
- Без флага `--trace` и без self-decision триггера — фаза SKIP, время не растёт
- Источник: [roadmap 260510](../../../docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) Phase 2 (§4.1+§4.2)

**Улучшения v4.3 (2026-05-20, OpenSpec auto-propose):**
- Опциональный флаг `--auto-propose` к команде `/analyze-1c-task` — после Write ANALYSIS-REPORT.md skill дополнительно создаёт OpenSpec change через `mcp__openspec-mcp__openspec_create_change` (template=feature, changeId=<jira>-<краткое-описание-kebab>), затем populate `proposal.md`/`tasks.md`/`design.md`/`specs/<cap>/spec.md` из соответствующих секций ANALYSIS-REPORT.
- Триггер: явный `--auto-propose` в аргументах. Без него — skill только пишет ANALYSIS-REPORT (как v4.2), рекомендует `/opsx:propose` в Секции 11.
- Post-conditions: change создан, `openspec validate <changeId>` возвращает `valid: true`. При fail — skill stop'ит с warning и not run `/opsx:propose` автоматически.
- Источник: [roadmap 260520 §K](../../../docs/roadmap/260520_ROADMAP_OPENSPEC_INTEGRATION_V2.md)

## Permission scope (Вариант C — read-only анализатор)

**Skill оперирует в режиме read-only + единичный write выходного отчёта.**

Разрешено:

- MCP-инструменты для чтения (`bsl_search`, `bsl_hybrid_search`, `bsl_call_graph`, `bsl_impact_analysis`, `bsl_object_info`, `get_metadata`, `validate_query`, `find_references_to_object`, `pdf-vector-graph`, `bsl-platform-context`)
- `Read` / `Glob` / `Grep` — чтение исходников конфигурации и поиск по файлам
- `Write` — **исключительно для `ANALYSIS-REPORT.md`** (других файлов не создавать)
- `1c-debug-hmr` инструменты для опциональной Фазы 2.5
- `execute_query` (1c-mcp-crud) — read-only SELECT для верификации данных
- `memory-orchestrator__route_and_save` — сохранение анализа в память

Запрещено по дизайну (не входит в `allowed-tools`):

- `Edit` — модификация существующих файлов конфигурации. Если выявлены правки кода — фиксируются в `ANALYSIS-REPORT.md` как точки модификации, применяются через `/implement-1c-task`.
- `Bash` — исполнение shell-команд. Вся исполняемая логика — через MCP. Если нужен fallback для GraphRAG — использовать MCP `bsl_search`/`bsl_hybrid_search` (см. таблицу типов запросов ниже).
- `execute_code` (1c-mcp-crud INSERT/UPDATE/DELETE) — никаких побочных эффектов в живой базе.

Цель: предотвратить scope-creep от «опиши изменения» к «внеси изменения». Применение правок — отдельная фаза (`/implement-1c-task`), которая запрашивает свои права явно.

## ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА АНАЛИЗА

### Правило 1: Ориентироваться на существующий код конфигурации

При анализе задачи ОБЯЗАТЕЛЬНО:

1. **Искать аналогичный функционал** — через bsl-semantic-search и Grep найти похожие реализации в конфигурации
2. **Использовать готовые функции** — если в конфигурации уже есть функция, решающая часть задачи, использовать её, а НЕ писать свою
3. **Следовать паттернам** — стиль именования, структура запросов, подходы к решению берутся из существующего кода
4. **Указывать в плане** — для каждой точки модификации указать, какой существующий код использован как образец

### Правило 2: Верификация имён полей

Для КАЖДОГО SQL-запроса в плане:
- Проверить имена полей через `get_metadata` (1c-mcp-crud)
- Обратить внимание на префикс `гкс_` — может быть или не быть
- Указать проверенные имена полей в отчёте

### Правило 3: Подготовка к реализации

В ANALYSIS-REPORT обязательно указать:
- Номер задачи (GKSTCPLK-XXXX) для комментариев в коде
- Точные строки вставки (проверенные по текущему коду)
- Зависимости между точками модификации
- Порядок выполнения

## 5 фаз анализа

### Фаза 1: Требования
- Разбор ТЗ на конкретные требования
- Определение scope (что менять, что НЕ менять)

### Фаза 2: Объекты конфигурации (Delta-spec классификация)
- Для КАЖДОГО объекта проверить существование через `get_metadata` (1c-mcp-crud)
- Маркировать: `[ADDED]` — новый объект, `[MODIFIED]` — существующий
- Список объектов, требующих изменений (с маркерами)
- Список объектов-источников данных (только чтение)
- Структура регистров/документов через get_metadata
- **Refactor gate** (добавлено в v4.1): для каждой точки модификации ответить на вопрос — **это рефакторинг существующего символа?**
  - **Критерий refactoring:** существующий метод/переменная меняет имя; существующий метод заменяет тело целиком; существующий метод удаляется с проверкой callers
  - **Критерий не refactoring:** добавление нового метода/реквизита/подсистемы; вставка строк в существующий метод без изменения его сигнатуры
  - Если refactoring → добавить маркер `[REFACTOR]` к точке и зафиксировать: тип символа, ожидаемый backend, confidence (через routing matrix `src/bsl/semantic_search/refactor/routing_matrix.yaml`)
  - Если гибрид (refactoring + новый функционал в одной задаче) → оба маркера в плане, разные точки модификации
  - Назначение: `implement-1c-task` v2.2+ использует этот маркер для выбора между стандартным путём (EDT-MCP `write_module_source`) и Этапом 3R (`bsl_rename_symbol` / `bsl_replace_method_body` / `bsl_safe_delete_symbol`)

### Фаза 2.5: Runtime Trace (опциональная, добавлено v4.2.0)

**Триггер активации** (любой из двух):
- Пользователь добавил флаг `--trace` к команде `/analyze-1c-task --trace ...`
- Skill self-decision: алгоритм существующего кода имеет **≥3 runtime-ветвлений** по значениям, которые **невозможно определить static reading** (вызовы `Пользователи.ТекущийПользователь()`, `ПолучитьФункциональнуюОпцию(...)`, условия по `Тип(Параметр)`, режимы проведения, контекст вызова `?:` цепочки)

**Цель:** получить actual call graph + variable snapshots для алгоритма на runtime, чтобы Фаза 3 (Алгоритм) построилась на реальных данных, а не предположениях из static reading. Surface'ит discrepancies между static-предсказанием и runtime-поведением.

**Pre-condition** (если не выполнено — phase SKIP с warning «runtime trace недоступен — runtime ветвления отмечены как [STATIC-ASSUMPTION]» в плане):
- `mcp__1c-debug-hmr__debug_health_check(mode="probe")` → `ready: true`
- В случае `auto_prepare_available[]` непустого — opt-in user prompt
- 1С infobase с активной debug session (dbgs.exe на :1550 + ragent с `-debug -http`)

**8-шаговый протокол:**

1. `mcp__1c-debug-hmr__debug_connect(infobase_alias=<имя из workspace>)` — attach как Debug UI. Если warning `pre_existing_rphost_warning` непустой — предупредить пользователя и предложить Solution C (UI после connect) ИЛИ `force_recycle_rphost=True` (только dev).
2. **Identify entry-point:** определить модуль + строку входа в подозрительный алгоритм из metadata (через `mcp__bsl-semantic-search__bsl_object_info` или `mcp__1c-mcp-crud__get_metadata_details`). Для отдельной процедуры — её первая исполняемая строка; для обработки проведения — начало `ОбработкаПроведения`.
3. `mcp__1c-debug-hmr__debug_set_breakpoint(object_id=<UUID>, line=<entry_line>, module_type=<TYPE>)` — `propertyID` auto-resolve. Verify через `debug_get_breakpoints`.
4. **Trigger через `execute_code`** — минимальный harness, вызывающий процедуру с реалистичными параметрами (использовать данные из живой базы через `execute_query`, не fabricate). Альтернатива: HTTP-сервис trigger через `execute_query`.
5. `mcp__1c-debug-hmr__debug_ping` — wait for `callStackFormed` event (max 3 iterations).
6. **Iterative inspection** — для каждого frame в стеке (top-down):
   - `mcp__1c-debug-hmr__debug_stack_trace` — кадры stack'а
   - `mcp__1c-debug-hmr__debug_variables(stack_level=N)` — auto-discover локальных переменных
   - `mcp__1c-debug-hmr__debug_evaluate(expression=<условие_ветвления>)` — eval каждого `Если` condition для определения какая ветка истинна
7. **Step через критические ветвления** — `debug_step(action="Step")` на КАЖДОЙ runtime-развилке (если), capture state ДО и ПОСЛЕ перехода. Цель — построить actual control flow graph без догадок.
8. `mcp__1c-debug-hmr__debug_step(action="Continue")` — release rphost, дать сценарию завершиться. ОБЯЗАТЕЛЬНО даже при abort'е trace'а (иначе rphost висит в pause-state).

**Output:** новая секция «3.Y Runtime Trace» в ANALYSIS-REPORT.md (см. шаблон ниже; `3.Y` — плейсхолдер для следующего свободного подраздела после `3.X Найденные паттерны`).

**Discrepancies — главная ценность фазы.** Если runtime показал branch, который static reading предсказал по-другому — это load-bearing finding для Фазы 3. Каждый discrepancy:
- ссылка на строку BSL (модуль:строка)
- что говорил static («условие А → ветка 1»)
- что реально на runtime («Тип(Параметр)=ДокументСсылка → ветка 2»)
- impact на план модификаций (Фаза 4)

**Acceptance critera Фазы 2.5:**
- ✅ Output содержит секцию Runtime Trace с jq-compatible JSON stack'ами
- ✅ Discrepancies секция непуста если runtime ≠ static (если все совпало — явно записать «No discrepancies — static analysis sufficient»)
- ✅ rphost не остался в pause-state (Continue вызван)
- ⚠️ Без флага `--trace` и без self-decision триггера — фаза SKIP (время analysis не растёт)

### Фаза 3: Алгоритм
- **ПОИСК ПАТТЕРНОВ**: через bsl-semantic-search найти аналогичные реализации
- Логика решения (с учётом найденных паттернов **И discrepancies из Фазы 2.5**, если она запускалась)
- SQL-запросы (с проверенными именами полей)
- Обработка граничных условий

### Фаза 4: План модификаций
- Пронумерованные точки модификации
- Для каждой: файл, строка, действие, код, зависимости
- Порядок выполнения
- Указание образцов из конфигурации для каждой точки

### Фаза 5: Верификация
- Проверка покрытия всех требований
- Проверка побочных эффектов
- Тест-план
- Верификация на реальных данных (если доступна база)

## Выходной формат: ANALYSIS-REPORT.md

```markdown
# НОМЕР-ЗАДАЧИ Описание задачи

## 1. Описание задачи
### 1.1 Требования
### 1.2 Суть проблемы

## 2. Задействованные объекты конфигурации
### 2.1 Основные объекты (требуют изменения) — с маркерами [ADDED]/[MODIFIED]
- [MODIFIED] Документ.гкс_Xxx — поле YYY ✓ get_metadata
- [ADDED] РегистрСведений.гкс_Zzz — новый регистр ✓ get_metadata (не найден)
### 2.2 Объекты-источники данных

## 3. Детальный анализ механизма
### 3.X Найденные паттерны в конфигурации  <-- ОБЯЗАТЕЛЬНО

### 3.Y Runtime Trace (опционально — только если запускалась Фаза 2.5)

**Entry point**:
- Модуль: `<ModuleFQN>`
- Строка входа: `<lineNo>`
- BP UUID: `<auto-resolved propertyID>`
- Trigger harness: `<краткое описание execute_code / execute_query>`

**Stack** (jq-compatible JSON для post-processing):

` ``json
[
  {"level": 0, "moduleName": "<FQN>", "lineNo": <N>, "method": "<MethodName>"},
  {"level": 1, "moduleName": "<FQN>", "lineNo": <N>, "method": "<CallerName>"},
  ...
]
` ``

**Variables snapshot**:

| Variable | Value | Stack level |
|---|---|---|
| Контрагент | `<ПРЕДСТАВЛЕНИЕ>` | 0 |
| Сумма | 12345.67 | 0 |
| ... | ... | ... |

**Branch evaluation** (runtime-результаты `Если`-условий, eval'нутые через debug_evaluate):

| Условие | Static prediction | Runtime result | Branch taken |
|---|---|---|---|
| `Тип(Параметр) = Тип("ДокументСсылка...")` | `Истина` (assumed) | `Истина` | A |
| `Пользователи.ТекущийПользователь() = Справочники.Пользователи.НайтиПоНаименованию("Админ")` | unknown (depends on session) | `Ложь` | B |

**Discrepancies** (static prediction vs runtime — load-bearing для Фазы 4):

- **Строка <N> модуля <FQN>**: static reading предсказывал `<X>`, runtime показал `<Y>`. Impact: точка модификации <M> в плане должна учитывать ветку <Y>, а не <X>.
- Или: «No discrepancies — static analysis sufficient» если runtime совпал с предсказанием.

## 4. План изменений
### Точка модификации N: ... [ADDED|MODIFIED]
- Файл, строка, действие, код
- Образец из конфигурации: <ссылка на аналогичный код>

### Порядок выполнения

## 5. Чек-лист верификации
## 6. Риски и открытые вопросы
## 7. Тест-план
## 8. Верификация по коду (если проводилась)
## 9. Резюме
## 10. Верификация на реальных данных (если проводилась)
## 11. Следующие шаги (SDD)
```

## Инструменты

- **bsl-semantic-search** — поиск аналогичного кода в конфигурации (ОБЯЗАТЕЛЬНО); для `[REFACTOR]` точек — routing matrix `src/bsl/semantic_search/refactor/routing_matrix.yaml` для определения ожидаемого backend
- **1c-mcp-crud** — get_metadata для структуры объектов, execute_query для верификации
- **bsl-platform-context** — API платформы 1С
- **Grep/Glob** — поиск файлов и паттернов

### GraphRAG query taxonomy (через MCP)

Под капотом `bsl-semantic-search` MCP стоит GraphRAG router (`src/bsl/semantic_search/hybrid_router.py`, 8 типов запросов, auto-classification, P50 82ms, 12/12 на max-complexity тестах). Skill этот router НЕ дёргает напрямую (`Bash`/Python из тела skill'а запрещены — см. Permission scope), но таксономия типов полезна для понимания, **какой MCP-вызов делать для какой задачи**:

**8 типов и куда применять в фазах анализа:**

| Тип запроса (auto-detect) | Strategy | Применение в фазах /analyze-1c-task |
|---------------------------|----------|------------------------------------|
| `semantic` | vector | Фаза 3 — общий поиск похожего кода |
| `multi_hop_callers` (`-[:CALLS*1..3]->`) | graph | Фаза 4 — кто вызывает изменяемую функцию через 2-3 уровня |
| `impact_analysis` (+ module hint) | graph | Фаза 2 — какие модули пострадают при изменении |
| `architectural` | community | Фаза 2 — Delta-spec классификация подсистем |
| `dead_code` | graph | Фаза 5 — экспортные функции без callers |
| `cross_cutting` | hybrid | Фаза 3 — функции в нескольких подсистемах |
| `topology` (in-degree rank) | graph | Фаза 5 — узкие места, горячие функции |
| `negative_pattern` (`NOT EXISTS`) | hybrid | Фаза 5 — "X но не Y" проверки |

**Module disambiguation** — extract_target автоматически отделяет module_hint (`гкс_Взвешивание`) от symbol (`СформироватьДвижения`). Для запросов про конкретный документ это даёт laser-focused результаты вместо ambiguous match.

**Стандартный путь — только MCP:**

- `bsl_search` / `bsl_hybrid_search` покрывает большинство типов запросов из таблицы выше.
- Для `topology` / `negative_pattern` / `community` overview, не покрытых MCP напрямую — построить запрос как комбинацию `bsl_search` + `bsl_call_graph` + `bsl_impact_analysis`, а не лезть в hybrid_router из Bash.
- Если действительно нужен прямой Python-вызов router'а (вне `/analyze-1c-task` scope) — выйти из skill'а, запустить в режиме с расширенными правами, вернуться с результатом.

Подробности: [`docs/roadmap/260502_ROADMAP_GRAPHRAG_BSL_COMPLEX_QUERIES.md`](../../../docs/roadmap/260502_ROADMAP_GRAPHRAG_BSL_COMPLEX_QUERIES.md), benchmark — [`tmp/phase6_e2e_results.json`](../../../tmp/phase6_e2e_results.json).

### Маркировка точек модификации в плане (Фаза 4)

Для каждой точки указать **все применимые** маркеры:

| Маркер | Значение | Источник |
|---|---|---|
| `[ADDED]` | Новый объект метаданных | get_metadata → не найден |
| `[MODIFIED]` | Существующий объект | get_metadata → найден |
| `[REFACTOR]` | Операция = рефакторинг существующего символа (rename / replace body / safe delete) | Refactor gate в Фазе 2 |

**Пример:**
- Точка 1: `[MODIFIED]` Документ.гкс_Xxx — добавить новый реквизит (не refactoring)
- Точка 2: `[MODIFIED] [REFACTOR]` ОбщийМодуль.гкс_Yyy — переименовать `СтараяФункция` → `НоваяФункция` (symbol_type: `module_export_proc`, backend: ast-grep cross-file, confidence: 0.85)
- Точка 3: `[ADDED]` РегистрСведений.гкс_Zzz — новый регистр

## Итеративный режим: /analyze-1c-task:research

### Принцип
Executor (фазы 1-4) -> Reviewer (фаза 5 + scoring) -> fix gaps -> repeat.
Три агента с разделением обязанностей (адаптация AutoResearch v2).

### Метрика: Analysis Quality Score (0-100)

| Компонент | Вес | Источник |
|-----------|-----|----------|
| Requirements coverage | 30% | Маркеры [REQ-N] в плане |
| Fields verified | 25% | Маркеры `✓ get_metadata` |
| Patterns found | 20% | Маркеры `✓ pattern` |
| SQL validated | 15% | Маркеры `✓ execute_query` |
| Open questions | 10% | Секция 6 |

### Маркеры (обязательны для scoring)

```
✓ get_metadata   — поле проверено через MCP
✗ не проверено   — поле не проверено (gap)
✓ pattern        — найден образец из конфигурации
✓ execute_query  — SQL валидирован на реальных данных
[REQ-N]          — привязка к требованию N
```

### Стоп-условия
- Score >= 85 (target)
- 3 итерации без улучшения (plateau)
- Max 7 итераций
- Все gaps = 0

### Как запускается

**Интерактивный (в Claude Code):**
```
/analyze-1c-task:research
GKSTCPLK-1234: Добавить расчёт суммы НДС по маршрутным листам
```
Claude выполняет Executor (main context) -> Reviewer (Agent subagent) -> fix -> repeat.

**Headless (скрипт):**
```powershell
.\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md -TargetScore 85
```

**Автономный (Ralph):**
```bash
scripts\ralph.bat --template 1c-analysis --task docs/tasks/GKSTCPLK-1234.md
```

### Протокол интерактивного режима

1. Создать сессию: `data/analyze-1c-research/{task-id}/`
2. **EXECUTOR** (main context): полный 5-фазный анализ -> analysis-report.md
3. **Цикл** (max 7 итераций):
   a. REVIEWER (Agent subagent): scorer + verify + gaps -> verdict
   b. Если score >= target -> DONE
   c. Если plateau >= 3 -> DONE
   d. Показать: "Score: N/100. K gaps. Verdict."
   e. EXECUTOR (main): Fix ONE gap из reviewer feedback
   f. Каждые 3 итерации: COMPARATOR (Agent subagent)
4. Финальный git commit: `[ANALYSIS] {task-id}: score {N}`

### Выходной формат с маркерами

```markdown
## 2. Задействованные объекты конфигурации
### 2.1 Основные объекты (требуют изменения)
- Документ.МаршрутныйЛист — поле СуммаНДС ✓ get_metadata
- РегистрНакопления.Движения — поле Сумма ✗ не проверено

## 4. План изменений
### Точка модификации 1: Добавить реквизит [REQ-1]
- Образец: Документ.ЗаказНаПеревозку.СуммаНДС ✓ pattern
- SQL:
` ``sql
ВЫБРАТЬ СуммаНДС ИЗ Документ.МаршрутныйЛист
` ``
✓ execute_query

## Метаданные анализа
- Score: 87/100
- Iterations: 4
- Session: data/analyze-1c-research/GKSTCPLK-1234/
```

## Интеграция с SDD (Spec Driven Development)

После завершения анализа ANALYSIS-REPORT используется как входные данные для OpenSpec workflow.

### Маршрутизация: анализ → OpenSpec

```
/analyze-1c-task-v2 (этот скилл)
  │ Генерирует ANALYSIS-REPORT.md с [ADDED]/[MODIFIED] маркерами
  ▼
/opsx:propose <task-id>
  │ Создаёт OpenSpec change из ANALYSIS-REPORT:
  │   proposal.md  ← из секций 1, 9
  │   specs/*.md   ← из секций 2, 7 (delta-specs с ADDED/MODIFIED)
  │   design.md    ← из секций 3, 4
  │   tasks.md     ← из секции 4 (точки модификации)
  ▼
/opsx:approve <change>
  │ Ревью + одобрение спецификации
  ▼
/opsx:apply <change>
  │ Реализация по tasks.md
  ▼
brownfield-validate <change>
  │ Gap + Design + Impl валидация
  ▼
/opsx:archive <change>
```

### Правило: когда использовать SDD, а когда прямой implement

| Сложность задачи | Маршрут | Критерий |
|-------------------|---------|----------|
| Тривиальная (1 файл, 1 условие) | analyze → implement-1c-task | Нет новых объектов метаданных |
| Средняя/Сложная (2+ файла, бизнес-логика) | analyze → /opsx:propose → approve → apply | Есть ADDED объекты или 3+ MODIFIED |

### Секция 11 в ANALYSIS-REPORT

В конце отчёта ОБЯЗАТЕЛЬНО указать рекомендуемый маршрут:

```markdown
## 11. Следующие шаги (SDD)
- **Сложность:** средняя (2 модуля, 1 MODIFIED объект)
- **Маршрут:** /opsx:propose gkstcplk-XXXX-<краткое-описание>
- **Или:** implement-1c-task (если задача тривиальная)
```
