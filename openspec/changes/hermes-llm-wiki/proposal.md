# Proposal: Hermes Agent / LLM Wiki Карпаты — интеграция в PDF Framework

## Бизнес-цель

Превратить PDF Vector & Graph Framework из системы с фрагментированной памятью (4 подсистемы + 17 MCP-серверов + 75 skills) в **систему с единым источником истины для знаний** по концепции LLM Wiki Андрея Карпаты. Знания должны **компаундировать** между сессиями: каждая сессия обогащает wiki, каждый запрос использует накопленный опыт.

## Мотивация

Текущая архитектура памяти фреймворка страдает от:

1. **Фрагментация знаний.** Факты живут одновременно в: `memory_ai.db` (SQLite), `learned_patterns` (Qdrant), `skill_library` (Qdrant), `experience_bank` (Qdrant), `MEMORY.md` (user-level), cache-директориях 11+ скиллов, docs/architecture/*.md, docs/roadmap/*.md. Дубликаты, противоречия, отсутствие дедупликации.

2. **Нет канонического источника.** Невозможно ответить "где живёт факт X?". При повреждении Qdrant (было на ChromaDB несколько раз) теряются месяцы обучения паттернам.

3. **Knowledge compound не работает.** Паттерны в `learned_patterns` медленно умирают через confidence decay, но никогда не "графдуируются" в canonical wiki-страницы.

4. **Нет human-readable слоя.** Открыв Qdrant, невозможно понять "что знает фреймворк". Требуется MCP + семантический запрос.

5. **Git-history знаний отсутствует.** Нет версионирования "что изменилось в понимании фреймворка с прошлого месяца".

## Предлагаемое решение

Внедрить **5-слойную модель памяти** с каноническим Wiki-слоем (L3) на markdown и derived индексами (L4) в Qdrant/LightRAG:

```
L4: Индексы (Qdrant wiki_pages_v1, LightRAG graph, learned_patterns, skill_library)
L3: Wiki (docs/wiki/, docs/architecture/, docs/roadmap/, cache/) — КАНОНИЧЕСКИЙ
L2: Semantic patterns (Qdrant learned_patterns + skill_learning JSONL)
L1: Episodic (SQLite memory_ai.db)
L0: Raw sources (conversations, PDFs, git history)
```

**Ключевые элементы:**

1. **Markdown = источник истины.** Wiki-страницы в `docs/wiki/` — canonical. Qdrant-коллекции — rebuildable cache. При повреждении индекса — восстановление из wiki.

2. **Git = бесплатное versioning.** Wiki в git, `git log` / `git blame` заменяют существующие `memory_version_*` tools для L3.

3. **Расширения существующей инфраструктуры, не переписывание.** Все 7 фаз используют уже реализованные компоненты: `MemoryCube`, `LinkRegistry`, `ConflictResolver`, `EventBus`, `PropagationEngine`, Phase 38 LightRAG, Phase 12.3 OAuth, `docs-change-tracker`, `HybridSearchService`.

4. **OSS-first.** Obsidian-MCP (3.3k⭐), LightRAG (33.1k⭐), E2B code-interpreter — готовые production-ready проекты.

## Scope

### Что меняется
- `src/memory/orchestrator/unified_id.py` — расширение MemoryType/SourceServer enum (+2 types, +2 sources)
- `src/memory/orchestrator/link_registry.py` — расширение LinkType enum + **SQL migration** (добавить 4 новых link types через ALTER TABLE)
- `src/memory/orchestrator/memcube.py` — добавить `to_wiki_page()`/`from_wiki_page()` методы + `ContentType.WIKI`
- `src/memory/orchestrator/unified_search.py` — новые адаптеры (использует существующий adapter pattern)
- `src/memory/orchestrator/memory_router.py` — добавить target `"wiki"` в ContentClassifier
- `.claude/hooks/memory-first-hook.py` — добавить Layer 0 (obsidian-mcp wiki search) с новыми RRF весами
- `.claude/hooks/docs-change-tracker.py` — расширить логикой wiki validation + L2→L3 promotion trigger
- `src/pdf_framework/agents/{grader,rewriter,hallucination_check}.py` — миграция f-string → DSPy Signatures
- `src/pdf_framework/indexing/wiki_exporter.py` — **новый** модуль экспорта entity graph → markdown
- `src/memory/librarian/wiki_promoter.py` — **новый** тонкий компонент промоции L2→L3
- `.mcp.json` — добавить `obsidian-mcp` сервер
- `.obsidian/` — новая конфигурация vault
- `docs/wiki/` — новая директория для structured wiki-страниц
- `docs/architecture/*.md` — миграция существующих 8 файлов на frontmatter + wiki-links (non-breaking)

### Что НЕ меняется
- Существующие 4 memory subsystems (ai_memory, vector_memory, skill_learning, pdf_docs) — работают без изменений
- Phase 38 LightRAG (`graph_store/entity_embeddings.py`, `search/strategies/graphrag_light.py`) — используется as-is
- Phase 6.5 Incremental Graph (`graph_store/incremental.py`, `change_detector.py`) — используется as-is
- Phase 12.3 OAuth в `src/bsl/mcp_server/auth/oauth2.py` — только экстракция в shared, семантика не меняется
- 26 существующих тестов `test_memory_unified.py` — должны проходить без регрессии
- 288 существующих тестов `test_auth.py` — должны проходить без регрессии
- OpenSpec 1C workflow (`gkstcplk-*` changes) — не затрагивается, отдельный profile

### Breaking changes
- **SQLite schema** `data/link_registry.db` — требует миграцию (ALTER TABLE links), есть rollback скрипт
- **LinkType enum** — добавление значений, старые literals продолжают работать

## Связанные документы

- **Полный roadmap (v1.3.4):** [docs/roadmap/260413_Hermes Agent и LLM Wiki Карпати персистентные системы знаний.md](../../../docs/roadmap/260413_Hermes%20Agent%20и%20LLM%20Wiki%20Карпати%20персистентные%20системы%20знаний.md) — 7 фаз, матрица OSS, 5 проходов аудита
- **GitHub research:** [.claude/skills/architecture-research/cache/hermes-llm-wiki-github-landscape.md](../../../.claude/skills/architecture-research/cache/hermes-llm-wiki-github-landscape.md)
- **Первоисточник:** Karpathy LLM Wiki [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- **Интегрируемые компоненты:**
  - `CLAUDE.md` — основной конфиг
  - `.claude/skills/memory-unified/SKILL.md`
  - `.claude/skills/hooks-skills-mcp-triad/SKILL.md`
  - `src/memory/orchestrator/` — 93KB memory_orchestrator.py, 68KB infrastructure

## Оценка трудоёмкости

- **Новый код:** ~1500-1800 LoC glue (после 5 проходов аудита — фреймворк на 85% готов)
- **Длительность:** 3-4 недели реализации
- **Экономия vs v1.0:** ~15-18 недель за счёт переиспользования существующих компонентов (LightRAG, OAuth, ConflictResolver, EventBus, PropagationEngine, MemoryCube, HybridSearchService)
- **Риск:** низкий благодаря brownfield-compatibility principle и инкрементальному подходу (каждая фаза независима и доставляет ценность)
