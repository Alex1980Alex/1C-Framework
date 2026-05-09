# Audit: docs/framework documentation/ главы 02-30 vs реальность

**Дата:** 2026-04-30 (вечер) → fully closed 2026-05-09 → CI guard extended + inner-files sweep 2026-05-09
**Статус:** ✅ FULLY DONE — initial closure 2026-05-01 (02.1 v1.17.1, 02.2 Qwen3/TEI default, 04.1 vector strategy, 28.4/29.6/29.4 banners). Final §6 mass-grep sweep 2026-05-09 закрыл remaining stale refs: 02.3:10 (Qdrant healthz output), 09.5:20+95+144 (compose+env), 10.1:21+63 (troubleshooting), 13.4:141 (MCP env doc default), 19.1 header (migration note для legacy chapter), 19.3:42+44+90 (`bsl_code_v3` legacy markers), 30.2:51 (`skill_library` Phase 9.1 4096d), 10.3 header (migration ref на ch.31). 26/26 sub-task checkboxes ticked. CI guard `tests/test_docs_invariants.py` расширен (2026-05-09): новый класс `TestAllChaptersNoStaleProductionStack` сканирует **все** главы (не только 01_ОБЗОР) на 7 stale-patterns (multilingual-e5-large / Qdrant 1.15+ / nomic-embed-text / all-MiniLM-L6-v2 / bsl_code_v2 / bsl_code_v3) с 21 LEGACY_MARKERS + 7 FILE_LEVEL_BANNERS (Migration note, Phase 8 note, DROPPED, …). Allowlist: `31_QWEN3_RETRIEVAL_PRODUCTION/` (migration doc, исторический контекст ожидаем). Inner-files sweep 2026-05-09: добавлены banners в 19.2/19.4/19.5/19.6 (legacy chapter), 10.1 (Phase 8 reference), 10.3 (Phase 8 production reference); inline markers — 27.3:18 «superseded by Phase 9.1», 29.6:68 «legacy reference, см. DROPPED banner». 3/3 docs invariants tests PASS.
**Scope:** Cross-check ~24 глав документации (исключая уже отдельно аудитированную 01_ОБЗОР и свежесозданную 31_QWEN3_RETRIEVAL_PRODUCTION).
**Связано:**
- [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §3 — главный roadmap
- [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md) — sibling, тот же подход

---

## 0. Резюме

Большинство глав (~15 из 24) актуальны (BSL pipeline, learning loop, ralph wiggum, memory unified — материал был дописан в 2026-04). **9 глав имеют конкретные несоответствия** с production-state после Phase 8 + 9.1 (2026-04-30):

| Severity | Count | Главы |
|----------|-------|-------|
| 🔴 Critical | 5 | 02.1, 02.2, 04.1, 28.4, 29.6 |
| 🟠 High | 3 | 04.6, 29.4, 19 (если будет) |
| 🟡 Medium | 1 | 03.x (chunk_size defaults) |

**Найдено несоответствий:** ~22
**Effort на refresh:** ~2.5 часа (главным образом search/replace + добавить Phase 8 footer-боксы со ссылкой на главу 31)

---

## 1. Метод

1. `Glob` по всем 24 главам, прочитать overview-файлы (`<N>.1_*`) каждой главы
2. Bash `grep` по «boundary-словам» (`E5\|nomic\|1024d\|bsl_code_v[23]\|visual_grounding\|qdrant.*1\.1[56]`)
3. Cross-check с production-state из `260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md` §30 + `260430_*_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md`

**Источник истины (2026-05-01):**
- 10 Qdrant collections × 4096d Qwen3 = 80 908 points
- Qdrant `pdf-rag-qdrant` `qdrant/qdrant:v1.17.1`
- TEI Docker `pdf-rag-tei` (image 1.7.2 Ampere)
- Production BSL retrieval: `bsl_code_v4_late` (Late Chunking)
- Memory hooks aligned (Phase 9.1, commit `ac91c4b7`)
- visual_grounding collection **DROPPED** 2026-04-30 (cleanup §27 в Phase 8 roadmap)

---

## 2. Critical (🔴) findings — by chapter

### 2.1 `02_БЫСТРЫЙ_СТАРТ/02.1_Установка.md` — Qdrant version stale

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **`qdrant/qdrant:v1.15.5`** (line 68) | `docker ps` → `qdrant/qdrant:v1.17.1` | 🔴 | Update tag в `docker run` примере |
| Docker storage path `data/qdrant_storage:/qdrant/storage` | Production: named volume `qdrant_storage` (per `docker/docker-compose.yml`) | 🟡 | Указать оба варианта (named volume + bind-mount) |

**Action items:**
- [x] **A.2.1.1** Update line 68: `qdrant/qdrant:v1.15.5` → `qdrant/qdrant:v1.17.1`
- [x] **A.2.1.2** Добавить footer-бокс: «См. также главу 31 для production retrieval setup (TEI + Qwen3)»

### 2.2 `02_БЫСТРЫЙ_СТАРТ/02.2_Конфигурация.md` — E5 default vs Qwen3 production

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **`EMBEDDING__MODEL=intfloat/multilingual-e5-large`** (line 40) | Production default Phase 8: `Qwen/Qwen3-Embedding-8B` (4096d) | 🔴 | Update + объяснить когда оставлять E5 (legacy fallback) |
| Comment «E5 модели требуют prefix» (line 55) | Корректно для legacy, но Qwen3 использует `Instruct: ... \nQuery: ...` | 🔴 | Добавить блок про Qwen3 instruction prompt |
| `EMBEDDING__DIMENSIONS=1024` упоминается? | Production: 4096 native (или 1024 MRL-truncated) | 🔴 | Update + объяснить MRL |

**Action items:**
- [x] **A.2.2.1** Заменить пример `EMBEDDING__MODEL=intfloat/multilingual-e5-large` на `EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B`
- [x] **A.2.2.2** Добавить `EMBEDDING__PROVIDER=tei`, `EMBEDDING__TEI_BASE_URL=http://localhost:8080`, `EMBEDDING__DIMENSIONS=4096`
- [x] **A.2.2.3** Секция «Legacy E5 fallback» — оставить старый пример но как опциональный (не default)
- [x] **A.2.2.4** Cross-ref на главу 31.2 (TEI Docker config)

### 2.3 `04_ПОИСК/04.1_Обзор_стратегий.md` — E5 hardcoded в таблице стратегий

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **«VectorSearchStrategy ... E5-large (1024d)»** (line 9) | Production: Qwen3 4096d | 🔴 | Update модель и dim |
| Table: возможные duplicate columns / мerged cells (нужна перепроверка) | — | 🟡 | Read целиком, выпрямить таблицу |
| Reference на `bsl_code_v3` или `_e5_legacy` коллекции? | Все dropped в Phase 8 §27 | 🔴 (если есть) | Удалить упоминания |

**Action items:**
- [x] **A.4.1.1** Update line 9: «E5-large (1024d)» → «Qwen3-Embedding-8B (4096d) через TEI; E5-large (1024d) — legacy fallback»
- [x] **A.4.1.2** Read весь файл, исправить все упоминания E5/nomic/1024d
- [x] **A.4.1.3** Если есть упоминание `bsl_code_v3` или `*_e5_legacy` — заменить на `bsl_code_v4_late` (production)

### 2.4 `28_BSL_SEMANTIC_SEARCH/28.4_Индексация.md` — `bsl_code_v2` + nomic stale

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **«`bsl_code_v2` ... nomic-embed-text»** (line 78) | Production BSL collection: `bsl_code_v4_late` × 4096d Qwen3 + Late Chunking | 🔴 | Update collection name + model |
| Возможные другие упоминания `bsl_code_v2` или `bsl_code_v3` в этой главе | — | 🔴 | grep по всему файлу |

**Action items:**
- [x] **A.28.4.1** `grep -n "bsl_code_v[123]\|nomic" docs/framework documentation/28_BSL_SEMANTIC_SEARCH/*.md` — собрать все
- [x] **A.28.4.2** Update таблицы коллекций → `bsl_code_v4_late` (production) + `bsl_code_v4` (research baseline std pooling)
- [x] **A.28.4.3** Footer-бокс «Phase 8 production switchover см. главу 31, ADR-008»

### 2.5 `29_XSKILL_CONTINUOUS_LEARNING/29.6_Visual_Grounding.md` — collection dropped

**Severity 🔴:**
- Глава целиком описывает `visual_grounding` Qdrant collection × 768d SigLIP
- Production state: collection **DROPPED 2026-04-30** (Phase 8 §27 cleanup, low ROI миграция)
- Исключение: всё ещё используется как concept для будущих visual feature

**Решение пользователя:** НЕ удалять features → НЕ удалять главу
**Action items:**
- [x] **A.29.6.1** Добавить prominent banner в самом верху:
  > ⚠️ **Status (2026-05-01):** Qdrant collection `visual_grounding` **dropped** в рамках Phase 8 cleanup (низкая ROI миграции 5 точек × 768d SigLIP на Qwen3 4096d). Реактивация — в Phase 9.4+ когда будет living source visual data. См. roadmap §32.5.1.
- [x] **A.29.6.2** Update line 20: `Qdrant: visual_grounding (768d)` → пометить как «(disabled, см. banner)»
- [x] **A.29.6.3** Cross-ref на главу 31.5 §«Что осталось на Phase 9.2+» / 9.4

---

## 3. High (🟠) findings

### 3.1 `04_ПОИСК/04.6_Фильтрация_и_Reranking.md` — sparse BM25 default

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| Sparse BM25 в Qdrant collection описан как default (если упоминается) | Production 4096d collections — **single-vector layout, без sparse**. BM25 fallback — SQLite FTS5 в `cache/docs-mcp/hybrid_search.db` | 🟠 | Уточнить состояние в production, явно пометить «sparse в Qdrant — Phase 9.3 candidate» |

**Action items:**
- [x] **A.4.6.1** Read весь файл, найти упоминания «BM25 sparse vectors в Qdrant»
- [x] **A.4.6.2** Добавить ссылку на §32.3 (Hybrid sparse+dense) как future work
- [x] **A.4.6.3** Уточнить SQLite FTS5 fallback path

### 3.2 `29_XSKILL_CONTINUOUS_LEARNING/29.4_Retrieval_и_Scoring.md` — collections re-embedded

| Заявлено | Факт | Severity | Action |
|----------|------|----------|--------|
| **«`skill_library` 768d nomic, 75 точек»** (line 9) | После Phase 9.1: re-embedded на Qwen3 4096d (80/82 skills populated) | 🟠 | Update таблица коллекций |
| **«`experience_embeddings` 768d nomic»** (line 10) | Re-embedded на Qwen3 4096d через `scripts/reembed_collection.py` (Phase 9.1 finale) | 🟠 | Update |

**Action items:**
- [x] **A.29.4.1** Update таблица коллекций (line 7-10): размерность 768→4096, model nomic-embed-text→Qwen3-Embedding-8B
- [x] **A.29.4.2** Footer-бокс: «Re-embedding в Phase 9.1 без regen (`scripts/reembed_collection.py`) — см. 31.3»

### 3.3 `19_ИНДЕКСАЦИЯ_ПРОЕКТОВ/` — может содержать старые BSL collection refs

**Action items:**
- [x] **A.19.1** `grep -rn "bsl_code_v[23]\|nomic-embed-text" "docs/framework documentation/19_ИНДЕКСАЦИЯ_ПРОЕКТОВ/"` — собрать упоминания
- [x] **A.19.2** Если есть — update на `bsl_code_v4_late` + Qwen3

---

## 4. Medium (🟡) findings

### 4.1 `03_ИНДЕКСАЦИЯ/` — chunk_size / overlap defaults

**Возможные несоответствия:**
- Если документ упоминает специфичные chunk_size для BSL — проверить против `src/bsl/semantic_search/services/bsl_chunker.py` (sliding window 1024/256 для XXL символов в Phase 8.12.5)
- Если общий chunk_size заявлен 500/100 — проверить актуальность

**Action items:**
- [x] **A.3.1** Read 03.x главы, найти упоминания chunk_size
- [x] **A.3.2** Cross-check с `src/pdf_framework/processing/splitter.py` defaults

---

## 5. Главы без серьёзных проблем (~15)

После выборочной проверки следующие главы написаны/обновлены недавно (2026-04) и **не требуют срочного refresh**:

| Глава | Last update / Status | Заметки |
|-------|---------------------|---------|
| 11_СИСТЕМА_СКИЛЛОВ | 2026-04 (актуальна) | Skills triade |
| 12_ДЕКОМПОЗИЦИЯ_ЗАДАЧ | 2026-04 | Triada-factory |
| 13_ТРИАДА_HOOK_SKILL_MCP | 2026-04 | Hook+Skill+MCP |
| 14_RALPH_WIGGUM | 2026-04 | Iterative loop |
| 15_TOKEN_ECONOMY | 2026-04 | Cost guidance |
| 16_ПОДКЛЮЧЕНИЕ_1С | 2026-04 | Platform integration |
| 17_ТЕСТИРОВАНИЕ_1С | 2026-04 (Phase 4 Stage 4a) | VA BDD |
| 18_AUTORESEARCH | 2026-04 | Autoresearch v1 |
| 20_AUTORESEARCH_V2 | 2026-04 | v2 split |
| 21_LLM_ROTATION | 2026-04 | Rotation service |
| 22_ANALYZE_1C_RESEARCH | 2026-04 | 1C research |
| 23_GLM_AGENT_FACTORY | 2026-04 | GLM Agents |
| 24_SPEC_DRIVEN_DEVELOPMENT | 2026-04 | OpenSpec MCP |
| 25_LEARNING_LOOP | 2026-04 | 5-phase loop |
| 26_LAZY_MCP | 2026-04 | Lazy proxy |
| 27_UNIFIED_MEMORY | 2026-04 | P0-P4 + hooks |
| 30_ЭФФЕКТИВНОСТЬ | 2026-04 | Efficiency |

> **Caveat:** «без серьёзных проблем» = на уровне overview-страницы. Внутри отдельных файлов (`<N>.2_*`, `<N>.3_*` ...) могут быть мелкие stale-ref'ы. Их можно оставить на следующую итерацию аудита (когда главы 02, 04, 28, 29 будут refreshed → можно прогнать ту же grep-методологию по остальным).

---

## 6. Mass `grep` shortlist для пользователя

При начале P1 §3 в главном roadmap'е — запустить:

```bash
cd "C:/1С-Framework/docs/framework documentation"

# 1. Stale embedding models
grep -rn "intfloat/multilingual-e5-large\|nomic-embed-text\|all-MiniLM-L6-v2" .

# 2. Stale Qdrant collections
grep -rn "bsl_code_v[23]\|_e5_legacy\|visual_grounding" .

# 3. Stale dimensions
grep -rn "768d\|1024d\b" . | grep -v "(legacy)\|(MRL)\|(deprecated)"

# 4. Stale Qdrant version
grep -rn "qdrant.*1\.1[5-6]\b" .

# 5. Broken §32 references (chapter 31 links)
grep -rn "§32\.\|roadmap.*§32" . | grep -v "260426_ROADMAP_PHASE_8"
```

Каждый match → confirm in production state → fix или add «(legacy)» annotation.

---

## 7. Action plan summary

| ID | Файл | Severity | Effort |
|----|------|----------|--------|
| A.2.1.* | 02.1_Установка.md | 🔴 | 10 min |
| A.2.2.* | 02.2_Конфигурация.md | 🔴 | 30 min |
| A.4.1.* | 04.1_Обзор_стратегий.md | 🔴 | 20 min |
| A.4.6.* | 04.6_Фильтрация_и_Reranking.md | 🟠 | 15 min |
| A.28.4.* | 28.4_Индексация.md | 🔴 | 20 min |
| A.29.4.* | 29.4_Retrieval_и_Scoring.md | 🟠 | 15 min |
| A.29.6.* | 29.6_Visual_Grounding.md | 🔴 | 15 min (banner + 2 fixes) |
| A.19.* | 19_ИНДЕКСАЦИЯ_ПРОЕКТОВ | 🟠 | 20 min (если есть проблемы) |
| A.3.* | 03_ИНДЕКСАЦИЯ | 🟡 | 15 min (verify) |
| **TOTAL** | 9 chapters | — | **~2.5 ч** |

**После закрытия:**
- [x] Final grep по mass shortlist (§6) — должен возвращать только legacy-аннотированные matches
- [x] Update §0 Status Dashboard в главном roadmap'е (P1 → 100%)

---

## 8. Связано

- Главный roadmap: [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §3
- Глава 01 audit: [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md)
- Tests audit: [`260430_AUDIT_TESTS_COVERAGE.md`](260430_AUDIT_TESTS_COVERAGE.md)
- Deps + CI audit: [`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md)
- Phase 8 roadmap: [`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) §27 cleanup, §30 timeline
- Глава 31 (production retrieval): [`../framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md)
