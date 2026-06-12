# 260612 — Roadmap: полная проверка memory-ai (EPISODIC, SQLite) — максимальное тестирование входа и выхода

> Статус: PROPOSED · Создан: 2026-06-12 · Источник: анализ блока `memory-ai` карты
> [27.12 §map](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md), по образцу
> [260611 skill-learning revival](260611_ROADMAP_SKILL_LEARNING_REVIVAL.md) + методика chain-testing
> [260610](260610_ROADMAP_MEMORY_CHAIN_TESTING.md)
> Связанные: [260609 P1 write-contract](260609_ROADMAP_MEMORY_PIPELINE_HARDENING.md), [260611 governance wiring](260611_ROADMAP_MEMORY_GOVERNANCE_WIRING.md), §26 P2 reflection

## 1. Инвентаризация (фактическое состояние 2026-06-12)

`data/memory_ai.db`, единственная таблица `important_messages` (9 колонок, PK `id` TEXT,
индексы created/category/importance): **107 строк**, окно 2026-04-04 → 2026-06-12.
Категории: `session_summary` 68 (avg imp 0.76), `decision`/`preference`/`reference` по 7,
`feedback` 3 (avg 0.85), хвост из 1-2. Аномалий типа `importance` нет (F2-фикс жив),
пустого content нет. **Но:** 5 dup-групп по content (legacy, до P1.3-дедупа);
`content_hash` в metadata лишь у **12/107**; `indexed_in_qdrant`: 74×`0` / 33×`1`.

**Писатели (вход), 6 живых:**
| # | Писатель | Канал | Контракт |
|---|----------|-------|----------|
| W1 | `save_important_message` | MCP `ai_memory/server.py` | content-equality dedup (P1.3), `_coerce_importance` (F2) |
| W2 | `session-memory-save.py` | Stop-хук | `session_summary`, dedup по session_id/date, auto-importance 0.5-0.95 |
| W3 | `route_and_save` target=memory-ai | orchestrator | CREATE-снапшот versioning (F8), `content_hash` в metadata |
| W4 | propagation-handler MEMORY_AI | orchestrator | `importance ± delta` clamp [0,1], UPDATE-снапшот, breaker `propagation:memory-ai` |
| W5 | rollback writeback | orchestrator `_apply_version_to_store` | content + importance (F16) |
| W6 | `memory_ttl_cleanup` / `delete_message` | orchestrator / MCP | DELETE (без tombstone) |

**Читатели (выход), 6 живых:**
| # | Читатель | Канал | Механика |
|---|----------|-------|----------|
| R1 | `memory-first-hook` Layer 1 | UPS-хук, weight 0.30 | top-**200** by importance → token-overlap + tag-boost, SCORE_THRESHOLD 0.3 |
| R2 | `AiMemorySearchAdapter` | `unified_search` | ai-плечо federated search (sources_failed честный, F2/F12) |
| R3 | `get_important_messages` / `search_messages` / `get_categories` | MCP | search = **голый SQL `LIKE`** по content/tags |
| R4 | reflection (§26 P2) | `scripts/reflect_memory.py` | episodic→semantic кластеры → `learned_patterns` + DERIVES_FROM |
| R5 | `cross_store_index`/`sync` | §26 P3 | MIRRORS-консолидация дублей |
| R6 | dashboard / `record_store_size` | §26 P4 + §27 | store_sizes в ingest-лог |

## 2. Проблема (что нашла инвентаризация)

- **G1 — мёртвый и ОПАСНЫЙ контур** `scripts/deferred_qdrant_indexing.py` (P5.3): эмбеддит
  multilingual-E5 **1024d** и upsert'ит в `learned_patterns`, который с Phase 8/9.1 —
  **4096d Qwen3**. Запуск сегодня = dimension-mismatch fail (лучший случай) или мусорные
  точки. Флаг `indexed_in_qdrant` полуживой: 33×`1` проиндексированы в E5-эпоху
  (эти точки умерли вместе с legacy-коллекциями 2026-04-30), 74×`0` никогда не уйдут.
- **G2 — выход слеп к морфологии**: `search_messages` = `LIKE %q%` без casefold/стемминга
  (кириллические морфоформы не матчатся — та же болезнь, что лечил P2.3 у skill-learning);
  R1 берёт только top-200 по importance — при росте БД важное за пределами окна невидимо,
  recency не учитывается вовсе.
- **G3 — гигиена данных**: 5 legacy dup-групп; `content_hash` у 12/107 → `cross_store_sync`
  / `fact-trace` не видят 89% эпизодики; tags — JSON-строки, ищутся `LIKE`-ом.
- **G4 — retention отсутствует**: эпизодика растёт unbounded (68 session_summary за 2 мес);
  importance статична (нет decay-аналога §22), ForgetGate покрывает только vector;
  `memory_ttl_cleanup` удаляет лишь то, что вручную попало в TTL-ledger.
- **G5 — delete без tombstone**: `delete_message`/TTL-delete не чистят link_registry →
  потенциальные dangling MIRRORS/DERIVES_FROM на удалённые id.
- **Тестовое покрытие входа/выхода фрагментарно**: W1/W3/W4/W5 покрыты точечно
  (write-contract, propagation, governance), W2/W6 и ВСЕ читатели R1-R6 — без
  систематических цепочек вход→выход.

Целевая модель: **каждый вход и каждый выход memory-ai покрыт исполняемой цепочкой
(unit + live), данные несут content_hash, выход нормализован, retention управляем.**

## 3. Тест-карта цепочек вход→выход (ядро роадмапа)

Методика 260610: цепочка = вход → store-инвариант → выход(ы); прогон сначала unit
(tmp-БД через `MEMORY_AI_DB_PATH`), затем live MCP/hook. Вердикт в §18.

### Блок A — входы

| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| A1 | W1 happy + dedup | `save_important_message` ×2 одинаковый content → `get_important_messages` | 1 строка, `action=dup` на повторе, `content_hash` в metadata |
| A2 | W1 importance coercion | save с importance `"high"`/`1.5`/`-1`/`None` | строка REAL ∈ [0,1], label-map работает (F2 не регрессировал) |
| A3 | W2 Stop-хук e2e | реальный Stop с diff/commits → строка `session_summary` | dedup по session_id (2-й Stop той же сессии = 0 новых), auto-importance в [0.5,0.95], wiki-log строка |
| A4 | W3 route_and_save | route контента класса decision/fact → memory-ai | строка + CREATE-снапшот в versioning + `content_hash` + ingest-событие `saved` |
| A5 | W4 propagation | `propagate_update` на episodic-узел с link | importance изменился на ±delta (clamp), UPDATE-снапшот, breaker закрыт; fail-инъекция → `failed_entities` |
| A6 | W5 rollback | history → rollback к v1 | content+importance восстановлены (F16), `applied:true, fields` |
| A7 | W6 delete-цикл | `delete_message` + `memory_ttl_cleanup` | строка удалена, ответ честный; **link_registry: рёбра на id — что с ними?** (вход в P2.G5) |
| A8 | Конкурентный вход | W1 ∥ W2 ∥ W4 на одной БД (threads) | WAL/busy-timeout не теряет записи, нет `database is locked` наружу |

### Блок B — выходы

| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| B1 | R1 surfacing | известный факт в БД → UPS-промпт с его терминами | факт в `[MEMORY CONTEXT]`, `layers.sqlite>0` в surfacing-логе; морфоформа запроса тоже матчится |
| B2 | R1 за пределами top-200 | факт importance 0.4 при 200+ строках выше | честно зафиксировать невидимость (бейзлайн для P2.G6) |
| B3 | R2 unified_search | query по эпизодике → ai-плечо | результат с `episodic:memory-ai:<id>`, при сломанной БД → `sources_failed:["memory-ai"]` |
| B4 | R3 search_messages | поиск точной подстроки / морфоформы / по тегу | бейзлайн LIKE: что находит, что нет (вход в P2.G2) |
| B5 | R4 reflection | ≥3 однотемных эпизода → `reflect_memory.py --apply` | 1 паттерн в `learned_patterns` + DERIVES_FROM на источники, идемпотентен (re-run = 0) |
| B6 | R5 cross-store | один факт в memory_ai + learned_patterns | MIRRORS mirror→canonical (`learned_patterns` canonical), dup_rate в дашборде |
| B7 | R6 наблюдаемость | W1-W6 события | `record_ingest(memory_ai, …)` нормализуется envelope, `fact-trace --key <content_hash>` тредит W→R5 |

### Блок C — отказы (honest-failure, контракт 260611)

| # | Цепочка | Критерий |
|---|---------|----------|
| C1 | БД залочена/отсутствует при R1/R2 | хук молчит fail-soft, `sources_failed` честный, Stop не ломается |
| C2 | Битая строка (malformed tags JSON / NULL category) | читатели не падают, строка скипается с трейсом |
| C3 | W4 handler-исключение ×5 | breaker `propagation:memory-ai` OPEN → `failed:circuit_open`, `memory_circuit_reset` чинит |

## 4. Фазы

### P0 — Обезвреживание + гигиена данных (фундамент)

| # | Задача | Файлы | Критерий |
|---|--------|-------|----------|
| P0.1 | **G1**: `deferred_qdrant_indexing.py` — ретирование (в `scripts/attic/`) ИЛИ rewire на TEI 4096d + отдельную коллекцию (НЕ `learned_patterns` — эпизодика ≠ семантика, §26 Q1 ADR); решение зафиксировать ADR-строкой. Флаг `indexed_in_qdrant`: 33×`1` сбросить (точки мертвы с 2026-04-30) | `scripts/`, миграция | запуск скрипта не может испортить production-коллекцию |
| P0.2 | **G3**: backfill `content_hash` в metadata всех 107 строк (общий `content_hash.hash_content`); merge 5 dup-групп (старейший выживает, рёбра переносятся) | `scripts/memory_ai_backfill.py` (новый, dry-run default) | 107/107 с hash; dup-групп 0; fact-trace видит эпизодику |
| P0.3 | Тест-фикстура: `MEMORY_AI_DB_PATH` уважается ВСЕМИ читателями/писателями (аудит — grep хардкодов `data/memory_ai.db`) | `server.py`, orchestrator, хуки | unit-цепочки не трогают production-БД |
| P0.4 | A8: включить WAL + busy_timeout в обоих местах подключения (server.py, orchestrator) если ещё нет | `server.py`, orchestrator | конкурентный тест A8 зелёный |

### P1 — ВХОД: цепочки A1-A8 исполняемы

- Unit-слой: `tests/unit/test_memory_ai_chains.py` — A1/A2/A4/A5/A6/A7/A8 на tmp-БД
  (паттерн `test_skill_learning_revival.py`: все silo в tmp, monkeypatch).
- Live-слой: A3 (реальный Stop), A5/A6/A7 живыми MCP-tools после `/mcp reconnect`;
  вердикты в §18 (методика 260610 D-прогонов).

### P2 — ВЫХОД: цепочки B1-B7 + фиксы слепоты

| # | Задача | Механизм |
|---|--------|----------|
| P2.G2 | `search_messages` + `AiMemorySearchAdapter`: casefold + RU-стемминг (готовый `_sl_tokenize` из orchestrator — переиспользовать, не копировать) поверх LIKE-предфильтра; B4 re-run фиксирует прирост | `ai_memory/server.py`, orchestrator |
| P2.G6 | R1: top-200 → score-кандидаты с учётом recency (`importance × exp(-age)` или `ORDER BY importance DESC, created_at DESC` + поднять окно с замером латентности; budget 200ms жёсткий) | `memory-first-hook.py` |
| P2.G5 | A7-хвост: delete → каскадная чистка/пометка рёбер link_registry (или tombstone-строка) | orchestrator |
| P2.B5 | reflection: B5-прогон live + закрепление идемпотентности тестом | `shared/reflection.py` |

### P3 — Retention (эпизодика не должна расти вечно)

| # | Задача | Механизм |
|---|--------|----------|
| P3.1 | Episodic decay: lazy importance-decay при чтении (аналог §22 lazy-on-read; БЕЗ записи на hot-path) — старые session_summary ранжируются ниже | R1/R2 read-пути |
| P3.2 | Job `archive_episodic` в `memory_maintenance.py`: session_summary старше N дней (default 90) и importance < порога → archive-пометка в metadata (invalidate-not-delete, инвариант §22 P3); R1/R2 фильтруют archived | `scripts/memory_maintenance.py`, dry-run default |
| P3.3 | Reflection-каденс: перед архивацией кластер консолидируется в semantic (B5) — знание не теряется, эпизод уходит | связка P3.2 ↔ R4 |

### P4 — Наблюдаемость и приёмка

- `record_ingest(memory_ai, …)` по всем W1-W6 (аудит: W2/W6 сейчас эмитят?) + B7 fact-trace.
- **Acceptance-окно 2 недели** (автоматизация по образцу
  [`skill_learning_acceptance.py`](../../scripts/skill_learning_acceptance.py) + SessionStart-хук
  с дневным sentinel и самотерминацией по «Acceptance вердикт: <итог>» в §18 — переиспользовать
  каркас, не копипастить):
  ≥5 новых эпизодов вне `session_summary`; B1-морфоформа всплывает в surfacing-логе
  (`layers.sqlite>0`); dup-события memory_ai ≠ 0; 0 строк без `content_hash`;
  reflection-прогон сконсолидировал ≥1 кластер; archive-job исполнился ≥1 раз без потерь.

## 5. Порядок и оценка

Inventory уже сделан (этот документ). P0 (0.5-1d, G1 — решение + миграция) →
P1 unit-цепочки (1d) → P2 (1-1.5d: G2 переиспользует готовый стеммер, G6 — замер до правки) →
P1 live-прогоны + P3 (1d) → P4 (0.5d каркас + 2 недели наблюдения). Учитывать
[[project-roadmap-audit-pattern]]: перед каждой фазой — повторная инвентаризация
(часть могла закрыться смежными roadmap'ами; W4/W5 уже частично покрыты 260609/260611).

## 6. Риски

- **G1-миграция**: сброс `indexed_in_qdrant` без проверки реального состояния
  `learned_patterns` может породить повторную индексацию мусора, если контур когда-нибудь
  оживят — сначала verify точек по детерминированным uuid5-id, потом сброс.
- **P2.G6 (окно R1)**: расширение скана top-200 → full — это hot-path UPS (бюджет 200ms);
  любое изменение только с per-stage таймингом в surfacing-логе (§24.4) до/после.
- **P3 retention vs курируемая память**: `decision`/`preference`/`feedback` — НЕ архивировать
  по возрасту (аналог invariant-типов §22 P3); только `session_summary`/`general`.
- **SQLite concurrency**: WAL смягчает, но не устраняет писатель-писатель гонки;
  цепочка A8 обязана гоняться в CI, не только локально.
- **Двойной счёт с vector**: reflection (R4) и cross-store sync (R5) оба создают
  semantic-копии эпизодики — P3.3 должен опираться на общий `content_hash`, иначе
  один факт разъедется (риск §4 из 260611 дословно применим).

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-12 | Roadmap создан | Инвентаризация: 107 строк / 6 писателей / 6 читателей; G1 (E5 1024d → 4096d коллекция, опасный мёртвый контур), G2 (LIKE без морфологии), G3 (content_hash 12/107, 5 dup-групп), G4 (retention нет), G5 (delete без tombstone); тест-карта A1-A8 / B1-B7 / C1-C3 |
| 2026-06-12 | **P0 DONE** + ADR-G1 | **ADR**: контур ретирован (`scripts/attic/deferred_qdrant_indexing.py`), НЕ rewire — эпизодика ≠ семантика (§26 Q1), sanctioned-путь = reflection. **Re-inventory поправил роадмап**: из 33 флагов `indexed_in_qdrant=1` живы 18 (re-embedded 4096d при Qwen3-миграции, payload в т.ч. `source:memory_ai_session`) — сброшены только 15 мёртвых (verify uuid5 ДО сброса, риск §6 отработан). `memory_ai_backfill.py --apply`: hash 98/98, 5 dup-групп → 0 (старейший выжил, 16 рёбер перенесено, 107→98 строк). P0.3: `ai_memory/db.py` (resolve+WAL+busy_timeout), env-override во всех читателях/писателях (9 мест orchestrator + 3 хука + 4 скрипта). P0.4: `journal_mode=wal` персистентно |
| 2026-06-12 | **P1 unit DONE** | `tests/unit/test_memory_ai_chains.py` — 16 PASS: A1 (dedup + hash в metadata + readback), A2 (×5 coercion), A3-lite (W2: hash, session-dedup, importance∈[0.5,0.95]), A4 (`_save_to_target` row+hash+label-coercion), A7 (honest delete + G5-каскад), A8 (4×25 конкурентных писателей, 0 потерь, wal), B4 (морфоформы), G6/P3.1 (decay-ranking), P3.2 (archive job + reader-filter + идемпотентность), C2 (битые tags/category/metadata). A5/A6 — уже покрыты `test_propagation_honest`/`test_governance_wiring` (re-inventory §5, не дублированы). B5-идемпотентность — `test_reflection.py::test_rerun_idempotent` (существовал) |
| 2026-06-12 | **P2 DONE** (G2/G5/G6/C2) | G2: стеммер → `src/memory/text_norm.py` (single-source, orchestrator алиасит), `search_messages` + `AiMemorySearchAdapter` матчат RU-морфоформы (LOWER/LIKE был слеп к кириллице); G6: R1 окно 200→500 + `created_at` recency-ordering + env `MEMORY_SQLITE_SCAN_LIMIT`, замер 8.5ms cold (бюджет 200ms, запас 23×); G5: `delete_message` → `links_removed` (прямой SQL по `LINK_REGISTRY_PATH`), TTL-delete → `delete_links_for_entity` + `store_actions.links_removed`; C2: `_safe_json` в читателях server.py + fail-soft tags/created_at в адаптере |
| 2026-06-12 | **P3 DONE** | `ai_memory/retention.py`: P3.1 lazy decay-on-read (half-life 90d, только `session_summary`/`general` — курируемые категории инвариантны, риск §6) в R1+R2; P3.2 `archive_episodic` job в maintenance-каденсе (>90d & imp<0.8 → `metadata.archived_at`, invalidate-not-delete, R1/R2 фильтруют, идемпотентен); P3.3 каденс-инвариант: job после reflect — кластер консолидируется до архива |
| 2026-06-12 | **P4 DONE** (каркас) | W2 штампует `content_hash` + `record_ingest(saved)`, W6 эмитит `record_ingest(deleted)` — W1-W6 видны fact-trace (B7). Acceptance-окно 12→26 июня: `scripts/memory_ai_acceptance.py` (6 критериев) + SessionStart `memory-ai-acceptance-on-start.py` (дневной sentinel, самотерминация по «Acceptance вердикт: <итог>» здесь в §18); каркас общий — `scripts/acceptance_common.py` + `hooks/shared/acceptance_watch.py`, skill-learning-пара отрефакторена на них (reuse, не копипаст). День 1: sqlite_fired=3/5, hash_complete=OK |
| 2026-06-12 | Верификация | Гейт `-m unit`: **1452 passed** (16 новых); ruff clean; maintenance dry-run с `archive_episodic` OK; smoke хуков subprocess'ом OK. ⚠ Pending live-слой (после `/mcp reconnect`): A3 реальный Stop, A5/A6/A7 живыми MCP-tools, B1 морфоформа в surfacing-логе, B3 unified_search, B6 cross-store MIRRORS, B7 fact-trace по hash; C1 — fail-soft подтверждён кодом, live не гонялся |

**Acceptance вердикт: PENDING** (окно открыто до 2026-06-26; финал зафиксирует строку «Acceptance вердикт: PASS/FAIL»).
