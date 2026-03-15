# Единый паттерн: Measure → Change → Verify → Keep/Revert

**Дата:** 2026-03-15
**Источник:** [Skills 2.0 Research](../260315_skills_2_0_research.md) + [AutoResearch v2 Roadmap](260315_AutoResearch_v2_Roadmap.md)
**Инсайт:** Skills 2.0 и AutoResearch — это ОДИН И ТОТ ЖЕ паттерн, применённый к разным доменам

---

## Паттерн

```
measure → change → verify → keep/revert → repeat
```

Karpathy применил его к ML-коду. Goenka обобщил на любой код. Skills 2.0 применил к скиллам.
Мы применяем ко **ВСЕМУ фреймворку** — к каждому домену, где есть измеримая метрика.

**Ключевое:** это не разовые действия ("починил 16 скиллов — готово").
Это **непрерывный цикл**, встроенный в систему. Скиллы деградируют
(модели обновляются, код меняется, появляются новые паттерны).
Улучшение должно быть **автоматическим и постоянным**.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   ДОМЕН            МЕТРИКА              VERIFY COMMAND        │
│   ─────            ───────              ──────────────        │
│   Код              ruff/mypy errors     ruff check --json     │
│   Скиллы           trigger accuracy     eval-skill-router.py  │
│   Хуки             false positive rate  eval-hooks.py         │
│   Документация     coverage %           audit-docs            │
│   BSL              bsl_analyze errors   bsl_analyze --json    │
│   Конфигурация 1С  knowledge coverage   1c_coverage.py        │
│   API              response time ms     pytest-benchmark      │
│   Тесты            coverage %           pytest --cov          │
│   Промпты          quality score        LLM-graded eval       │
│   Безопасность     findings count       bandit -r src/        │
│                                                              │
│   КАЖДЫЙ домен = тот же цикл.                                │
│   Отличается только: инструменты, метрика, verify command.   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Архитектура: AutoResearch как универсальный движок

```
                    ┌─────────────────────────┐
                    │     /autoresearch       │
                    │   (универсальный движок) │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
     ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
     │  Domain: Code  │ │ Domain: Skills │ │ Domain: 1C     │
     │                │ │                │ │                │
     │ metric: errors │ │ metric: F1     │ │ metric: cover% │
     │ tools: ruff    │ │ tools: eval.py │ │ tools: MCP     │
     │ scope: src/    │ │ scope: .claude/│ │ scope: cache/  │
     └────────────────┘ └────────────────┘ └────────────────┘
              │                  │                  │
              ▼                  ▼                  ▼
     ┌────────────────────────────────────────────────────┐
     │              ОДИНАКОВЫЙ ЦИКЛ:                      │
     │  Executor → Reviewer → Comparator → Log → Repeat   │
     └────────────────────────────────────────────────────┘
```

**Один движок. Разные домены. Одинаковый цикл.**

---

## Домены и их рецепты

### Домен 1: Скиллы (из Skills 2.0)

```
Проблема:  16 скиллов без YAML (невидимы), trigger accuracy ~70%
Метрика:   eval-skill-router.py → F1 score
Baseline:  F1 = текущий (64 ground truth)
Target:    F1 > 0.90

Executor:
  - Переписывает description одного скилла (pushy стиль)
  - Добавляет YAML frontmatter если нет
  - Добавляет type: reference|encoded_preference|capability_uplift
  - Добавляет ultrathink в критические фазы
  Инструменты: Read/Edit SKILL.md

Reviewer:
  - Запускает: python scripts/eval-skill-router.py → F1
  - Проверяет: description не > 500 символов (бюджет 2% контекста)
  - Проверяет: есть негативные маркеры ("НЕ для X — используй Y")
  - Проверяет: есть триггеры на русском И английском
  Verdict: F1 вырос → KEEP, F1 упал → REVERT

Comparator (каждые 5 итераций):
  - Слепое A/B: Claude с обновлёнными скиллами vs со старыми
  - 5 задач: подобрал правильный скилл?
  - Оценка: tool calls, токены, качество ответа
```

**Конкретные улучшения:**

| Итерация | Что меняем | Ожидаемый эффект |
|----------|-----------|------------------|
| 1-16 | YAML frontmatter к 16 скиллам без него | +25% видимость, F1 += 0.05-0.10 |
| 17-30 | Pushy description у слабых скиллов | Trigger accuracy += 10-15% |
| 31-36 | Ultrathink в 6 ключевых скиллах | Качество рассуждения в критических фазах |
| 37-45 | type: поле + last_verified | Lifecycle management |
| 46+ | Удаление/архивация бесполезных (по Comparator) | Меньше контекстного мусора |

**Скиллы без YAML (добавить первыми):**
```
bsl-development, llm-rotation, 1c-mcp-toolkit, deployment,
embedding-models, evaluation-benchmark, framework-caching,
framework-mcp-ui, framework-quickstart, graph-operations,
indexing-pipeline, memory-unified, prompt-engineering,
qdrant-operations, search-pipeline-debug, agent-orchestration
```

**Скиллы для ultrathink:**
```
analyze-1c-task-v2     → фаза анализа требований
architecture-research  → фаза evaluation matrix
implement-1c-task      → фаза проектирования алгоритма
task-evaluation        → фаза классификации задачи
triad-factory          → фаза Q1-Q5 анализа
autoresearch           → Phase 0 ANALYZE + Phase 2 IDEATE
```

---

### Домен 2: Хуки (из Hook eval)

```
Проблема:  Ложные срабатывания (ralph_activator в этой сессии), пропуски
Метрика:   scripts/eval-hooks.py → accuracy (40 тестов, 16 скиллов)
Baseline:  текущий accuracy
Target:    > 95% (0 false positives в production)

Executor:
  - Правит один хук: добавляет/убирает сигналы, меняет threshold
  Инструменты: Read/Edit .claude/hooks/*.py

Reviewer:
  - Запускает: python scripts/eval-hooks.py → accuracy
  - Проверяет: latency хука < 5s (timeout)
  - Проверяет: нет regression в других хуках
  Verdict: accuracy вырос + latency ok → KEEP

Comparator:
  - 10 типовых промптов → какие хуки сработали?
  - False positives, false negatives
```

**Конкретные улучшения:**

| Хук | Проблема | Исправление |
|-----|----------|-------------|
| ralph_activator.py | Ложно активирует Ralph на "autoresearch" в чате | Добавить проверку: в ralph.bat контексте? или интерактив? |
| skill-router.py | ~70% accuracy | Pushy descriptions в скиллах → роутер автоматически лучше |
| task-protocol-enforcer.py | Блокирует иногда без причины | Eval: 10 кейсов where block is wrong |
| ralph_wiggum_stop.py | Ложно блокирует в интерактиве | Проверка: `.ralph_active` file exists? |

---

### Домен 3: Код Python (из AutoResearch Comprehensive)

```
Проблема:  Не измерено, предположительно > 100 ruff ошибок
Метрика:   ruff check src/ --output-format json | jq length
Baseline:  не замерен
Target:    0 errors

Executor:
  - Исправляет ОДНУ категорию ошибок ruff во ВСЕХ файлах
  Инструменты: Read/Edit src/**/*.py, Bash (ruff)

Reviewer:
  - ruff check → кол-во ошибок
  - pytest → тесты не сломались?
  Verdict: errors уменьшились + тесты ok → KEEP

Шаблон: ralph.bat --template quality (уже существует)
```

---

### Домен 4: BSL-код (из BSL Intelligence)

```
Проблема:  Claude ошибается в синтаксисе BSL, путает API
Метрика:   bsl_analyze → count errors в написанном коде
Baseline:  не замерен
Target:    < 1 ошибка на 50 строк

Executor:
  - Пишет BSL-код, используя bsl-platform-context для проверки API
  Инструменты: bsl-platform-context, EDT-MCP, Read/Edit

Reviewer:
  - bsl_analyze → ошибки
  - Проверка: API вызовы существуют? (bsl-platform-context search)
  Verdict: 0 ошибок → KEEP

Кэш: bsl-development/cache/common_mistakes.md (накапливает паттерны ошибок)
```

---

### Домен 5: Конфигурация 1С (из AutoResearch 1C Study)

```
Проблема:  Claude не знает конфигурацию, каждую сессию заново
Метрика:   изученных объектов / всего объектов (27 документов + 190 регистров + 91 справочник)
Baseline:  ~5%
Target:    40% (Волна 1), 80% (Волна 3)

Executor:
  - Изучает 1 объект: get_metadata → find_references → execute_query → код модуля
  - Записывает в cache/documents/{name}.md
  Инструменты: 1c-mcp-toolkit, EDT-MCP, bsl-semantic-search

Reviewer:
  - Проверяет на базе: "в регистре X есть движения от документа Y?"
  - Валидирует: кэш-файл содержит реквизиты, ТЧ, движения, бизнес-смысл
  Verdict: данные верифицированы → KEEP

Шаблон: ralph.bat --template 1c-study (уже существует)
```

---

### Домен 6: Документация (из audit-docs)

```
Проблема:  Документация расходится с кодом
Метрика:   audit-docs → coverage score
Baseline:  не замерен
Target:    > 85% coverage

Executor:
  - Дописывает документацию к одному модулю/фиче
  Инструменты: Read/Write docs/**/*.md

Reviewer:
  - audit-docs → coverage score вырос?
  - Содержит: описание, примеры, API reference
  Verdict: coverage вырос → KEEP
```

---

### Домен 7: API Performance (новый)

```
Проблема:  Не измерено, возможны bottlenecks
Метрика:   avg response time (ms) по ключевым endpoints
Baseline:  не замерен
Target:    < 200ms на /search/ask

Executor:
  - Оптимизирует 1 endpoint: кэширование, async, query optimization
  Инструменты: Read/Edit src/api/, pytest-benchmark

Reviewer:
  - pytest --benchmark → время ответа
  - pytest → тесты ok?
  Verdict: быстрее + тесты ok → KEEP
```

---

### Домен 8: Безопасность (из /autoresearch:security)

```
Проблема:  Не проверено
Метрика:   findings count × severity
Baseline:  не замерен (предположительно > 0)
Target:    0 critical, 0 high

Executor (read-only!):
  - Анализирует 1 attack vector из STRIDE threat model
  Инструменты: Read, Grep, bandit

Reviewer:
  - Проверяет: finding реальный? (не false positive)
  - Классифицирует: OWASP category + severity
  Verdict: real finding → LOG, false positive → SKIP

Comparator:
  - Покрытие OWASP Top 10: сколько категорий проверено?
```

---

### Домен 9: Промпты (Prompt Optimization)

```
Проблема:  Промпты Executor/Reviewer не оптимизированы
Метрика:   качество результата (LLM-graded 1-10) при минимальных токенах
Baseline:  не замерен
Target:    quality > 8, tokens < 5000 на итерацию

Executor:
  - Переписывает 1 промпт (executor или reviewer)
  Инструменты: Read/Edit prompt файлы

Reviewer:
  - Запускает 5 тестовых задач с новым промптом
  - Оценивает: quality (1-10), tokens, tool calls
  Verdict: quality >= 8 + tokens < 5000 → KEEP
```

---

### Домен 10: Сам AutoResearch (мета-оптимизация)

```
Проблема:  Эффективность самого цикла не измерена
Метрика:   iterations_to_target / total_iterations (keep rate)
Baseline:  не замерен
Target:    keep rate > 50% (половина изменений полезны)

Executor:
  - Корректирует Phase-протокол: добавляет правила, убирает лишние шаги
  Инструменты: Read/Edit SKILL.md, autoresearch.md

Reviewer:
  - Запускает AutoResearch на эталонной задаче
  - Замеряет: iterations to target, keep rate
  Verdict: keep rate вырос → KEEP

Это рекурсивный цикл: AutoResearch улучшает сам AutoResearch.
```

---

## Непрерывный цикл (не разовая задача)

Улучшение скиллов, хуков, кода — это **не "запустил раз, починил, забыл"**.
Это постоянный процесс, встроенный в саму систему на трёх уровнях:

### Уровень 1: Автоматический (хуки — каждый промпт)

Хуки работают на каждом промпте, молча собирают данные и ловят деградацию.

```
┌─────────────────────────────────────────────────────────────┐
│  КАЖДЫЙ ПРОМПТ ПОЛЬЗОВАТЕЛЯ                                │
│                                                             │
│  UserPromptSubmit:                                          │
│  ├── skill-router.py        → какой скилл подобрал?         │
│  │   └── log: prompt, matched_skill, confidence             │
│  │                                                          │
│  ├── skill-quality-monitor.py  ← НОВЫЙ                      │
│  │   └── Считает: сколько раз пользователь                  │
│  │       вызвал Skill() ВРУЧНУЮ (= роутер не сработал)      │
│  │   └── Считает: сколько раз скилл вызван но не помог      │
│  │       (пользователь сразу переформулировал)              │
│  │   └── Копит в: data/skill-quality-metrics.jsonl          │
│  │                                                          │
│  PostToolUse (Skill):                                       │
│  ├── task-protocol-observer.py → записал какой скилл        │
│  └── skill-usage-tracker.py    ← НОВЫЙ                      │
│      └── Записывает: skill_name, duration, помог ли         │
│                                                             │
│  Stop:                                                      │
│  ├── skill-health-check.py     ← НОВЫЙ                      │
│  │   └── Раз в сессию: проверяет skill-quality-metrics      │
│  │   └── Если accuracy по скиллу < 70% за последние 20      │
│  │       вызовов → systemMessage "Скилл X деградировал"     │
│  │   └── Если reference-скилл last_verified > 30 дней       │
│  │       → systemMessage "Скилл X устарел"                  │
└─────────────────────────────────────────────────────────────┘
```

**Что это даёт:** система **сама замечает** когда скилл перестал работать.
Не нужно помнить "а давно ли я проверял скиллы?" — хук скажет.

### Уровень 2: Периодический (ночной AutoResearch цикл)

Раз в неделю (или по расписанию) — автономный цикл улучшений.

```
┌─────────────────────────────────────────────────────────────┐
│  НОЧНОЙ ЦИКЛ (cron / Task Scheduler)                       │
│                                                             │
│  1. Прочитать data/skill-quality-metrics.jsonl              │
│     → Какие скиллы деградировали? (accuracy < 80%)          │
│     → Какие скиллы не вызывались > 30 дней? (мёртвые)       │
│     → Какие скиллы вызывались вручную? (плохой trigger)     │
│                                                             │
│  2. Для каждого проблемного скилла:                         │
│     AutoResearch цикл (Executor → Reviewer):                │
│     - Executor: переписывает description (pushy стиль)      │
│     - Reviewer: eval-skill-router.py → F1 вырос?            │
│     - Keep / Revert                                         │
│                                                             │
│  3. Для reference-скиллов с last_verified > 30 дней:        │
│     - Проверить source_version vs текущая                    │
│     - Если расхождение → пометить needs_update              │
│                                                             │
│  4. Обновить data/skill-health-report.md                    │
│     (последний отчёт о здоровье всех скиллов)              │
│                                                             │
│  Запуск:                                                    │
│  scripts\ralph.bat --template skill-health --max-iterations 15
└─────────────────────────────────────────────────────────────┘
```

**Что это даёт:** скиллы **сами себя чинят**. Хук заметил деградацию →
ночной цикл автоматически переписал description → eval подтвердил улучшение.

### Уровень 3: Ручной (/autoresearch — по запросу)

Когда пользователь видит конкретную проблему или хочет целенаправленно улучшить.

```
> /autoresearch
> bsl-development скилл срабатывает на запросы про Python, почини

Claude анализирует → создаёт рецепт → пользователь запускает
```

### Три уровня работают вместе

```
Уровень 1 (хуки)           Уровень 2 (ночной)         Уровень 3 (ручной)
────────────────            ──────────────────          ─────────────────
Каждый промпт              Раз в неделю                По запросу
Пассивный сбор             Автономное исправление      Целенаправленная работа

  │ собирает метрики          │ читает метрики            │ анализирует идею
  │ ловит деградацию          │ чинит автоматически       │ создаёт рецепт
  │ предупреждает             │ запускает eval            │ запускает цикл
  ▼                           ▼                          ▼
  data/skill-quality-         Улучшенные SKILL.md        Улучшенные SKILL.md
  metrics.jsonl               + eval report              + autoresearch.md

  ДАТЧИК                      АВТОПИЛОТ                  РУЧНОЕ УПРАВЛЕНИЕ
```

**Аналогия:**
- Уровень 1 = **приборная панель** (показывает температуру двигателя)
- Уровень 2 = **автоматический термостат** (температура высокая → охлаждает)
- Уровень 3 = **механик** (разобрал двигатель, нашёл причину, починил)

---

## Непрерывный цикл для КАЖДОГО домена

Тот же трёхуровневый подход работает не только для скиллов:

| Домен | Уровень 1 (хук-датчик) | Уровень 2 (ночной цикл) | Уровень 3 (ручной) |
|-------|------------------------|--------------------------|---------------------|
| **Скиллы** | skill-quality-monitor: accuracy per skill | ralph --template skill-health | /autoresearch "improve trigger X" |
| **Хуки** | hook-latency-monitor: timing per hook | ralph --template hook-quality | /autoresearch "fix false positives" |
| **Python** | code-quality-monitor: ruff errors on Write | ralph --template python-quality | /autoresearch "0 ruff errors" |
| **BSL** | bsl-quality-monitor: errors on BSL Write | ralph --template bsl-quality | /autoresearch "0 bsl errors" |
| **1С знания** | knowledge-gap-detector: вопрос без ответа в кэше | ralph --template 1c-study | /autoresearch "изучи документ X" |
| **Документация** | docs-change-enforcer (уже есть) | ralph --template docs-coverage | /autoresearch "audit-docs > 85%" |
| **Безопасность** | нет (добавить bandit on Write) | ralph --template security-audit | /autoresearch:security |

---

## Жизненный цикл скилла (непрерывный)

```
Создание                  Жизнь                          Смерть
────────                  ─────                          ──────

  doc-to-skill     →    Хуки мониторят usage        →   Comparator: "скилл
  или вручную      →    Eval проверяет triggers     →   не приносит пользы"
                   →    Ночной цикл правит desc     →   → архивация
                   →    Модель обновилась?           →
                   │      → re-eval автоматически    │
                   │    Код изменился?               │
                   │      → docs-change-enforcer     │
                   │        ловит расхождение        │
                   │    Пользователь вызвал вручную? │
                   │      → плохой trigger,          │
                   │        ночной цикл починит      │
                   └─────────────────────────────────┘
                         НЕПРЕРЫВНО
```

---

## Новые хуки для непрерывного мониторинга

| Хук | Событие | Что делает |
|-----|---------|-----------|
| **skill-quality-monitor.py** | UserPromptSubmit | Логирует: какой скилл подобран, confidence, ручной вызов? |
| **skill-usage-tracker.py** | PostToolUse:Skill | Логирует: skill_name, помог ли (пользователь продолжил или переформулировал) |
| **skill-health-check.py** | Stop | Проверяет метрики за сессию, предупреждает о деградации |
| **code-quality-monitor.py** | PostToolUse:Write | На каждый Write .py — считает ruff errors в файле |
| **knowledge-gap-detector.py** | PostToolUse:MCP | Если вопрос про 1С и ответа нет в кэше → лог gap |

---

## Единый CLI

Все 10 доменов запускаются **одинаково**:

```bash
# Через /autoresearch в чате (интерактивный — уровень 3)
> /autoresearch
> Улучши trigger accuracy скиллов

# Через ralph с шаблоном (автономный — уровень 2)
scripts\ralph.bat --template skill-health --max-iterations 15
scripts\ralph.bat --template python-quality --max-iterations 15
scripts\ralph.bat --template bsl-quality --max-iterations 10
scripts\ralph.bat --template 1c-study --max-iterations 10
scripts\ralph.bat --template docs-coverage --max-iterations 10
scripts\ralph.bat --template security-audit --max-iterations 20

# Ночной cron (автоматический — уровень 2)
# В Windows Task Scheduler:
scripts\ralph.bat --template skill-health --max-iterations 10

# Или любая кастомная идея (уровень 3)
> /autoresearch
> Хочу чтобы все промпты Executor были < 1000 токенов без потери качества
```

---

## Анализ рисков

### Что безопасно (риск = 0, ничего не ломает)

| Действие | Почему безопасно |
|----------|------------------|
| YAML frontmatter к 16 скиллам | Добавление, не изменение. Скилл работал без YAML — будет работать и с ним |
| Eval 150+ промптов | Только измерение. Ничего не меняет в системе |
| type + last_verified в YAML | Метаданные, не влияют на логику |
| autoresearch.md (persistence) | Новый файл, ничего не трогает |
| autoresearch SKILL.md | Новый скилл, не конфликтует с существующими |

### Что рискованно (нужна защита)

| Действие | Риск | Защита |
|----------|------|--------|
| Pushy descriptions | Скилл начнёт триггериться когда не надо | **Eval ДО и ПОСЛЕ**. Один скилл за раз. F1 упал → revert |
| Новые хуки-датчики | +200-500ms на промпт (уже 13 хуков) | **Только логирование**, никаких блокировок. Timeout 2s |
| Ночной AutoResearch | Executor переписал description → сломал скилл | **Отдельная git ветка**. Ручной review → merge |
| Ultrathink | +$0.05-0.10 на вызов, медленнее | Только 2-3 скилла сначала, замерить разницу |
| ralph_activator расширение | Ложные срабатывания (как в этой сессии) | Проверка: `.ralph_active` exists? Контекст: ralph.bat или интерактив? |

### Текущие проблемы (уже сломано)

| Проблема | Где | Влияние |
|----------|-----|---------|
| ralph_activator ложно активирует в интерактиве | ralph_activator.py | ralph_wiggum_stop блокирует каждый ответ |
| 16 скиллов невидимы для Skill Router | bsl-development, llm-rotation и др. | Пользователь должен вызывать Skill() вручную |
| Reference-скиллы (35 шт.) могут устареть молча | claude-code-*, langchain-* | Неверная информация в ответах |
| Нет способа узнать: скилл помог или помешал | Все скиллы | Бесполезные скиллы занимают контекст |

---

## Дорожная карта: 4 этапа по возрастанию риска

### Этап 1: ИЗМЕРЕНИЕ (0 риск) — 1-2 дня

Ничего не меняем в поведении системы. Только замеряем текущее состояние
и добавляем метаданные.

```
Действия:
  1. Замерить baseline F1 Skill Router
     python scripts/eval-skill-router.py → F1 = ?

  2. YAML frontmatter к 16 скиллам без него
     (только name + description, ничего не ломает)

  3. type + last_verified + source_version к reference-скиллам
     (метаданные, не влияют на логику)

  4. Замерить F1 ПОСЛЕ добавления YAML
     python scripts/eval-skill-router.py → F1 = ? (ожидание: +0.05)

  5. Создать data/eval/skills/trigger_eval.json (150+ промптов)
     (расширить существующие 64 ground truth)

Артефакты:
  ├── 16 скиллов с новым YAML frontmatter
  ├── 35 reference-скиллов с type + last_verified
  ├── data/eval/skills/trigger_eval.json (150+ промптов)
  ├── data/eval/skills/baseline_f1.json (замер ДО)
  └── data/eval/skills/post_yaml_f1.json (замер ПОСЛЕ)

Критерий: F1 не упал после добавления YAML
```

---

### Этап 2: ТОЧЕЧНЫЕ УЛУЧШЕНИЯ (низкий риск) — 3-5 дней

Меняем по одному скиллу, после каждого — eval.
Параллельно создаём AutoResearch скилл (новый файл, ничего не трогает).

```
Действия:
  1. Pushy descriptions: по 1 скиллу за итерацию
     - Eval F1 ДО
     - Переписать description
     - Eval F1 ПОСЛЕ
     - F1 упал → git revert
     - F1 вырос → keep
     - Приоритет: 16 скиллов с новым YAML, потом 20 со слабым description

  2. AutoResearch SKILL.md
     - Новый скилл .claude/skills/autoresearch/SKILL.md
     - 10-фазный цикл, 3 агента
     - Не конфликтует с существующими

  3. autoresearch run.bat / run.ps1
     - Новый скрипт, ничего не трогает
     - Тестируем на 1 простой задаче (ruff errors)

  4. Ultrathink в 2 скиллах (analyze-1c-task-v2, architecture-research)
     - Замерить: качество ответа стало лучше?
     - Замерить: стоимость выросла на сколько?
     - Если quality/cost ratio плохой → убрать

Артефакты:
  ├── ~20 скиллов с улучшенным description
  ├── .claude/skills/autoresearch/ (новый скилл)
  ├── scripts/autoresearch.ps1 (новый скрипт)
  ├── data/eval/skills/post_tuning_f1.json
  └── 2 скилла с ultrathink + замер эффекта

Критерий: F1 >= baseline + 0.10, ни один скилл не сломан
Защита: eval после КАЖДОГО изменения, revert если хуже
```

---

### Этап 3: МОНИТОРИНГ (средний риск) — 1-2 недели

Добавляем 1 хук-датчик. ТОЛЬКО логирование, без блокировок.
Собираем данные месяц, потом решаем что с ними делать.

```
Действия:
  1. Создать skill-quality-monitor.py (UserPromptSubmit)
     ТОЛЬКО ЛОГИРОВАНИЕ:
     - Какой скилл подобрал Skill Router? С каким confidence?
     - Пользователь вызвал Skill() вручную? (= роутер не сработал)
     → Пишет в data/skill-quality-metrics.jsonl
     → НЕ блокирует. НЕ показывает systemMessage. Timeout 2s.
     → Если упал — молча, без влияния на работу.

  2. Починить ralph_activator.py
     - Баг: ложно активирует в интерактивном режиме
     - Проверка: запущен из ralph.bat (.ralph_active exists)?
       Или из интерактивного чата?

  3. Скрипт audit-skill-freshness.py
     - Для каждого reference-скилла:
       source_version vs текущая версия (pip show / npm list)
     - Если расхождение → report (не автоматическое исправление)

  4. Месяц сбора данных skill-quality-metrics.jsonl
     Через месяц анализ:
     - Какие скиллы деградировали?
     - Какие скиллы не вызывались ни разу? (кандидаты на архивацию)
     - Какие скиллы вызывались вручную? (плохой trigger)

Артефакты:
  ├── .claude/hooks/skill-quality-monitor.py (только логирование)
  ├── ralph_activator.py (исправлен баг)
  ├── scripts/audit-skill-freshness.py
  └── data/skill-quality-metrics.jsonl (копится месяц)

Критерий: хук не тормозит (< 2s), не падает, не влияет на работу
Защита: только логирование, никаких блокировок, graceful degradation
```

---

### Этап 4: АВТОПИЛОТ (высокий риск) — только после Этапа 3

Через месяц: данные собраны, AutoResearch обкатан, eval стабилен.
Теперь можно включить автоматическое исправление.

```
Действия:
  1. Ночной AutoResearch цикл для скиллов
     НА ОТДЕЛЬНОЙ GIT ВЕТКЕ (autoresearch/skill-health)
     - Читает skill-quality-metrics.jsonl → находит проблемные скиллы
     - Executor: переписывает description
     - Reviewer: eval → F1 вырос?
     - РУЧНОЙ REVIEW каждого коммита перед merge в master

  2. Через 2 недели: если 90%+ изменений полезны
     → автоматический merge (без ручного review)

  3. Расширить на другие домены:
     - skill-health → hook-quality → code-quality → ...
     - Тот же движок, новые рецепты

  4. Comparator: A/B для top-10 скиллов
     - Claude со скиллом vs без → tool calls, токены, качество
     - Бесполезные скиллы → архивация

Артефакты:
  ├── ralph.bat --template skill-health
  ├── Ветка autoresearch/skill-health
  ├── data/skill-health-report.md (еженедельный отчёт)
  └── Архив: .claude/skills/_archived/ (бесполезные скиллы)

Критерий: 90%+ автоматических изменений полезны (keep rate)
Защита: отдельная ветка, ручной review, revert при деградации
```

---

## Визуализация: от измерения к автопилоту

```
Этап 1               Этап 2                Этап 3               Этап 4
ИЗМЕРЕНИЕ             ТОЧЕЧНЫЕ              МОНИТОРИНГ           АВТОПИЛОТ
(0 риск)              (низкий)              (средний)            (высокий)

Замерить F1       →   Pushy desc        →   1 хук-датчик     →  Ночной цикл
YAML к 16         →   по 1 скиллу       →   Только логи      →  На ветке
type/verified     →   eval каждый раз   →   Месяц данных     →  Ручной review
150 eval промптов →   AutoResearch SKILL→   Починить ralph   →  Потом авто
                  →   Ultrathink в 2    →   audit-freshness  →  Comparator A/B

Дни 1-2               Дни 3-7               Недели 2-6           Месяц 2+

   НИЧЕГО НЕ           КАЖДОЕ                СОБИРАЕМ             СИСТЕМА
   ЛОМАЕТСЯ             ИЗМЕНЕНИЕ             ДАННЫЕ               САМА ЧИНИТ
                        ПРОВЕРЯЕМ                                  СКИЛЛЫ
```

---

## Приоритизация доменов

| Приоритет | Домен | Метрика | Этап внедрения | Impact |
|-----------|-------|---------|----------------|--------|
| **P0** | Скиллы | F1 trigger accuracy | Этап 1-4 (полный цикл) | Высокий: все 65 скиллов |
| **P0** | Хуки | eval-hooks accuracy + false positives | Этап 3 (мониторинг) | Высокий: каждый промпт |
| **P1** | Код Python | ruff + mypy errors | Этап 2 (AutoResearch) | Средний |
| **P1** | Конфигурация 1С | coverage % | Этап 2 (уже есть template) | Высокий для 1С задач |
| **P1** | BSL-код | bsl_analyze errors | Этап 2 (AutoResearch) | Средний |
| **P2** | Документация | audit-docs coverage | Этап 3+ | Низкий |
| **P2** | API Performance | response ms | Этап 4+ | Средний |
| **P2** | Безопасность | findings × severity | Этап 4+ | Важно но не срочно |
| **P3** | Промпты | quality / tokens | Этап 4+ | Мета |
| **P3** | Мета | keep rate | Этап 4+ | Рекурсивный |

---

## Связь компонентов

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ЕДИНЫЙ ПАТТЕРН                                   │
│                                                                      │
│  measure → change → verify → keep/revert → repeat                    │
│                                                                      │
│  4 этапа внедрения (по возрастанию риска):                           │
│  ├── Этап 1: Измерение   (0 риск)    — baseline, YAML, eval         │
│  ├── Этап 2: Точечные    (низкий)    — по 1 скиллу, eval каждый раз │
│  ├── Этап 3: Мониторинг  (средний)   — 1 хук, только логи, месяц   │
│  └── Этап 4: Автопилот   (высокий)   — отдельная ветка, review      │
│                                                                      │
│  Реализован через:                                                   │
│  ├── /autoresearch (Skill)     → анализ идеи, создание рецепта       │
│  ├── ralph.bat (Script)        → автономный цикл                     │
│  ├── 3 агента (Architecture)   → Executor + Reviewer + Comparator    │
│  ├── autoresearch.md (Memory)  → persistence между сессиями          │
│  ├── TSV + JSONL (Log)         → история экспериментов               │
│  └── skill-quality-monitor     → непрерывный датчик (Этап 3)         │
│                                                                      │
│  3 уровня непрерывности:                                             │
│  ├── Уровень 1: Хуки-датчики   → каждый промпт (пассивный сбор)     │
│  ├── Уровень 2: Ночной цикл    → раз в неделю (автоматическое fix)  │
│  └── Уровень 3: /autoresearch   → по запросу (целенаправленная)      │
│                                                                      │
│  Skills 2.0 концепции:                                               │
│  ├── Trigger Tuning            → pushy descriptions (Этап 2)         │
│  ├── Eval system               → 150+ промптов (Этап 1)              │
│  ├── Comparator                → слепое A/B (Этап 4)                 │
│  ├── Ultrathink                → 2 скилла сначала (Этап 2)           │
│  ├── Encoded Preference        → приоритет инвестиций (все этапы)    │
│  └── Scope separation          → personal vs project (Этап 4+)       │
│                                                                      │
│  Принцип: КАЖДЫЙ этап добавляет ценность сам по себе.                │
│  Можно остановиться на любом этапе — система уже лучше чем была.    │
└──────────────────────────────────────────────────────────────────────┘
```
