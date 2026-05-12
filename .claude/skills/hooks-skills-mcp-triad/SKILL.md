---
name: hooks-skills-mcp-triad
description: "Используй этот скилл для понимания архитектуры Hooks + Skills + MCP в PDF Framework. Триггеры: 'триада', 'triad', 'hooks skills mcp', 'как работают хуки', 'автоматизация фреймворка', 'как устроена интеграция', 'архитектура хуков', 'hook architecture'."
---

# Hooks + Skills + MCP — Реализация в PDF Framework

**Этот файл — знание.** Описывает конкретную реализацию триады в этом проекте: какие хуки, скиллы и MCP-инструменты существуют, как они связаны, как работают вместе.

Для создания нового компонента — используй Фабрику: skill `triad-factory` (ШАГ 1-5, Q1-Q5, формулы).

---

## Текущая конфигурация

### Hooks (17 шт.) — КОГДА

#### UserPromptSubmit (4)

| Hook | Назначение |
|------|-----------|
| `skill-router.py` | Config-driven маршрутизация: Layer A+B+C (keyword + fuzzy + TF-IDF) → рекомендация скиллов (25 bundles, config v7 + weighted_keywords) |
| `research-task-detector.py` | Детекция ВОПРОСОВ → роутинг: Architecture, 1С, Tech |
| `decision-to-triad.py` | Детекция РЕШЕНИЙ/ИДЕЙ → Фабрика (`triad-factory`, Q1-Q5) |
| `ralph_activator.py` | Активация Ralph Wiggum для сложных многошаговых задач |
| `document-persistence.py` | Детекция roadmap/analysis/plan → сохранение в docs/ |
| `implement-1c-task-preflight.py` | Content-фильтр на `/implement-1c-task` → запуск `scripts/smoke_test_implement_1c_task.py --json` → systemMessage с pipeline mode (Full / **Full (no-BP)** / Code-only / Read-only verify / Read-only research / unusable) + строка «Debug environment: ready/not-ready» по полю `mcp_health.debug_hmr` (2026-05-11 — roadmap 260510 Phase 1 §3.1). Не блокирует. Лог: `data/hook-invocations.jsonl` category=`preflight`, outcome содержит `debug_hmr=<0\|1>`. |
| `analyze-1c-task-preflight.py` | Content-фильтр на `/analyze-1c-task` (с/без `--trace`) → probe debug-hmr через shared `shared/debug_hmr_health.probe_debug_hmr_ready()` → systemMessage с readiness Phase 2.5 Runtime Trace (2026-05-11 — roadmap 260510 Phase 3 §5.1). Не блокирует — Phase 2.5 opt-in. Лог: `data/hook-invocations.jsonl` category=`preflight`, outcome содержит `debug_hmr=<0\|1>;trace_flag=<0\|1>`. |

#### PreToolUse (4)

| Hook | Matcher | Назначение |
|------|---------|-----------|
| `code-skill-enforcer.py` | Write\|Edit\|Bash | Skill-First: BLOCK если скилл не активирован (уровни A-C) |
| `root-clutter-guard.py` | Write | Блокировка ad-hoc файлов в корне (test_*, debug_*) |
| `search-optimizer.py` | Bash | Оптимизация параметров Search API |
| `approval-gate.py` | Skill | SDD Phase 3: блокировка implementation-skills (`implement-1c-task`, `opsx:apply`) без `approval.status: approved` в `.openspec.yaml`. Читает `profile` field (default `1c-bsl`). Поддерживаемые профили: `1c-bsl` (BSL changes), `python-framework` (Python framework changes, см. `openspec/profiles/python-framework.yaml`). Для new profile добавить YAML файл в `openspec/profiles/` — hook автоматически подхватит через `_read_profile()`. |

`code-skill-enforcer.py` читает конфигурацию из `shared/code-skill-patterns.json` (массив правил `{pattern, skill, label, domain}`). Каждое правило связывает regex-паттерн команды/файла с обязательным для активации скиллом. **Важно**: `skill` должен существовать в каталоге `.claude/skills/` — entries с несуществующими target-скиллами создают phantom-блокировки (enforcer требует активации скилла, которого нет), поэтому при удалении скилла нужно сразу чистить соответствующие правила.

#### PostToolUse (13)

| Hook | Matcher | Назначение |
|------|---------|-----------|
| `knowledge-cache-reminder.py` | WebSearch\|WebFetch | Напоминание сохранить в кеш: 1С, Tech, Architecture |
| `code-skill-enforcer.py` | WebSearch\|WebFetch | Research cache reminder (уровень D) |
| `code-skill-enforcer.py` | Write\|Edit | Post-verification + LEARN phase (уровни E-F) |
| `factory-enforcer.py` | Write | Контроль ШАГ 4-5 Фабрики: регистрация + верификация |
| `docs-change-tracker.py` | Write\|Edit | Код изменился → напоминание обновить docs/ + skills/ |
| `auto-git-save.py` | Write\|Edit\|Bash | Mandatory task на коммит незакоммиченных изменений |
| `skill-usage-metrics.py` | Skill | Логирование использования скиллов → `data/skill-usage.log` |
| `bulk-action-guard.py` | Bash | Детекция bulk/destructive операций → Q5 enforcer |
| `code-verify-reminder.py` | Write\|Edit, Skill, Task, Stop | Mandatory task на code-verify; tri-registered (PreToolUse:Write\|Edit + PostToolUse:Write\|Edit\|Skill\|Task + Stop). PostToolUse:Task закрывает задачу при `[CODE-VERIFY-PASS]`; Stop fallback (v2.4.0) — читает `transcript_path` JSONL и закрывает по rfind-сравнению PASS/FAIL маркеров (workaround #6305 regression на Windows, см. claude-code-hooks-bugs SKILL 2026-04-26) |
| `posttooluse-quality-feedback.py` | Write\|Edit | ruff check *.py → hookSpecificOutput feedback (Phase 2.1) |
| `posttooluse-delegation-tracker.py` | mcp__llm-rotation__llm_complete | Z.AI delegation outcomes → delegation-outcomes.jsonl (Phase 1.4) |
| `posttooluse-web-cache.py` | WebSearch\|WebFetch | Кеширование результатов веб-поиска 24h TTL |
| `posttooluse-docs-tracker.py` | Write\|Edit | Мгновенный docs-change reminder (Phase 1.3) |

#### Stop (4)

| Hook | Назначение |
|------|-----------|
| `task-enforcer.py` | Блокировка без выполнения mandatory задач (incl. code-skill-enforcer) |
| `git-commit-enforcer.py` | Блокировка без коммита изменений в `.claude/` |
| `docs-change-enforcer.py` | Блокировка если код изменён без обновления документации. `SKIP_PATTERNS` исключает инфра-файлы, не являющиеся product code: `pyproject.toml`, `.mcp.json`, `.env.example`, `.gitmodules`/`.gitignore`/`.gitattributes`, `tools/`, `scripts/`, `tests/`, `__init__.py`, `configuration/`, `ИБTransportManagementDevelop/` (EDT проект), `src/bsl/`, `openspec/`, `.pre-commit-config.yaml`, `.kblintrc.yml` (kb-lint config; living in `docs/wiki/.kblintrc.yml` per `kb_lint/config.py:60-78`), `codecov.yml`, `data/eval/`. При добавлении нового EDT-проекта в корень — добавить в `SKIP_PATTERNS`, иначе `UNMAPPED` блокировка. (Roadmap: динамическое обнаружение через `.bsl-language-server.json` маркер — см. `src/bsl/project_discovery.py`.) |
| `ralph_wiggum_stop.py` | Контроль итеративного цикла Ralph |

#### SessionStart (1)

| Hook | Назначение |
|------|-----------|
| `ensure-docker-qdrant.py` | Проверка Docker engine + контейнера `pdf-rag-qdrant` при старте сессии; фоновый авто-старт Docker Desktop и `docker compose up -d qdrant` при необходимости. Не блокирует сессию (SessionStart advisory); graceful degradation на Linux/Mac/отсутствие Docker. Timeout 10s. |

### Skills (66 шт.) — КАК / ЧТО

#### Доменные (5)

| Skill | Домен | Назначение |
|-------|-------|-----------|
| `1c-doc-research` | 1С | 5 фаз, кеш знаний (8 категорий), атрибуция |
| `tech-research` | RAG/ML/Python | 5 фаз, кеш знаний (7 категорий) |
| `architecture-research` | Architecture | cache/ (факты) + adr/ (решения, ADR формат) |
| `pdf-knowledge` | PDF | MCP-инструменты PDF search, indexing |
| `task-evaluation` | Классификатор | Research vs Brainstorm vs Hybrid маршрутизация |

#### Инфраструктурные (9)

| Skill | Назначение |
|-------|-----------|
| `triad-factory` | Фабрика: алгоритм создания компонентов (ШАГ 1-5, Q1-Q5) |
| `hooks-skills-mcp-triad` | Реализация триады в проекте (этот файл) |
| `create-hook` | Шаблон + чеклист создания хуков |
| `doc-to-skill` | Конвертер документации → SKILL.md |
| `doc-to-cache` | Конвертер документации → knowledge cache |
| `learning-loop` | Цикл обучения: SEARCH → FETCH → EXECUTE → CREATE skill |
| `code-verify` | Верификация кода: 3 уровня, 4 режима (knowledge/behavior/bugfix/quality) |
| `tenacity-retry` | Retry с tenacity: декораторы, backoff, jitter, async |
| `obsidian-vault` | Obsidian vault навигация: wiki-links, templates, MCP obsidian-mcp |
| `wiki-pipeline` | PDF → Structured Wiki Pages: WikiExporter, IncrementalWikiSync, ReverseSync (Hermes Phase 4) |

#### Операционные фреймворка (17)

| Skill | Назначение |
|-------|-----------|
| `framework-quickstart` | Установка, первый запуск |
| `framework-config` | Конфигурация .env |
| `framework-cli` | CLI-команды |
| `framework-api` | REST API endpoints |
| `framework-mcp-ui` | MCP Server, Gradio, Python API |
| `framework-troubleshooting` | Диагностика, ошибки, производительность |
| `framework-caching` | 3-уровневое кеширование |
| `audit-docs` | Аудит Code ↔ Docs ↔ Skills |
| `indexing-pipeline` | PDF индексация pipeline |
| `search-pipeline-debug` | 16 стратегий поиска, debug |
| `evaluation-benchmark` | RAGAS, AutoRAG, метрики |
| `embedding-models` | E5/Giga/BGE-M3, backends |
| `qdrant-operations` | Named vectors, sparse, migration |
| `prompt-engineering` | DSPy, MIPROv2 |
| `deployment` | Docker, health checks, monitoring |
| `agent-orchestration` | 6 типов RAG-агентов |
| `graph-operations` | LightRAG, GraphRAG, entity extraction |

#### LangChain / LangGraph (10)

| Skill | Назначение |
|-------|-----------|
| `langchain-core` | Агенты, @tool, модели, middleware, structured output |
| `langchain-integrations` | Vector stores, embeddings, loaders, retrievers |
| `langchain-multiagent` | Субагенты, handoffs, router, skills pattern |
| `langchain-streaming` | 5 режимов стриминга, SSE, useStream |
| `langchain-mcp-tools` | MCP в LangChain, MultiServerMCPClient |
| `langchain-tutorials` | RAG/SQL/Voice Agent туториалы |
| `langgraph-core` | StateGraph, functional API, Command, Send |
| `langgraph-memory-persistence` | Checkpointers, Store, long-term memory |
| `langgraph-production` | LangSmith, Studio, deploy, тестирование |
| `deep-agents` | Autonomous agents CLI, backends, middleware |

#### Claude Code (9 + 1)

| Skill | Назначение |
|-------|-----------|
| `claude-code-settings` | settings.json scopes, .env, CLAUDE.md |
| `claude-code-cli-interactive` | CLI reference, hotkeys, Vim mode, checkpoints |
| `claude-code-subagents` | Подагенты, YAML config, built-in agents |
| `claude-code-plugins` | Плагины, manifest, marketplace |
| `claude-code-github-actions` | CI/CD, PR automation, @claude trigger |
| `claude-code-programmatic` | Headless mode, Agent SDK, Ralph Wiggum |
| `claude-code-admin` | Monitoring, security, IAM, costs |
| `claude-code-vscode` | VS Code extension, shortcuts, MCP |
| `claude-code-terminal-ux` | Chrome, statusline, terminal setup |

#### 1С разработка (9)

| Skill | Назначение |
|-------|-----------|
| `analyze-1c-task-v2` | 5-фазный анализ задачи 1С (требования → объекты → алгоритм → план → верификация), SDD delta-specs. **v4.2.0 (2026-05-11)**: опциональная **Фаза 2.5 Runtime Trace** между «Объекты» и «Алгоритм» — live BP-trace через `1c-debug-hmr` для алгоритмов с ≥3 ветвлений по runtime-данным. Триггер: флаг `--trace` или self-decision. Output: секция «3.Y Runtime Trace» в ANALYSIS-REPORT с Discrepancies (static vs runtime). Roadmap: [260510](../../../docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) Phase 2 |
| `analyze-1c-research` | 3-агентный анализ (Executor + Reviewer + Comparator) с итеративным скорингом |
| `implement-1c-task` | 8-этапная реализация задачи: EDT-MCP + 1c-mcp-crud + bsl-debug-server + **1c-debug-hmr** (BP-verification). v2.7.0 (2026-05-11): Этап 0 `debug_health_check`, Этап 5.x Live BP-verification (8-шаговый протокол для каждой `[MODIFIED]` точки), Этап 5.y `debug_session_diff` regression, footer `<!-- debug_session_id: <UUID> -->`. Режимы: Full / **Full (no-BP)** / Code-only / Read-only verify / Read-only research. Roadmap: [260510](../../../docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) Phase 1 |
| `bsl-development` | Разработка BSL: процедуры, обработка проведения, модули, 3 стратегии reasoner |
| `1c-mcp-crud` | MCP доступ к живой базе 1С: execute_query, execute_code, get_metadata, event_log |
| `1c-debug-hmr` | MCP отладка BSL с HMR: **25 tools** (BP/stack/locals/eval/step/coverage/replay/exception_bp + warm-pool arming), persistent RDBG session через `.active.json`, unified `ping()` dispatch. **Шаблон 6 (2026-05-12):** JOB-based BP-verification через `гкс_ОтладкаВыполненияКода.ВыполнитьКод` закрывает RC2 warm-pool gap (HTTP IIS rphost невидим → JOB rphost свежий, auto-attach). 213+ tests passed |
| `va-bdd-testing` | VA BDD тестирование: калиброванные step-паттерны, Stage 4a pre-scenario TestDB check, post-verification |
| `auto-test-after-write` | Автопроверка BSL после Write через MCP (syntax + тесты) |
| `brownfield-validate` | Валидация реализации vs OpenSpec (Gap/Design/Impl валидаторы) |
| `activate-project` | Активация 1С-проекта в Serena с проверкой и индексацией |

Команды: `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests`.
Pipeline: анализ задачи → реализация кода → написание тестов → цепочный прогон тестов (секции с resume, переиспользование артефактов, `.run-state.json`).

### Skill Router — МАРШРУТИЗАЦИЯ

Config-driven маршрутизация промптов к скиллам через `skill-router-config.json`:

```
Промпт пользователя
  → skill-router.py (UserPromptSubmit)
    → _detect_skill_activations(): парсит <command-name> теги из предыдущего turn
      → если найден → SessionState.add_activated_skill() + log activate (source=prompt-detection)
    → Layer A: keyword matching по 32 bundles (config v7, weighted_keywords)
    → Layer B: fuzzy matching (fuzz.partial_ratio)
    → Layer C: TF-IDF semantic scoring (shared/tfidf_scorer.py, numpy-only)
      → генерирует prompt_id, пишет в SessionState.set_prompt_id() + skill-accuracy.jsonl (recommend)
        → systemMessage: "загрузи skill X, optional Y"
          → Claude загружает через Skill tool
            → skill-usage-metrics.py логирует → data/skill-usage.log (если PostToolUse работает)
            → skill-usage-metrics.py читает get_prompt_id() → skill-accuracy.jsonl (activate)
          → СЛЕДУЮЩИЙ промпт содержит <command-name>skill</command-name>
            → skill-router._detect_skill_activations() → activate (source=prompt-detection)
```

32 bundles сгруппированы по 8 доменам: framework (9), claude-code (6), langchain (2), research (3), tools (5), 1c (4), memory (2), llm (1).

**Домены и bundles (v6)**:
| Домен | Bundles |
|-------|---------|
| 1c | research-1c, bsl-dev, bsl-debug, 1c-mcp-data |
| framework | search, indexing, eval-benchmark, graph, agents, data-stores, deploy, framework-use, framework-ops |
| claude-code | claude-code-dev, claude-code-config, claude-code-ops, hooks, creation, docs |
| langchain | langchain-core, langchain-infra |
| research | research-tech, architecture, workflow |
| memory | memory, bsl-memory |
| llm | llm-rotation |
| tools | git-parsing, tenacity-retry, code-verify, learning-loop, task-protocol |

### Skill Accuracy — PER-PROMPT КОРРЕЛЯЦИЯ

Непрерывный pipeline для измерения точности рекомендаций. Два источника активаций:

```
skill-router.py          skill-usage-metrics.py     skill-router.py
  (recommend)              (activate via PostToolUse)  (activate via prompt-detection)
       │                            │                        │
       └──── skill-accuracy.jsonl ──┴────────────────────────┘
                prompt_id связывает:
                recommended=[X,Y] → activated=[X] → MATCH
                recommended=[X,Y] → activated=[]  → MISS
```

**Источники активаций**:
1. **PostToolUse:Skill** (`skill-usage-metrics.py`) — прямой, но ненадёжный (баг #6305)
2. **Prompt-detection** (`skill-router.py:_detect_skill_activations`) — workaround: при загрузке скилла через `Skill()` его содержимое попадает в следующий prompt как `<command-name>skill-name</command-name>` тег. `skill-router.py` парсит эти маркеры и логирует активацию с `source=prompt-detection`

- **Лог**: `data/skill-accuracy.jsonl` (JSONL, append-only)
- **Формат**: `{ts, type:"recommend"|"activate", prompt_id, skills/skill, prompt, source?}`
- **source**: `"prompt-detection"` (Level 1 workaround) или отсутствует (Level 2 PostToolUse)
- **Корреляция**: prompt_id = md5(timestamp + prompt[:80])[:8]
- **Shared state**: `SessionState.set_prompt_id()` / `SessionState.get_prompt_id()` связывает recommend → activate
- **Dedup (activations)**: `SessionState.get_already_activated()` предотвращает двойной счёт
- **Dedup (recommendations)**: `SessionState.record_recommendation()` / `get_already_recommended()` — skill-router не рекомендует один скилл дважды за сессию
- **Dashboard**: `python scripts/hook-dashboard.py --section accuracy`
- **Метрики**: match rate, per-skill precision, recent misses
- **SQLite**: таблицы `skill_activations` и `skill_accuracy` в `hook_metrics_db.py` (колонка `source TEXT`)
- **Auto-migration**: `_migrate()` добавляет `source` колонку при первом запуске на старой схеме
- **HookMetricsDB API**: `get_hook_metrics()` (incl. p95_ms), `get_skill_metrics()` (incl. `by_source`, per-skill `sources`), `get_accuracy_metrics()`, `get_enforcement_metrics()`, `get_error_log()`
- **HTML Dashboard** (`/metrics/html`): карточки Prompt Detection / PostToolUse + колонка Source с цветными тегами в таблице скиллов
- **CLI Dashboard** (`scripts/hook-dashboard.py`): `--section skills` показывает `Source` колонку (prompt-detection:N post-tool-use:N), summary показывает `via <source>: N`
- **Streamlit Dashboard** (`src/ui/pages/hook_dashboard.py`): Tab 2 "Skill Activations" — метрики-карточки по source + колонка Source в таблице

### MCP Server (1 сервер, 14 инструментов) — ЧЕМ

| Инструмент | Назначение |
|-----------|-----------|
| `index_pdf` | Индексация PDF в vector + graph store |
| `search_documents` | Семантический поиск (vector/graph/hybrid/bm25) |
| `ask_question` | RAG-ответ с цитированием |
| `graph_query` | Запрос к графу знаний |
| `analyze` | Аналитический RAG (multi-round evidence) |
| `research` | Deep research с верификацией |
| `web_search` | Поиск в интернете (Tavily/SerpAPI/DuckDuckGo) |
| `search_with_fallback` | Локальный + веб с fusion |
| `visual_search` | Поиск по визуальным страницам (таблицы, диаграммы) |
| `visual_hybrid_search` | Гибридный visual + text (RRF fusion) |
| `list_collections` | Список коллекций |
| `list_documents` | Список документов |
| `get_toc` | Оглавление документа |
| `get_stats` | Статистика индекса |

---

## Рабочие pipeline (как триада работает)

### Pipeline 1: 1С Research

```
ПОЛЬЗОВАТЕЛЬ: "что такое справочники в 1С?"
     │
     ▼
[КОГДА] research-task-detector.py (UserPromptSubmit)
     │  Keyword scoring: "что такое" + "справочники" + "1С" → strong signal
     │  → systemMessage: "используй 1c-doc-research"
     ▼
[КАК] Skill: 1c-doc-research
     │  Фаза 0: проверка кеша (_index.json)
     │  Фаза 1: POST /search/ask ─────────── [ЧЕМ] MCP: pdf-vector-graph
     │  Фаза 2: WebSearch (its.1c.ru, infostart.ru)
     │  Фаза 3: верификация + терминология
     │  Фаза 4: атрибуция каждого факта
     ▼
[КОГДА] knowledge-cache-reminder.py (PostToolUse:WebSearch)
     │  Результаты содержат 1С-термины → score >= 2
     │  → add_task("Сохранить в кеш") в hook-todos.json
     │  → systemMessage: "Фаза 5: сохрани в кеш"
     ▼
[КАК] Skill: 1c-doc-research (Фаза 5)
     │  → cache/<справочники>.md по шаблону (8 категорий)
     │  → _index.json обновлён
     ▼
ОТВЕТ ПОЛЬЗОВАТЕЛЮ с атрибуцией
```

### Pipeline 2: Tech Research

```
ПОЛЬЗОВАТЕЛЬ: "как работает ColBERT reranking?"
     │
     ▼
[КОГДА] research-task-detector.py (UserPromptSubmit)
     │  Keyword scoring: "как работает" + "colbert" + "reranking" → tech signal
     │  → systemMessage: "используй tech-research"
     ▼
[КАК] Skill: tech-research
     │  Фаза 0: проверка кеша (tech-research/cache/_index.json)
     │  Фаза 1: WebSearch official docs (sbert.net, GitHub)
     │  Фаза 2: WebSearch papers (arxiv), benchmarks
     │  Фаза 3: верификация + наш опыт (MEMORY.md)
     │  Фаза 4: атрибуция каждого факта
     ▼
[КОГДА] knowledge-cache-reminder.py (PostToolUse:WebSearch)
     │  Результаты содержат tech-термины → score >= 2
     │  → add_task("Сохранить в кеш (Tech)") в hook-todos.json
     │  → systemMessage: "Фаза 5: сохрани в tech-research/cache/"
     ▼
[КАК] Skill: tech-research (Фаза 5)
     │  → cache/<colbert-reranking>.md по шаблону (7 категорий)
     │  → _index.json обновлён
     ▼
ОТВЕТ ПОЛЬЗОВАТЕЛЮ с атрибуцией
```

### Pipeline 3: Decision → Artifact (мета-цикл)

```
ПОЛЬЗОВАТЕЛЬ: "давай создадим новый домен для DevOps"
     │
     ▼
[КОГДА] decision-to-triad.py (UserPromptSubmit)          ← ВХОД
     │  Keyword scoring: "давай создадим" + "новый домен" → strong signal
     │  → systemMessage: "Прогони через ФАБРИКУ ТРИАДЫ (skill triad-factory)"
     ▼
[КАК] Skill: triad-factory (Фабрика, ШАГ 1-3)
     │  Q1=Да → Hook   Q2=Да → Skill   Q3=Да → MCP
     │  Q4=Да → Cache  Q5=Да → Enforcer
     │  ФОРМУЛА: Hook + Skill + MCP + Cache + Enforcer
     ▼
[ЧЕМ] Claude создаёт артефакты (Write):
     │  skills/devops-research/SKILL.md
     │  hooks/devops-detector.py
     ▼
[КОГДА] factory-enforcer.py (PostToolUse:Write)           ← СЕРЕДИНА
     │  Обнаружена запись в .claude/hooks/ или .claude/skills/
     │  → add_task("ШАГ 4: Зарегистрировать") в hook-todos.json
     │  → add_task("ШАГ 5: Верифицировать") в hook-todos.json
     │  → systemMessage: "Выполни ШАГ 4 + ШАГ 5"
     ▼
[КАК] Claude выполняет ШАГ 4-5:
     │  settings.json, MEMORY.md, triad SKILL.md обновлены
     │  echo '{"prompt":"..."}' | python hook.py → тест
     ▼
[КОГДА] task-enforcer.py (Stop)                           ← ВЫХОД
     │  Проверка hook-todos.json: pending tasks?
     │  → Есть → exit(2) BLOCK
     │  → Нет  → exit(0) ALLOW
     ▼
ОТВЕТ ПОЛЬЗОВАТЕЛЮ
```

### Pipeline 4: Stop Enforcement

```
knowledge-cache-reminder ──[add_task()]──→ hook-todos.json
                                               │
                                          [read on Stop]
                                               │
                                               ▼
                                        task-enforcer.py
                                          │         │
                                    pending?     no pending
                                          │         │
                                    exit(2)      exit(0)
                                    BLOCK        ALLOW
```

---

## Инфраструктура

### Файловая структура

```
.claude/
├── hooks/                         (17 хуков)
│   ├── base/
│   │   ├── __init__.py            (BaseHook, HookInput, HookOutput)
│   │   ├── protocol.py            (протокол stdin/stdout JSON — РАБОЧАЯ база для всех хуков)
│   │   └── base.py                (альт. dataclass-версия с auto-detect event)
│   ├── shared/
│   │   ├── session_state.py       (SessionState: activated/recommended skills dedup, prompt_id, pending_learn)
│   │   ├── task_master.py         (задачи: add, complete, pending, cooldown, session_id tracking)
│   │   ├── tfidf_scorer.py        (TF-IDF scoring: pure numpy, utterance-based corpus, Layer C)
│   │   └── hook_lock.py           (межхуковая синхронизация)
│   ├── skill-router.py            (Submit: Layer A+B+C → skill bundles)
│   ├── research-task-detector.py  (Submit: ВОПРОСЫ → skill routing)
│   ├── decision-to-triad.py      (Submit: РЕШЕНИЯ → triad-factory)
│   ├── ralph_activator.py         (Submit: активация Ralph)
│   ├── document-persistence.py    (Submit: roadmap/plan → docs/)
│   ├── root-clutter-guard.py      (PreTool: блокировка мусора в корне)
│   ├── search-optimizer.py        (PreTool: параметры Search API)
│   ├── knowledge-cache-reminder.py (PostTool: кеш знаний)
│   ├── factory-enforcer.py        (PostTool: ШАГ 4-5 Фабрики)
│   ├── docs-change-tracker.py     (PostTool: код → обнови доки)
│   ├── auto-git-save.py           (PostTool: mandatory commit)
│   ├── skill-usage-metrics.py     (PostTool: логирование скиллов)
│   ├── bulk-action-guard.py       (PostTool: защита от bulk ops)
│   ├── task-enforcer.py           (Stop: mandatory tasks)
│   ├── git-commit-enforcer.py     (Stop: блокировка без коммита)
│   ├── docs-change-enforcer.py    (Stop: код изменён без обновления доков)
│   └── ralph_wiggum_stop.py       (Stop: контроль Ralph)
├── skills/                        (47 скиллов)
│   ├── skill-router-config.json   (25 bundles, v6 → keyword + fuzzy + TF-IDF routing)
│   ├── 1c-doc-research/           (+ cache/ — 8 категорий)
│   ├── tech-research/             (+ cache/ — 7 категорий)
│   ├── architecture-research/     (+ cache/ + adr/)
│   ├── langchain-core/            (LangChain ядро)
│   ├── langgraph-core/            (LangGraph ядро)
│   ├── ...                        (ещё 41 скилл)
│   └── hooks-skills-mcp-triad/    (ЗНАНИЕ: этот файл)
├── cache/
│   └── hook-todos.json            (задачи от хуков)
├── settings.json                  (регистрация хуков)
└── commands/
    └── pdf-search.md
```

### Коммуникация между хуками

Хуки общаются через `hook-todos.json`:
- **knowledge-cache-reminder** создаёт задачу (кеш) → **task-enforcer** блокирует stop
- **factory-enforcer** создаёт задачу (ШАГ 4-5) → **task-enforcer** блокирует stop
- **auto-git-save** создаёт задачу (коммит) → **git-commit-enforcer** блокирует stop
- **docs-change-tracker** создаёт задачу (обнови доки) → **task-enforcer** блокирует stop
- **docs-change-enforcer** (Stop) проверяет инфра-файлы (.claude/hooks/*.py, settings.json, settings.local.json) → требует обновить CLAUDE.md
- **skill-usage-metrics** логирует → `data/skill-usage.log` (не через todos)
- **skill-router** читает `skill-router-config.json` → systemMessage с рекомендациями
- **skill-router** + **skill-usage-metrics** пишут в `data/skill-accuracy.jsonl` (через shared prompt_id)
- Файл защищён file lock (Windows msvcrt / Unix fcntl)
- Atomic writes предотвращают corruption

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `except: pass` без logging | Скрывает ошибки | `BaseHook.run()` уже обрабатывает — не нужно дополнительно |
| Hook вызывает тот же инструмент | Зацикливание (PreToolUse:Read → Read) | Использовать альтернативный инструмент |
| Блокировка без причины | Claude не понимает что делать | Всегда указывать `reason` в `block()` |
| Относительные пути в settings.json | Не находит python.exe | Абсолютные: `D:\\1С-Framework\\.venv\\Scripts\\python.exe` |
| Тяжёлые вычисления в хуке | Timeout (3-5s) | Хуки должны быть лёгкими (keyword matching, file read) |
