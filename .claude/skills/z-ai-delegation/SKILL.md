---
name: z-ai-delegation
description: "Token Economy: делегирование генерации на Z.AI через LLM Rotation. Триггеры: 'экономия токенов', 'делегировать z.ai', 'token economy', 'draft review', 'delegation', 'llm_complete'. НЕ для архитектурных решений — используй architecture-research."
---

# Z.AI Delegation Protocol — Token Economy

## Обзор

Минимизация расхода токенов Opus путём делегирования генерации контента на дешёвые модели (Z.AI, Gemini, Ollama) через LLM Rotation. Паттерн: Z.AI генерирует черновик, Opus ревьюит и фиксит. Экономия 80-85% output-токенов Opus на генеративных задачах.

---

## Быстрый справочник

| Задача | Действие |
|--------|----------|
| Классификация уровня | Soft / Medium / Hard / Never (см. таблицу) |
| Делегирование | `mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)` |
| Проверка провайдеров | `mcp__llm-rotation__llm_list_providers` |
| Статистика | `mcp__llm-rotation__llm_get_stats` |

---

## Уровни делегирования

```
Задача
  |
  +-- Bulk/formatting (10+ items, шаблонные) -----> SOFT (без ревью)
  |
  +-- Docs/decomposition/tests (1-5 файлов) -----> MEDIUM (Opus review)
  |
  +-- Code/refactoring/analysis (будет в проде) --> HARD (Opus thorough review)
  |
  +-- Architecture/security/debugging ------------> NEVER (только Opus)
```

### Классификация по сигналам

| Сигнал | Уровень |
|--------|---------|
| 10+ однотипных элементов, форматирование | Soft |
| "сгенерируй docs", "разбей на файлы", "напиши тесты" | Medium |
| "напиши код", "рефакторинг", "создай модуль", "анализ" | Hard |
| "архитектура", "как лучше", "безопасность", "отладка" | Never |
| Ожидаемый output < 30 строк | Never (overhead) |

---

## Режим Orchestrator (основной)

Opus = мозг (декомпозиция + review). Z.AI = руки (генерация).

```
User: "Разбей roadmap на 10 файлов с декомпозицией"
  |
  +-- Opus: DECOMPOSE (сам, бесплатно)
  |     Подзадачи:
  |       1. INDEX.md (Medium)
  |       2. PHASE_58.md (Medium)
  |       3. PHASE_59.md (Medium)
  |       ...
  |       10. PHASE_67.md (Medium)
  |
  +-- Opus: DELEGATE пакетом
  |     Для каждой подзадачи:
  |       llm_complete(prompt="Generate PHASE_58.md...context...format...")
  |       llm_complete(prompt="Generate PHASE_59.md...context...format...")
  |       ... (параллельно или последовательно)
  |
  +-- Opus: REVIEW каждый результат
  |     Medium: accuracy + completeness + format
  |     Hard: + logic + security
  |     Fix inline
  |
  +-- Opus: ASSEMBLE
        Write() каждый файл с финальным контентом
```

### Когда включать Orchestrator

| Сигнал | Действие |
|--------|----------|
| Задача = 3+ файлов output | Orchestrator |
| Задача = повторяющаяся структура (N файлов по шаблону) | Orchestrator |
| Задача = один файл, сложный | Single Draft -> Review |
| Задача = архитектура, отладка | Never (Opus сам) |

### Алгоритм Orchestrator

```
Step 1: DECOMPOSE (Opus, 0 tokens Z.AI)
  - Разбей задачу на подзадачи
  - Для каждой: определи уровень (Soft/Medium/Hard/Never)
  - Never-подзадачи Opus делает сам
  - Остальные готовь к делегированию

Step 2: PREPARE PROMPTS (Opus, 0 tokens Z.AI)
  - Для каждой делегируемой подзадачи построй промпт:
    a) ЗАДАЧА — конкретно что сгенерировать
    b) КОНТЕКСТ — релевантные сниппеты из проекта
    c) ФОРМАТ — структура, стиль, язык
    d) ОГРАНИЧЕНИЯ — naming, паттерны
  - Используй шаблоны из секции "Шаблоны промптов"

Step 3: DELEGATE (Z.AI tokens)
  - Вызови llm_complete() для каждой подзадачи
  - Независимые подзадачи — параллельно
  - Зависимые (output одной = input другой) — последовательно

Step 4: REVIEW (Opus, минимум tokens)
  - Medium: accuracy + completeness + format
  - Hard: + logic + edge cases + security
  - Fix inline (Opus правит, не перегенерирует)
  - При > 50% переписывания: пометь подзадачу как Never, сделай сам

Step 5: ASSEMBLE + WRITE (Opus)
  - Собери финальный результат из всех подзадач
  - Write() файлы
  - Один проход — не возвращайся к Z.AI
```

### Пример: 10 файлов roadmap

```
Подзадача         | Уровень | Промпт для Z.AI                    | Review
INDEX.md          | Medium  | "Create index with table..."       | Format check
PHASE_58.md       | Medium  | "Expand phase 58: eval dataset..." | Accuracy check
PHASE_59.md       | Medium  | "Expand phase 59: AST parser..."   | Accuracy check
...повторить для каждой фазы...

Opus работа: decompose (1 мин) + prepare prompts (2 мин) + review (3 мин) = 6 мин
Z.AI работа: 10 x llm_complete = 10 файлов
Opus tokens saved: ~85% (только review, не генерация)
```

---

## Протокол: Draft -> Review (single task)

### Step 1: CLASSIFY
Определи уровень. Если Never — делай сам (Opus).

### Step 2: PROMPT для Z.AI
Построй промпт с 4 элементами:
- **a) ЗАДАЧА** — что сгенерировать (конкретно)
- **b) КОНТЕКСТ** — релевантный код/docs (вставь сниппеты)
- **c) ФОРМАТ** — структура, стиль, язык
- **d) ОГРАНИЧЕНИЯ** — naming, паттерны, антипаттерны

```
mcp__llm-rotation__llm_complete(
  prompt="[полный промпт с a/b/c/d]",
  max_tokens=4096
)
```

### Step 3: REVIEW

**Medium — проверь и поправь:**
- [ ] Фактическая точность (имена, API, ссылки)
- [ ] Полнота (ничего не пропущено?)
- [ ] Формат (соответствует стилю проекта?)

**Hard — всё из Medium ПЛЮС:**
- [ ] Логическая корректность (будет работать?)
- [ ] Edge cases обработаны?
- [ ] Консистентность с паттернами кодовой базы?
- [ ] Нет security-проблем?
- При > 50% переписывания — переклассифицируй в Never

### Step 4: OUTPUT
Запиши финальный результат после review-фиксов. Никогда не выводи сырой ответ Z.AI без ревью (Medium/Hard).

---

## Шаблоны промптов

### Шаблон 1: Генерация docs

```
Generate documentation for the following feature.

Context:
[ВСТАВЬ ОПИСАНИЕ/КОД]

Requirements:
- Language: Russian
- Format: Markdown, headers, tables
- Include: purpose, tasks with subtasks, deliverables, acceptance criteria
- Style: concise, technical, actionable

Output the complete document.
```

### Шаблон 2: Decomposition

```
Decompose this task into subtasks with maximum granularity.

Task: [ОПИСАНИЕ ЗАДАЧИ]

Requirements:
- Each task has ID (e.g., 1.1, 1.2.1)
- Include: description, deliverables, acceptance criteria
- Group by logical phases

Output structured Markdown.
```

### Шаблон 3: Code generation

```
Write [LANGUAGE] code for the following:

Task: [ЧТО РЕАЛИЗОВАТЬ]

Context:
[СУЩЕСТВУЮЩИЕ ПАТТЕРНЫ, ИНТЕРФЕЙСЫ, ТИПЫ]

Constraints:
- Follow these patterns: [ПАТТЕРНЫ]
- Naming: [КОНВЕНЦИИ]

Output only the code with minimal comments.
```

### Шаблон 4: Test generation

```
Generate tests for this code:

Code:
[КОД ФУНКЦИИ/КЛАССА]

Requirements:
- Framework: pytest
- Cover: happy path, edge cases, error cases
- Mock external dependencies

Output complete test file.
```

---

## Token Economics

| Сценарий | Без делегирования | С делегированием | Экономия Opus |
|----------|-------------------|------------------|---------------|
| 10 файлов docs | ~15K Opus out | ~2K Opus + 15K Z.AI | ~85% |
| 50 тест-кейсов | ~8K Opus out | ~1K Opus + 8K Z.AI | ~87% |
| Код 500 строк | ~3K Opus out | ~0.5K Opus + 3K Z.AI | ~83% |
| Архитектура | ~2K Opus out | N/A (never) | 0% |

---

## Провайдеры (приоритет — sonnet-first, актуализировано 2026-07-18)

| # | Провайдер | Модель | Сила |
|---|-----------|--------|------|
| 0 | **claude-cli-sonnet** | claude-sonnet-5 | **основной исполнитель** (CLI-подписка, младший тир квоты) |
| 1 | claude-cli-haiku | claude-haiku-4-5 | самый дешёвый тир для простой генерации |
| 2 | ollama-local | qwen2.5-coder:7b | бесплатный локальный (offline) |
| 3 | anthropic-sonnet | claude-sonnet-5 | платный API hot-path (выключен без ANTHROPIC_API_KEY) |

Легаси zai-glm5/gemini/openrouter/mistral **удалены** (аудит 2026-05-16); имя скилла «Z.AI» историческое — фактический делегат = **claude-cli-sonnet**.

## Целевой цикл оркестрации (мандат 2026-07-18)

**Opus (оркестратор) создаёт и анализирует задачу → sonnet (первый в очереди) исполняет через `llm_complete` → результат возвращается Opus → Opus ревьюит и решает: принять или доработать.**

```
Opus: сформулировать задачу (a/b/c/d промпт: ЗАДАЧА+КОНТЕКСТ+ФОРМАТ+ОГРАНИЧЕНИЯ)
  → llm_complete(prompt=..., temperature=0, timeout=120)   # sonnet исполняет
  → Opus review (чеклист Medium/Hard ниже)
  → принять (Write результата) | доработать (точечные правки Opus) | перегенерить (улучшенный промпт)
```

Гард [`z-ai-write-guard.py`](../../hooks/z-ai-write-guard.py) enforce'ит цикл: Write/Edit >15 строк кода блокируется без **недавнего** делегирования — окно свежести `LLM_DELEGATION_FRESH_MINUTES` (default 30 мин; фикс 2026-07-18 — раньше one-shot флаг без TTL переживал сессии и выключал гард навсегда).

## Делегат — text-only (W11, 2026-07-25)

`llm_complete` возвращает **текст** и репозиторий не мутирует. До 2026-07-25 это было не так:
провайдер `claude-cli` спавнится через `claude-agent-sdk` с `permission_mode="bypassPermissions"`
и `max_turns=3`, то есть был полноценным агентом с Write/Bash. Живой инцидент: промпт
«сгенерируй файл для `docs/roadmap`» исполнился агентно — субпроцесс **сам записал файл в репо**,
причём side-effect пережил клиентский таймаут (`llm_complete` вернул ошибку на 60с, а запись
состоялась). Обнаружено только тем, что `Write` оркестратора упёрся в уже существующий файл.

Закрыто в [`service.py`](../../../src/shared/llm_rotation/service.py) через `disallowed_tools`
(`Write`/`Edit`/`NotebookEdit`/`Bash`/`PowerShell`/`Task`/`Agent`/`AskUserQuestion`).
⚠ Держится именно на denylist: `allowed_tools=[]` в SDK 0.2.82 трактуется как «allowlist не задан»
(замер — делегат отчитался про доступные Glob/Grep/Read/Skill/ToolSearch). Read-only оставлены
сознательно: не мутируют и дают отвечать по фактам файла.

**Что это значит для промптов:** формулируй «сгенерируй ТЕКСТ», а не «создай файл X» —
записывает результат всегда оркестратор через `Write`. Правки MCP-серверного кода вступают
в силу после `/mcp reconnect` ([[feedback-mcp-stale-code-reconnect]]): проверять фикс надо
свежим процессом, иначе увидишь старое поведение.

## Таймауты (обрывы длинных вызовов)

claude-cli спавн = 25-150с. Обрыв клиентом до ответа = непарный Pre в tool-obs (выглядит «llm_complete сломан», хотя сервис здоров):
- для генераций >500 токенов передавай `timeout=120` (а лучше 180) в `llm_complete`;
- очень большой output — дели на 2-3 вызова по ≤4096 токенов;
- клиентский потолок поднят: `MCP_TOOL_TIMEOUT=240000` в `settings.local.json` (2026-07-18);
- **не прерывай** длинный вызов вручную без нужды — он доедет.

---

## Mandatory Opus Review

Opus review обязателен в двух случаях — **всегда после кода** и **всегда после Hard задач**.

### Когда ревью обязателен

| Ситуация | Review level | Пропустить? |
|----------|-------------|-------------|
| Любой код (.py, .js, .ts, .bsl) — даже 3 строки | Basic | НЕТ |
| Hard задача (Z.AI или Opus) | Thorough | НЕТ |
| Hard + код | Thorough | НЕТ |
| Docs / Markdown / config | Не требуется | Да |

> ⚠ **Ревью обязателен для BSL тоже, но делегирование — нет.** `.bsl`/`.os` (1С:Предприятие) **никогда не делегируются**: Z.AI не знает платформу и галлюцинирует API 1С — этот код пишет Opus сам. Строка таблицы выше про **ревью**, а не про исполнителя.
>
> С 2026-07-20 это проведено в код: `.bsl`/`.os` исключены из `_CODE_EXTENSIONS` хука [`z-ai-write-guard.py`](../../hooks/z-ai-write-guard.py), иначе гард требовал делегировать то, что правило запрещает делегировать. Регресс — [`tests/unit/test_z_ai_guard_bsl_exempt.py`](../../../tests/unit/test_z_ai_guard_bsl_exempt.py) (пинит обе стороны: BSL проходит, Python блокируется).

### Basic Review (для любого кода)

После Write/Edit кода — перечитай и проверь:
- [ ] Логика корректна (условия, циклы, возврат)
- [ ] Naming понятный и консистентный
- [ ] Нет copy-paste ошибок
- [ ] Edge cases (None, пустой список, 0, пустая строка)

Формат: 2-4 строки после Write/Edit, до перехода к следующей задаче.

```
Wrote `parser.py:45-60`. Review:
- Logic: regex matches both EN/RU keywords — OK
- Edge: empty file returns [] — OK
- Naming: `_extract_symbols` consistent with `_extract_calls` — OK
```

### Thorough Review (Hard задачи)

Всё из Basic ПЛЮС:
- [ ] Security (injection, hardcoded secrets, input validation)
- [ ] Паттерны проекта (async-first, provider pattern, Pydantic)
- [ ] Performance (N+1, blocking in async, resource leaks)
- [ ] Backward compatibility (public API не сломан)
- [ ] Error handling (try/except не глотает ошибки)

Формат: таблица после завершения задачи.

```
## Review: z-ai-delegation-enforcer.py
| Check | Status | Note |
|-------|--------|------|
| Logic | OK | Priority: Never > Orchestrator > Hard > Medium |
| Security | OK | No user input in regex, no file I/O |
| Patterns | OK | BaseHook, systemMessage advisory |
| Performance | OK | Keyword matching only, <1ms |
| Edge cases | OK | Short prompts (<40 chars) skipped |
```

### Review после Z.AI генерации

Z.AI не знает контекст проекта — ревью критически важен:
- [ ] Имена переменных/функций соответствуют проекту
- [ ] Импорты существуют и корректны
- [ ] API вызовы с правильными параметрами
- [ ] Нет выдуманных библиотек/функций (галлюцинации)
- [ ] Формат соответствует стилю проекта

---

## Диагностика проблем

| Проблема | Причина | Решение |
|----------|---------|---------|
| Пустой ответ Z.AI | Провайдер в cooldown | `llm_list_providers` проверить статус |
| Низкое качество черновика | Промпт без контекста | Добавь сниппеты кода/доков |
| Больше 50% переписывания | Задача слишком сложная | Переклассифицируй в Never |
| Timeout | max_tokens слишком большой | Разбей на 2-3 вызова по 4096 |
| Код не работает | Z.AI не знает проект | Добавь интерфейсы/типы в промпт |

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Делегировать всё | Overhead на мелких задачах | Только если output > 30 строк |
| Сырой Z.AI ответ без ревью | Ошибки в именах, логике | Medium/Hard — всегда ревью |
| Промпт без контекста | Галлюцинации | Вставляй сниппеты |
| Делегировать архитектуру | Нужен полный контекст | Never, только Opus |
| Повтор при плохом результате | Тот же промпт = тот же результат | Улучши промпт или сделай сам |
| Делегировать отладку | Интерактивный процесс | Never, только Opus |
