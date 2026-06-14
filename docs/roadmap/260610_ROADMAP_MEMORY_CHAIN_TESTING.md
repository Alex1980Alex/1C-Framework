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

### 4.1 Итоговая таблица (P5, 2026-06-11)

Прогон завершён: **23 PASS · 2 FAIL-by-design (A2/A3, F1) · 3 FAIL governance (D2/D3/D4, F8–F10) · 1 N/A (C4)** из 29. Найдено 13 находок (F1–F13), исправлено 5 (F2/F4/F6/F7/F11).

| Поток | Вердикт | Факт по метрикам §4 |
|---|---|---|
| write | **жив** (с ограничением F1) | routing: explicit/fallback точны (A1/A4), мульти-target недостижим by design → `duplicate_sources` проверен через C2; dup-rate на повторе 100% (B5/A12); partial-fail честен — `failed_targets` непуст (D6) |
| read | **жив**, hot-path деградирован по латентности (F3) | surfacing-инъекция свежего паттерна с 1-го промпта (A6); cache hit на перефразе той же темы (D5, P1.2 ✓); hot-path 3.8–3.9s **> 3s target** (стадия qdrant ~2.0s); federated 2.3s < 7.5s, p50 334ms/p95 1913ms; TEI-down fail-soft после F11 |
| cascade | **жив** | production-reinforce applied=3 (session 43538ff1) — исторический ноль снят; Beta точна: 0.70→0.7273=(7+1)/(10+1); epoch-инвалидация: cache miss сразу после Stop-мутации; cascade непуст при рёбрах (B2 после F4), negative-контроль `cascaded:0` ✓ |
| migrate | **жив** | рёбра всех 3 типов созданы в P3 (derives_from 1→19, mirrors, promoted_to после F7); cross_store_dup_rate 0.179; C4 N/A — LIGHT-хвост закрыт исторически |
| governance | **частично разорван** | живы: forget→revive полный круг (D1; archived hard-exclude, не ×0.5 — поведение §24.2.4), audit, fact-trace без разрывов (D7). Разорваны: TTL bookkeeping-only (F9), versioning без писателей (F8), circuit breaker неподключён + silent-drop handler'ов (F10/F12) — отдельная итерация |

Observability-diff vs baseline P0 (7d-окно): sinks 8 fresh/2 cold → **9 fresh/1 cold** (`read` ожил, `circuit` — F10); learned_patterns 28→39 (после cleanup −9 chain-test), memory_ai 104→115 (−11), links 28→48 легитимных после снятия 12 тестовых рёбер; surfacing injected 83.4→86.1%; ingestion dup_rate 34.4→33.8%; reinforce apply-rate 66→63%.

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
| 2026-06-10 | **P1 PASS 10/12** (A2/A3 FAIL-by-design) | **PASS:** A1 (route explicit 1.0 → vector-memory → R1 rank#1, 347ms, ingest `saved`+hash), A4 (fallback memory-ai 0.3 → ai-arm rank#1), A5 (advisory 0.95/0.99 → prior **0.70**, UUID5 pid), B5 досрочно (`action=dup`, тот же pid `5ad1d692…`), A6 (свежий паттерн всплыл №1 с 1-го промпта, `pattern_dense=5`), A7 (`pattern_lexical=3`), A8 (saved → виден в R1), A9 (pending НЕ виден → confirm → виден, score 1.0; ingest `skipped:pending`), A11 (`layers.md=1` — слой жив; в топ-5 инъекции не пробился по рангу), A12 (по логам). A10: SQLite-половина PASS (summary 06-08/09/10), wiki-половина — после Stop (stub восстановлен лишь сегодня P2.2). **FAIL-by-design A2/A3 (находка F1):** мульти-target недостижим — Phase 1 explicit-словари (`важно`, `код`, `паттерн`…) перекрывают CATEGORY_KEYWORDS и срабатывают раньше (conf 1.0), Phase 2 требует match ~половины словаря (skills max 6/13=0.46<0.5), Phase 0 перехватывает ≥2-сигнальный контент (stuffed-зонд → auto_classify fact 0.6). Production: `multi_target_routes=0` за всю историю. Цепочки A2/A3 мастер-схемы — теоретические; `duplicate_sources`/cross-link 0.7 проверяются через C2/B2 |
| 2026-06-11 | **P2 PASS 4/5 (B1 — после Stop) + D1 PASS досрочно** | **B2 PASS**: negative-контроль `cascaded:0` без рёбер ✓; с bare-id ребром supports 0.8 → `cascaded:1`, сосед получил ровно `succ+=0.4` (1.0×0.8×0.5×1.0), conf 7.4/10.4=0.711538 точно, propagation-лог `entities_updated:1` 12.6ms. **B3 PASS**: `propagate_update` sync, повторный вызов не глотается (P2.3 ✓), vector-сосед мутирует в Qdrant (succ 0.4→0.48), episodic-сосед — importance 0.7→0.73 в SQLite (delta 0.1×0.6×0.5=0.03 точно). **B4 PASS**: fail×8 → eff 7/18=0.3889<0.40, Beta-математика точна на каждом шаге. **B5** — PASS в P1. **D1 PASS досрочно**: sweep пропускает паттерны <1 дня (by design) → backdate 2d → `archived:1` (`expired_at` стоит) → `search_patterns` **hard-исключает** архивные (§24.2.4; ожидание роадмапа «вес ×0.5» устарело — поведение изменено на exclude + `MEMORY_INCLUDE_ARCHIVED=1` override) → `apply(success=true)` → **revive** (`expired_at:null`, 8/19≈0.421). Lifecycle-лог: непрерывный тред apply×9 + decay_sweep×2 (archived:1) + MCP-side события живы. **B1-сетап**: A5-паттерн заведён в `surfaced-patterns-43538ff1…json` (salience 0.5261, топ-1) производственным вызовом hook'а; ожидание после Stop: reinforce (7+1)/(10+1)=0.7273 |
| 2026-06-11 | **🐛 F4: cascade слеп к unified-ID рёбрам** (B2-прогоном, исправлено) | `_cascade_confidence` ([vector_memory/server.py](../../src/memory/vector_memory/server.py)) искал рёбра `get_links_from(<голый pid>)` и ретривил соседа по `link.target_id` как Qdrant-id — а orchestrator `create_link` пишет unified `semantic:vector-memory:<pid>` → каскад no-op для всех оркестраторных рёбер (эмпирика: unified-ребро → `cascaded:0`, bare-ребро → `cascaded:1`). Фикс: двойной lookup (bare + unified prefix) + нормализация `target_id` (strip prefix; cross-store → `cascades_prevented`); seen-dedup коллапсит дубль bare/unified. MCP-side → после reconnect. **🐛 F6: один malformed point ронял весь `search_patterns`** (`Error: 'source_type'`): `pattern_harvest.py:318` писал `evidence_sources=[{"source": …}]` вместо полной схемы → `EvidenceSource.from_dict` KeyError. Фикс 3 слоя: tolerant `from_dict` ([models.py](../../src/memory/vector_memory/models.py)), правильная схема в писателе ([pattern_harvest.py](../../.claude/hooks/shared/pattern_harvest.py), хуки спавнятся свежими), data-repair точки `d4b763da…`. R4 ожил сразу после data-repair. **F5 (косметика, не чинилось):** `get_pattern` отдаёт `archived:true` при `pattern.expired_at:null` — `_pattern_from_payload` не маппит `expired_at` в модель |
| 2026-06-11 | **P3 PASS 4/4 + C4=N/A** | **C1 PASS**: 3 почти-идентичных эпизода (1-й заход с разными формулировками дал Jaccard~0.27<0.5 — порог токенный, не семантический; пересеяно) → `reflect_memory.py` dry-run видит кластер → `--apply` → 4 паттерна (1 chain-test + 3 легитимных исторических), `derives_from` 1→**19**. **C2 PASS**: идентичный текст в learned_patterns+memory-ai → `cross_store_sync.py` dry-run 30 пар / canonical=learned_patterns → `--apply` created 10 / existing 20 / errors 0 → `mirrors`-ребро, `get_related` обходит (eff_strength 1.0 depth 1). **C3 PASS после F7**: донор докачан apply×2 до conf 0.80 (12/15) & count 5 → `export_graph_to_wiki promote-patterns` → драфт + строка в `docs/wiki/log.md` (вставляется в середину файла перед «Format Template» — tail её не показывает) + ребро `promoted_to` ✓. **C4 = N/A**: `normalize_light_patterns.py` → `to_normalize=0` (хвост закрыт исторически, 37 rich + 2 session_summary skip by design). **C5 PASS**: полный `memory_maintenance.py` dry-run — все джобы, forget evaluated keep=39, дашборд написан, cross_store_dup_rate 0.179. Все 3 миграционных типа рёбер в графе ✓ |
| 2026-06-11 | **🐛 F7: PROMOTED_TO терялся молча** (C3-прогоном, исправлено) | `cmd_promote_patterns` в [export_graph_to_wiki.py](../../scripts/export_graph_to_wiki.py) не передавал `link_registry` в WikiPromoter (opt-in параметр) → `_create_promotion_link` всегда no-op, причём это именно тот путь, которым ходит §26 P4 cadence и `try_promote_patterns` Stop-хука. Фикс: `LinkRegistry()` в конструктор; re-run → ребро `semantic:vector-memory:b46f2fa9… → wiki:obsidian-vault:chain-test-b2…` создано. Скрипт-side (не MCP) — действует сразу |
| 2026-06-11 | **P4: D1/D5/D6/D7 PASS · D2/D3/D4 FAIL (governance-скаффолдинг без проводки)** | **D1 PASS** (см. P2-строку). **D6 PASS**: сломанный target (RENAME TABLE important_messages) → `success:false` + `failed_targets:["memory-ai"]` — честность P1.4 ✓ (partial-вариант недостижим из-за F1: мульти-target нет). **D5 PASS после F11**: TEI down → хук fail-soft, exit 0, sqlite/md-слои живы; `unified_search` отвечает на выживших плечах 2.3s; `cache:hit` на повторном промпте той же темы (P1.2 ✓); bonus: `linked_entities`/`duplicate_sources` в выдаче работают (рёбра C1/C2). **D7 PASS**: fact-trace 11 событий save→ingest→apply×9 через 2 sink'а; gap — `decay_sweep`/archive глобальны (без pattern_id), в per-fact тред не попадают. **D2 FAIL (F9)**: `memory_ttl_cleanup` удаляет только TTL-леджер — сущность остаётся полностью читаемой; «запись исчезает из чтения» не выполняется (TTL = bookkeeping-only). **D3 FAIL (F8)**: у versioning-сервиса 0 писателей (только read/rollback/compare endpoints; `total_versions=0` глобально при всей активности дня) — цепочка save→update→history не существует. **D4 FAIL (F10)**: реестр `CircuitBreakerRegistry` оркестратора инициализируется, но ни один breaker не создаётся — `memory_circuit_status`/`reset` управляют пустотой; внутренний breaker PropagationEngine (threshold 5) недостижим: `_apply_update:517` глотает ВСЕ исключения handler'ов → False. Эмпирика: Qdrant down → propagate НЕ падает, vector-сосед молча выпадает из `entities_updated` (даже без счётчика/причины), breaker не двигается. Рекомендация: проводка breaker'ов вокруг handler-вызовов + surfaced `failed_entities[]` в PropagationResult — отдельная итерация |
| 2026-06-11 | **🐛 F11: lexical-плечо голодало при TEI-down** (D5-прогоном, исправлено) | `memory-first-hook.py:581` передавал в `_search_learned_patterns` общий `start` дозового бюджета — TEI-попытка съедала `QDRANT_TIMEOUT` целиком, lexical обрывался на 1-й точке → `pattern_lexical:0`, `no-results` ровно в сценарии, где lexical должен быть единственным выжившим (docstring обещал обратное). Фикс: собственные часы `time.monotonic()`. Верифицировано при лежащем TEI: `pattern_lexical:1`, A5-паттерн всплыл №1, `outcome:injected`. Хуки спавнятся свежими — действует сразу. **F12 (наблюдение, не чинилось):** `unified_search` при TEI-down возвращает `sources_failed:[]` — vector-плечо деградирует молча, «0 хитов» неотличимо от «плечо умерло»; той же природы, что и silent-drop в F10 |
| 2026-06-11 | **Follow-up roadmap создан** | Открытые находки F5/F8/F9/F10/F12/F13 + новая F14 (reinforce_miss считался errors) декомпозированы в [260611 Governance & Honest-Failure Wiring](260611_ROADMAP_MEMORY_GOVERNANCE_WIRING.md) — исследование локализовало все разрывы до строк; F3 (perf surfacing) и F1 (мульти-target) — вне scope, отдельные решения |
| 2026-06-11 | **B1 PASS (полная пятёрка) + A10-wiki PASS — P2 закрыт 5/5, P1 11/12** | После Stop сессии 43538ff1: (1) lifecycle-лог `reinforce` pid `5ad1d692…` `0.70 → 0.7273` точно =(7+1)/(10+1); (2) `session 43538ff1 applied=3 skipped=4 errors=0`; (3) epoch обновлён; (4) сессия N+1: тематический промпт production-вызовом hook'а → `cache:"miss"` (epoch вшит) + паттерн **№1 в инъекции**, `pattern_dense=5/pattern_lexical=1`, gate passed=6. **A10-wiki PASS**: `## 2026-06-11 — Session Summary` в `docs/wiki/log.md` от session-memory-save (stub P2.2 отработал на живом Stop впервые). MCP-side фиксы F2/F4 активны со старта новой сессии (свежие серверы — reconnect не понадобился) |
| 2026-06-11 | **P5 DONE: сводка §4.1 + cleanup** | Итог: **23 PASS / 2 FAIL-by-design / 3 FAIL governance / 1 N/A** (см. §4.1). Observability 7d: 9 fresh / 0 stale / 1 cold (`circuit`=F10). **Cleanup `[CHAIN-TEST]` полный:** 9 паттернов (`delete_pattern`), 11 сообщений (`delete_message`), 12 рёбер link_registry (supports 2 + derives_from 6 + mirrors 2 + promoted_to 1 + bare-дубль), wiki-драфт + 4 promote-блока в log.md, 4 `surfaced-patterns-chain-test-*.json`, 1 строка `patterns.jsonl` skill-learning; `cleanup_memory_test_pollution.py` dry-run — 0 pytest-загрязнений. Контроль: grep по всем store'ам/wiki/cache = 0 остатков. **F13 (наблюдение, не чинилось):** WikiPromoter не идемпотентен по `log.md` — каждый re-promote того же паттерна аппендит дублирующийся блок (4 идентичных за день: C3 + re-run + Stop-хуки); draft перезаписывается корректно. Кандидат: dedup по (pattern_id, draft-slug) перед append |
| 2026-06-11 | **✅ Хвост закрыт итерацией [260611](260611_ROADMAP_MEMORY_GOVERNANCE_WIRING.md)** | F5/F8/F9/F10/F12/F13 (+F14) реализованы: D2/D3/D4 **FAIL → PASS-after-fix** — TTL enforcement до store'ов (archive/delete + честный ответ), versioning wire-minimal (ADR-V: route_and_save CREATE + propagation UPDATE + rollback со store-writeback), named breakers `propagation:<source>` + `failed_entities[]` в PropagationResult, vector-плечо `unified_search` больше не глотает исключения (`sources_failed`), promote идемпотентен (3 слоя), reinforce_miss → `missing`. Sink `circuit` ожил: observability 10/10 fresh. Подтверждение на MCP-уровне выполнено 2026-06-11: live re-run D2–D5 **PASS** после `/mcp reconnect` (детали в §18 260611; +F16-кандидат — rollback CREATE-снапшота не разворачивает `metadata.importance`). Вне scope остались F1 (мульти-target, нужно продуктовое решение) и F3 (perf hot-path) |
| 2026-06-10 | **🐛 F2: ai-плечо unified_search падало** (найдено A1-прогоном, исправлено) | `sources_failed: memory-ai "'<' not supported between float and str"` — 3 legacy-строки с `importance='high'/'medium'` (TEXT) роняли адаптер (`min(row[2] or 0.0, 1.0)`). Фикс 3 слоя: (1) данные — 3 строки → 0.9/0.6/0.9, эффект немедленный (ai-arm ожил, `sources_failed=[]`); (2) `_coerce_importance()` в [memory_orchestrator.py](../../src/memory/orchestrator/memory_orchestrator.py) — адаптер-read, `_save_to_target`-write, propagation-handler; (3) тот же коэрсер в [ai_memory/server.py](../../src/memory/ai_memory/server.py) `save_important_message`. Код MCP-side → активен после `/mcp reconnect`. **F3 (наблюдение):** surfacing hot-path 3.77–3.92s > 3s target, стадия qdrant ~2.0s; `session_id:null` в surfacing-логе при живом bridge-файле — косметика логирования |

---

## Связанные документы

- [27.12 Memory Systems Map §10](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) — мастер-схема (источник блоков)
- [27.12.7 Блок Потоки](../framework%20documentation/27_UNIFIED_MEMORY/27.12.7_Блок_Потоки.md) — пошаговые рельсы + точки разрыва
- [260609 Memory Remediation](260609_ROADMAP_MEMORY_REMEDIATION.md) / [260608 Unit-test remediation](260608_ROADMAP_UNIT_TEST_REMEDIATION.md) — фиксы, которые эта карта подтверждает в production
- [260605 Full Observability](260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md) — fact-trace / report, используемые как выход R5
- Skill: `memory-unified`
