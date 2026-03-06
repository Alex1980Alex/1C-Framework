# Сравнение технологий: Миграция vs Текущий фреймворк + Лучшие решения GitHub

**Дата:** 2026-03-06
**Цель:** Для каждой фазы миграции (44-55) сравнить внедряемые технологии с уже реализованными в PDF Vector & Graph Framework, выявить улучшения и лучшие open-source альтернативы.

---

## Навигация

- [Фаза 44: Infrastructure](#фаза-44-infrastructure)
- [Фаза 45: BSL Semantic Search](#фаза-45-bsl-semantic-search)
- [Фаза 46: MCP 1C Integration](#фаза-46-mcp-1c-integration)
- [Фаза 47: Auto-Documenter](#фаза-47-auto-documenter)
- [Фаза 48: BSL Debugger](#фаза-48-bsl-debugger)
- [Фаза 49: Unified Memory](#фаза-49-unified-memory)
- [Фаза 50: LLM Rotation](#фаза-50-llm-rotation)
- [Фаза 51: Task Pipeline](#фаза-51-task-pipeline)
- [Фаза 52: Serena LSP](#фаза-52-serena-lsp)
- [Фаза 53: BSL Fine-tuning](#фаза-53-bsl-finetuning)
- [Фаза 54: Infrastructure Tools](#фаза-54-infrastructure-tools)
- [Фаза 55: Integration & Cleanup](#фаза-55-integration--cleanup)
- [Сводная матрица улучшений](#сводная-матрица-улучшений)
- [ТОП-10 GitHub решений](#топ-10-github-решений-для-интеграции)

---

## Фаза 44: Infrastructure

### Что внедряется
- MCP профили (pdf.json, bsl.json, full.json, lazy-mcp.json)
- Launcher скрипт `scripts/claude.bat` с выбором профиля
- Hook `bsl-tool-router.py` для BSL-запросов
- Skill `bsl-development/SKILL.md`
- Структура директорий `src/bsl/`, `src/memory/`, `src/shared/`

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| MCP конфиг | `.mcp.json` (1 сервер, 12 tools) | 4 профиля (pdf/bsl/full/lazy) | **+4 профиля**, модульность |
| Launcher | Нет (ручной запуск) | `claude.bat` с 7 профилями | **Новый** — автоматизация запуска |
| Hooks | 13 хуков (protocol, router, git, verify) | +1 `bsl-tool-router.py` | Расширение существующей инфраструктуры |
| Skills | 57+ скиллов | +6 BSL скиллов | Расширение skill-router-config.json |
| Структура | `src/pdf_framework/` (единый пакет) | +`src/bsl/`, `src/memory/`, `src/shared/` | Параллельные пакеты |

### Улучшения

1. **Профильная система MCP** — текущий фреймворк имеет один `.mcp.json`. Миграция приносит модульные профили. Это решает проблему контекстного раздувания (issue #7336).
2. **Launcher** — автоматизирует выбор конфигурации, чего нет сейчас.
3. **Рекомендация:** Вместо самописного lazy-mcp использовать [voicetreelab/lazy-mcp](https://github.com/voicetreelab/lazy-mcp) (Go, 2 meta-tools, 95% экономия контекста) или [MetaMCP](https://github.com/metatool-ai/metamcp) (~2K stars, веб-UI для управления серверами).

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [metatool-ai/metamcp](https://github.com/metatool-ai/metamcp) | ~2,000 | Агрегатор + оркестратор MCP серверов с веб-UI |
| [TBXark/mcp-proxy](https://github.com/TBXark/mcp-proxy) | ~585 | Go-прокси, агрегация stdio/SSE/HTTP серверов |
| [docker/mcp-gateway](https://github.com/docker/mcp-gateway) | ~1,300 | Контейнерная изоляция MCP серверов, управление секретами |

---

## Фаза 45: BSL Semantic Search

### Что внедряется
- Qdrant коллекция `bsl_code_v2` (768d, nomic-embed-text)
- 3,908 BSL модулей проиндексировано
- FastMCP сервер для BSL поиска
- Hybrid search (dense + sparse BM25)
- Embedding cache (JSON файлы)

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый BSL | Дельта |
|-----------|-------------------|-----------------|--------|
| Vector Store | Qdrant (1024d, E5 multilingual) | Qdrant (768d, nomic-embed-text) | **Разные коллекции**, разные модели |
| Hybrid Search | Qdrant native RRF (dense+BM25 sparse) | Отдельная реализация hybrid | Фреймворк **зрелее** — 15 стратегий |
| BM25 | FTS5 SQLite + Qdrant sparse | Qdrant sparse BM25 | Фреймворк имеет **оба** бэкенда |
| Embedding Cache | SQLite (aiosqlite, SHA-256 ключ, TTL 30d) | JSON файлы в `cache/embeddings/` | Фреймворк **лучше** — async, TTL, stats |
| Reranking | LLM (Claude), ColBERT, CrossEncoder, FlashRank | Нет | Фреймворк **значительно лучше** |
| MMR | Есть (Phase 2.1) | Нет | Фреймворк **лучше** |
| Section-Aware | Two-pass section-first pipeline | Нет | Фреймворк **лучше** |
| MCP Server | FastMCP (12 tools) | FastMCP (BSL search) | Дополняют друг друга |

### Улучшения

1. **Унификация Embedding Cache** — BSL использует JSON-файлы, фреймворк — SQLite. При миграции переключить BSL на существующий `sqlite_cache.py` с TTL и hit-rate метриками.
2. **Добавить reranking к BSL поиску** — подключить существующий LLM Reranker (Phase 25) к BSL результатам.
3. **Добавить MMR к BSL** — diversity search уже реализован для PDF, легко подключить к BSL коллекции.
4. **Рассмотреть E5 вместо nomic** — E5 multilingual (1024d) уже в production, показывает recall@10=0.9933. nomic (768d) может быть слабее.
5. **Рекомендация:** Использовать [SeaGOAT](https://github.com/kantord/SeaGOAT) (~1.2K stars) как референс для hybrid code search (vector + regex).

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [kantord/SeaGOAT](https://github.com/kantord/SeaGOAT) | ~1,200 | Hybrid code search (vector + ripgrep), 100% локальный |
| [NirDiamant/RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques) | ~24,500 | Cookbook всех RAG-техник (fusion, adaptive, contextual) |
| [jina-ai/late-chunking](https://github.com/jina-ai/late-chunking) | ~480 | Контекстуальный chunking, +10-12% retrieval accuracy |

---

## Фаза 46: MCP 1C Integration

### Что внедряется
- MCP framework для 1C (Python + Java JAR)
- bsl-platform-context сервер
- HTTP Service + COM-коннектор
- 8 инструментов (metadata, platform docs, module context и др.)

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| MCP Server | Python (FastMCP), 12 tools | Python + Java JAR | Новый тип: **Java компонент** |
| Platform Integration | Нет (только PDF/документы) | COM, HTTP Service к 1C | **Полностью новый** |
| Metadata Access | Нет | 1C metadata exploration | **Полностью новый** |

### Улучшения

1. **Использовать EDT-MCP** — [DitriXNew/EDT-MCP](https://github.com/DitriXNew/EDT-MCP) (~95 stars) — самый зрелый MCP для 1C, работает как плагин EDT. Глубокий анализ BSL (call hierarchy, content assist). Может дополнить или заменить самописный bsl-platform-context.
2. **Интеграция с bsl-language-server** — [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) (~388 stars, v0.28.5) — 100+ диагностик, SonarQube интеграция. Уже Java-based — совместим с JAR-подходом.
3. **Рекомендация:** Обернуть bsl-language-server как MCP tool вместо написания своего анализатора. 100+ готовых диагностик > самописные проверки.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [DitriXNew/EDT-MCP](https://github.com/DitriXNew/EDT-MCP) | ~95 | MCP в 1C:EDT — BSL анализ, call hierarchy |
| [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) | ~388 | LSP для BSL, 100+ диагностик, SonarQube |
| [artesk/1C_MCP_metadata](https://github.com/artesk/1C_MCP_metadata) | low | MCP для metadata 1C конфигурации |

---

## Фаза 47: Auto-Documenter

### Что внедряется
- Node.js MCP сервер (5 tools)
- Tree-sitter-bsl (WASM grammar)
- 11 типов BSL модулей, 25+ типов метаданных
- 5 AI-провайдеров с ротацией (Gemini/Groq/Ollama/Grok/OpenRouter)
- Call graph analysis

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Документация кода | Нет автогенерации | Tree-sitter + LLM | **Полностью новый** |
| AST Parsing | Нет (text-based processing) | Tree-sitter WASM | **Новый** — AST-level |
| AI Providers | 1 (Claude через Z.AI) | 5 (Gemini/Groq/Ollama/Grok/OR) | **Значительно больше** |
| Call Graph | Entity extraction (NER) | BSL call graph (AST-based) | Разные подходы |
| Runtime | Python only | Node.js (TypeScript) | **Новый runtime** |

### Улучшения

1. **Заменить 5 кастомных провайдеров на LiteLLM** — вместо ручной ротации Gemini/Groq/Ollama использовать [LiteLLM](https://github.com/BerriAI/litellm) (~38K stars) — единый API для 100+ провайдеров, встроенный retry/fallback, cost tracking.
2. **Использовать Repomix для контекста** — [yamadashy/repomix](https://github.com/yamadashy/repomix) — tree-sitter compression (~70% token reduction), MCP server mode. Может подготовить контекст для auto-documenter более эффективно.
3. **Рассмотреть RepoAgent** — [OpenBMB/RepoAgent](https://github.com/OpenBMB/RepoAgent) (~900 stars) — AST-based, auto-detects git changes, поддержка Qwen/Llama. Может дополнить или заменить auto-documenter для Python-части фреймворка.
4. **Tree-sitter BSL** — нет standalone репозитория. Использовать [tree-sitter-language-pack](https://github.com/Goldziher/tree-sitter-language-pack) (100+ языков, включая BSL) или ANTLR4-based парсер из 1c-syntax.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [yamadashy/repomix](https://github.com/yamadashy/repomix) | high | Tree-sitter codebase compression, MCP mode |
| [OpenBMB/RepoAgent](https://github.com/OpenBMB/RepoAgent) | ~900 | AST-based auto-docs, git change detection, local LLMs |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | ~38,000 | Заменить 5 провайдеров одним unified API |

---

## Фаза 48: BSL Debugger

### Что внедряется
- Собственный BSL Lexer (450 LOC), Parser (890 LOC), Engine (950 LOC)
- 10 debug tools (analyze, start, breakpoints, step, variables и др.)
- TypeScript/Node.js, MCP server
- Runtime simulation через OneScript

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Debugging | Нет | Полный BSL debugger | **Полностью новый** |
| Code Analysis | Entity extraction (NER) | AST-based (Lexer+Parser) | BSL debugger **глубже** для кода |
| MCP Tools | 12 (PDF-centric) | +10 (debug-centric) | Значительное расширение |

### Улучшения

1. **Рассмотреть DebugMCP от Microsoft** — [microsoft/DebugMCP](https://github.com/microsoft/DebugMCP) — zero-config VS Code MCP debugger, multi-language. Для Python-части фреймворка может быть полезнее собственного BSL debugger.
2. **Использовать DAP-based подход** — [debugmcp/mcp-debugger](https://github.com/debugmcp/mcp-debugger) (~1K stars) — Debug Adapter Protocol, 1019 тестов, Python/JS/Go/Rust. Более maintainable чем собственный Lexer/Parser (1390 LOC кастомного кода).
3. **BSL Debugger остаётся уникальным** — ни один GitHub-проект не предоставляет BSL debugging через MCP. Собственная реализация необходима для 1C-специфичного отладки.
4. **Рекомендация:** Оставить BSL debugger как есть (уникальный), но добавить [microsoft/DebugMCP](https://github.com/microsoft/DebugMCP) для отладки Python/TS кода самого фреймворка.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [microsoft/DebugMCP](https://github.com/microsoft/DebugMCP) | new (MS) | VS Code MCP debugger, multi-language |
| [debugmcp/mcp-debugger](https://github.com/debugmcp/mcp-debugger) | ~1,000 | DAP-based, Python/JS/Go/Rust, 1019 тестов |
| [FloridSleeves/LLMDebugger](https://github.com/FloridSleeves/LLMDebugger) | research | Block-level variable tracking, 98.2% accuracy |

---

## Фаза 49: Unified Memory

### Что внедряется
- 4 системы памяти: Memory Orchestrator, AI Memory, Vector Memory, Skill Learning
- UnifiedID: `{memory_type}:{source}:{identifier}`
- LinkRegistry (SQLite, BFS traversal)
- Federated Search (P50<200ms, P95<500ms)
- TimescaleDB + Qdrant + Neo4j для AI Memory

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Memory | Session state (JSON), MEMORY.md | 4 системы (orchestrator + 3 stores) | **Значительно сложнее** |
| Conversation | SQLite backend (Phase 9) | TimescaleDB (time-series) | Мигрируемый **мощнее** |
| Vector Search | Qdrant (1024d, PDF) | Qdrant (768d, memory) | **Доп. коллекции** |
| Graph | Neo4j (3166 entities, documents) | Neo4j (memory links) | **Расширение** существующего |
| Link Registry | Нет | SQLite, BFS, cross-refs | **Новый** |
| Federated Search | SearchManager (15 стратегий) | UnifiedSearchEngine (4 системы) | Разные scope'ы |
| Knowledge Base | CollectionStore (Phase 32) | AI Memory (episodic/semantic) | Мигрируемый **богаче** |
| Feedback Loop | FeedbackCollector + Few-Shot (Phase 22) | Skill Learning MCP | Дополняют друг друга |

### Улучшения

1. **КРИТИЧНО: Рассмотреть Mem0** — [mem0ai/mem0](https://github.com/mem0ai/mem0) (~41K stars, Apache 2.0) — hybrid datastore (graph + vector + KV), поддерживает Qdrant как бэкенд, MCP-ready. Может **заменить** все 4 кастомных системы памяти одной зрелой библиотекой. $24M инвестиций, 14M+ загрузок, интеграции с CrewAI/Langflow.
2. **OpenMemory для self-hosted** — [CaviraOSS/OpenMemory](https://github.com/CaviraOSS/OpenMemory) (~3.5K stars) — нативный MCP сервер, temporal graph с decay, zero-config. Меньше features чем Mem0, но полностью self-hosted.
3. **Переиспользовать существующий Qdrant** — не создавать отдельные коллекции `ai_memory` и `learned_patterns`. Использовать `payload`-based фильтрацию в существующих коллекциях (как multi-tenancy в Phase 23).
4. **Унифицировать Neo4j** — текущий граф (3166 entities) и memory graph должны жить в одном Neo4j instance с namespace-разделением.
5. **Рекомендация:** Использовать Mem0 как primary memory layer, сохранив UnifiedID как адаптер поверх.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | ~41,000 | Полная замена 4 систем памяти, Qdrant-совместим |
| [CaviraOSS/OpenMemory](https://github.com/CaviraOSS/OpenMemory) | ~3,500 | Self-hosted, MCP-native, temporal graph |
| [MemTensor/MemOS](https://github.com/MemTensor/MemOS) | growing | Memory OS: textual + activation + parametric, +43.7% accuracy |

---

## Фаза 50: LLM Rotation

### Что внедряется
- 5 провайдеров: Mistral -> OpenRouter -> Gemini -> Ollama Cloud -> Ollama Local
- ProviderStatus: HEALTHY/DEGRADED/UNAVAILABLE/COOLDOWN
- Auto-fallback на 429/402/503/timeout
- Daily limit tracking
- Health monitoring (avg response time)

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| LLM Provider | Claude (Anthropic) через Z.AI proxy | 5 провайдеров с ротацией | **Значительно больше** |
| Fallback | Нет (single provider) | Auto-fallback цепочка | **Новый** |
| Cost Tracking | CostTracker (Phase 40) | Daily limit tracking | Фреймворк **лучше** (детальнее) |
| Health Monitor | Нет | ProviderState + cooldown | **Новый** |
| Rate Limiting | API rate_limit middleware | Provider-level rate limits | Разные уровни |

### Улучшения

1. **КРИТИЧНО: Заменить на LiteLLM** — [BerriAI/litellm](https://github.com/BerriAI/litellm) (~38K stars, MIT) — 100+ провайдеров через unified OpenAI API. Proxy-mode (AI Gateway). Retry + fallback. Cost tracking + бюджеты. 8ms P95 latency. Заменяет И кастомную ротацию ИЗ миграции, И текущий Z.AI proxy.
2. **Альтернатива: TensorZero** — [tensorzero/tensorzero](https://github.com/tensorzero/tensorzero) (~11K stars) — Rust, <1ms p99 latency. A/B тестирование, evaluation, experimentation. Может заменить и LLM routing, и RAGAS evaluation.
3. **Альтернатива: Portkey** — [Portkey-AI/gateway](https://github.com/Portkey-AI/gateway) (~10.8K stars) — 1,600+ моделей, 50+ guardrails, 122KB footprint. MCP Gateway с auth.
4. **Интегрировать с существующим CostTracker** — LiteLLM имеет встроенный cost tracking, но существующий CostTracker (Phase 40) детальнее. Использовать LiteLLM для routing, CostTracker для аналитики.
5. **Рекомендация:** LiteLLM как единый gateway для ВСЕХ LLM-вызовов (и существующих Claude, и мигрируемых 5 провайдеров).

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | ~38,000 | Unified API для 100+ провайдеров, proxy mode |
| [tensorzero/tensorzero](https://github.com/tensorzero/tensorzero) | ~11,000 | Rust gateway, <1ms latency, A/B testing |
| [Portkey-AI/gateway](https://github.com/Portkey-AI/gateway) | ~10,800 | 1600+ моделей, 50+ guardrails, MCP Gateway |

---

## Фаза 51: Task Pipeline

### Что внедряется
- Claude Task Master (38 tools, npx)
- Development Pipeline (~3,000 LOC Python)
- LangGraph-based pipeline агенты (initializer, reviewer, QA)
- 100+ checkpoint файлов

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Task Protocol | Hooks-based (enforcer + observer) | Claude Task Master (38 tools) | **Конкурируют** |
| Task Decomposition | Manual (TaskCreate) | AI-декомпозиция | Мигрируемый **умнее** |
| Pipeline | Нет CI/CD pipeline | LangGraph agents | **Новый** |
| Checkpointing | LangGraph checkpoints (Phase 43) | 100+ checkpoint JSON | **Оба** используют checkpoints |
| Agent Infrastructure | 4 LangGraph agents (RAG, Research, Analytical, Multi) | 3 pipeline agents (init, review, QA) | Фреймворк **зрелее** |

### Улучшения

1. **Task Master — дополнение, не замена** — существующий Task Protocol (hooks) обеспечивает enforcement. Task Master добавляет AI-декомпозицию. Использовать вместе.
2. **Рассмотреть CCPM** — [automazeio/ccpm](https://github.com/automazeio/ccpm) (~7K stars) — GitHub Issues как task database + git worktrees для параллельных агентов. Может улучшить Ralph Wiggum pattern.
3. **Pipeline agents -> существующие LangGraph agents** — не дублировать инфраструктуру. Использовать существующий create_plan_execute_agent (Phase 36) для pipeline вместо отдельных LangGraph графов.
4. **Рекомендация:** Интегрировать Task Master через npx, pipeline agents адаптировать под существующую LangGraph инфраструктуру.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master) | ~24,900 | AI task management, 13+ IDE, npx |
| [automazeio/ccpm](https://github.com/automazeio/ccpm) | ~7,000 | GitHub Issues + worktrees, parallel agents |
| [SkyworkAI/DeepResearchAgent](https://github.com/SkyworkAI/DeepResearchAgent) | growing | Hierarchical multi-agent planning |

---

## Фаза 52: Serena LSP

### Что внедряется
- LSP-агент для 30+ языков
- Symbol-level code extraction
- BSL support через bsl_language_server.py
- MCP server implementation

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Code Intelligence | Entity extraction (NER, text-based) | LSP (symbol-level, AST-based) | Мигрируемый **значительно лучше** |
| Language Support | Нет | 30+ языков | **Полностью новый** |
| Go to Definition | Нет | LSP definitions/references | **Полностью новый** |
| MCP Integration | 12 tools (PDF-centric) | Serena MCP tools | Дополняют |

### Улучшения

1. **Копировать кастомную версию** — Serena в `1C-Enterprise_Framework` была **доработана под BSL/1C**: добавлен `bsl_language_server.py`, зарегистрирован Language ID `bsl`, настроены capabilities (symbols, definitions, references) для `.bsl` файлов. Upstream [oraios/serena](https://github.com/oraios/serena) (~21K stars) **не поддерживает BSL нативно** — использовать upstream нельзя без потери BSL-кастомизаций.
2. **Стратегия: fork + upstream merge** — скопировать кастомную версию, но отслеживать upstream (oraios/serena) для общих обновлений (новые языки, багфиксы). BSL-специфичный код поддерживать отдельно.
3. **Альтернатива для не-BSL кода: mcp-language-server** — [isaacphi/mcp-language-server](https://github.com/isaacphi/mcp-language-server) (~858 stars) — легковесный Go bridge LSP->MCP. Может работать параллельно с кастомной Serena для Python/TS файлов фреймворка.
4. **Рекомендация:** Копировать кастомную Serena с BSL-расширениями. Периодически мержить обновления из upstream oraios/serena. Рассмотреть PR BSL-поддержки в upstream.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [oraios/serena](https://github.com/oraios/serena) | ~21,000 | LSP agent, 30+ языков, MCP-native |
| [isaacphi/mcp-language-server](https://github.com/isaacphi/mcp-language-server) | ~858 | Go bridge LSP->MCP, любой LSP сервер |
| [SilasMarvin/lsp-ai](https://github.com/SilasMarvin/lsp-ai) | ~3,100 | Rust, AI-enhanced language server |

---

## Фаза 53: BSL Fine-tuning

### Что внедряется
- Fine-tuning Qwen2.5-Coder-7B на BSL-коде
- LoRA (r=16, alpha=16)
- 10,000 BSL примеров (~22 MB)
- GGUF quantization для Ollama
- Colab notebook для training

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| Fine-tuning | Нет | LoRA pipeline | **Полностью новый** |
| Local LLM | Нет (только API) | Ollama (GGUF) | **Новый** |
| BSL Dataset | Нет | 10K примеров | **Новый** |
| Training Infra | Нет | Colab T4 GPU | **Новый** |

### Улучшения

1. **Использовать Unsloth** — [unslothai/unsloth](https://github.com/unslothai/unsloth) (~53K stars) — 2x быстрее обучение, 70% меньше VRAM. Поддерживает Qwen. LoRA/QLoRA/full. Qwen3-30B на 17.5GB VRAM.
2. **Альтернатива: ms-swift** — [modelscope/ms-swift](https://github.com/modelscope/ms-swift) (~12.9K stars) — 600+ моделей, Alibaba-backed. Специализация на Qwen models.
3. **BSL Dataset — уникальная возможность** — ни один публичный dataset BSL/1C кода не существует. Создание и публикация такого dataset стало бы значительным вкладом в сообщество.
4. **Рекомендация:** Заменить кастомный training pipeline на Unsloth (стандарт индустрии, 53K stars).

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [unslothai/unsloth](https://github.com/unslothai/unsloth) | ~53,000 | 2x faster training, 70% less VRAM, Qwen support |
| [modelscope/ms-swift](https://github.com/modelscope/ms-swift) | ~12,900 | 600+ LLMs, Qwen specialization, Megatron |
| 1c-syntax repos | varied | Источник данных для BSL dataset |

---

## Фаза 54: Infrastructure Tools

### Что внедряется
- Lazy MCP proxy (Python, 3 meta-tools)
- Docker MCP Pilot (POC)
- AST Grep MCP (Python, 60s timeout)
- BSL Semantic Diff (Python)

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| MCP Proxy | Нет | Lazy MCP (3 meta-tools) | **Новый** |
| Docker | Docker для Qdrant | Docker orchestration | **Расширение** |
| AST Analysis | Нет (text-based grep) | AST-grep MCP | **Новый** |
| Code Diff | git diff (стандартный) | BSL Semantic Diff | **Новый** |
| Containerization | docker-compose (Qdrant only) | Multi-service compose | **Расширение** |

### Улучшения

1. **Lazy MCP — использовать upstream** — [voicetreelab/lazy-mcp](https://github.com/voicetreelab/lazy-mcp) (Go) лучше чем самописный Python-вариант: производительность Go, 2 meta-tools (vs 3 — проще), активно развивается.
2. **AST Grep — использовать официальный** — [ast-grep/ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp) (~351 stars) — 4 tools (dump_syntax_tree, test_match, find_code, find_by_rule). Лучше поддерживаемый чем форк.
3. **Docker MCP — Docker Gateway** — [docker/mcp-gateway](https://github.com/docker/mcp-gateway) (~1.3K stars) — официальный Docker проект, container isolation, secrets management. Заменяет POC Docker MCP Pilot.
4. **Рекомендация:** Для всех 4 компонентов использовать upstream/official versions вместо копирования старых форков.

### Лучшие решения GitHub

| Решение | Stars | Применение |
|---------|-------|------------|
| [voicetreelab/lazy-mcp](https://github.com/voicetreelab/lazy-mcp) | ~60 | Go proxy, 95% token reduction |
| [ast-grep/ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp) | ~351 | AST structural code search, 4 MCP tools |
| [docker/mcp-gateway](https://github.com/docker/mcp-gateway) | ~1,300 | Official Docker MCP, container isolation |

---

## Фаза 55: Integration & Cleanup

### Что внедряется
- E2E тесты (BSL workflow, cross-search)
- Performance benchmarks
- Documentation update
- Cleanup + git tag v0.34.0-bsl-migration

### Что уже есть в фреймворке

| Компонент | Текущий фреймворк | Мигрируемый | Дельта |
|-----------|-------------------|-------------|--------|
| E2E тесты | RAGAS eval, benchmark runner | BSL workflow E2E | **Расширение** тестов |
| Benchmarks | AutoRAG (Phase 20), eval dataset | Performance metrics (latency) | Дополняют |
| Documentation | CLAUDE.md, MEMORY.md, 57 skills | BSL секции в документации | **Расширение** |
| Linting | Нет enforcement | ruff + mypy (0 errors) | **Новый** enforcement |
| Audit | audit-docs skill | audit-docs + BSL | **Расширение** |

### Улучшения

1. **ruff + mypy для всего фреймворка** — если мигрируемый код требует 0 errors от ruff/mypy, применить тот же стандарт к существующему `src/pdf_framework/`.
2. **Unified benchmark** — объединить существующий AutoRAG benchmark с BSL performance metrics в единый dashboard.
3. **Рекомендация:** Фаза 55 — возможность поднять качество всего фреймворка, не только BSL.

---

## Сводная матрица улучшений

### По каждой фазе: что улучшить при миграции

| Фаза | Ключевое улучшение | Приоритет | Тип |
|------|-------------------|-----------|-----|
| 44 | MetaMCP/lazy-mcp вместо самописного proxy | HIGH | Замена |
| 45 | Переиспользовать SQLite embedding cache + добавить reranking к BSL | HIGH | Унификация |
| 46 | Обернуть bsl-language-server как MCP tool | MEDIUM | Интеграция |
| 47 | LiteLLM вместо 5 кастомных провайдеров | **CRITICAL** | Замена |
| 48 | Добавить microsoft/DebugMCP для Python/TS | LOW | Дополнение |
| 49 | Mem0 вместо 4 кастомных систем памяти | **CRITICAL** | Замена |
| 50 | LiteLLM вместо кастомной ротации | **CRITICAL** | Замена |
| 51 | Pipeline agents -> существующие LangGraph agents | HIGH | Унификация |
| 52 | Копировать BSL-кастомизированную Serena + отслеживать upstream | HIGH | Миграция + Merge |
| 53 | Unsloth вместо кастомного training pipeline | HIGH | Замена |
| 54 | Upstream versions для всех 4 компонентов | HIGH | Обновление |
| 55 | ruff/mypy для всего фреймворка | MEDIUM | Стандартизация |

### Пересечения технологий

```
Текущий фреймворк          Мигрируемый            Рекомендация
─────────────────          ────────────            ────────────
Qdrant (1024d, E5)    <->  Qdrant (768d, nomic)   Оставить обе коллекции
Neo4j (documents)     <->  Neo4j (memory links)   Один instance, namespaces
SQLite (cache, BM25)  <->  SQLite (LinkRegistry)  Унифицировать
Claude via Z.AI       <->  5 LLM провайдеров      LiteLLM для всех
LangGraph agents      <->  LangGraph pipeline     Общая инфраструктура
FastMCP (12 tools)    <->  FastMCP (BSL tools)     MCP профили
Hooks (13)            <->  Hooks (+3 BSL)          Расширение
Skills (57)           <->  Skills (+6 BSL)         Расширение
```

---

## ТОП-10 GitHub решений для интеграции

Ранжировано по impact на проект:

| # | Решение | Stars | Заменяет | Impact |
|---|---------|-------|----------|--------|
| 1 | [BerriAI/litellm](https://github.com/BerriAI/litellm) | ~38K | LLM Rotation (Phase 50) + Auto-Documenter providers (Phase 47) + Z.AI proxy | **CRITICAL** — унификация всех LLM-вызовов |
| 2 | [mem0ai/mem0](https://github.com/mem0ai/mem0) | ~41K | 4 системы памяти (Phase 49) | **CRITICAL** — замена 4 кастомных систем одной |
| 3 | [oraios/serena](https://github.com/oraios/serena) | ~21K | Upstream для BSL-кастомизированной Serena (Phase 52) | **HIGH** — мержить обновления в BSL-форк |
| 4 | [unslothai/unsloth](https://github.com/unslothai/unsloth) | ~53K | Кастомный training pipeline (Phase 53) | **HIGH** — стандарт индустрии |
| 5 | [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master) | ~25K | Task Pipeline (Phase 51) | **HIGH** — уже в roadmap |
| 6 | [NirDiamant/RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques) | ~24.5K | Референс для BSL RAG (Phase 45) | **MEDIUM** — cookbook новых техник |
| 7 | [metatool-ai/metamcp](https://github.com/metatool-ai/metamcp) | ~2K | Самописный lazy-mcp (Phase 54) | **MEDIUM** — MCP orchestration |
| 8 | [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) | ~388 | Кастомный BSL analysis (Phase 46) | **MEDIUM** — 100+ готовых диагностик |
| 9 | [docker/mcp-gateway](https://github.com/docker/mcp-gateway) | ~1.3K | Docker MCP Pilot (Phase 54) | **MEDIUM** — official Docker |
| 10 | [ast-grep/ast-grep-mcp](https://github.com/ast-grep/ast-grep-mcp) | ~351 | Форк ast-grep (Phase 54) | **LOW** — upstream version |

---

## Итоговые рекомендации

### 3 критических замены (экономят ~15 часов разработки)

1. **LiteLLM** заменяет кастомную LLM ротацию (Phase 50) И 5 провайдеров auto-documenter (Phase 47). Один `pip install litellm` вместо ~2000 LOC кастомного кода.

2. **Mem0** заменяет 4 системы памяти (Phase 49). Одна библиотека с Qdrant backend (уже используется) вместо Memory Orchestrator + AI Memory + Vector Memory + Skill Learning.

3. **Upstream versions** для ast-grep-mcp (Phase 54), lazy-mcp (Phase 54). Serena — копировать BSL-кастомизированную версию (содержит `bsl_language_server.py` и BSL-расширения, отсутствующие в upstream).

### 3 ключевых унификации (улучшают архитектуру)

1. **Embedding cache** — переключить BSL (JSON-файлы) на существующий SQLite cache с TTL и метриками.
2. **LangGraph agents** — pipeline agents (Phase 51) построить на существующей инфраструктуре (create_plan_execute_agent), не дублировать.
3. **Neo4j instance** — один instance с namespace-разделением для documents (текущий) и memory (мигрируемый).

### Пересмотр оценки трудоёмкости

С учётом замен на готовые решения:

| Фаза | Было | Стало | Экономия | За счёт чего |
|------|------|-------|----------|-------------|
| 49 | 8ч | 4ч | -4ч | Mem0 вместо 4 кастомных систем |
| 50 | 4ч | 2ч | -2ч | LiteLLM вместо кастомной ротации |
| 47 | 6ч | 4ч | -2ч | LiteLLM для провайдеров |
| 52 | 4ч | 3ч | -1ч | Копирование BSL-форка + venv (без переписывания) |
| 53 | 3ч | 2ч | -1ч | Unsloth вместо кастомного pipeline |
| 54 | 5ч | 3ч | -2ч | Upstream versions |
| **Итого** | **57ч** | **44ч** | **-13ч** | |
