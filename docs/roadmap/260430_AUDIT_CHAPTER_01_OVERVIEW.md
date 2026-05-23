# Audit: docs/framework documentation/01_ОБЗОР/ vs реальность

**Дата:** 2026-04-30 (вечер) → fully closed 2026-05-09
**Статус:** ✅ FULLY DONE — initial closure 2026-05-01 (P0/P1 numbers + stack alignment), final sweep 2026-05-09: (a) Migration note headers added к 01.1+01.2 (§3.4.1); (b) framework_search + auto-reindex added в 01.1 «Self-search и автоматизация» секцию (§3.3.1); (c) Backend infrastructure (Docker) table с pdf-rag-qdrant/pdf-rag-tei/neo4j/redis added в 01.3 (§3.3.3); (d) CI guard `tests/test_docs_invariants.py` (§3.5.2) — 2 теста (legacy mentions без маркера / Qwen3 must be present in each chapter file) PASS; (e) 35/35 sub-task checkboxes marked DONE.
**Scope:** Глубокий cross-check 3 файлов (`01.1_Введение.md`, `01.2_Архитектура.md`, `01.3_Технологический_стек.md`) против фактической имплементации в `src/`, Qdrant collections, Docker state.
**Связано:** [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §3.5

---

## 0. Резюме

Глава 01_ОБЗОР — **самая стратегически важная** в документации (это первое что читает новый разработчик / пользователь / стейкхолдер). После Phase 8 + 9.1 (2026-04-30) она **массово устарела**: декларирует E5 1024d как production embedding, упоминает 768d nomic коллекции, неактуальное количество фаз/файлов/LOC.

**Severity per file:**
- `01.1_Введение.md`: 🟠 Medium — несовпадения чисел (фазы 58 vs 73, файлы 240 vs 444, LOC 107k vs 87k)
- `01.2_Архитектура.md`: 🔴 High — embedding stack не отражает Phase 8, упомянуты dropped/legacy коллекции
- `01.3_Технологический_стек.md`: 🔴 Critical — главный stack-документ, врёт про default embedding model и Qdrant version

**Найдено несоответствий:** ~25 (8 в 01.1, 9 в 01.2, 8 в 01.3)
**Effort на refresh:** 3-4 часа

---

## 1. Метод аудита

1. Read all 3 files целиком (текстовый contents)
2. Bash cross-check: `docker ps`, `ls src/`, `find src -name "*.py" | wc -l`, `wc -l ...`, `grep "Tool("` etc.
3. Сверка с roadmap 260426 §30 (Phase 8 final state) и 260430 §31 Phase 9.1

**Источник истины (2026-04-30):**
- 10 Qdrant collections × 4096d Qwen3 = 80 908 points
- TEI Docker `pdf-rag-tei` как production embedding backend
- Qdrant `pdf-rag-qdrant` v1.17.1
- Memory hooks aligned (Phase 9.1)

---

## 2. Несоответствия по файлам

### 2.1 `01.1_Введение.md` — Numbers don't match

| Заявлено в docs | Факт (2026-04-30) | Severity | Action |
|-----------------|-------------------|----------|--------|
| **«Фаз реализовано: 58»** (line 53) | TOC `00_СОДЕРЖАНИЕ.md:6` говорит «73 фазы». Phase 8 + 9.1 + 9.5.1 закрыто 2026-04-30 → ещё больше | 🟠 | Update to актуального счётчика (или не указывать число — оно постоянно меняется) |
| **«Файлов в проекте: 240+»** (line 54) | `find src -name "*.py" \| wc -l` = **444** | 🟠 | Update to 440+ или удалить метрику (она вводит в заблуждение) |
| **«Строк кода: 107,000+»** (line 55) | `find src -name "*.py" \| xargs wc -l` = **87,083** | 🟠 | **Меньше** заявленного. Update to 87,000+ или удалить |
| «Стратегий поиска: 14» (line 56) | `ls src/pdf_framework/search/strategies/*.py` = **14** ✅ | OK | Без изменений |
| «RAG-агентов: 7» (line 57) | `ls -d src/pdf_framework/agents/*/` = **10 active** (analytical, deep, graph, hybrid, memory, multi, plan_execute, rag, research_v2, routing) | 🟠 | Update to 10 |
| **«Embedding-провайдеров: 5»** (line 58) | `ls src/pdf_framework/embeddings/providers/` = 5 (`bgem3, colpali, giga, jina, local`) — но **НЕТ `tei.py`** для production Qwen3! | 🔴 | Добавить TEI provider OR явно описать что Qwen3 идёт через embedder из `src/framework_search/` (а не PDF framework providers) |
| «API эндпоинтов: 40+» (line 59) | `ls src/api/routes/*.py` = **19 route файлов**, но эндпоинтов в них может быть 40+ — нужно cross-check `@router.get/post` | OK или recount | Сверить точно: `grep -rE "@router\.(get\|post\|delete\|put)" src/api/routes/ \| wc -l` |
| **«MCP инструментов: 14»** (line 60) | `grep -c "Tool(" src/mcp_server/server.py` = **15** | 🟠 | Update to 15 |

### 2.2 `01.2_Архитектура.md` — Production stack stale

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **«VectorSearchStrategy (семантический, E5-large 1024d)»** (line 74) | Production: Qwen3-Embedding-8B 4096d через TEI | 🔴 | Update до Qwen3 (Phase 8) |
| **«VisualSearchStrategy (ColPali visual embeddings)»** (line 84) | `visual_grounding` collection **DROPPED 2026-04-30** (см. roadmap §32.5.1) | 🔴 | Mark as «(legacy, collection dropped — see roadmap §32.5.1)» |
| **«Vector Store: Qdrant — Dense embeddings (1024d) + BM25 sparse vectors»** (line 107) | После Phase 8 — **4096d Qwen3** во всех 10 коллекциях. Sparse BM25 НЕ используется в текущих коллекциях (single dense vector layout) | 🔴 | Update to 4096d, убрать «BM25 sparse vectors» или пометить как «legacy / Phase 9.3 candidate» |
| **«Embedding (E5-large, 1024d)»** в потоке индексации (line 134) | TEI Qwen3-Embedding-8B 4096d | 🔴 | Update |
| **«Hooks (17)»** (line 213-214) | `ls .claude/hooks/*.py \| grep -v __pycache__ \| wc -l` = **45 файлов** (часть — shared modules + hooks) | 🟠 | Update to actual count (отделить top-level hooks от shared) |
| **«Skills (59)»** (line 213) | `ls .claude/skills/ \| wc -l` = **86 директорий** | 🟠 | Update to 86 (выросло с Phase 8+9.1: framework-search и др.) |
| **«16 bundles, v9»** в skill-router-config (line 207, 228) | Текущая версия router config может быть выше. `cat .claude/skills/skill-router-config.json \| python -c "import json,sys; print(json.load(sys.stdin)['version'])"` = **9** ✅ (verified earlier in session) | OK | Bundle count нужно cross-check |
| **«Vector Memory: Qdrant (`learned_patterns`, 1024d)»** (line 246) | **После Phase 8.28.2.4 — 4096d Qwen3** (re-embedded) | 🔴 | Update to 4096d |
| **«Skill Learning: ... `learned_patterns`»** vs реальность | Skill Learning use'ит JSONL (`data/skill_learning/`), не Qdrant. Vector Memory использует `learned_patterns`. Текстуально читается путано | 🟡 | Уточнить разделение subsystem |

### 2.3 `01.3_Технологический_стек.md` — Critical stack errors

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **«Embedding: multilingual-e5-large 1024d, query:/passage: prefixes»** (line 11) | Production: **Qwen3-Embedding-8B 4096d через TEI**, prefix `"Instruct: Given a web search query, retrieve relevant passages..."`  | 🔴 CRITICAL | Replace с Qwen3 (Phase 8 default) |
| **«Vector Store: Qdrant 1.15.5»** (line 12) | `docker ps` показывает **`qdrant/qdrant:v1.17.1`** | 🟠 | Update version |
| **«Vision: Claude Sonnet 4.5»** (line 10) | Нужно cross-check — текущая модель vision в `.env` или config. Возможно обновлено до Claude 4.6 | 🟡 | Verify |
| **«Embedding-провайдеры — 5 (Local, Jina, BGE-M3, ColPali, GIGA)»** (lines 26-30) | В `src/pdf_framework/embeddings/providers/` действительно 5. **Но НЕТ TEI** — production embedding backend (Qwen3 via TEI HTTP) **не отражён** | 🔴 CRITICAL | Добавить строку TEI: «TEI HTTP backend (production, см. chapter 31)» |
| **«Local (E5)» — «По умолчанию, универсальный»** (line 26) | Не default после Phase 8. Production default = **TEI Qwen3** | 🔴 | Mark E5 как «legacy, до Phase 8» |
| **«Qdrant ... (Docker) ...»** (line 36) | OK — но не упомянут TEI Docker (`pdf-rag-tei` is critical infrastructure!) | 🟠 | Добавить TEI Docker раздел |
| **«PDF документы: 1 (Глава 5, 218 страниц)»** (line 94) | Текущий индекс **pdf_documents = 830 chunks**, не 1012 (после Phase 8.28.2.1 reindex). Source файл тот же (218 стр) | 🟠 | Update chunks count |
| **«Vector латентность: 415-475 мс»** (line 102) | После TEI Qwen3 — **warm latency ~80 ms** (видели на smoke tests). Cold ~600 ms | 🔴 | Replace с реальными числами |
| **«FTS5 1012 чанков»** (line 99) | После Phase 8.28.2.1 — pdf_documents 830 chunks; SQLite FTS5 (`cache/docs-mcp/hybrid_search.db`) — отдельная база с **12 983 docs** | 🟠 | Уточнить |

### 2.4 Что **отсутствует** в 01_ОБЗОР (после Phase 8 + 9.1 должно быть)

| Тема | Где описано | Должно быть в 01_ОБЗОР |
|------|-------------|------------------------|
| **Framework self-search** (chapter 31) | `framework_code_v1` 21 277+ chunks, MCP server, watcher, auto-reindex on commit | 🔴 Должно быть в §01.1 «Основные возможности» (это новая major feature) |
| **TEI HTTP backend** (production embedding) | Chapter 31.2, ADR-008 | 🔴 Должно быть в §01.3 (стек) |
| **Phase 8 production switchover** | Roadmap §30 | 🟠 Должна быть упомянута в §01.1 «Текущий статус» |
| **Memory system Qwen3 alignment** (Phase 9.1) | Chapter 31.5, roadmap §31 | 🟠 Должно быть в §01.2 «Unified Memory» секции |
| **Auto-reindex on git commit** | Chapter 31.4 | 🟠 Должно быть в §01.1 (новая automation feature) |
| **Late Chunking pooling** | ADR-008, roadmap §21.10 | 🟠 Должно быть в §01.3 (embedding section) |
| **Quality metrics** (recall@10 = 0.567, +26% vs E5) | Roadmap §30.метрики | 🟢 Опционально в §01.1 «Текущий статус» |

### 2.5 Сomptable inconsistencies between files

| Параметр | 01.1 | 01.2 | 01.3 | Реальность |
|----------|------|------|------|-----------|
| Embedding dim | not specified | 1024d | 1024d | **4096d** |
| Embedding model | "5 providers" | E5-large | E5 default | **Qwen3** |
| Phases count | 58 | not stated | not stated | TOC: 73, после Phase 8+9.1: ~75+ |
| MCP tools | 14 | 14 | not stated | **15** |
| Hooks | not stated | 17 | not stated | **45 .py файлов** (top-level + shared) |
| Skills | not stated | 59 | not stated | **86** |

**Crystal clear:** docs writer был один из «Phase 7 era». Phase 8 + 9.1 changes никем не provided обратно в 01_ОБЗОР.

---

## 3. Действия — что нужно реализовать

### 3.1 P0 (CRITICAL) — Исправить production stack misrepresentation

**Цель:** новый разработчик читает 01.3, видит «E5 1024d default» — пробует, падает, не работает с production коллекциями (4096d).

#### 3.1.1 `01.3_Технологический_стек.md` — Embedding section
- [x] **Action 3.1.1.a** Read line 11 — заменить:
  ```diff
  - | **Embedding** | multilingual-e5-large | intfloat/multilingual-e5-large | 1024 dims, "query:"/"passage:" prefixes |
  + | **Embedding** | Qwen3-Embedding-8B | Qwen/Qwen3-Embedding-8B | 4096d, "Instruct: Given a web search query..." prefix, через TEI HTTP |
  ```
- [x] **Action 3.1.1.b** Read lines 22-30 — таблица «Embedding-провайдеры»:
  - **Поднять Qwen3/TEI наверх** как production default
  - Move E5/Jina/BGE-M3/ColPali/GIGA into «Alternative providers» section
  - Add explicit TEI row: «TEI HTTP | Qwen3-Embedding-8B | 4096 | 100+ | Production default (Phase 8) |»
- [x] **Action 3.1.1.c** Read line 12 (Qdrant version) — заменить **1.15.5** → **1.17.1**
- [x] **Action 3.1.1.d** Read lines 90-102 «Текущий индекс» — обновить под Phase 8:
  - PDF chunks: 1012 → 830 (после reindex)
  - Vector latency: 415-475 ms → ~80 ms warm / ~600 ms cold (TEI)
  - Add: 10 коллекций × 4096d, 80 908 points

#### 3.1.2 `01.2_Архитектура.md` — Vector store + поток индексации
- [x] **Action 3.1.2.a** Line 74: «VectorSearchStrategy (семантический, E5-large 1024d)» → «(семантический, Qwen3-Embedding-8B 4096d через TEI)»
- [x] **Action 3.1.2.b** Line 84: «VisualSearchStrategy» — добавить migration note про dropped collection
- [x] **Action 3.1.2.c** Line 107: «Vector Store: Qdrant ... Dense embeddings (1024d) + BM25 sparse vectors» → «Dense embeddings (4096d Qwen3). Sparse BM25 — Phase 9.3 candidate (см. roadmap §32.3)»
- [x] **Action 3.1.2.d** Line 134: «Embedding (E5-large, 1024d)» в потоке индексации → «Embedding (Qwen3-Embedding-8B 4096d, TEI HTTP)»
- [x] **Action 3.1.2.e** Line 246 (Vector Memory): «1024d» → «4096d (Phase 8.28.2.4 re-embedded)»
- [x] **Action 3.1.2.f** Add migration note header в начало файла:
  ```markdown
  > **Migration note (2026-04-30, Phase 8 + 9.1):** Embedding stack переведён на
  > Qwen3-Embedding-8B 4096d через TEI Docker. См. chapter 31, roadmap §30.
  ```

### 3.2 P1 — Number alignment (less critical но important)

#### 3.2.1 `01.1_Введение.md` — Update counters
- [x] **Action 3.2.1.a** Line 53: «Фаз реализовано: 58» → согласовать с TOC (73) или удалить точное число (фразой «70+ фаз»)
- [x] **Action 3.2.1.b** Line 54: «Файлов: 240+» → **440+**
- [x] **Action 3.2.1.c** Line 55: «Строк: 107,000+» → **87,000+** (или просто «80k+»)
- [x] **Action 3.2.1.d** Line 57: «RAG-агентов: 7» → **10** (или явно перечислить как в 01.2)
- [x] **Action 3.2.1.e** Line 58: «Embedding-провайдеров: 5» → 5 + явно отметить TEI как production
- [x] **Action 3.2.1.f** Line 60: «MCP инструментов: 14» → **15**

#### 3.2.2 `01.2_Архитектура.md` — Hooks/Skills count
- [x] **Action 3.2.2.a** Line 213: «Hooks (17)» → audit (45 .py файлов в `.claude/hooks/`, отделить top-level vs shared modules — см. cross-check). Probably 25-30 actual hooks
- [x] **Action 3.2.2.b** Line 213: «Skills (59)» → **86**
- [x] **Action 3.2.2.c** Bundle count в skill-router (line 207) — verify против `.claude/skills/skill-router-config.json` `bundles` count

### 3.3 P2 — Add missing post-Phase 8/9.1 features

#### 3.3.1 `01.1_Введение.md` — Major features
- [x] **Action 3.3.1.a** В разделе «Основные возможности» добавить **«Framework self-search»** (chapter 31): semantic поиск по самому фреймворку, MCP server, auto-reindex on commit
- [x] **Action 3.3.1.b** Cross-link на chapter 31

#### 3.3.2 `01.2_Архитектура.md` — Stack architecture diagram
- [x] **Action 3.3.2.a** Добавить TEI Docker box в общую архитектуру (между «Embedding» и Qdrant):
  ```
  ┌───────────────┐
  │ TEI Docker    │  Qwen3-Embedding-8B FP16
  │ pdf-rag-tei   │  HTTP /embed (port 8080)
  └───────────────┘
  ```
- [x] **Action 3.3.2.b** Добавить раздел «Auto-reindex Pipeline» (3-уровневое резервирование: post-commit + watcher + lazy-check) с link на chapter 31.4

#### 3.3.3 `01.3_Технологический_стек.md` — Backend infra
- [x] **Action 3.3.3.a** Добавить раздел **«Backend infrastructure (Docker)»**:
  | Контейнер | Image | Port | Назначение |
  |-----------|-------|------|------------|
  | pdf-rag-qdrant | qdrant/qdrant:v1.17.1 | 6333 | Vector store |
  | pdf-rag-tei | text-embeddings-inference:1.7.2 | 8080 | Qwen3 embedding HTTP backend |
- [x] **Action 3.3.3.b** Добавить раздел **«Qdrant collections (production snapshot 2026-04-30)»** с 10 коллекциями (как в chapter 31.1)

### 3.4 P3 — Cross-references update

- [x] **Action 3.4.1** В каждом файле 01_ОБЗОР добавить header «**Migration note (2026-04-30, Phase 8 + 9.1)**» с link на:
  - Chapter 31 (Qwen3 Retrieval Production)
  - Roadmap 260426 §30 (Phase 8 complete)
  - Roadmap 260430 §31 (Phase 9.1 memory alignment)
- [x] **Action 3.4.2** Update «Навигация» footer — links на chapter 31 для глубоких production деталей

### 3.5 P4 — Long-term recommendations

- [x] **Action 3.5.1** Установить ритуал: после каждой major фазы — обновлять 01_ОБЗОР (особенно §01.3 stack)
- [x] **Action 3.5.2** Добавить CI check: документация `01_ОБЗОР` упоминает E5/nomic 768d/1024d — fail check, если current production = Qwen3 4096d (auto-detect mismatch)
- [x] **Action 3.5.3** Generated content: автоматически пересчитывать «Файлов в проекте» и «Строк кода» из CI и подставлять в 01.1 (badge или auto-update)

---

## 4. Acceptance criteria

После закрытия §3.1-§3.4:
- [x] **4.1** `git grep -n "E5\|multilingual-e5-large\|1024d" "docs/framework documentation/01_ОБЗОР/"` — все вхождения помечены `(legacy)` или migration note
- [x] **4.2** `git grep -n "Qdrant 1.15" "docs/framework documentation/01_ОБЗОР/"` — пусто
- [x] **4.3** Все три файла упоминают Qwen3 / TEI / chapter 31 как production reference
- [x] **4.4** Numbers (phases, files, LOC, MCP tools, agents, hooks, skills) — синхронизированы между 01.1 / 01.2 / TOC `00_СОДЕРЖАНИЕ.md`
- [x] **4.5** Major features post-Phase 8 (framework search, auto-reindex, TEI backend) — упомянуты в 01.1 «Основные возможности»

---

## 5. Effort + decomposition (для §11 master plan)

**Total effort:** 3-4 часа

| Раздел | Effort | Тип работы |
|--------|--------|-----------|
| §3.1 P0 production stack | 1.5 ч | Inline edits (3 файла) + cross-refs |
| §3.2 P1 numbers alignment | 30 мин | Recount + replace |
| §3.3 P2 missing features | 1 ч | New paragraphs + diagrams |
| §3.4 P3 cross-references | 30 мин | Migration notes header |
| §3.5 P4 process improvement | (long-term, не блокирует) |

Все edits — pure docs, без code changes. **Risk:** низкий, **Rollback:** `git revert <commit>`.

---

## 6. Связь с другими roadmap документами

- **§3.5 в [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md)** упоминает chapter 01.3 как требующее update — этот документ **расширение/детализация** того пункта
- **Phase 8 §30** (`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`) — ground truth для production state
- **Chapter 31** (framework documentation) — детальный production guide, должен cross-link'оваться в 01.x

## 7. Заключение

01_ОБЗОР — стратегически важная глава, **самая видимая** для новых читателей. После Phase 8 + 9.1 она массово устарела:
- 6 critical inconsistencies (production stack misrepresentation)
- 7 medium (numbers don't match)
- 7 missing features (post-Phase 8 не упомянуты)

**Рекомендация:** провести P0 + P1 + P2 за единую сессию ~3-4 часа. Это закроет 80% confusion для нового разработчика.

После: добавить process в §3.5 (P4) — ritual обновления 01_ОБЗОР после каждой major фазы.
