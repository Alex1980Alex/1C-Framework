# Plan: Улучшение точности рекомендаций скиллов

## Context

Рекомендаций 72, а активаций 4 — Activation Rate 2%. Две причины:
1. **Рекомендации неточные** — `min_score: 1` слишком низкий, generic keywords срабатывают на обычных промптах, информационные запросы получают рекомендации для action-скиллов
2. **Session dedup сломан** — `get_already_recommended()` / `record_recommendation()` импортируются в `skill-router.py:302-303`, но **не определены** в `session_state.py` → except молча глотает ошибку → один скилл рекомендуется повторно каждый промпт

Запрос: «рекомендации некорректные — нужно делать правильные рекомендации, и если рекомендация последовала — использовать скиллы»

---

## Часть 1: Анализ механизмов принуждения

### Почему нельзя заставить Claude активировать скилл на 100%

Claude — языковая модель, не детерминированная программа. Все механизмы работают как **инструкции**, а не как принуждение.

#### Каналы доставки рекомендаций

| Канал | Механизм | Activation Rate | Ограничение |
|-------|----------|----------------|-------------|
| `systemMessage` (JSON) | `<system-reminder>` тег | ~55% | Claude трактует как совет |
| stdout (plain text) | Прямая инъекция в контекст | ~100% оценки | Claude может решить "не релевантно" |
| Stop + `exit 2` | Блокирует завершение | Формально 100% | Скилл вызовется постфактум — бесполезно |
| PostToolUse:Skill | Мониторинг вызовов | — | Сломан (баг #6305) |

Источник: исследование Scott Spence (650+ trials) — JSON systemMessage 55%, shell stdout 100%.

#### Почему `exit 2` не решает проблему скиллов

```
1. UserPromptSubmit  →  skill-router рекомендует скилл
2. Claude думает     →  решает вызвать Skill() или нет
3. Claude отвечает   →  код уже написан
4. Stop              →  хук проверяет: скилл не вызван → exit 2 → блок
5. Claude получает   →  "вы не активировали скилл X"
6. Claude вызывает   →  Skill() ПОСТФАКТУМ — ответ уже дан без знаний скилла
```

Результат: скилл формально активирован, но **бесполезен** — знания из него не повлияли на ответ.

#### Единственный рабочий момент — UserPromptSubmit

Скилл полезен только **до** того как Claude начал отвечать. Enforcement через stdout — единственный реальный рычаг. Работает на уровне "настоятельно попросить", а не "заставить".

---

## Часть 2: Проблема с 1С-скиллами при программировании

### Текущая ситуация

```
Пользователь: "добавь обработку проведения в документ Заказ"
    │
    ▼
skill-router → ловит "проведение" → рекомендует 1c-doc-research
enforcer → "MANDATORY SKILL EVALUATION"
    │
    ▼
Claude → видит рекомендацию, но...
  → уже "знает" как написать проведение из training data
  → решает: "скилл не нужен, я и так могу"
  → пишет код из памяти (может быть устаревший синтаксис 8.3.25)
```

**Проблема**: Claude **уверен** в своих знаниях по 1С, поэтому считает скилл нерелевантным. Training data — версии до 8.3.25, актуальная — 8.3.27.

### Цепочка событий при программировании

```
Пользователь: "реализуй endpoint для загрузки PDF"
    │
    ▼
UserPromptSubmit хуки (ЕДИНСТВЕННАЯ точка влияния)
    ├── skill-router.py       → [SKILL-ROUTER] Рекомендуется: framework-api
    ├── enforcer-shell.py     → MANDATORY SKILL EVALUATION
    │
    ▼
Claude получает: промпт + рекомендации + enforcement
    │
    ▼
Claude программирует (может быть 20+ tool calls):
  1. Skill("framework-api")     ← активирует скилл (если решит)
  2. Read(файл1)
  3. Edit(файл1)
  4. Bash("pytest")
  ...
```

Рекомендация приходит **один раз в начале**. Между tool calls хуки не вмешиваются в выбор скиллов.

### 3 уровня решения для 1С-скиллов

#### Уровень 1: CLAUDE.md — жёсткое правило (самый простой, ~70%)

Добавить в `CLAUDE.md`:

```markdown
## 1С Программирование — ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА

При ЛЮБОЙ работе с кодом 1С (BSL, модули, формы, обработки):
1. СНАЧАЛА активируй skill `1c-doc-research`
2. Проверь кеш: `.claude/skills/1c-doc-research/cache/`
3. Только ПОСЛЕ проверки документации — пиши код
4. НИКОГДА не полагайся на свои знания по API 1С — они могут быть устаревшими

Твои training data по 1С — версии до 8.3.25. Актуальная — 8.3.27.
Разница критична: изменены API, добавлены новые методы, deprecated старые.
```

Claude следует инструкциям из CLAUDE.md с высоким приоритетом — это project rules.

#### Уровень 2: Отдельный 1C-enforcer хук (stdout, ~95%)

Файл: `.claude/hooks/1c-code-enforcer.py` (UserPromptSubmit)

```python
_1C_MARKERS = [
    "1с", "1c", "bsl", "проведение", "регистр", "справочник",
    "документ 1с", "табличная часть", "реквизит", "модуль объекта",
    "модуль менеджера", "общий модуль", "подсистема",
]

def main():
    prompt = get_prompt()
    prompt_lower = prompt.lower()

    if not any(m in prompt_lower for m in _1C_MARKERS):
        sys.exit(0)  # Не 1С — пропускаем

    # stdout = прямая инъекция в контекст (100% видимость)
    print(
        "CRITICAL: Обнаружен контекст 1С-программирования.\n"
        "ПЕРЕД написанием любого кода 1С ты ОБЯЗАН:\n"
        "1. Вызвать Skill('1c-doc-research') — загрузить документацию 8.3.27\n"
        "2. Проверить кеш: Read('.claude/skills/1c-doc-research/cache/')\n"
        "3. Найти точный API метод/объект в документации\n"
        "4. Только потом писать код, ссылаясь на найденную документацию\n"
        "НЕ ИСПОЛЬЗУЙ знания из training data по API 1С — они УСТАРЕВШИЕ."
    )
```

Сильнее generic enforcer-а, потому что **конкретно** указывает что делать для 1С.

#### Уровень 3: Кеш с шаблонами кода (максимальный эффект)

Наполнить `.claude/skills/1c-doc-research/cache/` готовыми шаблонами:

```
cache/
  проведение-документа.md      ← правильный шаблон с API 8.3.27
  регистр-сведений-запись.md   ← примеры записи в регистр
  http-сервис-шаблон.md        ← шаблон HTTP-сервиса
  запрос-к-базе.md             ← синтаксис запросов
```

Claude предпочитает использовать конкретные примеры из контекста, а не генерировать из памяти. Кеш наполняется итеративно — каждый раз когда пишется 1С-код, правильный шаблон сохраняется.

#### Сравнение уровней

| Подход | Эффективность | Сложность |
|--------|--------------|-----------|
| Правило в CLAUDE.md | ~70% | 5 минут |
| 1C-enforcer хук (stdout) | ~95% оценки | 30 мин |
| Кеш с шаблонами кода | Максимум | Зависит от объёма 1С-объектов |
| **Все три вместе** | **Близко к 100%** | — |

---

## Часть 3: Технические изменения (план реализации)

### 1. `session_state.py` — добавить недостающие функции

Файл: `.claude/hooks/shared/session_state.py`

Добавить в класс `SessionState`:
- `record_recommendation(skills: list[str])` — записывает в `state["recommended_skills"]` (dedup)
- `get_already_recommended() -> list[str]` — возвращает уже рекомендованные

Добавить module-level обёртки + обновить `__all__`, `_empty_state()`, `reset_session()`.

### 2. `skill-router-config.json` — поднять пороги, убрать generic keywords

Файл: `.claude/skills/skill-router-config.json`

| Параметр | Было | Станет | Почему |
|----------|------|--------|--------|
| `min_score` | 1 | 2 | Одно keyword-совпадение — слишком шумно |
| `max_bundles` | 3 | 2 | Меньше шума, точнее рекомендации |

Очистка generic keywords:
- `framework-config`: убрать `"настройка"`, `"settings"`
- `framework-troubleshooting`: убрать `"ошибка"`, `"error"`, `"проблема"`
- `search`: убрать `"найди"`, `"найти"`
- `infrastructure`: убрать `"hook"`, `"skill"`, `"mcp"`, `"хук"`, `"навык"`
- `workflow-research`: убрать `"как работает"`, `"что такое"`, `"объясни"`, `"explain"`, `"research"`

Стратегия: generic keywords → weighted_keywords (вес 1), конкретные фразы → вес 3+.

### 3. `skill-router.py` — intent classification + confidence

Файл: `.claude/hooks/skill-router.py`

- `_classify_intent(prompt)` → `action | informational | system`
- Intent-dependent min_score: action=2, informational=3, system=skip
- Confidence levels: HIGH (>=4) / MEDIUM (3) / LOW (2)

### 4. `skill-eval-enforcer-shell.py` — conditional enforcement

Файл: `.claude/hooks/skill-eval-enforcer-shell.py`

Skip enforcement для `informational` и `system` промптов.

### 5. `1c-code-enforcer.py` — специализированный 1С-enforcer (НОВЫЙ)

Файл: `.claude/hooks/1c-code-enforcer.py`

UserPromptSubmit хук, stdout-инъекция при обнаружении 1С-маркеров.

## Файлы

| Файл | Действие |
|------|----------|
| `.claude/hooks/shared/session_state.py` | +`record_recommendation()`, +`get_already_recommended()` |
| `.claude/skills/skill-router-config.json` | `min_score: 2`, `max_bundles: 2`, очистить generic keywords |
| `.claude/hooks/skill-router.py` | +`_classify_intent()`, intent-dependent thresholds, confidence |
| `.claude/hooks/skill-eval-enforcer-shell.py` | Conditional enforcement (skip informational) |
| `.claude/hooks/1c-code-enforcer.py` | **НОВЫЙ** — 1С-специализированный enforcer |
| `CLAUDE.md` | Добавить секцию "1С Программирование — ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА" |

---

## Часть 4: Исследование — баг #6305 и PreToolUse как альтернатива

### Статус бага #6305

**Проверено 2026-02-24**: GitHub issue [#6305](https://github.com/anthropics/claude-code/issues/6305) — **OPEN**, не починен.

Заголовок: "Post/PreToolUse Hooks Not Executing in Claude Code"

Ключевые факты из обсуждения:
- Проблема подтверждена множеством пользователей (fwends, Dmdv, tytung2020, Xopher00)
- Не проблема конфигурации — хуки работают при ручном запуске, но не вызываются автоматически
- Затрагивает версии 1.0.38+
- **Stop, SubagentStop, UserPromptSubmit — работают**
- **PreToolUse, PostToolUse — заявлены как сломанные**

### Но! Наши данные противоречат issue

Анализ `data/hook-invocations.jsonl` показывает **другую картину**:

| Событие | Tool | Статус | Количество срабатываний |
|---------|------|--------|------------------------|
| PreToolUse | Edit | **Работает** | Сотни записей |
| PreToolUse | Write | **Работает** | Десятки записей |
| PreToolUse | Bash | **Работает** | Десятки записей |
| PostToolUse | Edit | **Работает** | Десятки записей |
| PostToolUse | Bash | **Работает** | Записи есть |
| **PreToolUse** | **Skill** | **Почти не работает** | **1 запись за всю историю** |
| **PostToolUse** | **Skill** | **Не работает** | **0 записей** |

**Вывод**: баг #6305 **специфичен для tool=Skill**, а не для всех PreToolUse/PostToolUse. Хуки на Edit/Write/Bash работают стабильно.

Единственное срабатывание PreToolUse:Skill:
```json
{"ts": "2026-02-23T03:48:19", "hook": "SkillUsageMetrics", "event": "PreToolUse", "tool": "Skill"}
```

### CodeSkillEnforcer — уже существует и работает

Файл: `.claude/hooks/code-skill-enforcer.py`
Событие: `PreToolUse: Write|Edit|Bash`

Этот хук уже работает на каждый Edit/Write/Bash и проверяет паттерны:
- **Level A**: Content patterns (StateGraph → langgraph-core)
- **Level B**: Directory rules (.claude/hooks/ → create-hook)
- **Level C**: Bash commands (docker compose → deployment)
- **Level D**: Research cache reminder
- **Level E**: Post-verification
- **Level F**: LEARN phase

В логах: `outcome: "block"` — хук реально блокирует операции когда скилл не загружен.

### Решение: PreToolUse:Edit как Level 2 enforcement для 1С

Поскольку PreToolUse:Edit работает стабильно, можно добавить **1С-паттерны** в `code-skill-patterns.json`:

```json
{
  "1c-bsl": {
    "patterns": [
      "Процедура.*Проведение",
      "РегистрСведений",
      "РегистрНакопления",
      "СправочникМенеджер",
      "ДокументМенеджер",
      "ОбщийМодуль",
      "ТабличнаяЧасть",
      "ПланВидовХарактеристик"
    ],
    "required_skill": "1c-doc-research",
    "block_message": "Обнаружен код 1С (BSL). Загрузи skill `1c-doc-research` и проверь кеш документации 8.3.27 перед редактированием."
  }
}
```

Цепочка:
```
Claude пишет Edit с кодом 1С
    │
    ▼
PreToolUse:Edit → code-skill-enforcer
    │  видит паттерн "РегистрСведений" в содержимом Edit
    │  проверяет: skill 1c-doc-research активирован?
    │
    ├── Да → allow (пропускает Edit)
    └── Нет → block! "Загрузи 1c-doc-research сначала"
              │
              ▼
         Claude загружает скилл → повторяет Edit
```

**Преимущество перед UserPromptSubmit**: ловит момент когда Claude **уже пишет код**, но **ещё не записал**. Работает даже если Claude проигнорировал рекомендацию на UserPromptSubmit.

### Обновлённая таблица уровней enforcement

| Уровень | Хук | Событие | Надёжность | Момент |
|---------|-----|---------|------------|--------|
| 0 | CLAUDE.md | — | ~70% | Всегда в контексте |
| 1 | skill-router.py | UserPromptSubmit | ~55% (systemMessage) | До начала работы |
| 1+ | enforcer-shell.py | UserPromptSubmit | ~95% (stdout) | До начала работы |
| 1++ | 1c-code-enforcer.py | UserPromptSubmit | ~95% (stdout, 1С-specific) | До начала работы |
| **2** | **code-skill-enforcer.py** | **PreToolUse:Edit** | **Блок (exit 2)** | **В момент записи кода** |
| 3 (broken) | skill-usage-metrics.py | PostToolUse:Skill | ~0% | После вызова Skill() |

Level 2 (PreToolUse:Edit) — **единственный механизм блокировки** для скиллов, который реально работает.

---

## Часть 5: Итоговый план изменений

### Файлы

| Файл | Действие |
|------|----------|
| `.claude/hooks/shared/session_state.py` | +`record_recommendation()`, +`get_already_recommended()` |
| `.claude/skills/skill-router-config.json` | `min_score: 2`, `max_bundles: 2`, очистить generic keywords |
| `.claude/hooks/skill-router.py` | +`_classify_intent()`, intent-dependent thresholds, confidence |
| `.claude/hooks/skill-eval-enforcer-shell.py` | Conditional enforcement (skip informational) |
| `.claude/hooks/1c-code-enforcer.py` | **НОВЫЙ** — 1С-специализированный enforcer (UserPromptSubmit) |
| `.claude/hooks/shared/code-skill-patterns.json` | +1С-паттерны для PreToolUse:Edit блокировки |
| `CLAUDE.md` | Добавить секцию "1С Программирование — ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА" |

### Verification

```bash
# 1. Проверить session dedup
cd .claude/hooks && python -c "
from shared.session_state import record_recommendation, get_already_recommended
record_recommendation(['tech-research', 'pdf-search'])
print('Recommended:', get_already_recommended())
record_recommendation(['tech-research'])  # Dedup
print('After dedup:', get_already_recommended())
"

# 2. Проверить intent classification
cd .claude/hooks && python -c "
from skill_router import _classify_intent
print(_classify_intent('что такое RAG?'))           # -> informational
print(_classify_intent('создай новый endpoint'))     # -> action
print(_classify_intent('/help'))                     # -> system
"

# 3. Проверить min_score=2 (одно keyword не проходит)
echo '{"prompt":"найди файл config.py"}' | python .claude/hooks/skill-router.py
# Ожидание: НЕТ рекомендаций (score=1 < min_score=2)

# 4. Проверить 1C-enforcer (UserPromptSubmit)
echo '{"prompt":"добавь обработку проведения в документ"}' | python .claude/hooks/1c-code-enforcer.py
# Ожидание: CRITICAL инструкция с требованием загрузить 1c-doc-research

# 5. Проверить PreToolUse:Edit блокировку на 1С-паттерн
# (через code-skill-enforcer с паттерном "РегистрСведений" в содержимом)

# 6. Dashboard
curl http://127.0.0.1:8000/metrics | python -c "import sys,json; print(json.load(sys.stdin)['skill_metrics'])"
```

---

## Часть 6: PreToolUse — справочник по matcher-ам и входным данным

### Что такое PreToolUse

`PreToolUse` — событие хука Claude Code, которое срабатывает **перед** тем как Claude выполнит инструмент. Название расшифровывается: "Pre" (до) + "ToolUse" (использования инструмента) + ":Matcher" (для какого инструмента).

**Matcher** задаётся в `settings.json` и определяет для каких инструментов хук срабатывает.

### Текущая конфигурация PreToolUse (`.claude/settings.json`)

```json
"PreToolUse": [
  {
    "matcher": "Write|Edit|Bash",
    "hooks": [{ "command": "code-skill-enforcer.py", "timeout": 3 }]
  },
  {
    "matcher": "Write",
    "hooks": [{ "command": "root-clutter-guard.py", "timeout": 3 }]
  },
  {
    "matcher": "Bash",
    "hooks": [{ "command": "search-optimizer.py", "timeout": 3 }]
  }
]
```

### Доступные matcher-ы

Matcher может быть **любым инструментом** Claude Code. Regex OR через `|`.

| Matcher | Когда срабатывает | tool_input содержит |
|---------|-------------------|---------------------|
| `Edit` | Перед редактированием файла | `file_path`, `old_string`, `new_string` |
| `Write` | Перед созданием/перезаписью файла | `file_path`, `content` |
| `Bash` | Перед выполнением команды | `command`, `description` |
| `Read` | Перед чтением файла | `file_path` |
| `Skill` | Перед вызовом скилла | `skill`, `args` — **сломан (баг #6305)** |
| `WebSearch` | Перед веб-поиском | `query` |
| `WebFetch` | Перед загрузкой URL | `url`, `prompt` |
| `Glob` | Перед поиском файлов | `pattern`, `path` |
| `Grep` | Перед поиском в содержимом | `pattern`, `path` |
| `Task` | Перед запуском подагента | `prompt`, `subagent_type` |
| `Write\|Edit\|Bash` | Перед любым из трёх | Зависит от конкретного tool |

### Что хук получает на вход (stdin JSON)

```json
{
  "session_id": "abc123...",
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/path/to/file.bsl",
    "old_string": "Процедура ОбработкаПроведения()",
    "new_string": "Процедура ОбработкаПроведения(Отказ)\n  РегистрСведений.Записать();"
  }
}
```

Для `code-skill-enforcer.py` ключевое поле — `tool_input.new_string`. В нём видно **что именно** Claude собирается записать. Хук может:
- Проверить содержимое на паттерны (1С-код, LangChain, etc.)
- Проверить активирован ли нужный скилл (`SessionState.is_skill_activated()`)
- Заблокировать запись (`exit 2`) если скилл не загружен

### Что хук может вернуть

| Действие | Как | Результат |
|----------|-----|-----------|
| Пропустить | `exit 0` | Edit выполняется |
| Заблокировать | `exit 2` + stdout сообщение | Edit НЕ выполняется, Claude видит сообщение |
| Добавить контекст | stdout текст + `exit 0` | Edit выполняется + Claude видит дополнительную информацию |

### Почему PreToolUse:Edit — ключевой механизм для 1С-скиллов

```
UserPromptSubmit (Level 1)          PreToolUse:Edit (Level 2)
─────────────────────────           ────────────────────────────
Момент: до начала работы            Момент: в момент записи кода
Механизм: рекомендация (совет)      Механизм: блокировка (exit 2)
Claude может проигнорировать        Claude ОБЯЗАН подчиниться
Не видит код                        Видит СОДЕРЖИМОЕ кода (new_string)
```

Level 2 (PreToolUse:Edit) — **единственный механизм**, который одновременно:
1. Работает стабильно (сотни срабатываний в логах)
2. Может **блокировать** операцию (`exit 2`)
3. Видит **содержимое** того что Claude пишет
4. Срабатывает **до** записи в файл
