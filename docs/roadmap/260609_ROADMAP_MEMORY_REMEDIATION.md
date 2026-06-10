# 260609 — Roadmap: ремедиация Unified Memory (расхождения карты 27.12 + сломанные части)

> **Источник:** аудит при написании глав-детализаций [27.12.1–27.12.7](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) (2026-06-09): каждый блок мастер-схемы сверен с кодом + **эмпирическая проверка живых sink'ов/БД** (lifecycle-log, surfacing-log, link_registry, memory_ai.db, events.*, maintenance-runs).
>
> **Главный вывод:** retrieval-половина системы работает (surfacing инжектит, харвестеры наполняют, maintenance dry-run ходит), но **петля обратной связи §22 разомкнута в production с момента создания** — ни одного реального reinforce за всю историю. Всё, что зависит от роста confidence (gating-ранжирование, wiki-promote, forget-staleness, cascade), работает в «замороженном» режиме prior 0.70.

---

## 1. Методика

1. 7 глав-детализаций: построчная сверка документации с кодом `src/memory/` + `.claude/hooks/` (расхождения помечены ⚠ в главах).
2. Эмпирика (2026-06-09): подсчёт событий по типам в `confidence-lifecycle.log`, классификация session/pattern id (тестовые фикстуры vs реальные), латентности `memory-first-surfacing.log` (n=272), содержимое `link_registry.db`, наличие/размер всех sink'ов, симуляция вызова `reinforce_session` из контекста хука.

---

## 2. Сломанные части (подтверждено эмпирически)

### A1 🔴 CRITICAL — Петля reinforcement не работала ни разу

**Факт:** в `confidence-lifecycle.log` **0 production-событий** `session`/`session_error`/`reinforce` — все 135 `session` и 48 `reinforce(_error)` имеют тестовые id (`s1`, `s-cap`, `idem-ses`, `pid-err`, `pid-1`). При этом мост C1 жив: 28 файлов `surfaced-patterns-<uuid>.json` с реальными сессиями копятся впустую. Единственный `apply` — 2026-05-31 (smoke).

**Следствия (каскадная блокировка):** все паттерны заморожены на prior 0.70 / `application_count≈0` → confidence-gating §24 деградирует до «пропустить всех» → wiki-promote gate (`conf≥0.8 & count≥5`) **недостижим** (0 drafts за всю историю — подтверждено) → forget-staleness меряет «простой» у паттернов, которые физически не могут получить apply → `_cascade_confidence` мёртв (нечего каскадировать).

**Корневые причины (по коду [session-memory-save.py:280-302](../../.claude/hooks/session-memory-save.py)):**
1. **Структурный баг потока:** `reinforce_session` вызывается ПОСЛЕ early-return'ов `is_meaningful` и `already_saved` (дедуп «1 сводка в день»). Все Stop'ы кроме первого-за-день → reinforce пропущен by design.
2. **Бюджет:** на первом-за-день прогоне до строки 297 идут git diff/status/log (большой репозиторий) + SQLite; затем `reinforce_session` лениво импортирует `qdrant_client` (+~1s) и делает до 50 retrieve/set_payload (timeout 2s каждый) — при `timeout: 5` в settings.json процесс убивается до финального `log_event`.
3. **Маскировка:** `except Exception: pass` (строка 298) — ни одна из причин не оставляет следа.

*Примечание: симуляция `reinforce_session('diag', True)` из repo-cwd под `.venv` python — работает и логирует. Ломается именно прохождение до этой строки в реальном Stop-контексте.*

### A2 🔴 HIGH — Тесты пишут в production-sinks и production-граф

**Факт:** pytest-прогоны оставили в **реальном** `confidence-lifecycle.log` 183 фикстурных события (27 прогонов × набор), а в **реальном** `data/link_registry.db` — 5 мусорных рёбер (`test-source-001`, `orphan-src`, `verify-src-42`, …). Загрязняется §27 observability (error-rate, fact-trace) и граф, по которому ходит реальный `_cascade_confidence`.

### A3 🟠 HIGH — Surfacing систематически за бюджетом

**Факт (n=272):** p50 = **3.30s** при `TOTAL_BUDGET=3.0s`; 173/272 (64%) over-budget; p95 = 4.14s; max 4.69s при hard-kill 5s. Любая деградация TEI/Qdrant → молчаливый обрыв инъекции.

### A4 🟠 HIGH — Execution-cache §24 фактически не работает

**Факт:** 1 cache-hit на 272 вызова (**0.4%**). Ключ = exact-match отсортированных токенов промпта — реальные промпты почти никогда не повторяются дословно. ~2s экономии на hit не реализуются; вся стоимость A3 платится каждый раз.

### A5 🟡 MEDIUM — 40% прогонов surfacing впустую

**Факт:** 110/272 `outcome: no-results` — при p50 3.3s это ~6 минут/день чистых затрат без инъекции. Связано с A4 (пустые результаты кэшируются, но cache не хитует).

### A6 🟡 MEDIUM — Write-контракт §26 не выполняется прямыми писателями

`save_pattern` / `route_and_save._save_to_target` / `save_important_message` / `capture_pattern` не проставляют `content_hash`, не дедупят, не зовут `record_ingest` (контракт реализован **только** харвестерами). Записи этих путей невидимы для cross-store-sync M2 и плодят дубликаты. Плюс `_save_to_target` fail-soft → `success:true` при молча упавших target'ах. (Практический масштаб пока мал: `memory-routing.log` — 5 событий.)

### A7 🟡 MEDIUM — Migrate-цепочка не доходила до записи

Maintenance cadence: 2 прогона, оба `applied: false` (dry-run default). `promote` — apply-only → 0 wiki-drafts за всю историю. Включать apply ДО починки A1 бессмысленно (gate недостижим) — зависимость A1 → A7.

### A8 ⚪ LOW — Мёртвые/неиспользуемые контуры

- `memory-read.log` отсутствует → `unified_search` в реальной работе не используется (orchestrator MCP практически не поднимается; `memory-routing.log` — 5 строк).
- `data/services/versions.jsonl` / `ttl.jsonl` отсутствуют → Versioning/TTL services не использовались ни разу.
- PropagationEngine (контур 3.2) — «simulate success» без `update_handlers`: BFS/лог реальны, мутаций нет.
- `memory-circuit.log` отсутствует — CB ни разу не переходил состояний (это норм).

---

## 3. Расхождения код ↔ документация (без поломки runtime)

| # | Расхождение | Где зафиксировано |
|---|---|---|
| B1 | `save_to_wiki_log`/`try_promote_patterns`/`_emit_langfuse_span` — стабы (PR#2-регрессия), док заявляет wiki-log | [27.12.1 §5](../framework%20documentation/27_UNIFIED_MEMORY/27.12.1_Блок_Вход_Запись.md) |
| B2 | 27.2: LinkType=6 (реально 10), формулы Propagation, поля MemCube — устарели | [27.12.2](../framework%20documentation/27_UNIFIED_MEMORY/27.12.2_Блок_Координация.md) |
| B3 | pdf-docs = SQLite FTS5 + опц. Qdrant, а не «Qdrant framework collections» (27.12 §2) | [27.12.3 §4](../framework%20documentation/27_UNIFIED_MEMORY/27.12.3_Блок_Хранилища.md) |
| B4 | 27.3/27.10: старые веса слоёв (0.35/0.40/0.25), бюджет 4s, плечи exp/conv (удалены §26 Q1) | [27.12.4](../framework%20documentation/27_UNIFIED_MEMORY/27.12.4_Блок_Выход_Чтение.md) |
| B5 | Харвестеры не бампают epoch → новые паттерны невидимы surfacing'у до 5 мин | [27.12.1 §10](../framework%20documentation/27_UNIFIED_MEMORY/27.12.1_Блок_Вход_Запись.md) |
| B6 | EventStore: `max_hot_buffer_mb` объявлен, не используется; Audit default-путь `data/audit/` vs фактический `data/services/` | [27.12.5 §2.3](../framework%20documentation/27_UNIFIED_MEMORY/27.12.5_Блок_Отдельно.md) |
| B7 | Versioning `max_versions=100` прунит только in-memory cache, JSONL растёт вечно | [27.12.6 §2](../framework%20documentation/27_UNIFIED_MEMORY/27.12.6_Блок_Governance.md) |
| B8 | vector-memory: docstring «1024d» stale; описание `decay_confidence` «deleted» vs реальный archive; docstring хука «2s budget» stale | [27.12.3 §2](../framework%20documentation/27_UNIFIED_MEMORY/27.12.3_Блок_Хранилища.md), [27.12.4](../framework%20documentation/27_UNIFIED_MEMORY/27.12.4_Блок_Выход_Чтение.md) |
| B9 | skill-learning: rewrite `pending_patterns.jsonl` без atomic `os.replace`; memory-ai/link_registry без WAL | [27.12.3 §3,§7](../framework%20documentation/27_UNIFIED_MEMORY/27.12.3_Блок_Хранилища.md) |
| B10 | `memory_forget` (MCP) не делает авто-sweep (пустой candidates=[]), стрелка §8 на деле реализована maintenance-вариантом | [27.12.6 §6](../framework%20documentation/27_UNIFIED_MEMORY/27.12.6_Блок_Governance.md) |
| B11 | TTL `is_expired()` для незарегистрированной сущности = True («unknown=expired») — ловушка семантики | [27.12.6 §1](../framework%20documentation/27_UNIFIED_MEMORY/27.12.6_Блок_Governance.md) |

---

## 4. Дорожная карта

Зависимости: **P0.1 разблокирует** P2.1 (promote/forget со смыслом) и оживляет cascade; **P0.2 — предусловие** доверия к любым метрикам §27.

### P0 — Замкнуть петлю + чистые данные (1-2 дня)

| ID | Задача | Содержание | Acceptance |
|---|---|---|---|
| **P0.1** | Reinforce-мост в production | (a) Вынести reinforce из `session-memory-save` в **отдельный Stop-хук** `pattern-reinforce-stop.py` (или вызвать ДО early-return'ов): свой timeout 10-15s, async, без зависимости от дедупа сводок; (b) заменить `except: pass` на `log_event("session_error", …)`; (c) cap кандидатов согласовать с бюджетом (напр. 10 на прогон) | После сессии с коммитом: событие `session` с реальным 8-hex sid и `applied>0` в lifecycle-log; `get_pattern` показывает `succ>0`, confidence ≠ 0.70; файлы surfaced-patterns консьюмятся |
| **P0.2** | Изоляция тестов от prod-sinks | conftest-фикстура (autouse для memory-тестов): `CLAUDE_CACHE_DIR=tmp_path`, `LINK_REGISTRY_PATH`/db-path override (добавить env-хук в `lifecycle_log.py` уже есть — проверить остальные писатели: link_registry default-путь, ingest_metrics) | `pytest tests/ -m unit` не меняет ни одного файла в `.claude/cache/` и `data/` (сравнение mtime/size до-после) |
| **P0.3** | Чистка загрязнений | Скрипт-однострочник: удалить из `link_registry.db` рёбра с фикстурными id (`test-*`, `orphan-*`, `verify-*`, `only-in-links`); зачистить фикстурные строки lifecycle-log (или ротировать с пометкой) | `SELECT … WHERE source_id LIKE 'test-%'` → 0; observability-report не считает фикстуры |

### P1 — Read-путь: латентность и кеш (2-4 дня, после P0)

| ID | Задача | Содержание | Acceptance |
|---|---|---|---|
| **P1.1** | Surfacing в бюджет | Профилировать по stage-полям surfacing-log (tei vs qdrant vs md); кандидаты: переиспользование TEI-коннекта, снизить lexical-scroll (100 → 50), параллелить sqlite+md с qdrant; либо осознанно поднять `TOTAL_BUDGET`/hook-timeout парой | p50 < 2.5s, p95 < 4.0s, 0 вызовов > 4.5s на окне 100 прогонов |
| **P1.2** | Cache-key §24 редизайн | Exact-match токенов → ослабленный ключ (top-N стем-токенов / minhash / Jaccard-бакет) + TTL 300→900s; кэш пустых результатов с отдельным коротким TTL | hit-rate > 10% на окне 100 прогонов (сейчас 0.4%) |
| **P1.3** | Контракт §26 в прямых писателях | `content_hash` + skip-on-exists + `record_ingest` в `save_pattern`, `_save_to_target`, `save_important_message`, `capture_pattern` (через `MemoryCube`-проекции — код уже есть) | повторный `save_pattern` с тем же контентом → `action=dup`, нет новой точки; запись видна `cross_store_sync` |
| **P1.4** | Честный ответ `route_and_save` | партиальный фейл targets → `success:false` / `saved_partial` + список упавших | unit-тест: упавший target отражён в ответе |
| **P1.5** | Epoch-bump в харвестерах | `epoch.bump()` при `created>0` в `pattern_harvest`/`skills_harvest` | новый паттерн виден surfacing'у на следующем промпте |

### P2 — Governance/migrate активация + доки (по готовности P0/P1)

| ID | Задача | Содержание |
|---|---|---|
| **P2.1** | Включить maintenance-apply | После ~2 недель живого reinforcement: `MEMORY_MAINTENANCE_APPLY=1`, наблюдать первый реальный wiki-promote и forget-bound через dashboard |
| **P2.2** | Судьба стабов B1 | Решение: восстановить `save_to_wiki_log`/`try_promote_patterns` (план был L5) **или** удалить из кода и доков. Не оставлять стабы молча |
| **P2.3** | ADR: PropagationEngine vs `_cascade_confidence` | Контур 3.2 «simulate success» — либо wire `update_handlers`, либо официально депрекейтить в пользу server-side каскада (сейчас два полу-живых механизма) |
| **P2.4** | Док-фиксы B2-B4, B8 | Обновить 27.2 (LinkType/Propagation/MemCube), 27.3/27.10 (веса/arm'ы), stale-docstrings в коде |
| **P2.5** | Надёжность хранилищ B9 | atomic `os.replace` для rewrite pending_patterns; WAL+timeout для `memory_ai.db`/`link_registry.db` |
| **P2.6** | Мелочи B6/B7/B10/B11 | Удалить мёртвый `max_hot_buffer_mb` или реализовать; компакция versions.jsonl; doc-уточнение `memory_forget`; пересмотреть «unknown=expired» |

### Вне скоупа (зафиксировать и не делать сейчас)

- Оживление `unified_search`-трафика (A8) — нет потребителя; вернуться при появлении сценария.
- Versioning/TTL продакшн-использование — сервисы готовы, потребителя нет.
- BSL embedding collapse (A1/C1 из памяти `feedback_bsl_embedding_collapse`) — отдельный трек.

---

## 5. Сводный приговор по блокам мастер-схемы

| Блок (глава) | Статус | Главное |
|---|---|---|
| ВХОД (27.12.1) | 🟢 работает / 🟡 без контракта | харвестеры — эталон; прямые писатели — слепой upsert (P1.3) |
| КООРДИНАЦИЯ (27.12.2) | 🟡 простаивает | оркестратор жив, но почти не используется (5 route-событий, 0 read-trace) |
| ХРАНИЛИЩА (27.12.3) | 🟢 работают | 28 паттернов, 101 episodic, граф 32 ребра (5 — мусор тестов, P0.3) |
| ВЫХОД (27.12.4) | 🟠 за бюджетом | инжектит, но p50>бюджета (P1.1), кеш мёртв (P1.2) |
| ОТДЕЛЬНО (27.12.5) | 🟢 работает | курируемый слой жив; EventStore наполняется при живом orchestrator'е |
| GOVERNANCE (27.12.6) | 🟡 наполовину | §22 decay-only (apply нет — P0.1); cadence dry-run; TTL/Versioning не используются |
| ПОТОКИ (27.12.7) | 🔴 петля разомкнута | write✓ read✓ **cascade✗** (P0.1) migrate=dry-run (P2.1) |

## 6. Верификация (команды)

```bash
# петля жива? (после P0.1)
tail -5 .claude/cache/confidence-lifecycle.log          # ждём session с 8-hex sid, applied>0
# латентность/кеш (после P1.1/P1.2)
.venv/Scripts/python.exe scripts/memory_observability_report.py --since 7d
# трасса одного факта через все sink'и
.venv/Scripts/python.exe scripts/memory_observability_query.py --view fact-trace --key <pattern_id>
# чистота графа (после P0.3)
sqlite3 data/link_registry.db "SELECT COUNT(*) FROM entity_links WHERE source_id LIKE 'test-%' OR source_id LIKE 'orphan-%'"
```

## §18 Progress Log

| Дата | Событие |
|---|---|
| 2026-06-09 | Roadmap создан по итогам аудита глав 27.12.1–27.12.7 + эмпирической проверки sink'ов. Ключевая находка: 0 production-reinforce за всю историю (A1) |
| 2026-06-09 | **P0 DONE + P1.5.** P0.1: reinforce вынесен в отдельный Stop-хук [`pattern-reinforce-stop.py`](../../.claude/hooks/pattern-reinforce-stop.py) (timeout 15s async, session_id из payload, early-exit без Qdrant-импорта при пустом surfaced, cap=10 `REINFORCE_CAP`); вызов удалён из `session-memory-save.py`; в `pattern_reinforce.py` ленивый Qdrant-импорт перенесён ПОСЛЕ подсчёта кандидатов. Изолированный смоук E2E PASS (`session`-событие + systemMessage). P0.2: `tests/conftest.py` — изоляция sink'ов на import-time (`CLAUDE_CACHE_DIR` + новый env `LINK_REGISTRY_PATH` в `link_registry.py`); acceptance PASS — 41 тест, прод-sink'и unchanged. P0.3: [`scripts/cleanup_memory_test_pollution.py`](../../scripts/cleanup_memory_test_pollution.py) (dry-run default) — удалено 184 фикстурных события из lifecycle-лога (бэкап) + 4 мусорных ребра из link_registry; остались 28 реальных рёбер. P1.5: `epoch.bump()` в обоих харвестерах при created/upserted/deleted>0. **Acceptance A1 финально подтвердится первым реальным `session`-событием с 8-hex sid в новых сессиях** (хук подхватится при следующем старте сессии) |
| 2026-06-09 | **🎯 Acceptance A1 ПОДТВЕРЖДЁН ВЖИВУЮ** — в той же сессии на первом Stop новый хук отработал в production: `session=1bab9bcd success=True applied=10 skipped=0 errors=0`; lifecycle-лог показывает реальные мутации Beta-confidence (напр. `0.5→0.6614`, `0.7→0.7273`) по full-UUID pattern_id. **Первый production-reinforce за всю историю системы. Петля §22 замкнута.** Доки обновлены: CLAUDE.md (Memory-хуки), `memory-unified` SKILL.md (Hooks P5 + Test isolation), главы 27.12.1/27.12.4/27.12.7 |
| 2026-06-10 | **P1 read-путь + write-контракт (P1.1–P1.4) реализованы + покрыты unit-тестами.** **P1.3** (§26 write-contract, A6): новый общий [`content_hash.point_id()`](../../src/memory/orchestrator/content_hash.py) (UUID5, namespace харвестера → manual+harvested writes коллапсят в одну точку); `content_hash` + детерминированный id + skip-on-exists dedup + `record_ingest` в **save_pattern** ([vector_memory/server.py](../../src/memory/vector_memory/server.py)), **_save_to_target** (все 4 target'а — [memory_orchestrator.py](../../src/memory/orchestrator/memory_orchestrator.py)), **save_important_message** (content-equality dedup, [ai_memory/server.py](../../src/memory/ai_memory/server.py)), **capture_pattern** (dedup по pending+saved, [skill_learning/server.py](../../src/memory/skill_learning/server.py)); харвестер `_point_id` делегирует общему хелперу. Acceptance: повторный `save_pattern` → `action=dup`, новой точки нет, `content_hash` в payload (unit `test_write_contract.py::test_save_pattern_dedups_identical_content`). **P1.4** (честный `route_and_save`): partial-fail → `success:false` + `saved_partial` + `failed_targets[]` (3 unit-теста: partial/full/total). **P1.2** (cache-key редизайн, A4/A5): exact-token → top-K (8) salient-stem ключ + epoch fold-in (мгновенная инвалидация) + TTL 300→900s + отдельный empty-TTL 180s; 4 unit-теста (collision/exact-short/empty-faster/roundtrip). **P1.1** (A3): lexical-scroll 100→50 (env-knob) + per-stage timing (`sqlite/qdrant/md/rerank`) в surfacing-log для профилирования. **Тесты:** 12 новых unit (`test_write_contract.py` 11, `test_surfacing_cache.py` 4 — все PASS) + 47 integration (memory_first_hook + memory_orchestrator) PASS, 0 регрессий; 208 memory-unit PASS. ⚠ **MCP-side** правки (`vector_memory`/`ai_memory`/`skill_learning`/orchestrator servers) подхватятся после `/mcp reconnect`. ⚠ **Production-acceptance** P1.1 (p50<2.5/p95<4.0 на окне 100) и P1.2 (hit-rate>10%) подтвердятся накоплением surfacing-лога после reconnect — механизм проверен unit'ами, метрика требует живого трафика. **Остаётся P2.x** (governance/migrate-активация + док-фиксы B2-B11) |
