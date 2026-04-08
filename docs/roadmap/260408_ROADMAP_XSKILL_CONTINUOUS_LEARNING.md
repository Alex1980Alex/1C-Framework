# Roadmap: XSkill Continuous Learning Architecture

**Date:** 2026-04-08 | **Status:** Phase 3-4 IMPLEMENTED | **Priority:** HIGH
**Source:** XSkill (arXiv: 2603.12056) — Continual Learning from Experience and Skills in Multimodal Agents
**Goal:** Внедрить двухпоточную архитектуру непрерывного обучения агентов в 1C-Enterprise Framework без обновления весов модели

---

## Текущее состояние (AS-IS)

| XSkill концепция | Аналог в фреймворке | Зрелость | GAP |
|---|---|---|---|
| **Skill Library** (Markdown task-level) | `.claude/skills/*/SKILL.md` (30+ навыков) | 90% | Skills статичны, не обновляются по опыту |
| **Experience Bank** (JSON action-level) | `auto-save-memory.jsonl`, `work-history.jsonl` | 30% | Сырые логи без дистилляции |
| **Accumulation Phase** | `pattern-capture-hook.js` (Phase 1) | 25% | Нет cross-rollout critique, нет auto-promotion |
| **Inference Phase** (retrieval + injection) | Skill Router + memory-first-hook | 90% | Hybrid keyword + semantic (Qdrant), experience injection |
| **Continuous Loop** (use → evaluate → update) | Отсутствует | 5% | Петля полностью разорвана |
| **Cross-model Transfer** | GLM agents + Claude общие skills | 40% | Нет tracking эффективности per-model |
| **Failure Capture** | Отсутствует | 0% | Только успешные паттерны |
| **Consolidation** | Отсутствует | 0% | Дубликаты накапливаются без ревизии |

**Оценка покрытия XSkill: ~40%** — основа есть, но два ключевых потока (Experience distillation + Learning loop) не реализованы.

---

## Архитектура (TO-BE)

```
                        ┌──────────────────────────────────────────────┐
                        │          CONTINUOUS LEARNING LOOP            │
                        └──────────────────────────────────────────────┘

  ┌─────────────────┐       ┌────────────────────┐       ┌──────────────────┐
  │  ACCUMULATION   │       │   KNOWLEDGE BASE   │       │    INFERENCE     │
  │     PHASE       │──────▶│                    │──────▶│      PHASE       │
  │                 │       │  ┌──────────────┐  │       │                  │
  │ A. Rollout      │       │  │ Skill Library│  │       │ D. Task Decomp   │
  │    Summary      │       │  │ (SKILL.md)   │  │       │                  │
  │                 │       │  └──────────────┘  │       │ E. Semantic      │
  │ B. Contrastive  │       │                    │       │    Retrieval     │
  │    Critique     │       │  ┌──────────────┐  │       │                  │
  │                 │       │  │ Experience   │  │       │ F. Context-Aware │
  │ C. Hierarchical │       │  │ Bank (JSONL) │  │       │    Adaptation    │
  │    Consolidation│       │  └──────────────┘  │       │                  │
  └────────┬────────┘       └────────────────────┘       │ G. Prompt        │
           │                                              │    Injection     │
           │              ┌────────────────────┐          └────────┬─────────┘
           │              │   EVALUATION LOOP  │                   │
           └──────────────│                    │◀──────────────────┘
                          │ H. Outcome Scoring │
                          │ I. Skill Revision  │
                          │ J. Model Profiling │
                          └────────────────────┘
```

---

## Phase 1: Experience Distillation Engine

> **Цель:** Превратить сырые логи (`auto-save-memory.jsonl`, `work-history.jsonl`) в структурированные тактические инсайты (Experience Bank)
> **Срок:** 2-3 сессии | **Зависимости:** нет | **Приоритет:** P0

### 1.1. Формат Experience Record

**Задача:** Определить JSON-схему для дистиллированных experience-записей

**Файл:** `cache/experience-bank/schema.json`

```json
{
  "experience_id": "exp-2026-04-08-001",
  "trigger": {
    "task_type": "bsl-analysis",
    "keywords": ["анализ", "модуль", "BSL"],
    "context_pattern": "user asks to analyze BSL module"
  },
  "insight": {
    "tool_preference": "mcp__ast-grep-mcp__ast_grep",
    "tool_avoided": "mcp__serena__find_symbol",
    "reason": "ast-grep 95% accuracy vs Serena 30-40% for BSL structural search",
    "category": "tool_selection"
  },
  "evidence": {
    "success_count": 12,
    "failure_count": 3,
    "sessions_observed": 5,
    "last_observed": "2026-04-08T14:30:00Z",
    "source_entries": ["auto-save-memory.jsonl:line:1234", "..."]
  },
  "confidence": 0.92,
  "model_specificity": "all",
  "status": "confirmed",
  "created_at": "2026-04-05T10:00:00Z",
  "updated_at": "2026-04-08T14:30:00Z"
}
```

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 1.1.1 Спроектировать JSON Schema | `cache/experience-bank/schema.json` | 15 мин |
| 1.1.2 Определить категории инсайтов | Enum: `tool_selection`, `parameter_tuning`, `workflow_order`, `error_avoidance`, `prompt_pattern` | 10 мин |
| 1.1.3 Определить уровни confidence | Формула: `success_count / (success_count + failure_count) * session_weight` | 10 мин |
| 1.1.4 Создать директорию `cache/experience-bank/` | mkdir + .gitignore entry | 5 мин |
| 1.1.5 Создать файл `cache/experience-bank/experiences.jsonl` | Пустой JSONL + header comment | 5 мин |

---

### 1.2. Distillation Hook (session-end)

**Задача:** Хук на `PreCompact` / session-end, который анализирует сырые логи и выделяет experience-записи

**Файл:** `scripts/hooks/learning/experience-distiller.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 1.2.1 Создать скелет `experience-distiller.py` | Python script с argparse, stdin parsing | 20 мин |
| 1.2.2 Парсер `auto-save-memory.jsonl` | Функция `parse_raw_logs(path) -> List[RawEntry]` | 30 мин |
| 1.2.3 Парсер `work-history.jsonl` | Функция `parse_work_history(path) -> List[WorkEntry]` | 20 мин |
| 1.2.4 Tool-use pattern detector | Функция `detect_tool_patterns(entries) -> List[Pattern]` — группировка по tool_name, подсчёт success/fail | 45 мин |
| 1.2.5 Retry detector | Функция `detect_retries(entries) -> List[RetryPattern]` — один и тот же tool вызван >1 раза подряд с разными params | 30 мин |
| 1.2.6 Tool-switch detector | Функция `detect_tool_switches(entries) -> List[SwitchPattern]` — начали с tool A, переключились на tool B для той же задачи | 30 мин |
| 1.2.7 Success/failure classifier | Функция `classify_outcome(entry) -> Outcome` — по наличию error, retry, user correction | 30 мин |
| 1.2.8 Experience synthesizer | Функция `synthesize_experiences(patterns) -> List[Experience]` — объединение паттернов в experience records | 45 мин |
| 1.2.9 Dedup engine | Функция `deduplicate(new, existing) -> List[Experience]` — семантическое сравнение с existing experiences | 30 мин |
| 1.2.10 Writer | Функция `append_experiences(experiences, path)` — атомарная запись в JSONL | 15 мин |
| 1.2.11 Интеграция в `settings.json` | Hook registration: `PreCompact` trigger → `experience-distiller.py` | 10 мин |
| 1.2.12 Unit-тесты | `tests/test_experience_distiller.py` — 10+ тест-кейсов | 45 мин |
| 1.2.13 Smoke test на реальных логах | Запуск на `auto-save-memory.jsonl` → проверка выхода | 20 мин |

---

### 1.3. Incremental Distillation (real-time)

**Задача:** Мини-дистилляция после каждого `PostToolUse` — не ждём конца сессии

**Файл:** `scripts/hooks/learning/micro-experience-capture.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 1.3.1 Создать `micro-experience-capture.py` | Python PostToolUse hook | 20 мин |
| 1.3.2 Sliding window buffer | In-memory буфер последних 10 tool calls для контекста | 20 мин |
| 1.3.3 Immediate pattern detection | Детекция retry/switch в окне без ожидания session-end | 30 мин |
| 1.3.4 Lightweight JSONL append | Запись micro-experience в `cache/experience-bank/pending-micro.jsonl` | 15 мин |
| 1.3.5 Merge при session-end | `experience-distiller.py` подхватывает `pending-micro.jsonl` | 20 мин |
| 1.3.6 Регистрация в `settings.json` | PostToolUse trigger | 10 мин |

---

## Phase 2: Failure Capture System

> **Цель:** Захватывать неудачные попытки (retries, denials, switches) как отрицательные примеры для контрастного обучения
> **Срок:** 1-2 сессии | **Зависимости:** Phase 1.1 (формат) | **Приоритет:** P0

### 2.1. Failure Event Taxonomy

**Задача:** Классифицировать типы неудач агента

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 2.1.1 Определить failure types enum | `tool_error`, `user_denied`, `tool_retry`, `approach_switch`, `timeout`, `empty_result`, `wrong_result` | 15 мин |
| 2.1.2 Определить severity levels | `minor` (empty result), `moderate` (retry), `major` (user denied), `critical` (approach switch after 3+ retries) | 10 мин |
| 2.1.3 Формат failure record | JSON schema расширение Experience Record с полем `failure_context` | 15 мин |

---

### 2.2. Failure Detection Hook

**Задача:** PostToolUse хук, детектирующий неудачи в реальном времени

**Файл:** `scripts/hooks/learning/failure-capture.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 2.2.1 Создать `failure-capture.py` | Python PostToolUse hook | 20 мин |
| 2.2.2 Error detector | Парсинг tool result на наличие error/exception/traceback | 20 мин |
| 2.2.3 Empty result detector | Детекция пустых/бесполезных результатов (0 matches, empty file) | 15 мин |
| 2.2.4 Retry detector (stateful) | Отслеживание: тот же tool + похожие params в окне 3 вызовов | 30 мин |
| 2.2.5 User denial tracker | Парсинг `tool_denied` events из stdin | 15 мин |
| 2.2.6 Approach switch detector | Детекция: tool A failed → tool B used для той же задачи (по совпадению params/path) | 30 мин |
| 2.2.7 Failure record writer | Append в `cache/experience-bank/failures.jsonl` | 15 мин |
| 2.2.8 Регистрация хука | `settings.json` PostToolUse entry | 10 мин |
| 2.2.9 Unit-тесты | `tests/test_failure_capture.py` | 30 мин |

---

### 2.3. Contrastive Analysis (XSkill Cross-Rollout Critique)

**Задача:** Периодическое сравнение success vs failure паттернов для одного типа задач

**Файл:** `scripts/hooks/learning/contrastive-analyzer.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 2.3.1 Создать `contrastive-analyzer.py` | Python script (вызывается из experience-distiller) | 20 мин |
| 2.3.2 Task type grouper | Группировка experiences + failures по `trigger.task_type` | 20 мин |
| 2.3.3 Success/failure pair matcher | Для каждого task_type: найти пары (success tool A, failure tool B) | 30 мин |
| 2.3.4 Contrastive insight generator | Формат: "Для {task_type}: {tool_A} работает (N успехов), {tool_B} не работает (M провалов), потому что {reason}" | 30 мин |
| 2.3.5 Confidence scorer | confidence = (success_A + failure_B) / total_observations * recency_weight | 15 мин |
| 2.3.6 Output writer | Append contrastive insights в `cache/experience-bank/contrastive-insights.jsonl` | 15 мин |
| 2.3.7 Integration в experience-distiller | Вызов contrastive-analyzer после основной дистилляции | 10 мин |
| 2.3.8 Unit-тесты | `tests/test_contrastive_analyzer.py` | 30 мин |

---

## Phase 3: Hierarchical Consolidation ✅ IMPLEMENTED

> **Цель:** Периодическая очистка, дедупликация и слияние experience records для предотвращения неограниченного роста
> **Срок:** 1-2 сессии | **Зависимости:** Phase 1, Phase 2 | **Приоритет:** P1
> **Реализовано:** 2026-04-08 | **Тесты:** 32/32 passed

### 3.1. Semantic Deduplication

**Задача:** Удаление семантически дублирующихся experience records

**Файл:** `scripts/hooks/learning/experience-consolidator.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 3.1.1 Создать `experience-consolidator.py` | Python script | 20 мин |
| 3.1.2 Embedding generator | Генерация эмбеддингов для `insight.reason` через Ollama/text-embedding | 30 мин |
| 3.1.3 Cosine similarity matcher | Пороговое сравнение (threshold=0.85) для детекции дубликатов | 20 мин |
| 3.1.4 Merge strategy | При дубликатах: объединить evidence (суммировать counts), взять max confidence, обновить updated_at | 30 мин |
| 3.1.5 Conflict resolver | При противоречиях (tool A лучше vs tool B лучше): флаг `conflicting=true`, оба сохраняются | 20 мин |
| 3.1.6 Stale record eviction | Удаление записей с `last_observed` > 30 дней И confidence < 0.5 | 15 мин |
| 3.1.7 Archive writer | Перемещение удалённых в `cache/experience-bank/archive/` с timestamp | 15 мин |
| 3.1.8 Unit-тесты | `tests/test_experience_consolidator.py` | 30 мин |

---

### 3.2. Skill Library Auto-Update

**Задача:** Промоция high-confidence experience records в SKILL.md файлы (Phase 2 pattern-capture-hook)

**Файл:** `scripts/hooks/learning/skill-promoter.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 3.2.1 Создать `skill-promoter.py` | Python script | 20 мин |
| 3.2.2 Promotion criteria | confidence >= 0.9 AND sessions_observed >= 5 AND status == "confirmed" | 10 мин |
| 3.2.3 Target skill finder | По `trigger.task_type` найти соответствующий SKILL.md в `.claude/skills/` | 20 мин |
| 3.2.4 Skill section appender | Добавить секцию `## Learned Experiences` в конец SKILL.md | 30 мин |
| 3.2.5 New skill creator | Если нет подходящего SKILL.md — создать новый минимальный skill | 30 мин |
| 3.2.6 Promotion log | Запись promoted records в `cache/experience-bank/promotions.jsonl` | 10 мин |
| 3.2.7 Dry-run mode | Флаг `--dry-run` показывает что будет promoted без записи | 15 мин |
| 3.2.8 Integration в consolidator | Вызов skill-promoter после consolidation | 10 мин |
| 3.2.9 Unit-тесты | `tests/test_skill_promoter.py` | 30 мин |

---

### 3.3. Consolidation Scheduler

**Задача:** Запуск consolidation по расписанию (каждые N сессий)

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 3.3.1 Session counter | Инкремент в `cache/experience-bank/meta.json` → `sessions_since_consolidation` | 15 мин |
| 3.3.2 Trigger logic | Если `sessions_since_consolidation >= 5` → запуск consolidator | 10 мин |
| 3.3.3 Integration в session-start hook | Проверка counter при старте сессии | 15 мин |
| 3.3.4 Manual trigger command | Slash command `/consolidate-experiences` | 20 мин |

---

## Phase 4: Semantic Skill Retrieval ✅ IMPLEMENTED

> **Цель:** Заменить keyword matching в Skill Router на семантический поиск с fallback
> **Срок:** 1-2 сессии | **Зависимости:** нет (параллельно с Phase 1-3) | **Приоритет:** P1
> **Реализовано:** 2026-04-08 | **Тесты:** 37/37 passed
> **Qdrant коллекции:** `skill_library` (75 skills, 768d nomic-embed-text), `experience_bank` (768d, empty — ожидает Phase 1)
> **Файлы:** `.claude/hooks/shared/semantic_search.py`, `scripts/index-skills-to-qdrant.py`, `scripts/hooks/learning/experience-embedder.py`, `cache/experience-bank/schema.json`
> **Router:** Layer D в `.claude/hooks/skill-router.py` (semantic fallback + hybrid boost + A/B logging). Env: `SKILL_ROUTER_NO_SEMANTIC=1` для отключения

### 4.1. Skill Indexing в 1c-docs-rag

**Задача:** Проиндексировать все SKILL.md в существующий RAG для semantic retrieval

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 4.1.1 Инвентаризация всех SKILL.md | Glob `.claude/skills/*/SKILL.md` → список (30+ файлов) | 10 мин |
| 4.1.2 Batch indexing script | `scripts/index-skills-to-rag.py` — вызов `mcp__1c-docs-rag__add_document` для каждого | 30 мин |
| 4.1.3 Metadata enrichment | При индексации: добавить `source=skill`, `skill_name=...`, `trigger_keywords=[...]` | 20 мин |
| 4.1.4 Запуск индексации | Выполнить скрипт, проверить в RAG | 15 мин |
| 4.1.5 Incremental update hook | При изменении SKILL.md → автообновление в RAG | 30 мин |

---

### 4.2. Experience Bank Indexing

**Задача:** Проиндексировать experience records для semantic retrieval

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 4.2.1 Embedding pipeline для experiences | `scripts/hooks/learning/experience-embedder.py` — генерация эмбеддингов при записи | 30 мин |
| 4.2.2 Qdrant collection для experiences | Создание collection `experience-bank` в Qdrant | 15 мин |
| 4.2.3 Search API | Функция `search_experiences(query, limit=5) -> List[Experience]` | 30 мин |
| 4.2.4 Integration в experience-distiller | При записи нового experience → автоиндексация | 15 мин |
| 4.2.5 Тест: поиск по запросу | "какой инструмент для анализа BSL" → experience про ast-grep | 15 мин |

---

### 4.3. Hybrid Skill Router (keyword + semantic)

**Задача:** Добавить semantic fallback в существующий Skill Router

**Файл:** `.claude/hooks/skill-router.py` (модификация)

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 4.3.1 Анализ текущего skill-router.py | Понять keyword matching pipeline | 15 мин |
| 4.3.2 Добавить semantic search fallback | Если keyword match < threshold → вызвать `mcp__1c-docs-rag__search_docs(source=".claude/skills")` | 30 мин |
| 4.3.3 Score fusion | `final_score = 0.6 * keyword_score + 0.4 * semantic_score` | 20 мин |
| 4.3.4 Experience injection point | После skill retrieval → search experience bank → inject relevant experiences | 30 мин |
| 4.3.5 A/B logging | Логировать `matched_by: "keyword"` vs `"semantic"` vs `"hybrid"` для анализа | 15 мин |
| 4.3.6 Тест: edge case фразировки | "проверь этот модуль на ошибки" → должен загрузить `review-1c-code` skill | 15 мин |
| 4.3.7 Performance guard | Timeout 500ms на semantic search, fallback на keyword-only | 15 мин |

---

## Phase 5: Continuous Learning Loop

> **Цель:** Замкнуть петлю: использование знаний → оценка результата → обновление знаний
> **Срок:** 2-3 сессии | **Зависимости:** Phase 1, Phase 3, Phase 4 | **Приоритет:** P1

### 5.1. Outcome Tracking

**Задача:** Отслеживание результата применения знаний (skills и experiences)

**Файл:** `scripts/hooks/learning/outcome-tracker.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 5.1.1 Создать `outcome-tracker.py` | Python PostToolUse + UserPromptSubmit hook | 20 мин |
| 5.1.2 Knowledge usage logger | При injection skill/experience → записать `knowledge_id`, `timestamp`, `task_context` | 20 мин |
| 5.1.3 Implicit success detector | Пользователь продолжил без коррекции → `outcome=implicit_success` | 20 мин |
| 5.1.4 Implicit failure detector | Пользователь сказал "нет", "не так", retry → `outcome=implicit_failure` | 20 мин |
| 5.1.5 Explicit feedback parser | Паттерны: "отлично", "правильно", "не то", "переделай" → score mapping | 25 мин |
| 5.1.6 Outcome record writer | Append в `cache/experience-bank/outcomes.jsonl` | 15 мин |
| 5.1.7 Регистрация хука | `settings.json` UserPromptSubmit + PostToolUse entries | 10 мин |
| 5.1.8 Unit-тесты | `tests/test_outcome_tracker.py` | 30 мин |

---

### 5.2. Knowledge Scoring Engine

**Задача:** Пересчёт confidence scores на основе outcome data

**Файл:** `scripts/hooks/learning/knowledge-scorer.py`

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 5.2.1 Создать `knowledge-scorer.py` | Python script (вызывается из consolidator) | 20 мин |
| 5.2.2 Score formula | `new_confidence = (old * decay) + (outcome_score * learning_rate)` с EMA smoothing | 20 мин |
| 5.2.3 Decay function | Временной decay: records без использования >14 дней теряют 5% confidence/неделю | 15 мин |
| 5.2.4 Outcome aggregation | Суммирование outcomes per knowledge_id → win_rate | 20 мин |
| 5.2.5 Score updater | Обновление `confidence` в `experiences.jsonl` | 15 мин |
| 5.2.6 Threshold alerts | Если confidence упал < 0.3 → флаг `needs_review=true` | 10 мин |
| 5.2.7 Integration в consolidator | Вызов scorer перед dedup/promotion | 10 мин |
| 5.2.8 Unit-тесты | `tests/test_knowledge_scorer.py` | 30 мин |

---

### 5.3. Skill Revision Pipeline

**Задача:** Автоматическое обновление/деактивация skills с низким score

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 5.3.1 Skill health checker | Скрипт: прочитать все SKILL.md → проверить наличие outcome data → рассчитать health score | 30 мин |
| 5.3.2 Low-score alerter | Skill с health < 0.4 → запись в `cache/experience-bank/skills-needing-revision.json` | 15 мин |
| 5.3.3 Auto-deprecation | Skill с health < 0.2 за 30 дней → добавить `deprecated: true` в YAML frontmatter | 20 мин |
| 5.3.4 Revision suggestion generator | Для deprecated skill: сгенерировать diff-suggestion на основе contrastive insights | 30 мин |
| 5.3.5 User notification | При session start: "Skill X has low effectiveness, consider revision" | 15 мин |
| 5.3.6 Slash command `/skill-health` | Показать dashboard health всех skills | 25 мин |

---

## Phase 6: Cross-Model Knowledge Profiling

> **Цель:** Отслеживать эффективность знаний per-model (Claude Opus/Sonnet/Haiku, GLM)
> **Срок:** 1 сессия | **Зависимости:** Phase 5.1 | **Приоритет:** P2

### 6.1. Model-Aware Outcome Tracking

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 6.1.1 Добавить `model` field в outcome record | Определить модель из контекста (Agent model param, main model) | 15 мин |
| 6.1.2 Per-model score aggregation | `knowledge_scorer.py` → отдельные confidence scores per model | 20 мин |
| 6.1.3 Model affinity matrix | Матрица: skill × model → effectiveness score | 25 мин |
| 6.1.4 Conditional injection | Если текущая модель = haiku и skill effectiveness для haiku < 0.3 → не инжектить | 20 мин |
| 6.1.5 Dashboard `/model-knowledge-fit` | Показать какие skills работают для каких моделей | 25 мин |

---

### 6.2. GLM ↔ Claude Knowledge Transfer Tracking

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 6.2.1 Tag source model при experience creation | Какая модель создала experience | 10 мин |
| 6.2.2 Track cross-model usage | Experience создан Claude Opus, использован GLM → записать transfer event | 15 мин |
| 6.2.3 Transfer effectiveness score | Отдельный confidence для cross-model transfers | 15 мин |
| 6.2.4 Report: "Knowledge transfer matrix" | Таблица: source_model × target_model × success_rate | 20 мин |

---

## Phase 7: Observability & Metrics Dashboard

> **Цель:** Полная видимость процесса непрерывного обучения
> **Срок:** 1-2 сессии | **Зависимости:** Phase 1-5 | **Приоритет:** P2

### 7.1. Metrics Collection

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 7.1.1 Experience Bank stats | Общее кол-во, по категориям, avg confidence, growth rate | 15 мин |
| 7.1.2 Failure rate tracking | Failures per session, per tool, per task_type | 15 мин |
| 7.1.3 Consolidation stats | Дубликатов удалено, записей promoted, conflicting | 15 мин |
| 7.1.4 Retrieval stats | Skills found by keyword vs semantic, experience hit rate | 15 мин |
| 7.1.5 Learning loop velocity | Среднее время: raw log → distilled experience → promoted skill | 20 мин |
| 7.1.6 Write to `cache/experience-bank/metrics.json` | Обновляемый файл с timestamp | 15 мин |

---

### 7.2. Slash Commands

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 7.2.1 `/xskill-status` | Общий статус: кол-во experiences, skills updated, last consolidation | 25 мин |
| 7.2.2 `/xskill-experiences` | Топ-10 experiences по confidence с фильтрами | 25 мин |
| 7.2.3 `/xskill-failures` | Топ-10 failure patterns, рекомендации | 25 мин |
| 7.2.4 `/xskill-health` | Health dashboard: skills, experiences, loop velocity | 25 мин |
| 7.2.5 `/xskill-consolidate` | Ручной запуск consolidation | 15 мин |

---

## Phase 8: Advanced — Visual/Multimodal Grounding (Research)

> **Цель:** Исследовать привязку знаний к визуальному контексту (скриншоты 1С форм)
> **Срок:** research phase | **Зависимости:** Phase 1-5 полностью реализованы | **Приоритет:** P3

### 8.1. Screenshot-Aware Experience Capture

| Подзадача | Deliverable | Оценка |
|-----------|-------------|--------|
| 8.1.1 Research: image embedding models | Сравнить CLIP, SigLIP, Qwen-VL для скриншотов 1С | 2 часа |
| 8.1.2 Screenshot capture hook | При работе с формами 1С → автосохранение скриншота | 1 час |
| 8.1.3 Image-text alignment | Привязка experience record к конкретному скриншоту формы | 1 час |
| 8.1.4 Visual similarity search | "Покажи experience для формы, похожей на эту" | 2 часа |
| 8.1.5 PoC evaluation | Оценить: улучшает ли visual grounding качество retrieval | 1 час |

---

## Сводная таблица

| Phase | Название | Подзадач | Зависимости | Приоритет | Оценка |
|-------|----------|----------|-------------|-----------|--------|
| **1** | Experience Distillation Engine | 24 | нет | P0 | 8-10 ч |
| **2** | Failure Capture System | 20 | 1.1 | P0 | 6-8 ч |
| **3** | Hierarchical Consolidation | 17 | 1, 2 | P1 | ~~6-8 ч~~ DONE |
| **4** | Semantic Skill Retrieval | 17 | нет | P1 | ~~5-7 ч~~ DONE |
| **5** | Continuous Learning Loop | 20 | 1, 3, 4 | P1 | 8-10 ч |
| **6** | Cross-Model Knowledge Profiling | 9 | 5.1 | P2 | 3-4 ч |
| **7** | Observability & Metrics | 11 | 1-5 | P2 | 3-5 ч |
| **8** | Visual/Multimodal Grounding | 5 | 1-5 | P3 | research |
| | **ИТОГО** | **123** | | | **39-52 ч** |

---

## Порядок реализации (Critical Path)

```
                     ┌─────────────────────────────┐
                     │ Phase 1: Experience          │
             ┌──────▶│ Distillation (P0)            │──────┐
             │       └─────────────────────────────┘      │
             │                    │                         │
             │                    ▼                         ▼
         PARALLEL          ┌──────────────┐         ┌──────────────┐
             │              │ Phase 2:     │         │ Phase 3:     │
             │              │ Failure      │────────▶│ Consolidation│
             │              │ Capture (P0) │         │ (P1)         │
             │              └──────────────┘         └──────┬───────┘
             │                                              │
    ┌────────┴──────────┐                                   │
    │ Phase 4: Semantic  │                                   │
    │ Retrieval (P1)     │──────────────────────────────────▶│
    └───────────────────┘                                    │
                                                             ▼
                                                    ┌──────────────┐
                                                    │ Phase 5:     │
                                                    │ Learning     │
                                                    │ Loop (P1)    │
                                                    └──────┬───────┘
                                                           │
                                              ┌────────────┴────────────┐
                                              ▼                         ▼
                                     ┌──────────────┐         ┌──────────────┐
                                     │ Phase 6:     │         │ Phase 7:     │
                                     │ Cross-Model  │         │ Observability│
                                     │ (P2)         │         │ (P2)         │
                                     └──────────────┘         └──────────────┘
                                                                      │
                                                                      ▼
                                                             ┌──────────────┐
                                                             │ Phase 8:     │
                                                             │ Visual       │
                                                             │ (P3/Research)│
                                                             └──────────────┘
```

**Параллельный старт:** Phase 1 + Phase 4 можно начинать одновременно (нет зависимостей).

---

## Метрики успеха (Definition of Done)

| Метрика | Baseline (сейчас) | Target (после Phase 5) | Target (после Phase 7) |
|---------|-------------------|------------------------|------------------------|
| Experience records auto-created per session | 0 | >= 3 | >= 5 |
| Failure patterns captured per session | 0 | >= 1 | >= 2 |
| Skill retrieval: semantic hit rate | 0% (keyword only) | >= 30% via semantic | >= 50% |
| Knowledge reuse rate (injected → used) | unknown | >= 40% | >= 60% |
| Stale knowledge ratio (>30 days unused) | ~100% manual | < 30% | < 15% |
| Time from raw log → actionable insight | infinite (manual) | < 1 session | < 5 min (real-time) |
| Skills auto-updated from experience | 0 | >= 1/week | >= 3/week |
| Cross-model transfer success rate | unknown | measured | >= 70% |

---

## Риски и митигации

| Риск | Вероятность | Impact | Митигация |
|------|-------------|--------|-----------|
| Distillation генерирует шум, а не инсайты | Высокая | Средний | Строгий confidence threshold (0.9 для promotion), human review на первых 50 records |
| Hook latency: слишком много PostToolUse хуков | Средняя | Высокий | Micro-capture < 10ms (no IO в hot path), batch write через buffer |
| Semantic search добавляет 500ms+ к skill routing | Средняя | Средний | Hard timeout 500ms, fallback на keyword-only |
| Conflicting experiences путают агента | Низкая | Высокий | Contrastive analyzer + conflict resolution → inject only highest-confidence |
| Experience Bank растёт неограниченно | Высокая | Средний | Consolidation каждые 5 сессий, stale eviction > 30 дней |
| Auto-deprecation ломает working skills | Низкая | Критический | deprecation через 30 дней low score, notification пользователю, easy revert |

---

## Связь с существующими roadmap-ами

| Существующий roadmap | Пересечение | Действие |
|---------------------|-------------|----------|
| `260320_ROADMAP_DELEGATION_LEARNING.md` | Outcome tracking, learning loop | Phase 5 расширяет Iteration 2-5 |
| `PHASE_22_SELF_LEARNING_FEEDBACK.md` | Feedback collection, score tuning | Phase 5.1-5.2 обобщает подход |
| `SKILL_ROUTER_ROADMAP.md` | Semantic matching | Phase 4.3 — прямое продолжение |
| `260329_ROADMAP_POSTTOOLUSE_HOOKS_V2.md` | PostToolUse hook architecture | Phase 1.3, 2.2 — новые хуки в той же архитектуре |
| `GAP_P5_HOOK_OBSERVABILITY.md` | Hook metrics, latency | Phase 7 — observability для learning hooks |

---

**Версия:** 1.0
**Автор:** Claude Opus 4.6
**Следующий шаг:** Phase 1.1 — определить JSON schema для Experience Record
