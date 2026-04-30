# Roadmap — Documentation & Code Audit Findings (post-Phase 8 + 9.1)

**Дата:** 2026-04-30 (вечер)
**Статус:** ⏳ PROPOSED
**Приоритет:** Высокий (P0 — security + production consistency)
**Метод аудита:** 2 параллельных subagent'а (Explore type) на `docs/framework documentation/` и `src/`
**Связано:** [`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md)

---

## 0. Status Dashboard

После закрытия Phase 8 + 9.1 (миграция retrieval на Qwen3-Embedding-8B 4096d через TEI) образовался **технический долг рассинхронизации** между production-конфигурацией и:
1. Документацией (старые главы упоминают E5/nomic как defaults)
2. Кодом (legacy hardcoded models в src/)
3. TOC (chapter 26 LAZY_MCP пропущен; ссылки на §32 в chapter 31 не resolveable)

**Найдено через автоматический audit:**
- Documentation: ~25 issues (stale embedder refs, broken chapter refs, structural gaps)
- Code: ~15 issues (E5 hardcoded в 7+ файлах, 13 TODO/FIXME, 4 half-implemented features)

**Приоритеты:**
- **P0** (критичны для production consistency + security): 3 пункта, ~2-3 часа
- **P1** (документация → reality): 6 глав требуют refresh, ~3-4 часа
- **P2** (half-implemented features): 4 stub'а — реализовать или убрать, ~4-8 часов
- **P3** (code-without-docs): 5 модулей без документации, ~6-10 часов

---

## 1. Контекст и метод аудита

### 1.1 Что аудитировано

- **Documentation:** все 31 глава `docs/framework documentation/` (чтение overview-файлов + grep на deprecated terms)
- **Source code:** `src/` (Grep TODO/FIXME, hardcoded model strings, dead imports, unused config fields)
- **Cross-reference:** map модулей `src/*/` против глав docs

### 1.2 Что НЕ покрыто

- `tools/` (vendored + project-specific tooling — отдельный аудит)
- `tests/` (тестовое покрытие — отдельная задача)
- `scripts/` (utility scripts — обычно не в docs scope)
- `data/`, `cache/` (runtime artifacts)

### 1.3 Метод

Каждое наблюдение — **конкретный file:line** с цитатой проблемного фрагмента. Не общие наблюдения.

---

## 2. P0 — Critical inconsistencies (security + production consistency)

**Цель:** убрать прямые конфликты между Phase 8 production switchover (Qwen3 4096d default) и кодом, где hardcoded legacy models. Также закрыть JWT auth stub.

### 2.1 P0 — Embedding defaults в core config (КРИТИЧНО)

После Phase 8 production retrieval работает на Qwen3 4096d через TEI. Однако базовые config-классы всё ещё имеют E5 1024d как default. Если кто-то запустит `python -m src.cli.main index` без явного `EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B`, индексация пойдёт на **E5** — **dim mismatch с production коллекциями 4096d** → upsert failure.

- [ ] **2.1.1** [`src/pdf_framework/config/embedding.py:15-16`](../../src/pdf_framework/config/embedding.py) — заменить `model = "intfloat/multilingual-e5-large"` → `"Qwen/Qwen3-Embedding-8B"`, `dimensions = 1024` → `4096`. Добавить `provider: str = "tei"` field
- [ ] **2.1.2** [`src/pdf_framework/config/vector_store.py:15`](../../src/pdf_framework/config/vector_store.py) — `dimensions = 1024` → `4096`
- [ ] **2.1.3** [`src/pdf_framework/evaluation/autorag.py:33`](../../src/pdf_framework/evaluation/autorag.py) — `embedding_model = "intfloat/multilingual-e5-large"` → `"Qwen/Qwen3-Embedding-8B"`
- [ ] **2.1.4** [`src/pdf_framework/processing/image_processor.py:276`](../../src/pdf_framework/processing/image_processor.py) — same E5 update
- [ ] **2.1.5** [`src/ui/pages/settings.py:105`](../../src/ui/pages/settings.py) — UI defaults `"all-MiniLM-L6-v2"` → `"Qwen/Qwen3-Embedding-8B"`
- [ ] **2.1.6** [`src/bsl/semantic_search/mcp.py:713`](../../src/bsl/semantic_search/mcp.py) — fallback embedder `TextEmbedding("intfloat/multilingual-e5-large")` → Qwen3 через TEI HTTP
- [ ] **2.1.7** [`src/pdf_framework/processing/splitters/semantic_splitter.py:50`](../../src/pdf_framework/processing/splitters/semantic_splitter.py) — `embedding_model = "all-MiniLM-L6-v2"` → решение: либо Qwen3 (через TEI), либо явный комментарий что MiniLM — лёгкий быстрый default для dev

**Effort:** 30-60 мин. **Acceptance:** smoke test `python -m src.cli.main index` без env vars даёт 4096d вектора, не 1024d.

### 2.2 P0 — JWT auth stub (security-critical)

Multi-tenant isolation сейчас фиктивна:

```python
# src/api/routes/tenants.py:34
def get_current_tenant():
    # TODO: Parse JWT and extract tenant_id
    return "default"  # ← всегда default, нет изоляции

# src/api/routes/tenants.py:45
def require_admin():
    # TODO: Parse JWT and verify admin role
    return True  # ← все админы
```

- [ ] **2.2.1** Реализовать `get_current_tenant()` — distill JWT через `python-jose` или `pyjwt`, exctract `tenant_id` claim. Если invalid/missing → 401
- [ ] **2.2.2** Реализовать `require_admin()` — проверить `roles` claim содержит `admin`; иначе 403
- [ ] **2.2.3** Добавить unit-tests с моком JWT (valid/invalid/expired/missing claim)
- [ ] **2.2.4** Smoke test через `pytest tests/api/test_tenants.py`

**Effort:** 2-3 часа. **Acceptance:** запросы с invalid JWT возвращают 401, с tenant=A не видят данные tenant=B.

### 2.3 P0 — Stale chapter 32 references in chapter 31

Главы [`31.1_Обзор.md:121-126`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md) и [`31.2_Архитектура.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.2_Архитектура.md) ссылаются на `§32.2 Reranker`, `§32.3 Hybrid sparse+dense`, `§32.4 Auto-populate`, `§32.5.2 Cleanup snapshots` — эти секции существуют только в **roadmap** (`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md §32`), не в `docs/framework documentation/`.

- [ ] **2.3.1** Заменить все `§32.X` в chapter 31 на относительные ссылки на roadmap: `[Roadmap §32.2](../../roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md#322-phase-92--cross-encoder-reranker-next-big-win-4-8-часов)`
- [ ] **2.3.2** Опционально — создать `docs/framework documentation/32_FUTURE_RETRIEVAL_QUALITY/` с заголовком и pointer на roadmap §32 (если хочется keeping framework docs self-contained)

**Effort:** 30 мин. **Acceptance:** все ссылки в chapter 31 ведут на существующие файлы.

---

## 3. P1 — Documentation refresh (stale chapters → Phase 8 reality)

**Цель:** обновить главы которые писались до Phase 8 (некоторые ещё до Phase 7) и упоминают deprecated модели/коллекции как production.

### 3.1 P1 — Chapter 27.3 Memory_First_Hook

[`27.3_Memory_First_Hook.md:16,78,86-87`](../framework%20documentation/27_UNIFIED_MEMORY/27.3_Memory_First_Hook.md) описывает Layer 2 semantic search через Ollama nomic 768d. Phase 9.1 (commit `ac91c4b7`) заменил это на **TEI Qwen3 4096d**. Hook сейчас работает корректно, доки врут.

- [ ] **3.1.1** Обновить упоминания Ollama nomic 768d → TEI Qwen3 4096d
- [ ] **3.1.2** Обновить таблицу коллекций (skill_library, experience_embeddings, conversation_memory) — все теперь 4096d
- [ ] **3.1.3** Добавить ссылку на chapter 31.5 §31 Phase 9.1 alignment

### 3.2 P1 — Chapter 04.8 Dual_Vector_Search

[`04.8_Dual_Vector_Search.md:23,55,74,90`](../framework%20documentation/04_ПОИСК/04.8_Dual_Vector_Search.md) упоминает `bsl_code_v4` как 768d nomic. Реально `bsl_code_v4` (research) и `bsl_code_v4_late` (production) — оба **4096d Qwen3**.

- [ ] **3.2.1** Заменить все 768d → 4096d
- [ ] **3.2.2** Указать какая из коллекций (`v4` vs `v4_late`) production
- [ ] **3.2.3** Добавить ссылку на ADR-008 (Late Chunking decision)

### 3.3 P1 — Chapter 28 BSL_SEMANTIC_SEARCH

- [ ] **3.3.1** [`28.1_Обзор.md:48`](../framework%20documentation/28_BSL_SEMANTIC_SEARCH/28.1_Обзор.md) — `Ollama + nomic-embed-text` отметить как **legacy** (BSL retrieval теперь через TEI Qwen3)
- [ ] **3.3.2** [`28.4_Индексация.md:78-80`](../framework%20documentation/28_BSL_SEMANTIC_SEARCH/28.4_Индексация.md) — таблица коллекций упоминает `bsl_code_v2` (dropped) и `metadata_rrf` / `docs_rag` (несуществующие). Заменить на `bsl_code_v4_late`

### 3.4 P1 — Chapter 29 XSKILL_CONTINUOUS_LEARNING

- [ ] **3.4.1** [`29.1_Обзор.md:29,88-90`](../framework%20documentation/29_XSKILL_CONTINUOUS_LEARNING/29.1_Обзор.md) — `experience_embeddings (768d, nomic)` → 4096d Qwen3, `visual_grounding 768d` → **dropped 2026-04-30**
- [ ] **3.4.2** [`29.4_Retrieval_и_Scoring.md:9-11`](../framework%20documentation/29_XSKILL_CONTINUOUS_LEARNING/29.4_Retrieval_и_Scoring.md) — Source-таблица показывает все 768d nomic, после Phase 9.1 — 4096d
- [ ] **3.4.3** [`29.6_Visual_Grounding.md`](../framework%20documentation/29_XSKILL_CONTINUOUS_LEARNING/29.6_Visual_Grounding.md) — добавить header «Phase status: DROPPED 2026-04-30 (collection visual_grounding 5 pts × 768d удалён, см. roadmap §32.5.1). Visual retrieval — future work»

### 3.5 P1 — Chapter 01.3 Технологический_стек

[`01.3_Технологический_стек.md:11,26`](../framework%20documentation/01_ОБЗОР/01.3_Технологический_стек.md) — E5 1024d перечислена как default embedding. После Phase 8 — **Qwen3-Embedding-8B 4096d через TEI**.

- [ ] **3.5.1** Обновить таблицу embedding-моделей под Phase 8 production
- [ ] **3.5.2** Удалить или пометить legacy: `multilingual-e5-large`, `all-MiniLM-L6-v2`

### 3.6 P1 — Chapter 26 LAZY_MCP отсутствует в TOC

Папка `docs/framework documentation/26_LAZY_MCP/` существует с 6 файлами, но `00_СОДЕРЖАНИЕ.md` её **не упоминает**. Структурный navigation gap.

- [ ] **3.6.1** Добавить раздел `### [26. LAZY_MCP]` с list файлов в `00_СОДЕРЖАНИЕ.md`
- [ ] **3.6.2** Добавить быструю ссылку в bottom-section TOC

**Effort на §3 в сумме:** 3-4 часа (text edits, no code change).

---

## 4. P2 — Half-implemented features (stub APIs)

**Цель:** либо реализовать, либо убрать чтобы не вводить пользователей в заблуждение «функция есть, но возвращает 501».

### 4.1 P2 — `bsl_similar()` MCP tool (stub)

[`src/bsl/semantic_search/mcp.py:206-227`](../../src/bsl/semantic_search/mcp.py) — tool заявлен, возвращает «в разработке».

- [ ] **4.1.1** **Decision:** реализовать или удалить
  - Если реализовать (~2-3 часа): vector search через embedding текущего chunk_id, return top-k similar
  - Если удалить (~10 мин): убрать из MCP tool registration

### 4.2 P2 — SONAR analytics CLI

[`src/bsl/sonar/cli.py:49`](../../src/bsl/sonar/cli.py) — все команды возвращают `TODO: Реальный анализ` stub. Также [`src/bsl/sonar/config_manager.py:39,46`](../../src/bsl/sonar/config_manager.py) — load/save config не реализованы.

- [ ] **4.2.1** **Decision:** реализовать или удалить
  - Реализовать SonarQube integration (~1-2 дня): полноценный анализ BSL через Sonar API
  - Удалить (~30 мин): убрать `tools/sonar-bsl-plugin.jar` reference + cli + tests

### 4.3 P2 — RAPTOR tree traversal

[`src/pdf_framework/search/strategies/raptor_search.py:163`](../../src/pdf_framework/search/strategies/raptor_search.py) — TODO: implement tree traversal. Сейчас работает только collapsed mode.

- [ ] **4.3.1** Реализовать tree traversal (deep search через RAPTOR levels) — оригинал требовал ~4-8 часов, см. RAPTOR paper
- [ ] **4.3.2** Альтернатива: задокументировать что collapsed-only sufficient для нашего use-case, удалить TODO

### 4.4 P2 — HyDE other methods

[`src/pdf_framework/search/hyde.py:254`](../../src/pdf_framework/search/hyde.py) — TODO: Implement other methods. Сейчас один HyDE generation подход.

- [ ] **4.4.1** Audit: какие other methods (paper упоминает зеро-shot, multi-query)? Релевантны ли нашему workflow?
- [ ] **4.4.2** Реализовать или удалить TODO

**Effort на §4:** decision call + 4-12 часов реализации (зависит от того что оставляем).

---

## 5. P3 — Code-without-docs gaps (новые главы документации)

**Цель:** покрыть документацией модули которые есть в коде но не упомянуты ни в одной главе.

### 5.1 P3 — `src/pdf_framework/guardrails/`

Не упомянут в documentation. Безопасность критична — pii detection, prompt injection.

- [ ] **5.1.1** Создать `docs/framework documentation/33_GUARDRAILS/33.1_Обзор.md` (или интегрировать в chapter 10 troubleshooting)
- [ ] **5.1.2** Описать: PII modes (detect/redact/block), injection threshold, max query length

### 5.2 P3 — `src/pdf_framework/knowledge_base/`

Не упомянут в docs. Что это за подсистема? — нужна экспозиция.

- [ ] **5.2.1** Audit: что делает knowledge_base? Чем отличается от vector_store?
- [ ] **5.2.2** Создать обзор или delete если orphan модуль

### 5.3 P3 — `src/pdf_framework/multitenancy/`

Описан в chapter 09.1 (admin), но детали реализации (per-tenant collections, JWT integration) отсутствуют.

- [ ] **5.3.1** Расширить chapter 09 разделом «Multi-tenancy implementation» с реальными примерами

### 5.4 P3 — `src/extensions/`

2 mentions в docs — minimal coverage. Что это?

- [ ] **5.4.1** Прочитать `src/extensions/__init__.py` + main файлы, понять назначение
- [ ] **5.4.2** Документировать или delete

### 5.5 P3 — `src/workers/`

ARQ async workers. Описаны в chapter 09 deployment, но без детальных примеров tasks (indexing/graph/eval).

- [ ] **5.5.1** Расширить chapter 09 разделом «ARQ tasks» с примерами `index_document`, `rebuild_graph`, `run_evaluation`

**Effort на §5:** 6-10 часов (новые разделы документации с примерами).

---

## 6. P4 — Long-term + maintenance

### 6.1 P4 — Unused config fields cleanup

- [ ] **6.1.1** [`src/pdf_framework/config/features.py:43`](../../src/pdf_framework/config/features.py) — `classifier_cache_enabled` определено, нигде не читается. Удалить или wire
- [ ] **6.1.2** [`src/pdf_framework/config/features.py:53-56`](../../src/pdf_framework/config/features.py) — `route_simple_strategy`, `route_moderate_strategy`, `route_complex_strategy`, `route_thematic_strategy` — определены, но 80% routing-логики hardcoded. Audit `src/pdf_framework/agents/adaptive*.py` — использует ли их?
- [ ] **6.1.3** Если не используются — удалить из `Settings` класса (Pydantic будет недоволен extra fields в .env)

### 6.2 P4 — Deprecated providers cleanup

- [ ] **6.2.1** [`src/pdf_framework/embeddings/providers/giga.py`](../../src/pdf_framework/embeddings/providers/giga.py) — Path D research alternative, не выбрано в Phase 8. Решение: оставить как option или удалить?
- [ ] **6.2.2** [`src/pdf_framework/embeddings/providers/bgem3.py`](../../src/pdf_framework/embeddings/providers/bgem3.py) — same — оставить или delete

### 6.3 P4 — Other TODO/FIXME (low priority)

Полный список из аудита:

- [ ] **6.3.1** [`src/pdf_framework/optimization/dspy_optimizer.py:105`](../../src/pdf_framework/optimization/dspy_optimizer.py) — TODO: integrate with FeedbackStore to auto-populate
- [ ] **6.3.2** [`src/pdf_framework/processing/summary_index.py:280`](../../src/pdf_framework/processing/summary_index.py) — TODO: Use actual embedding engine from components
- [ ] **6.3.3** [`src/pdf_framework/evaluation/synthetic.py:283`](../../src/pdf_framework/evaluation/synthetic.py) — TODO: Load human questions from file
- [ ] **6.3.4** [`src/bsl/semantic_search/services/search.py:245`](../../src/bsl/semantic_search/services/search.py) — TODO: LLM Re-ranking (см. roadmap §32.2 Phase 9.2)

---

## 7. Decision triggers — когда брать какой пункт

| Сигнал | Какой раздел решает |
|--------|---------------------|
| `python -m src.cli.main index` падает с dim mismatch | §2.1 P0 embedding defaults |
| Пользователь сообщает что виден чужой tenant | §2.2 P0 JWT auth |
| Пользователь видит broken link в chapter 31 | §2.3 P0 §32 refs |
| Новый разработчик читает chapter 27.3 и пытается ставить Ollama | §3.1 P1 chapter 27.3 update |
| Pull request трогает `bsl_similar()` или `sonar/cli.py` | §4.1 / §4.2 P2 decision |
| Audit security review | §5.1 P3 guardrails docs |
| Code review замечает unused config field | §6.1 P4 cleanup |

---

## 8. Эффективная стратегия исполнения

### 8.1 Один день (8 часов) можно закрыть

**P0 (~3 часа):** §2.1 + §2.2 + §2.3 — все 3 пункта critical
**P1 (~3 часа):** §3.1 + §3.2 + §3.6 — самые видимые user-facing chapters
**Buffer:** 2 часа на тесты + commits

### 8.2 Неделя (40 часов) — закрыть P0 + P1 + P2

**День 1:** P0 (3 часа) + remaining P1 chapters 28/29/01.3 (4 часа)
**День 2-3:** P2 decisions + half-implementation (8-12 часов)
**День 4-5:** P3 documentation (6-10 часов) + buffer/review

### 8.3 Можно закрыть incremental

- P0 §2.1 — 5 минут на файл, можно делать «между делом» при следующем правке config'а
- P3 documentation — открыть chapter, добавить параграф, commit

---

## 9. Acceptance — что считаем «закрытым»

| Раздел | Acceptance |
|--------|------------|
| §2.1 | `EMBEDDING__MODEL` default = Qwen3, smoke index без env vars даёт 4096d |
| §2.2 | Тест `pytest tests/api/test_tenants.py` зелёный, реальный JWT parsing |
| §2.3 | `grep "§32" docs/framework documentation/31_*` — все ссылки относительные на roadmap |
| §3.1-§3.5 | `grep -r "768d\|nomic-embed-text\|multilingual-e5-large" docs/framework documentation/{04,27,28,29,01.3}*` — пусто или с пометкой `(legacy)` |
| §3.6 | `grep "26_LAZY_MCP" docs/framework documentation/00_СОДЕРЖАНИЕ.md` — содержит раздел |
| §4.x | Либо реализовано (есть unit-tests), либо удалено из public API |
| §5.x | Каждый src/* модуль из списка имеет ≥ один параграф в documentation |
| §6.x | `pyproject.toml lint` чистый, no orphan config fields |

---

## 10. Lessons learned (применимы к этому roadmap)

Из roadmap 260426 §33 lessons learned релевантные сюда:

- **Lesson #1 «Все коллекции» = нужен прогресс-чекер.** Применимо: для §2.1 нужен smoke test что **все** имплементации embedding default'а синхронизированы — простой grep `multilingual-e5-large` в `src/`
- **Lesson #2 silent dim mismatch.** Уже найден в Phase 9.1, но в `src/` остаются hardcoded 1024d (см. §2.1.2). После закрытия §2.1 — добавить CI assertion `EMBEDDING__DIMENSIONS == 4096`
- **Lesson #6 backup verification.** Применимо: §2.2 JWT change — повлияет на existing tokens. Pre-flight: создать tenant с известным JWT, проверить что после fix он всё ещё работает (no breaking change на api consumers)

---

## Источники

- [Roadmap Phase 8](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — production state context
- [Framework documentation chapter 31](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/) — текущий production guide
- Аудит run: 2026-04-30 вечер (2 параллельных Explore subagent'а)
- Файлы аудита приложены в commit message соответствующего PR
