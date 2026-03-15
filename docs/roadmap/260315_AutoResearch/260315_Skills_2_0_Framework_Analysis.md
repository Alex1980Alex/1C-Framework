# Skills 2.0: Анализ улучшений для всего фреймворка

**Дата:** 2026-03-15
**Источник:** [Skills 2.0 Research](../260315_skills_2_0_research.md)
**Scope:** 65 скиллов, 15,700 строк, 13 хуков

---

## 1. Аудит текущего состояния

### 1.1 YAML Frontmatter: 16 скиллов без метаданных

```
NO_YAML (16):                    YAML (49):
├── 1c-mcp-toolkit               ├── 1c-doc-research
├── agent-orchestration           ├── analyze-1c-task-v2
├── bsl-development               ├── architecture-research
├── deployment                    ├── audit-docs
├── embedding-models              ├── ... (45 more)
├── evaluation-benchmark
├── framework-caching
├── framework-mcp-ui
├── framework-quickstart
├── graph-operations
├── indexing-pipeline
├── llm-rotation
├── memory-unified
├── prompt-engineering
├── qdrant-operations
├── search-pipeline-debug
```

**Проблема:** 16 скиллов без YAML = **невидимы** для Skill Router и Claude Code.
Claude не знает когда их вызывать — только если пользователь явно напишет `Skill('name')`.

**Skills 2.0 говорит:** `description` в YAML — **главный сигнал** для триггеринга.
Без него скилл мёртв.

### 1.2 Классификация по типам (Skills 2.0 таксономия)

| Тип | Скиллы | Кол-во | Долговечность |
|-----|--------|--------|---------------|
| **Encoded Preference** (workflow) | task-protocol, triad-factory, code-verify, auto-git-save, git-commit-message, create-hook, doc-to-skill, doc-to-cache, audit-docs, implement-1c-task, analyze-1c-task-v2, learning-loop, z-ai-delegation, architecture-research, task-evaluation | 15 | Высокая |
| **Capability Uplift** (компенсация) | bsl-development, 1c-doc-research, 1c-mcp-toolkit | 3 | Средняя (зависит от модели) |
| **Reference** (справочник) | claude-code-*, langchain-*, langgraph-*, framework-*, tenacity-retry, git-porcelain-parsing, deep-agents | 35 | Низкая (устаревают) |
| **Infrastructure** (инфра скиллы) | hook-debugging, hook-enforcement-pattern, windows-hooks-paths, claude-code-hooks-bugs, multi-level-hook-architecture, hooks-skills-mcp-triad, memory-unified, llm-rotation | 8 | Средняя |
| **Domain Knowledge** (знания домена) | pdf-knowledge, embedding-models, qdrant-operations, graph-operations, prompt-engineering, search-pipeline-debug, evaluation-benchmark, framework-caching, deployment, indexing-pipeline, agent-orchestration | 11 | Средняя |

### 1.3 Ключевые метрики

| Метрика | Текущее | Проблема |
|---------|---------|----------|
| Скиллов без YAML | 16 (25%) | Невидимы для триггеринга |
| Средний размер SKILL.md | 242 строки | Некоторые > 500 (triad-factory: 537) |
| Reference-скиллов | 35 (54%) | Потенциально устаревают, **самая большая группа** |
| Eval-тесты для скиллов | 0 | Нет способа проверить регрессии |
| Trigger accuracy | ~70% (субъективно) | Skill Router ловит не всё |

---

## 2. Улучшения из Skills 2.0

### 2.1 YAML Frontmatter для всех 16 скиллов (P0)

**Что:** добавить `---` YAML с `name` и `description` ко всем 16 скиллам без него.

**Пример — bsl-development:**

```yaml
---
name: bsl-development
description: >
  Разработка на BSL (1С:Предприятие 8.3.27): написание кода, модули объектов,
  обработки, процедуры проведения, запросы, формы. MCP: bsl-semantic-search,
  bsl-platform-context, EDT-MCP, bsl-debugger. Триггеры: 'написать BSL',
  'код 1С', 'модуль объекта', 'обработка проведения', 'BSL код', 'процедура 1С',
  'функция 1С', 'запрос 1С', 'форма 1С'. НЕ для документации 1С — используй
  1c-doc-research. НЕ для анализа задач — используй analyze-1c-task-v2.
---
```

**Объём:** 16 файлов, ~5-10 строк YAML каждый.

**Эффект:** все 65 скиллов видимы для Skill Router → trigger accuracy +10-15%.

---

### 2.2 Trigger Tuning: "настойчивые" описания (P1)

**Что:** Skills 2.0 рекомендует делать description **pushy** —
недотриггеринг чаще, чем перетриггеринг. Бюджет: 2% контекстного окна.

**Текущие проблемы:**
- Слишком короткие описания: `"LLM Rotation Service"` — о чём это?
- Нет негативных маркеров: когда НЕ использовать
- Нет явных триггеров на русском

**Паттерн хорошего описания (из наших лучших):**

```yaml
description: >
  [ЧТО ДЕЛАЕТ — 1 предложение].
  [ИНСТРУМЕНТЫ / MCP].
  Триггеры: '[ключевое слово 1]', '[ключевое слово 2]', ...
  НЕ для [X] — используй [другой скилл].
```

**Скиллы с плохими описаниями (нужно переписать):**

| Скилл | Текущий description | Проблема |
|-------|-------------------|----------|
| bsl-development | (нет YAML) | Невидим |
| llm-rotation | (нет YAML) | Невидим |
| deployment | (нет YAML) | Невидим |
| embedding-models | (нет YAML) | Невидим |
| framework-quickstart | (нет YAML) | Невидим |
| qdrant-operations | (нет YAML) | Невидим |
| search-pipeline-debug | (нет YAML) | Невидим |
| pdf-knowledge | Есть YAML но нет триггеров на русском | Частичная видимость |

---

### 2.3 Eval-система для скиллов (P1)

**Что:** из Skills 2.0 — система eval для проверки триггеринга и качества.

**Что создать:**

```
data/eval/skills/
├── trigger_eval.json              # 100+ промптов: какой скилл должен сработать?
├── negative_eval.json             # 50+ промптов: какой скилл НЕ должен сработать
├── eval_results_{date}.json       # Результаты последнего прогона
└── eval_history.tsv               # История: date, trigger_accuracy, false_pos, false_neg

scripts/
├── eval-skill-triggers.py         # Прогон eval через Skill Router
└── eval-skill-triggers-report.py  # Отчёт с рекомендациями
```

**Уже есть частично:** `scripts/eval-skill-router.py` (64 ground truth, F1/precision/recall).
Нужно **расширить** до 150+ промптов и добавить **A/B бенчмарк**.

**A/B бенчмарк:** запустить задачу со скиллом vs без → сравнить:
- Количество tool calls
- Токены
- Качество результата (graded 1-10)

---

### 2.4 Классификация и lifecycle скиллов (P2)

**Что:** из Skills 2.0 — два типа скиллов имеют разный lifecycle.

**Reference-скиллы (35 шт.) — риск устаревания:**

Скиллы-справочники (claude-code-*, langchain-*, langgraph-*, framework-*)
содержат **зашитую документацию**. При обновлении Claude Code или LangChain
информация в них **устаревает молча**.

**Решение: `expires` поле + auto-audit:**

```yaml
---
name: langchain-core
description: "..."
created: 2026-02-21
last_verified: 2026-03-01
source_version: "langchain 0.3.x"
type: reference  # reference | encoded_preference | capability_uplift | infrastructure
---
```

**Auto-audit скрипт:**

```python
# scripts/audit-skill-freshness.py
# Для каждого reference-скилла:
# 1. Прочитать source_version
# 2. Проверить текущую версию (pip show / npm list)
# 3. Если расхождение → пометить "needs update"
# 4. Если last_verified > 30 дней → warning
```

**Encoded Preference скиллы (15 шт.) — приоритет инвестиций:**

Эти скиллы кодируют **наши workflow** — они не устаревают с обновлением моделей.
Именно в них нужно **инвестировать больше** (eval, trigger tuning, расширение).

---

### 2.5 Ultrathink в ключевых скиллах (P2)

**Что:** из Skills 2.0 — слово `ultrathink` в SKILL.md включает extended thinking (31999 токенов).

**Где добавить:**

| Скилл | Где ultrathink | Почему |
|-------|---------------|--------|
| analyze-1c-task-v2 | Фаза анализа требований | Сложное рассуждение о бизнес-логике |
| architecture-research | Фаза evaluation matrix | Взвешивание подходов |
| implement-1c-task | Фаза проектирования алгоритма | Сложный BSL-код |
| task-evaluation | Фаза классификации | Правильный тип = правильный workflow |
| triad-factory | Фаза Q1-Q5 анализа | 5 вопросов требуют глубокого рассуждения |
| autoresearch (новый) | Phase 0 ANALYZE + Phase 2 IDEATE | Подбор инструментов, гипотезы |

**Как встроить:**

```markdown
## Phase: Анализ требований

ultrathink

Проанализируй задачу по 5 аспектам:
1. Какие объекты конфигурации затронуты?
...
```

---

### 2.6 Scope-разделение скиллов (P3)

**Что:** из Skills 2.0 — скиллы бывают personal / project / enterprise.

**Текущее:** все 65 скиллов в `.claude/skills/` (project scope).

**Рекомендация: выделить universal скиллы в personal scope:**

```
~/.claude/skills/  (personal — работают во всех проектах)
├── claude-code-cli-interactive/   # Справочник CLI — универсален
├── claude-code-settings/          # Настройки — универсальны
├── claude-code-admin/             # Администрирование — универсально
├── claude-code-vscode/            # VS Code — универсален
├── claude-code-programmatic/      # Headless mode — универсален
├── git-commit-message/            # Git коммиты — универсальны
├── git-porcelain-parsing/         # Git парсинг — универсален
├── tenacity-retry/                # retry паттерн — универсален
└── windows-hooks-paths/           # Windows пути — универсальны

.claude/skills/  (project — только для этого фреймворка)
├── pdf-knowledge/                 # PDF Framework
├── bsl-development/               # BSL разработка
├── 1c-doc-research/               # 1С документация
├── framework-api/                 # REST API фреймворка
├── task-protocol/                 # Наш workflow
├── ...                            # Остальные project-specific
```

**Эффект:**
- 9 скиллов → personal (доступны в любом проекте)
- Меньше контекстного мусора при загрузке в других проектах
- Соответствует Skills 2.0 архитектуре

---

### 2.7 Comparator для Skill Router (P2)

**Что:** из Skills 2.0 — слепое A/B сравнение скиллов.

**Применение:** сравнить работу Claude **со скиллом vs без скилла**
на одних и тех же задачах. Скилл приносит пользу или мешает?

**Методика:**

```
Для каждого скилла:
1. Выбрать 5 типичных задач
2. Запустить Claude без скилла → замерить: tool calls, tokens, quality (1-10)
3. Запустить Claude со скиллом → замерить те же метрики
4. Слепое сравнение результатов (Comparator агент)
5. Если скилл ухудшает → пересмотреть или удалить
```

**Ожидаемые результаты:**
- Encoded Preference скиллы: **значительное улучшение** (5-12 tool calls → 3-5)
- Reference скиллы: **умеренное** (экономия на поиске документации)
- Некоторые скиллы: **ухудшение** (слишком длинные, забивают контекст)

---

## 3. План действий по приоритетам

### P0: Немедленно (1-2 дня)

| # | Действие | Файлов | Эффект |
|---|----------|--------|--------|
| 1 | Добавить YAML к 16 скиллам без frontmatter | 16 | +25% видимость |
| 2 | Добавить `type:` поле ко всем YAML (reference/encoded_preference/capability_uplift/infrastructure) | 65 | Классификация для lifecycle management |

### P1: На этой неделе (3-5 дней)

| # | Действие | Файлов | Эффект |
|---|----------|--------|--------|
| 3 | Trigger Tuning: переписать слабые description (pushy стиль) | ~20 | +10-15% trigger accuracy |
| 4 | Расширить eval до 150+ промптов (с trigger_eval.json) | 3 | Измеримый trigger accuracy |
| 5 | Ultrathink в 6 ключевых скиллах | 6 | Глубже рассуждение в критических фазах |

### P2: На следующей неделе

| # | Действие | Файлов | Эффект |
|---|----------|--------|--------|
| 6 | `last_verified` + `source_version` в reference-скиллах | 35 | Отслеживание устаревания |
| 7 | `scripts/audit-skill-freshness.py` | 1 | Автоматическая проверка свежести |
| 8 | A/B Comparator для top-10 скиллов | 1 | Объективная оценка полезности |

### P3: Через 2 недели

| # | Действие | Файлов | Эффект |
|---|----------|--------|--------|
| 9 | Выделить 9 universal скиллов в `~/.claude/skills/` | 9 | Чище project scope |
| 10 | Удалить/архивировать бесполезные скиллы (по данным Comparator) | ? | Меньше контекстного мусора |

---

## 4. Ожидаемый результат

| Метрика | До | После |
|---------|-----|-------|
| Скиллы с YAML | 49/65 (75%) | **65/65 (100%)** |
| Trigger accuracy | ~70% | **>85%** |
| Reference скиллы проверены | 0/35 | **35/35** (last_verified) |
| Eval промптов | 64 | **150+** |
| Скиллы с ultrathink | 0 | **6** |
| Скиллы в personal scope | 0 | **9** |
| Подтверждённо полезных (A/B) | неизвестно | **измерено** |

---

## 5. Связь с AutoResearch v2

AutoResearch v2 может **автоматизировать** улучшение скиллов:

```
/autoresearch
Goal: Улучшить trigger accuracy Skill Router с 70% до 90%
Metric: eval-skill-router.py F1 score
Scope: .claude/skills/*/SKILL.md (description поля)

Executor: переписывает description, добавляет триггеры
Reviewer: запускает eval → F1 вырос?
Comparator: слепое A/B — новый description vs старый
```

Это идеальный use case для AutoResearch — измеримая метрика, атомарные изменения (1 скилл за итерацию), автоматическая верификация.
