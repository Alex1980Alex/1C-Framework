# Roadmap — Memory Ingestion & Cross-Store Synchronization (§26)

> **Дата:** 2026-06-03 · **Статус:** PLANNED (дизайн + research готовы, реализация не начата) · **Родитель:** [260523 §26](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)
>
> Детальная дочерняя карта обзорной главы §26. Содержит per-phase deliverables + acceptance-критерии, по образцу [§25 → 260601](260601_ROADMAP_MEMORY_EFFECTIVENESS.md). Research — live WebSearch 2026-06-02 (атрибуция в §3) + code-grounded inventory (§2).

---

## 1. Краткая постановка

Машинерия памяти (§22 confidence / §24 surfacing / §25 self-tuning) — богатая на стороне **retrieval/governance**, но **нечем кормить**: `learned_patterns` = 22 точки (после dedup), `experience_embeddings`/`conversation_memory` = **0 writers**, skill-learning JSONL = 1 stale-запись. Система **асимметрична**: сильный приём знаний наружу (поиск), тонкий и силосный приём внутрь (запись).

Цель §26 — замкнуть **ingestion** (авто-наполнение по всем слоям) + **синхронизацию** (один факт = одна сущность `MemoryCube` + связи, а не независимые копии в каждом store), оставаясь bounded (governance/ForgetGate).

**Ключевой принцип [own]:** НЕ строить новую инфру — связать уже существующие мосты в авто-петлю:
- [`MemoryCube`](../../src/memory/orchestrator/memcube.py) — канонический sync-unit (уже умеет проецироваться: `to_ai_memory_row` / `to_vector_memory_payload` / `to_skill_learning_record` / `to_wiki_page` / `from_wiki_page`);
- [`link_registry`](../../src/memory/orchestrator/link_registry.py) — «один факт ↔ связи, не копии» (10 типов связей);
- [`WikiPromoter`](../../src/memory/librarian/wiki_promoter.py) — образец L2→L5 промоушена;
- §22 confidence + `ForgetGate` (`memory_forget`) — граница роста;
- `content_key()` = `sha256(content)[:16]` из [`dedupe_learned_patterns.py:55`](../../scripts/dedupe_learned_patterns.py#L55) — **idempotency-ключ cross-store** (анти-флуд + детект «один факт в ≥2 store»).

> **Коррекция master §26.3 P0:** канонический dedup-ключ — `content_key()` (`sha256`, первые 16 hex от полного контента), а НЕ `sha1(content[:200])` (приближение в обзорной главе). Везде в реализации использовать существующий `content_key`, не плодить второй хэш.

## 2. Инвентаризация (code-grounded, live 2026-06-02)

Силовая линия проблемы — таблица потоков (из §26.1, здесь с привязкой к файлам):

| Поток | Статус | Где / блокер |
|---|---|---|
| `save_pattern` → learned_patterns | AUTO-механизм, но **вызов только вручную** | [`vector_memory/server.py`](../../src/memory/vector_memory/server.py) — нет харвестера-вызывателя |
| session save (Stop) | ✅ AUTO | [`session-memory-save.py`](../../.claude/hooks/session-memory-save.py) — пишет в SQLite `memory_ai.db`, **НЕ** в паттерны |
| skill-learning `capture`→`confirm` | MANUAL | [`skill_learning/server.py`](../../src/memory/skill_learning/server.py) — **confirmed НИКОГДА не попадает в learned_patterns** (silo) |
| feedback-drafts | AUTO создание | [`shared/feedback_draft.py`](../../.claude/hooks/shared/feedback_draft.py) → `data/memory_drafts/` — нет промоушена в `MEMORY.md` (orphaned) |
| memory-ai → learned_patterns | MANUAL one-off | [`normalize_light_patterns.py`](../../scripts/normalize_light_patterns.py) — не ongoing |
| learned_patterns → wiki | MANUAL | `WikiPromoter` — нет cron |
| decay / dedup / archive | MANUAL | `export_graph_to_wiki`, `dedupe_learned_patterns.py` — нет cron |
| experience_embeddings / conversation_memory | **NONE** | `ConversationMemory` init-only, 0 writers |
| skill_library | MANUAL | [`index-skills-to-qdrant.py`](../../scripts/index-skills-to-qdrant.py) — не AUTO при добавлении скилла |
| cross-store dedup | **NONE** | один факт в memory-ai И learned_patterns = независимые копии |
| `conflict_resolver` | STUB | [`infrastructure/conflict_resolver.py`](../../src/memory/infrastructure/conflict_resolver.py) — задекларирован, не вшит в `route_and_save` |
| link_registry auto-links | PARTIAL | только на multi-target save, не на promotion/migration |

## 3. Research synthesis (live 2026-06-02, attributed)

- **mem0** [web] — память как **слой** поверх агента: авто fact-extraction + CRUD-retrieval. Урок: ingestion = отдельный авто-слой, не ручные вызовы.
- **Letta/MemGPT** [web] — 3-tier (core/recall/archival), агент «пейджит» память функциями. Урок: тиры + явные переходы.
- **Zep/Graphiti** [web] — темпоральный knowledge-graph движок памяти. Урок: связи между фактами (наш `link_registry`) первичны для sync.
- **Generative Agents** [web/arxiv 2404.00573] — `recency + importance + relevance`; **reflection** консолидирует episodic→semantic по эвристическим триггерам (*«user corrected date 3× → semantic prefers DD/MM/YYYY»*). Урок: консолидация = memory-ai→learned_patterns по триггеру кластеризации повторов.
- **Bounded/gated memory (CraniMem, arxiv 2603.15642; «Episodic Memory is the Missing Piece» 2502.06975)** [web] — dual-store с явными consolidation-pathways БЕЗ unbounded growth. Урок: `ForgetGate` как граница.
- **Внутреннее** [exp] — мосты уже есть (`MemoryCube`, `link_registry`, `WikiPromoter`, §22, dedup/normalize-скрипты, §24/§25).

## 4. Архитектура решения

```
        источники событий (хуки)                  консолидация            граница
  feedback-drafts ─┐                            ┌─ reflection (P2) ─┐
  session-lessons ─┼─► HARVESTERS (P1) ─► MemoryCube ──► learned_patterns ──► ForgetGate (P4)
  skill confirmed ─┘        │             (sync-unit)        │  ▲                  │
                            │             content_key        │  │ links            ▼
                            └─ idempotency ─┴── link_registry ┘  └── §22 confidence-gate
                                            │
                                  cross-store dedup/sync (P3)  ──► conflict_resolver (stub→active)
```

`MemoryCube` = single-source-of-truth, **проецируемый** в store'ы (а не копируемый); `content_key` = ключ идемпотентности; `link_registry` = связи `PROMOTED_TO`/`DERIVES_FROM`/`MIRRORS` вместо дублей.

---

## 5. Фазы (deliverables + acceptance)

### P0 — Контракты ingestion+sync (foundation) — ✅ DONE (2026-06-03)

**Deliverables:**
- D0.1 — добавить поле `content_hash` в `MemoryCube` (заполняется `content_key(content)` при создании); протащить в payload **всех** проекций (`to_vector_memory_payload` / `to_ai_memory_row` / `to_skill_learning_record`).
- D0.2 — единый «писатель»-контракт: документировать per-store, кто пишет, через какой MemCube-метод, с каким `content_hash`. Таблица в [27.12 Memory Systems Map](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md).
- D0.3 — ingestion-метрики (`ingest_rate`, `dup_rate`, `store_sizes`, `harvest_skipped`) в существующий [`MetricsCollector`](../../src/memory/infrastructure/metrics.py); проброс в §25 analyzer (`analyze_memory_effectiveness.py`).
- D0.4 — backfill: разовый проход проставляет `content_hash` существующим 22 паттернам (idempotent, dry-run by default, vector-backup).

**Acceptance:**
- [x] `MemoryCube(content=X).content_hash == content_key({"...": X})` — parity-тест (`test_content_hash.py::TestDedupeParity`).
- [x] Каждая из 3 проекций несёт `content_hash` в payload/row/record (parametrized unit-тест).
- [x] Ingestion-метрики пишутся (`ingest_metrics.record_ingest` → JSONL + counters); `memory_metrics`-провод к P1-харвестеру — при P1.
- [x] Backfill на реальном Qdrant: **23/23** точки получили `content_hash`, повторный запуск = no-op (`backfill_content_hash.py`).
- [x] Reversible: `from_dict` без `content_hash` пересчитывает из content (lazy default); backup записан при apply.

**Артефакты:** `src/memory/orchestrator/content_hash.py` (новый, canonical) · `memcube.py` (+`content_hash` поле/проекции) · `ingest_metrics.py` (новый, D0.3) · `scripts/backfill_content_hash.py` (новый, D0.4) · `dedupe_learned_patterns.py` (делегирует) · доки [27.12 §11](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md). Тесты: 30 unit (content_hash 19 + backfill 5 + ingest 6) + 12 memcube-wiki regression = 42 green.

### P1 — Авто-ingestion харвестеры (по всем слоям)

**Deliverables:**
- D1.1 *Patterns harvester* — Stop-хук (образец [`session-memory-save.py`](../../.claude/hooks/session-memory-save.py)) майнит подтверждённые feedback-drafts (`data/memory_drafts/`) + session-lessons → `MemoryCube` → `save_pattern`. **Gated:** `content_hash` dedup (skip если existing) + §22 confidence-floor + cap N/сессия (анти-флуд) + opt-out env.
- D1.2 *Skills harvester* — [`index-skills-to-qdrant.py`](../../scripts/index-skills-to-qdrant.py) → AUTO при изменении `.claude/skills/**` (PostToolUse:Write/Edit на skill-путь, либо Stop-batch). Idempotent по skill-hash.
- D1.3 *Experience/conversation решение (ADR)* — либо (a) вшить `ConversationMemory` writer (наполнить пустые коллекции из session-transcript), либо (b) **формально deprecate** обе коллекции (ADR + убрать из карты/skill). **Не держать мёртвые коллекции.** Решение фиксируется ADR в этой же папке.

**Acceptance:**
- [ ] Patterns harvester: на синтетическом drafts+lessons прогоне создаёт K cubes, повтор прогона = 0 новых (dedup PASS), флуд-cap срабатывает при >N.
- [ ] Harvester fail-soft: Qdrant/TEI down → хук не падает, exit 0, лог-warning.
- [ ] Skills harvester: добавление тест-скилла → AUTO upsert в `skill_library` без ручного запуска; удаление → stale-cleanup.
- [ ] ADR по experience/conversation принят и закоммичен; карта 27.12 приведена в соответствие (наполнено ИЛИ deprecated — не «0 writers без объяснения»).
- [ ] Все харвестеры reversible (opt-out env, документирован в CLAUDE.md).

### P2 — Консолидация episodic→semantic (reflection)

**Deliverables:**
- D2.1 *Reflection job* — кластеризует повторяющиеся episodic-факты (`memory_ai.db`) → консолидирует в semantic-паттерн (`learned_patterns`) по триггеру «N повторов / суммарная importance ≥ θ» (Generative Agents). Обобщить [`normalize_light_patterns.py`](../../scripts/normalize_light_patterns.py) из one-off в ongoing reflection-проход.
- D2.2 *Закрыть skill-learning silo* — мост confirmed `data/skill_learning/*.jsonl` → `learned_patterns` (через `MemoryCube.to_vector_memory_payload`), gated dedup+confidence.
- D2.3 — `link_registry` связь `DERIVES_FROM` от semantic-паттерна к исходным episodic-фактам (трассируемость консолидации).

**Acceptance:**
- [ ] Синтетический набор из M эпизодов «одна тема» → reflection создаёт 1 semantic-паттерн (не M), с `DERIVES_FROM` на источники.
- [ ] Триггер консолидации настраиваемый (N/θ), dry-run by default, reviewable (лог что бы консолидировалось).
- [ ] skill-learning silo: confirmed pattern появляется в `learned_patterns` после прогона; повтор = no-op.
- [ ] Консолидация не дублирует существующее (cross-store `content_hash` check ПЕРЕД записью).
- [ ] Все вставки проходят §22 confidence-gate (не флуд low-confidence).

### P3 — Cross-store синхронизация и дедуп

**Deliverables:**
- D3.1 *Cross-store index* — индекс `content_hash → [stores]` (детект «один факт в ≥2 store»). Источник правды дедупа уже есть (`content_key`); строим обратный индекс.
- D3.2 *conflict_resolver активация* — вшить [`conflict_resolver`](../../src/memory/infrastructure/conflict_resolver.py) (stub→active) в `route_and_save` + cross-store writes; стратегии `LAST_WRITE_WINS` / `SOURCE_PRIORITY` / `MERGE` (уже задекларированы в `ConflictStrategy`).
- D3.3 *Авто-links на promotion/migration* — `PROMOTED_TO` (learned→wiki), `MIRRORS` (один факт в 2 store как связь, не копия), `DERIVES_FROM`. `MemoryCube` = single-source, проецируемый в store'ы.

**Acceptance:**
- [ ] Cross-store index на реальных данных выявляет дубли memory-ai↔learned_patterns (если есть) — отчёт.
- [ ] При конфликте записи (один `content_hash`, разный контент) `conflict_resolver` применяет выбранную стратегию, пишет `ConflictRecord` (аудит).
- [ ] Promotion learned→wiki создаёт `PROMOTED_TO` link, НЕ вторую независимую сущность.
- [ ] `MIRRORS`-связь заменяет копию: federated search (`unified_search`) возвращает факт **один раз** (dedup по link), не дважды.
- [ ] Reversible: dry-run отчёт ПЕРЕД любым merge/delete; vector-backup.

### P4 — Scheduling & bounded governance

**Deliverables:**
- D4.1 *Scheduling* — manual-джобы (decay / dedup / promote / archive / reflection) → scheduled. Вариант A: `/schedule` cron; вариант B: Stop-cadence (раз в N сессий, sentinel-state как у `post-indexing-analyzer`). Выбрать по нагрузке.
- D4.2 *ForgetGate как граница* — `memory_forget` (archive/decay/delete) встроить в cadence как bound роста (CraniMem-урок); invariant-паттерны (§22 P3 `is_invariant`) исключены из time-archival.
- D4.3 *Дашборд* — ingestion-rate, cross-store-dup-rate, promotion-rate, store-sizes → в §25 reports (`data/reports/memory/`).

**Acceptance:**
- [ ] Scheduled-проход запускается без ручного триггера (cron-лог ИЛИ Stop-sentinel срабатывает раз в N).
- [ ] ForgetGate: при синтетическом наборе stale+low-conf паттернов archive срабатывает, invariant — нет.
- [ ] Store-sizes стабилизируются (не растут unbounded) на длинном прогоне — graph в §25 report.
- [ ] Полный цикл наблюдаем: ingestion → consolidation → sync → forget виден в `confidence-lifecycle.log` + новый ingestion-лог.
- [ ] Все cadence-джобы opt-out + reversible.

---

## 6. Guardrails (для всех фаз)

dry-run by default + vector-backup (паттерн dedup/normalize) · §22 confidence-gating · `content_hash` dedup (анти-флуд + cross-store idempotency) · human-confirm для курируемого `.md` (`MEMORY.md` остаётся ручным — drafts только предлагают) · `ForgetGate` как bound против unbounded growth · полностью reversible (opt-out env на каждый харвестер/джоб) · fail-soft (Qdrant/TEI down → хук не падает).

## 7. Метрики (→ §25 analyzer)

| Метрика | Источник | Назначение |
|---|---|---|
| `ingest_rate` | cubes/сессию по store | наполняемость |
| `dup_rate` | skipped-by-hash / attempted | здоровье анти-флуда |
| `cross_store_dup_rate` | факты в ≥2 store / total | дивергенция |
| `promotion_rate` | L2→L5 / период | живость консолидации |
| `store_sizes` | points/rows per store | bounded-рост |
| `harvest_skipped` | gate-drops (conf/cap/hash) | калибровка порогов |

## 8. Зависимости и риски

- **Зависит от:** §22 (confidence), §24 (surfacing), §25 (метрики/self-tuning — туда же ingestion-метрики), `MemoryCube`/`link_registry`/`WikiPromoter`/`conflict_resolver`/dedup-скриптов.
- **Риски:** флуд паттернами → dedup + confidence-gate + cap + ForgetGate; cross-store дивергенция → `MemoryCube` single-source + связи вместо копий; плохие авто-промоушены → gated + reviewable + reversible; «мёртвые» коллекции → P1 D1.3 решение (наполнить ИЛИ deprecate ADR).
- **Не входит:** изменение §22-математики и §24-surfacing (только кормим данными). Online-MAB тюнинг ingestion — future (после §25 B3).

## 9. Открытые вопросы (решить при старте фазы)

- **Q1 (P1 D1.3):** experience_embeddings/conversation_memory — наполнить или deprecate? → **РЕШЕНО (2026-06-03): DEPRECATE обе** — роль покрыта episodic (`memory_ai.db`) → reflection → semantic (`learned_patterns`); популяция = net-negative (cross-store дубликаты). ADR: [260603_ADR_Q1_EXPERIENCE_CONVERSATION_COLLECTIONS.md](260603_ADR_Q1_EXPERIENCE_CONVERSATION_COLLECTIONS.md). Реализационные шаги 1-7 — в составе P1 close.
- **Q2 (P2):** триггер reflection — фиксированный N-повторов или адаптивный по importance-сумме? → начать с фиксированного, параметризовать.
- **Q3 (P4 D4.1):** scheduling через `/schedule` cron vs Stop-cadence? → решить по реальной нагрузке после P1-P3 (cadence проще/безопаснее на старте).

## 10. Прогресс (§18-лог)

| Дата | Веха | Коммит |
|---|---|---|
| 2026-06-03 | Дочерняя карта §26 создана (PLANNED) | ca12b2f45 |
| 2026-06-03 | **P0 DONE** — content_hash foundation (D0.1-D0.4), 42 теста, backfill 23/23 на Qdrant | (этот) |
| 2026-06-03 | **Q1 РЕШЁН (ADR)** — experience_embeddings/conversation_memory → DEPRECATE; блокер P1 close снят | (этот) |
| 2026-06-03 | **Q1 ИСПОЛНЕН (D1.3)** — обе коллекции dropped (snapshot+delete, 0 pts), surfacing-arms убраны, конфиги/карта/stub вычищены; 29/29 hook-тестов, code-verify behavior-preservation PASS. P1 остаётся открыт: D1.1 patterns-harvester + D1.2 skills-harvester | af84f4d0e |

> Обновлять при старте/закрытии каждой фазы (P0…P4): отметка DONE + ключевые коммиты + отклонения от плана.
