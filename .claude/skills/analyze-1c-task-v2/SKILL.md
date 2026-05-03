---
name: analyze-1c-task-v2
description: >
  5-фазная методология анализа задачи 1С:Предприятие.
  Требования -> Объекты -> Алгоритм -> План -> Верификация.
  v4.0: SDD-интеграция (OpenSpec delta-specs, approval gate, brownfield validation).
version: 4.1.0
updated: 2026-04-19
tags: [1c, analysis, bsl, configuration, methodology, semantic-search, autoresearch, three-agent]
ultrathink: true
commands:
  - /analyze-1c-task-v2
  - /analyze-1c-task:research
---

# Анализ задачи 1С — 5-фазная методология (v3.0)

## Overview

Skill для комплексного анализа задачи по конфигурации 1С:Предприятие.
На входе — ТЗ (описание задачи). На выходе — ANALYSIS-REPORT.md с пронумерованными
точками модификации, готовый для передачи в implement-1c-task.

**Улучшения v2 (D:С-Framework):**
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

### Фаза 3: Алгоритм
- **ПОИСК ПАТТЕРНОВ**: через bsl-semantic-search найти аналогичные реализации
- Логика решения (с учётом найденных паттернов)
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

### GraphRAG router (fallback)

Если `bsl-semantic-search` MCP недоступен или нужны типы запросов вне его покрытия — используй встроенный GraphRAG router (`src/bsl/semantic_search/hybrid_router.py` + `scripts/bench_graphrag_e2e.py`). 8 типов запросов с auto-classification, P50 82ms, 12/12 (100%) на max-complexity тестах.

**Вызов** (прямой Python из Bash):

```python
from src.bsl.semantic_search.hybrid_router import hybrid_search
from scripts.bench_graphrag_e2e import make_vector_fn, make_graph_fn, make_community_fn, embed_query
# wire backends (Qdrant + Neo4j) и hybrid_search(query, k=10) → результаты с метаданными
```

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

**Когда использовать GraphRAG router vs MCP-tools:**
- MCP `bsl_search` / `bsl_hybrid_search` — стандартный путь, доступен в production
- GraphRAG router — когда MCP падает, или нужны типы `topology` / `negative_pattern` / `community` overview, не покрытые MCP
- Оба используют одни бэкенды (Qdrant `bsl_code_v4_late` + Neo4j) — результаты совместимы

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
