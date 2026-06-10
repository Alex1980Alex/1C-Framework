# 260610 — Дорожная карта тестирования цепочек Unified Memory (по мастер-схеме 27.12 §10)

> **Цель:** на реальных примерах прогнать **все** осмысленные цепочки «вход → блоки → выход»
> мастер-схемы ([27.12 §10](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md)),
> измерить эффективность каждого потока (write / read / cascade / migrate) и подтвердить,
> что ремедиации roadmap 260609 (P0.1 reinforce-bridge, P1 write-contract + cache, P2.2/P2.3
> propagation) работают в production, а не только в unit-тестах.
>
> **Метод:** каждый блок схемы = узел; цепочка = путь от блока «ВХОД» до блока «ВЫХОД»
> (или до наблюдаемого артефакта governance). Для каждой цепочки — реальный пример
> (конкретный MCP-вызов / скрипт / промпт), ожидаемый sink-евиденс и критерий PASS.
> Пошаговые рельсы потоков — [27.12.7 Блок Потоки](../framework%20documentation/27_UNIFIED_MEMORY/27.12.7_Блок_Потоки.md).

---

## 1. Анализ блоков мастер-схемы (узлы графа)

### 1.1 ВХОД (запись) — 7 точек входа

| # | Вход | Куда ведёт | Особенность |
|---|---|---|---|
| W1 | `route_and_save` (MCP orchestrator) | Router → 1..3 store'а | единственный «умный» вход; пороги 0.80/0.50/0.30; с P1.3 — `content_hash` + dedup + `record_ingest`; с P1.4 — честный `failed_targets` |
| W2 | `save_pattern` (MCP vector-memory) | learned_patterns (Qdrant) | prior Beta(7,3)=0.70, advisory-confidence игнорируется; с P1.3 — детерминированный `point_id = UUID5(content_hash)` |
| W3 | `save_important_message` (MCP memory-ai) | memory_ai.db (SQLite) | importance 0..1; с P1.3 — content-equality dedup |
| W4 | `capture_pattern` (MCP skill-learning) | pending_patterns.jsonl | двухфазный: pending → `confirm_pattern` → saved |
| W5 | Stop-хук `session-memory-save` | memory_ai.db + `docs/wiki/log.md` | авто, dedup по session_id; промоут делегирует detached Popen (P2.2) |
| W6 | Stop-хуки `patterns-harvester` / `skills-harvester` | learned_patterns / skill_library | ingest-контракт §26: UUID5(content_hash), `memory-ingestion.log` |
| W7 | Ручной `.md` (курируемый слой) | `memory/*.md` + MEMORY.md | мимо оркестратора; читается только surfacing-хуком (layer `md`) |

### 1.2 КООРДИНАЦИЯ — 5 узлов оркестратора

Router (classify → targets), UnifiedSearchEngine (adapters → normalize → RRF k=60 → dedup → rerank → link-enrich), LinkRegistry (10 link-типов, BFS), PropagationEngine (BFS depth≤3, time×dist decay, честные handlers с P2.3), MemCube (мост форматов, `content_hash` в `__post_init__`).

### 1.3 ХРАНИЛИЩА — 5 колонок

memory-ai (EPISODIC, SQLite) · vector-memory (SEMANTIC, Qdrant `learned_patterns` 4096d, §22 confidence) · skill-learning (LEARNING, JSONL) · pdf-docs (DOCS, Qdrant) · LinkRegistry (связи, SQLite).

### 1.4 ВЫХОД (чтение) — 5 точек выхода

| # | Выход | Путь | Особенность |
|---|---|---|---|
| R1 | `unified_search` (MCP) | через оркестратор, federated + RRF | `duplicate_sources`, `linked_entities`, `sources_failed` |
| R2 | `memory-first-hook` (surfacing) | мимо оркестратора, hot-path <3s | 3 плеча {skill, pattern_dense, pattern_lexical} + layer md; cache top-K salient (P1.2); contract `record_surfaced` |
| R3 | `get_full_context` / `get_related` (MCP) | граф LinkRegistry, BFS | `effective_strength = strength × 0.9^(depth-1)` |
| R4 | Прямые read'ы store'ов | `search_patterns` / `list_patterns` / `get_pattern` / `search_messages` / `get_pending_patterns` | `search_patterns` ранжирует по **effective** confidence (lazy decay-on-read) |
| R5 | Observability | `fact-trace`, `memory_observability_report` | «выход» для оператора: восстановление пути факта по sink'ам |

### 1.5 ОТДЕЛЬНО + GOVERNANCE

Курируемая память (ручной `.md`), Event Store (events.jsonl/db). Governance: TTL · Versioning · ForgetGate (archive/decay/delete; revive-on-apply) · CircuitBreaker · Audit · Metrics · §22 confidence · §24 epoch.

---

## 2. Каталог цепочек «вход → блоки → выход» (29 цепочек)

Нотация: `→` шаг потока, `[X]` блок схемы. Каждая цепочка начинается во ВХОДЕ и заканчивается в ВЫХОДЕ (или наблюдаемом governance-артефакте).

### Группа A — write → store → read (12 цепочек, «субстрат»)

| ID | Цепочка | Что доказывает |
|---|---|---|
| A1 | W1 `route_and_save`(conf≥0.80) → [Router 1 target] → [vector-memory] → R1 `unified_search` (vector arm → RRF) | точность классификации + видимость роутерной записи в federated read |
| A2 | W1 (conf 0.50–0.79) → [Router 2 targets] → [vector-memory]+[memory-ai] → cross-link 0.7 → R1 → `duplicate_sources` | мульти-store запись + Deduplicator коллапсит дубль с провенансом |
| A3 | W1 (conf 0.30–0.49) → [Router 3 targets] → 3 store'а → [LinkRegistry] → R1 → `linked_entities` | LinkEnricher обогащает выдачу cross-link'ами записи |
| A4 | W1 (нет сигналов) → fallback [memory-ai] conf 0.3 → R1 (ai arm: LIKE + importance-rerank) | деградация роутера управляемая, запись не теряется |
| A5 | W2 `save_pattern` → [vector-memory prior 0.70] → R4 `search_patterns` | прямой писатель соблюдает §22 prior + §26 write-contract (P1.3) |
| A6 | W2 → [vector-memory] → R2 surfacing, плечо `pattern_dense` → injected | свежий паттерн всплывает на тематический промпт |
| A7 | W2 → [vector-memory] → R2 surfacing, плечо `pattern_lexical` (TEI не нужен) | лексическое плечо живо независимо от TEI |
| A8 | W3 `save_important_message` → [memory-ai] → R1 (ai arm) | episodic-вход виден federated-поиску |
| A9 | W4 `capture_pattern` → [skill-learning pending] → `confirm_pattern` → saved → R1 (skill arm) / R2 (skill arm) | двухфазный learning-цикл; pending НЕ виден, saved виден |
| A10 | W5 Stop-хук → [memory-ai session_summary] + `docs/wiki/log.md` → R1 / R2 следующей сессии | авто-сохранение сессий реально пишет и реально читается |
| A11 | W7 ручной `.md` → R2 surfacing layer `md` | курируемый слой доезжает до инъекции |
| A12 | W6 harvester → `ingest_items` → [vector-memory UUID5] → R2 | Stop-ingestion жив; re-harvest → `action=dup` (идемпотентность) |

### Группа B — петля обратной связи read → cascade → read (5 цепочек, «ядро §10.2»)

| ID | Цепочка | Что доказывает |
|---|---|---|
| B1 | R2 surfacing → `record_surfaced` → Stop `pattern-reinforce-stop` → `reinforce_pattern` → confidence ↑ (0.70→0.7273) → `epoch.bump` → cache-miss → R2 ре-ранжирование | **полная автономная петля** — главный тест карты (мост чинился в 260609 P0.1) |
| B2 | `apply_pattern(success)` → `_cascade_confidence` → соседи по SUPPORTS/EXTENDS (предсозданы `create_link`) → [LinkRegistry] → `memory-propagation.log` + epoch | cascade-on-apply НЕ no-op при реальных рёбрах |
| B3 | `propagate_update` → [PropagationEngine BFS depth≤3] → handlers: vector (succ/fail nudge) + memory-ai (importance±delta) → честный `entities_updated` | P2.3: мутации реальные, sync-режим, без фантомов |
| B4 | `apply_pattern(success=false)` ×N → fail↑ → eff↓ → кандидат `should_archive` (eff<0.40) | отрицательная ветвь валюты confidence |
| B5 | повторный W2 с тем же content → `action=dup`, та же точка UUID5, новой нет | write-contract dedup (P1.3) на прямом писателе |

### Группа C — migrate, медленная ось (5 цепочек)

| ID | Цепочка | Что доказывает |
|---|---|---|
| C1 | ≥3 похожих эпизода [memory-ai] → `reflect` (M1) → [vector-memory] + рёбра `DERIVES_FROM` → R1 | действующий канал episodic→semantic |
| C2 | один факт в 2 store'ах → `cross_store_sync` (M2) → рёбра `MIRRORS` (canonical: learned_patterns > memory_ai) → R3 `get_related` | cross-store консолидация по `content_hash` |
| C3 | паттерн conf≥0.8 & count≥5 → `WikiPromoter` (M3, apply-only) → `docs/wiki/drafts/*.md` + ребро `PROMOTED_TO` | escape semantic→wiki, новый read-источник |
| C4 | LIGHT-записи → `normalize_light_patterns.py` (one-shot) → full LearnedPattern → лучшее ранжирование R4 | исторический хвост схемы «light→normalize→full» |
| C5 | полный cadence `memory_maintenance.py` (reflect→sync→promote→forget→dashboard) | оркестровка M1–M5 + дашборд `data/reports/memory/` |

### Группа D — governance и негативные ветви (7 цепочек)

| ID | Цепочка | Что доказывает |
|---|---|---|
| D1 | паттерн → `decay_confidence` sweep → дрейф к prior → ForgetGate archive (`expired_at`) → R4 вес ×0.5 → `apply` → **revive** | полный цикл raise→decay→forget→revive (§22 P3) |
| D2 | `memory_ttl_set`(short) → `memory_ttl_cleanup` → запись исчезает из чтения | TTL-механика governance |
| D3 | save → update → `memory_version_history` / `memory_version_compare` / `memory_version_rollback` → R чтение старой версии | Versioning |
| D4 | серия fail propagation → CircuitBreaker OPEN → `propagate_update` отвергнут (`circuit_breaker_open`) → `memory_circuit_reset` | анти-лавина каскада |
| D5 | TEI/Qdrant down → R2 lexical-only fallback (`tei=down`) / R1 `sources_failed[]`, поток жив на выживших плечах | graceful degradation чтения |
| D6 | W1 с искусственно сломанным target'ом → `success:false` + `saved_partial:true` + `failed_targets[]` | честность route_and_save (P1.4) — раньше молча терял |
| D7 | любая операция A/B/C → R5 `fact-trace --key <hash|pid>` → непрерывный тред ingestion→reinforce→(forget) | §27 observability как сквозной выход |

**Покрытие схемы:** все 7 входов (W1–W7), все 5 узлов координации, все 5 хранилищ, все 5 выходов (R1–R5), все 4 потока (`write` A*, `read` A*/D5, `cascade` B*, `migrate` C*), governance — D1–D4 + §22/§24 внутри B1/B4. Непокрытым остаётся только pdf-docs как write-цель (индексация PDF — отдельный пайплайн, глава 31).

---

## 3. Дорожная карта тестирования (фазы P0–P5)

### Гигиена тестовых данных (обязательна для всех фаз)

- Контент маркируется префиксом **`[CHAIN-TEST]`** + тег `chain-test` в metadata — уникальность (не схлопнется dedup'ом с боевыми) и адресная чистка.
- Тесты идут по **production-пути намеренно** (в этом смысл); `MEMORY_TEST_ISOLATION_DISABLE` не трогать — изоляция действует только под pytest.
- Чистка после фазы: `delete_pattern` / `delete_message` по найденным id + `python scripts/cleanup_memory_test_pollution.py` (сначала dry-run).
- Все скрипты — через `.venv/Scripts/python.exe` ([[feedback-venv-python-windows]]).
- После любой правки кода MCP-серверов в ходе фикса — `/mcp reconnect` ([[feedback-mcp-stale-code-reconnect]]).

### P0 — Pre-flight (инфраструктура жива) — ~15 мин

1. `mcp__vector-memory__health_check`, `mcp__memory-orchestrator__health_check`, `mcp__skill-learning__health_check` → все green.
2. TEI: `docker ps` → `pdf-rag-tei` Up; Qdrant `localhost:6333`.
3. Базовые sink'и не stale: `python scripts/memory_observability_report.py --since 7d` → нет регрессии «sink молчит N дней».
4. Снять **baseline-снапшот** для метрик: `get_system_stats`, `list_patterns(limit=0)` counts, `sqlite3 data/link_registry.db "SELECT link_type, COUNT(*) FROM entity_links GROUP BY link_type"`.

**PASS-гейт фазы:** все health green + baseline зафиксирован в §18.

### P1 — Группа A: писатели → читатели — ~1.5 ч

Реальные примеры (контент — настоящие 1С-факты, чтобы тест заодно был полезен):

- **A1:** `route_and_save(content="[CHAIN-TEST] Паттерн: для РС подчинённого регистратору использовать периодичность RecorderPosition, календарная периодичность даёт коллизию ключа", metadata={"hint":"pattern"})` → ответ: 1 target `vector-memory`, confidence≥0.80 → `unified_search("периодичность регистра подчинённого регистратору")` → факт в выдаче, `source=vector-memory`. Sink: `.claude/cache/memory-routing.log` (`event:route`), `memory-ingestion.log` (`action:saved`, есть `content_hash`).
- **A2:** контент со смешанными сигналами (FACT+PREFERENCE): «[CHAIN-TEST] Предпочитаю двухэтапную группировку: ref-ключи во ВТ, строковые детали join'ом без агрегации» → 2 target'а → `unified_search` → один результат с `duplicate_sources=[второй store]`. Проверить ребро: `get_related(entity_id)` → `session_context` strength 0.7.
- **A3:** размытый контент → 3 target'а → `unified_search` → `linked_entities` непуст.
- **A4:** контент без сигналов («[CHAIN-TEST] просто заметка про погоду в офисе») → fallback memory-ai conf 0.3.
- **A5/B5:** `save_pattern(content="[CHAIN-TEST] ...", confidence=0.95)` → `get_pattern` → confidence **0.70** (advisory проигнорирован — PASS); повторный `save_pattern` того же контента → `action=dup`, тот же `point_id` (UUID5).
- **A6/A7:** новый промпт в сессии, тематически близкий к A5 → `tail .claude/cache/memory-first-surfacing.log` → `arms.pattern_dense>0` (A6); проверить `pattern_lexical>0` (A7); `outcome:"injected"`.
- **A8:** `save_important_message(content="[CHAIN-TEST] ...", importance=0.9)` → `unified_search` → найден, скор отражает importance.
- **A9:** `capture_pattern` → `unified_search` (НЕ найден — pending) → `confirm_pattern` → `unified_search` (найден) — двухфазность.
- **A10:** завершить сессию с осмысленной работой → `sqlite3 data/memory_ai.db "SELECT ... WHERE category='session_summary' ORDER BY rowid DESC LIMIT 1"` + `tail docs/wiki/log.md` — свежая запись.
- **A11:** записать тест-файл в `~/.claude/projects/.../memory/chain-test-fact.md` + строку в MEMORY.md → промпт по теме → surfacing-лог `layers` содержит `md`-хит → удалить файл после.
- **A12:** после Stop проверить `memory-ingestion.log`: `harvester:"patterns"`, `action:saved|dup`.

**Метрики фазы:** routing-accuracy (≥4/5 целевых store'ов угаданы на golden-наборе A1–A4), surfacing hit-rate свежего паттерна (инъекция ≤2 промптов), ingest dup-rate.

### P2 — Группа B: петля reinforce / cascade — ~1.5 ч (через границу ≥2 сессий)

- **B1 (главный тест):** (1) сессия N: убедиться что A5-паттерн всплыл (surfacing-лог) и существует `.claude/cache/surfaced-patterns-<sid>.json` с его pid; (2) сделать коммит (сигнал успеха `_detect_success`); (3) завершить сессию → в `confidence-lifecycle.log` событие `session` + `reinforce` с `old_confidence:0.70 → new_confidence:0.7273`; (4) `cat .claude/cache/confidence-epoch.txt` — timestamp обновился; (5) сессия N+1: тот же промпт → surfacing-лог `cache:"miss"` (epoch вшит в ключ), паттерн ранжирован выше. **PASS = вся пятёрка**; математика сверяется точно: `(7+1)/(10+1)=0.7273`.
- **B2:** создать второй паттерн + `create_link(source=<pid_A5>, target=<pid_2>, link_type="supports", strength=0.8)` → `apply_pattern(pid_A5, success=true)` → ответ содержит `cascaded`; `tail .claude/cache/memory-propagation.log` — сосед получил delta `1.0×0.8×0.5×time≈0.4`; `get_pattern(pid_2)` — confidence сдвинулся. ⚠ Без create_link — задокументированный no-op (это тоже проверить: D-контроль).
- **B3:** `propagate_update(entity_id="semantic:vector-memory:<pid>", delta=0.1, success=true)` → `entities_updated` непуст, повторный вызов НЕ глотается (dedup off, P2.3), `memory-propagation.log` свежий; для episodic-соседа — importance в SQLite изменился.
- **B4:** `apply_pattern(pid_доноров, success=false)` ×5 → `get_pattern` → effective падает ((7+1)/(10+1+5)≈0.50 при 1 succ/5 fail); `memory_forget(dry_run)` показывает его кандидатом при eff<0.40.

**Метрики фазы:** production-reinforce applied>0 (исторический ноль до 260609 P0.1 — регресс-маркер), точность Beta-математики до 4 знаков, cascade непустой при наличии рёбер, латентность Stop-хука ≤15s.

### P3 — Группа C: migrate — ~1 ч

- **C1:** засеять 3 похожих эпизода через `save_important_message` (Jaccard≥0.5) → `.venv/Scripts/python.exe scripts/memory_maintenance.py --skip sync,promote,forget` (dry-run: план кластера виден) → с `--apply` → новый паттерн в learned_patterns + `sqlite3 data/link_registry.db` → рёбра `derives_from`.
- **C2:** один `[CHAIN-TEST]`-факт записать в learned_patterns И memory-ai (одинаковый текст → одинаковый `content_hash`) → `scripts/cross_store_sync.py` dry-run → пара найдена, canonical=learned_patterns → `--apply` → ребро `mirrors`; `get_related` показывает mirror→canonical.
- **C3:** взять паттерн с conf≥0.8 & application_count≥5 (или догнать B1-паттерн apply'ями) → `-m scripts.export_graph_to_wiki promote-patterns` → файл в `docs/wiki/drafts/`, ребро `promoted_to`, строка в `docs/wiki/log.md`.
- **C4:** `scripts/normalize_light_patterns.py` dry-run — есть ли ещё LIGHT-записи; если 0 → цепочка закрыта исторически, фиксируем как N/A.
- **C5:** полный `memory_maintenance.py` (dry-run) → дашборд `data/reports/memory/memory_maintenance_*.md` со store_sizes / dup_rate / forget summary.

**Метрики фазы:** появление рёбер всех 3 миграционных типов (`derives_from`/`mirrors`/`promoted_to` — на baseline P0 их могло не быть вовсе), cross_store_dup_rate из дашборда.

### P4 — Группа D: governance + негативные — ~1.5 ч

- **D1:** на жертвенном паттерне `decay_confidence` (агрессивный `decay_rate`) → eff к prior; искусственно набить fail'ы до eff<0.40 → `memory_forget` (dry-run → apply) → `expired_at` стоит; `search_patterns` отдаёт его с весом ×0.5; `apply_pattern(success=true)` → `expired_at` снят (**revive**).
- **D2:** `memory_ttl_set(entity, ttl="short")` → подождать/смоделировать → `memory_ttl_check` → expired → `memory_ttl_cleanup` → из выдачи исчез.
- **D3:** `memory_version_history(entity)` после пары update'ов → `memory_version_compare(v1,v2)` diff осмысленный → `memory_version_rollback(v1)` → чтение видит старый контент.
- **D4:** `memory_circuit_status` → CLOSED; навести 5 fail'ов (например propagate на несуществующие entity с принудительной ошибкой handler'а) → OPEN → `propagate_update` возвращает `circuit_breaker_open` → `memory_circuit_reset` → CLOSED.
- **D5:** `docker stop pdf-rag-tei` → промпт → surfacing-лог `tei:"down"`, `pattern_lexical` жив, `outcome` не error; `unified_search` → `sources_failed` содержит vector-memory, остальные плечи отвечают → `docker start pdf-rag-tei`.
- **D6:** временно сломать один target (например `MEMORY_AI_DB_PATH` → несуществующий каталог в env MCP-сервера) → `route_and_save` (2-target контент) → `success:false`, `saved_partial:true`, `failed_targets:["memory-ai"]` → вернуть env. ⚠ ровно тот случай, который до P1.4 терялся молча.
- **D7:** для факта из B1: `python scripts/memory_observability_query.py --view fact-trace --key <pattern_id>` → непрерывный тред `ingest(saved) → reinforce → (forget/revive)`; разрыв треда = баг моста.

**Метрики фазы:** все 4 governance-механизма срабатывают и откатываются; деградации не роняют поток (0 unhandled error в sink'ах).

### P5 — Сводка эффективности + отчёт — ~1 ч

1. Повторно `memory_observability_report.py --since 7d` и diff с baseline P0.
2. Свести метрики в итоговую таблицу (см. §4) — по каждому потоку: жив / деградирован / разорван + латентности.
3. Cleanup: удалить все `[CHAIN-TEST]`-артефакты (patterns, messages, links, md-файл, wiki-drafts) + `cleanup_memory_test_pollution.py`.
4. Обновить §18 здесь + при системных находках — issue/roadmap-итерация.

---

## 4. Критерии эффективности (что меряем)

| Поток | Метрика | Источник | Target |
|---|---|---|---|
| write | routing accuracy (golden A1–A4) | memory-routing.log vs ожидание | ≥80% |
| write | dup-rate идемпотентности (B5/A12) | memory-ingestion.log `action` | 100% dup на повторе |
| write | честность partial-fail (D6) | ответ route_and_save | `failed_targets` непуст |
| read | surfacing hit свежего паттерна | memory-first-surfacing.log | инъекция ≤2 тематических промптов |
| read | cache hit-rate после P1.2 (top-K key) | surfacing-лог `cache` | hit на перефразированном промпте той же темы |
| read | латентность surfacing / unified_search | per-stage timing (P1.1) / memory-read.log | <3s hot-path / <7.5s federated |
| cascade | production-reinforce | confidence-lifecycle.log `session`/`reinforce` | applied>0 за сессию с surfaced+commit |
| cascade | точность Beta-математики | old/new confidence в логе | ==(7+succ)/(10+succ+fail) |
| cascade | epoch-инвалидация | confidence-epoch.txt + cache-miss | miss сразу после мутации |
| migrate | рёбра derives_from/mirrors/promoted_to | link_registry.db GROUP BY | >0 каждого типа после P3 |
| governance | forget→revive цикл | expired_at + search вес ×0.5 | полный круг без удаления данных |
| все | непрерывность fact-trace | observability_query fact-trace | тред без разрывов write→…→forget |

## 5. Риски и известные ограничения

- **B2 no-op без рёбер** — каскад на горячем пути требует реальных pattern↔pattern связей; тест создаёт их сам (`create_link`). Отрицательный контроль (без рёбер → `cascaded:0`) — тоже PASS-критерий.
- **MCP stale code** — половина проверяемых фиксов (P1.3/P1.4/P2.3, cascade, epoch MCP-side) живёт в MCP-серверах: перед P1 убедиться, что сессия стартовала после последнего изменения кода, иначе `/mcp reconnect`.
- **B1 требует границу сессий** — полная петля проверяется минимум в 2 сессии (Stop-хук). Планировать фазу P2 как «вечер дня 1 → утро дня 2».
- **27.12.7 §5 частично устарел** — строки «route_and_save без content_hash» и «молчаливый success:true» исправлены 260609 P1.3/P1.4; после PASS A1/D6 — поправить главу (docs-change-enforcer сам напомнит при правке кода, для доков — вручную).
- Производственные store'ы — тест пишет в боевые базы намеренно; маркер `[CHAIN-TEST]` + cleanup обязательны (см. гигиену).

## 6. Оценка трудоёмкости

| Фаза | Цепочки | Время | Зависимости |
|---|---|---|---|
| P0 | preflight | 15 мин | Docker/Qdrant/TEI up |
| P1 | A1–A12 | 1.5 ч | P0 |
| P2 | B1–B5 | 1.5 ч (2 сессии) | P1 (паттерны-доноры) |
| P3 | C1–C5 | 1 ч | P0; C3 удобнее после P2 (накрученный count) |
| P4 | D1–D7 | 1.5 ч | P1–P2 (жертвенные паттерны) |
| P5 | сводка | 1 ч | всё |
| **Итого** | **29** | **~6.5 ч** (2 рабочих захода) | |

> ⚠ По [[project-roadmap-audit-pattern]] оценки склонны к завышению 1.5–3×: перед стартом каждой фазы — 10-мин inventory (какие цепочки уже де-факто подтверждены свежими production-логами — например A12/B1 могли «пройти сами» после 2026-06-09/10; такие фиксируем по логам без повторного прогона).

---

## §18 Progress Log

| Дата | Событие | Детали |
|---|---|---|
| 2026-06-10 | Roadmap создан | Анализ мастер-схемы 27.12 §10 → 29 цепочек (A12/B5/C5/D7), фазы P0–P5, метрики эффективности. Базис: 27.12.7 (рельсы потоков + точки разрыва), ремедиации 260609 P0.1/P1/P2 как объекты подтверждения |
| 2026-06-10 | **P0 PASS** | Health: orchestrator/skill-learning/vector-memory green (1-й health_check vector-memory timeout 60s — cold-start, retry OK, count=28), TEI+Qdrant Up 2 days healthy. Observability 7d: 8 sinks fresh / 0 stale / 2 cold (`read`, `circuit` — закроются P1/P4). **Baseline:** learned_patterns=28, memory_ai=104 (avg_imp 0.71), skill_learning saved=1; links=28 (`mirrors` 25, `supports` 2, `derives_from` 1, `promoted_to` **0**); ingestion 7d: 566 attempts, dup_rate 34.4%; surfacing injected 83.4%, TEI-down 42.2%; reinforce apply-rate 66% |
| 2026-06-10 | **Inventory (по [[project-roadmap-audit-pattern]])** | **A12 PASS по production-логам без прогона**: `memory-ingestion.log` — re-harvest того же `content_hash:9897eb26…` → `action=dup`, тот же UUID5 `pattern_id` ×8 за день (идемпотентность). **B1 production-метрика PASS досрочно**: `confidence-lifecycle.log` — события `session` applied=3 ×2 (cf61d36f, dc1ae682) + applied=0 skipped=5 (dedup повторного reinforce работает); полная контролируемая пятёрка B1 — в P2 |

---

## Связанные документы

- [27.12 Memory Systems Map §10](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) — мастер-схема (источник блоков)
- [27.12.7 Блок Потоки](../framework%20documentation/27_UNIFIED_MEMORY/27.12.7_Блок_Потоки.md) — пошаговые рельсы + точки разрыва
- [260609 Memory Remediation](260609_ROADMAP_MEMORY_REMEDIATION.md) / [260608 Unit-test remediation](260608_ROADMAP_UNIT_TEST_REMEDIATION.md) — фиксы, которые эта карта подтверждает в production
- [260605 Full Observability](260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md) — fact-trace / report, используемые как выход R5
- Skill: `memory-unified`
