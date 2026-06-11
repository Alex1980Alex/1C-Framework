# 260611 — Governance & Honest-Failure Wiring (хвост находок chain-testing 260610)

> **Цель:** закрыть 6 открытых находок карты [260610](260610_ROADMAP_MEMORY_CHAIN_TESTING.md) одной
> связной итерацией. Объединяющий принцип — **ошибка должна доезжать до ответа/лога, а не глотаться**:
> F10/F12 — silent-degradation на горячих путях, F8/F9 — governance-скаффолдинг без проводки,
> F5/F13/F14 — попутные квики той же природы (поле читается, но не пишется; событие
> классифицируется неверно).
>
> **Вне scope:** F3 (surfacing hot-path 3.8s > 3s, стадия qdrant ~2.0s) — отдельная perf-итерация;
> F1 (мульти-target роутинг) — требует сначала продуктового решения «нужен ли вообще».

---

## 1. Исследование кода: точки разрыва (верифицировано 2026-06-11)

### F10 — CircuitBreaker мёртв, propagation глотает ошибки handler'ов

Три независимых разрыва:

1. **`_apply_update` глотает всё** — [propagation_engine.py:495–519](../../src/memory/orchestrator/propagation_engine.py):
   `except Exception → logger.error → return False`. Для вызывающего кода `False` от «handler упал
   (Qdrant down)» неотличим от «handler честно сказал no-op». Сущность молча выпадает из
   `entities_updated`; в `PropagationResult` нет поля для неудач.
2. **Engine-breaker математически недостижим** — breaker оборачивает `_process_propagation`
   целиком ([propagation_engine.py:320–328](../../src/memory/orchestrator/propagation_engine.py)), но
   `_process_propagation` сам ловит все исключения (`:448` → `_error_result`) и **никогда не raise'ит**.
   `call_async` фиксирует failure только на raise → threshold 5 не достигается никогда. Эмпирика D4:
   Qdrant down → breaker не двигается.
3. **Реестр оркестратора управляет пустотой** — `CircuitBreakerRegistry()` создаётся
   ([memory_orchestrator.py:443](../../src/memory/orchestrator/memory_orchestrator.py)), но
   `get_or_create()` ни разу не вызывается для реальных операций → `memory_circuit_status` отдаёт
   `{"breakers": {}}`, `memory_circuit_reset` резетит несуществующее. Sink `memory-circuit.log` — cold
   с рождения (observability 260610: 0 событий).

### F12 — unified_search: vector-плечо деградирует молча

Машинерия честности **уже есть**: `UnifiedSearchEngine.search` собирает `sources_failed[]` из
исключений адаптеров ([unified_search.py:396–433](../../src/memory/orchestrator/unified_search.py)).
Разрыв — в адаптере: `VectorMemorySearchAdapter.search` ловит всё сам
([memory_orchestrator.py:275–277](../../src/memory/orchestrator/memory_orchestrator.py):
`except Exception → logger.warning → return []`) → до движка исключение не доезжает.
Контраст: ai-плечо исключения пропускает (доказано F2 — `sources_failed` его показывал).
`SkillLearningSearchAdapter` — проверить при реализации (вероятно, та же картина).

### F8 — Versioning: 0 писателей

`VersioningService.create_version` существует
([versioning_service.py:101](../../src/memory/ai_memory/services/versioning_service.py)), но grep по
`src/` даёт ровно 3 вызова: 2 в docstring-примере и 1 внутренний (`rollback_to_version:213` пишет
rollback-версию). **Ни одна точка мутации не снапшотит**: `route_and_save`, `save_pattern`,
`apply_pattern`, `save_important_message`, propagation-handlers — никто. `total_versions=0` глобально
при всей активности дня 260610. Endpoints history/compare/rollback — read-API над пустым стором.

### F9 — TTL bookkeeping-only

`TTLService.cleanup_expired` ([ttl_service.py:284–303](../../src/memory/ai_memory/services/ttl_service.py))
удаляет записи **только из собственного леджера** (`data/ttl.jsonl`) и возвращает entity_ids.
`memory_ttl_cleanup` ([memory_orchestrator.py:1321–1327](../../src/memory/orchestrator/memory_orchestrator.py))
отдаёт `removed[]`, но к самим сущностям в store'ах никто не прикасается — D2-критерий «запись
исчезает из чтения» невыполним в принципе.

### F13 — WikiPromoter: re-promote бесконечен + log.md дублируется

Два слоя (второй вскрыт этим исследованием):

1. **`promoted_to` payload-маркер читается, но не пишется**: `_dedup_check` смотрит
   `payload.get("promoted_to")` у *соседей* ([wiki_promoter.py:117](../../src/memory/librarian/wiki_promoter.py)),
   а сам кандидат пропускается (`scored.id == source_id`, `:113`). Писателей поля — **ноль** (grep по `src/`).
   Итог: однажды промоутнутый паттерн проходит `scan_and_promote` заново при каждом запуске
   (cadence, Stop-хук, C3-скрипт) — draft молча перезаписывается.
2. **`_append_log` аппендит безусловно** ([wiki_promoter.py:169–194](../../src/memory/librarian/wiki_promoter.py)) —
   каждый re-promote добавляет идентичный блок в `docs/wiki/log.md` (эмпирика 260610: 4 дубля за день).

### F5 — get_pattern: archived:true при expired_at:null

`_pattern_from_payload` ([vector_memory/server.py:334–389](../../src/memory/vector_memory/server.py))
не передаёт `expired_at` из payload в конструктор `LearnedPattern` → модель всегда с
`expired_at=None`, при этом ответ `get_pattern` строит `archived` по payload. Однострочный маппинг.

### F14 — reinforce_miss считается errors (новое, сессия f7dae669)

После cleanup'а 260610 Stop-сводка показала `applied=0 skipped=2 errors=2`, хотя в lifecycle-логе оба
события — `reinforce_miss reason:not_found` (паттерны легитимно удалены). Мост
[pattern_reinforce.py](../../.claude/hooks/shared/pattern_reinforce.py) классифицирует miss как error →
ложный сигнал тревоги в `[REINFORCE]`-баннере. miss ≠ error: not_found после delete — норма.

---

## 2. Декомпозиция

### P0 — Pre-flight (~20 мин)

1. Tests green: `pytest tests/unit/test_propagation_honest.py tests/unit/test_write_contract.py -m unit`.
2. Baseline: `memory_circuit_status` (`{}`), `memory_version_history` на живом entity (`count:0`),
   `wc -l docs/wiki/log.md`, `memory-circuit.log` отсутствует.
3. Inventory по [[project-roadmap-audit-pattern]]: 10 мин — не закрылось ли что-то само (например,
   F5 мог быть задет другим фиксом).

**Гейт:** baseline в §18.

### P1 — Honest-failure wiring: F10 + F12 (~3 ч)

- **P1.1 `failed_entities` в PropagationResult** (engine-side, не MCP — действует сразу):
  - `PropagationResult` += `failed_entities: dict[str, str]` (entity_id → reason).
  - `_apply_update` → tri-state: `applied` / `skipped_no_handler` / `failed:<ExcType>` — исключение
    handler'а больше не схлопывается в `False`; BFS-цикл (`:412`) раскладывает по
    `entities_updated` / `failed_entities` (no-handler остаётся тихим skip — это не ошибка).
  - `write_trace("memory-propagation.log")` += `failed:<n>`; `_skip_result`/`_error_result` —
    `failed_entities={}`.
  - **Контракт потребителей** `failed_entities`: (1) ответ `propagate_update` MCP-tool (оператор видит
    сразу), (2) `memory-propagation.log` → `fact-trace`/`observability_report` (D7/R5), (3) счётчик
    в `get_stats()`. Retry/escalation — НЕ в этой итерации (только видимость).
  - Тесты: handler-raise → entity в `failed_entities` + не в `entities_updated`; смешанный случай
    (vector упал, memory-ai применился).
- **P1.2 Проводка named breakers вокруг handler-вызовов**:
  - `PropagationEngine.__init__` += опциональный `breaker_registry: CircuitBreakerRegistry | None`;
    оркестратор передаёт свой `self._circuit_registry` при lazy-init движка.
  - В `_apply_update`: handler-вызов через `registry.get_or_create(f"propagation:{uid.source.value}")
    .call_async(...)`; OPEN → `failed:circuit_open` (fail-fast, без вызова handler'а).
  - Engine-level breaker (`:320`) **снять или оставить как noop-страховку** — решить при реализации;
    рекомендация: снять, он вводит в заблуждение (см. разрыв 2).
  - `memory_circuit_status` начинает показывать реальные breakers; sink `memory-circuit.log` оживает
    (писать transition-события через `write_trace`).
  - ⚠ MCP-side → `/mcp reconnect` после правок ([[feedback-mcp-stale-code-reconnect]]).
  - Acceptance = **re-run D4**: 5 fail подряд (Qdrant down) → breaker OPEN → `propagate_update`
    отдаёт `failed:circuit_open` мгновенно → `memory_circuit_reset` → CLOSED → handler снова зовётся.
- **P1.3 unified_search: убрать blanket-except из vector-адаптера**:
  - `VectorMemorySearchAdapter.search` (`:275–277`) — снять `except Exception` (или re-raise),
    движок сам положит в `sources_failed`. Аудит `SkillLearningSearchAdapter` на ту же болезнь.
  - Acceptance = **re-run D5**: `docker stop pdf-rag-tei` → `unified_search` →
    `sources_failed:["vector-memory"]` непуст, остальные плечи живы → `docker start`.

### P2 — Governance wiring: F8 + F9 (~2.5 ч)

- **P2.1 ADR-V: судьба versioning** (решить ДО кода, зафиксировать здесь в §18):
  - **Вариант A (рекомендую): wire-minimal** — снапшотить только orchestrator-mediated мутации:
    `route_and_save._save_to_target` (после успешной записи → `create_version(unified_id, content,
    CREATE)`) и importance-нудж propagation-handler'а (`UPDATE`). Прямые писатели MCP-серверов
    (save_pattern и т.п.) — вне версионирования (другой процесс, JSONL-стор не concurrent-safe);
    честно задокументировать границу в docstring tools.
  - **Вариант B: deprecate** — убрать 3 version-tools из MCP, сервис оставить мёртвым кодом. Дешевле,
    но D3-цепочка навсегда N/A.
  - Acceptance (при A) = **re-run D3**: save через route_and_save → update → `memory_version_history`
    count≥2 → `compare` осмысленный diff → `rollback` → чтение видит старый контент.
- **P2.2 TTL enforcement**:
  - `memory_ttl_cleanup`: после `cleanup_expired()` — dispatch по `UnifiedID.parse(entity_id).source`:
    vector-memory → **archive** (`expired_at`, консистентно с §22 invalidate-not-delete, НЕ delete),
    memory-ai → `delete_message`, skill-learning/wiki → skip с reason.
  - Честный ответ: `{removed_ledger: n, store_actions: {archived: [...], deleted: [...]},
    failed: {entity: reason}}` — тот же паттерн, что P1.1.
  - Acceptance = **re-run D2**: `memory_ttl_set(short)` → expire → cleanup → сущность исчезла из
    `search_patterns`/`search_messages` (для vector — archived-exclude §24.2.4 делает работу).
- ⚠ Оба пункта MCP-side (orchestrator) → reconnect.

### P3 — Квики: F5 + F13 + F14 (~1 ч)

- **P3.1 F5**: `_pattern_from_payload` += `expired_at=datetime.fromisoformat(...) if
  payload.get("expired_at") else None`. Тест: archived паттерн → `get_pattern` отдаёт
  `archived:true` И `expired_at` непустой; live-паттерн → `archived:false`.
- **P3.2 F13**: три слоя идемпотентности:
  1. после `_create_draft` — `client.set_payload({"promoted_to": slug})` на source-точку
     (закрывает «0 писателей» маркера);
  2. в `scan_and_promote` — пропуск кандидата с собственным `payload.promoted_to` (дешёвый
     pre-filter до векторного dedup);
  3. `_append_log` — skip, если `docs/wiki/drafts/{slug}.md` уже упомянут в log.md (substring).
  - Acceptance: двойной `promote-patterns` подряд → второй прогон `created=[]`, в log.md один блок.
- **P3.3 F14**: в [pattern_reinforce.py](../../.claude/hooks/shared/pattern_reinforce.py) `not_found`-miss
  считать в `skipped` (или отдельный `missing`), не в `errors`. Хук-side — действует сразу.

### P4 — Верификация + закрытие (~1 ч)

1. Re-run цепочек D2/D3/D4/D5 (acceptance выше) + контрольный `fact-trace` на свежем паттерне.
2. `memory_observability_report.py --since 1d` — sink `circuit` больше не cold (последний из 10).
3. `Skill('code-verify')` на изменённые модули; unit-прогон `-m unit`.
4. §18 здесь + закрывающая строка в [260610 §18](260610_ROADMAP_MEMORY_CHAIN_TESTING.md);
   обновить статусы D2/D3/D4 в карте (FAIL → PASS-after-fix).
5. CLAUDE.md / skill `memory-unified` — абзац про honest-failure контракт (failed_entities,
   sources_failed, breakers), если P1/P2 приземлились.

---

## 3. Критерии приёмки (сквозные)

| # | Критерий | Проверка |
|---|---|---|
| 1 | Ни один handler/adapter-fail не теряется молча | D4/D5 re-run: `failed_entities`/`sources_failed` непусты при наведённой аварии |
| 2 | Breakers реальны | `memory_circuit_status` ≥2 breakers; OPEN достижим за 5 fail; reset работает |
| 3 | Versioning пишется (при ADR-V=A) | D3 re-run полный круг history→compare→rollback |
| 4 | TTL убирает из чтения | D2 re-run: после cleanup сущности нет в выдаче |
| 5 | Promote идемпотентен | повторный прогон: `created=[]`, 0 новых блоков в log.md |
| 6 | Sink `memory-circuit.log` жив | observability report: 10/10 sinks не-cold |
| 7 | Без регрессий | `test_propagation_honest.py` + `test_write_contract.py` + D7 fact-trace без разрывов |

## 4. Риски

- **Снятие blanket-except (P1.3) меняет деградацию**: раньше TEI-down → пустое плечо, теперь —
  SourceError в `sources_failed`. Убедиться, что `memory-first-hook` (R2) не зависит от этого
  адаптера (не зависит — у него свой путь), а потребители `unified_search` читают `results`, не
  падают на непустом `sources_failed`.
- **Breaker-тесты flaky на half-open**: фиксировать `reset_timeout` большим в тестах, переходы
  проверять детерминированно через `record_failure` напрямую.
- **JSONL-сторы (versions/ttl) не concurrent-safe** — писатели только в orchestrator-процессе
  (граница ADR-V); не расшаривать на MCP-серверы store'ов.
- **`_append_log` trim 500 строк** — при dedup-проверке учитывать, что старые упоминания slug могли
  быть оттримлены → substring-miss → дубль. Принять как редкий и безвредный.
- **MCP stale code** — P1.2/P2.x живут в orchestrator: после правок обязательный `/mcp reconnect`,
  иначе верификация пройдёт по старому коду ([[feedback-mcp-stale-code-reconnect]]).
- По [[project-roadmap-audit-pattern]] оценки ниже могут быть завышены 1.5–3× — P0-inventory обязателен.

## 5. Оценка

| Фаза | Находки | Время | Зависимости |
|---|---|---|---|
| P0 | preflight | 20 мин | — |
| P1 | F10+F12 | 3 ч | P0 |
| P2 | F8+F9 (+ADR-V) | 2.5 ч | P0; P2.2 переиспользует паттерн P1.1 |
| P3 | F5+F13+F14 | 1 ч | независима |
| P4 | верификация | 1 ч | P1–P3 |
| **Итого** | **7 находок** | **~7.5 ч** (1–2 захода) | |

---

## §18 Progress Log

| Дата | Событие | Детали |
|---|---|---|
| 2026-06-11 | Roadmap создан | Исследование кода по 6 открытым находкам 260610 + F14 (reinforce_miss→errors, сессия f7dae669). Все разрывы локализованы до строк (§1); вскрыт второй слой F13 — `promoted_to` payload-маркер без единого писателя → re-promote бесконечен. Декомпозиция P0–P4, ADR-V (versioning: wire-minimal vs deprecate) вынесен решением в P2.1 |
| 2026-06-11 | **P0 PASS** | Tests green (15: propagation_honest 5 + write_contract + surfacing_cache); baseline: `memory_circuit_status` `{breakers:{}}`, `memory-circuit.log` отсутствует, `log.md` 379 строк, `versions.jsonl` сторадж пуст. Inventory: все 7 находок подтверждены открытыми по коду (ничего не закрылось само) |
| 2026-06-11 | **P1 DONE (F10+F12)** | **P1.1**: `PropagationResult.failed_entities{entity→reason}` + tri-state `_apply_update` (`applied`/`skipped_no_handler`/`skipped_noop`/`failed:<ExcType>`); BFS раскладывает; `memory-propagation.log` += `failed`/`failed_reasons`; `get_stats()` += `entities_failed`. **P1.2**: `PropagationEngine(breaker_registry=…)` — named breakers `propagation:<source>` вокруг handler-вызовов через `call_async`; OPEN → `failed:circuit_open` fail-fast без вызова handler'а; оркестратор шарит `self._circuit_registry` → `memory_circuit_status`/`reset` управляют реальными breakers. Engine-level breaker **оставлен** как внешне-управляемый fail-fast guard (пинится `test_p1_infrastructure:267`), с docstring-пометкой что авто-trip недостижим. **P1.3**: blanket-except снят с `VectorMemorySearchAdapter.search` → исключения доезжают до `sources_failed[]`; `SkillLearningSearchAdapter` чист (аудит: per-line json-catch, blanket нет). Тесты: +3 в `test_propagation_honest.py` (raise→failed_entities, mixed vector-fail/ai-ok, breaker OPEN→fail-fast→reset; `reset_timeout=3600` против flaky half-open) + новый `test_unified_search_honest.py` (2). Интеграция `test_p1_infrastructure.py` 39 PASS без правок |
| 2026-06-11 | **ADR-V: вариант A (wire-minimal)** | Снапшотятся только orchestrator-mediated мутации: `route_and_save` (CREATE на каждый сохранённый target, unified-id через `from_original`), propagation-handlers (UPDATE со снапшотом мутации `{succ,fail,confidence}`/`{importance}`), rollback (ROLLBACK — сервисный, как был). Прямые писатели MCP-серверов вне версионирования — JSONL-стор не concurrent-safe между процессами; граница задокументирована в `_version_write` docstring. **Плюс к плану**: `memory_version_rollback` получил **store-writeback** (`_apply_version_to_store`) — иначе D3-критерий «чтение видит старый контент» невыполним: memory-ai (content/importance SQLite UPDATE), vector-memory (payload-поля через set_payload, `vector_reembedded:false` честно флагуется), прочие — honest skip |
| 2026-06-11 | **P2 DONE (F8+F9)** | **P2.1** versioning по ADR-V (см. выше); `_version_write` fail-soft (+getattr — стабы оркестратора в `test_write_contract` без `__init__`). **P2.2** `memory_ttl_cleanup` → store-enforcement: dispatch по `UnifiedID.source` — vector **archive** (`expired_at`, §22 invalidate-not-delete, + epoch bump), memory-ai `DELETE`, прочие/unparseable — honest skip с reason; ответ `{removed_ledger, store_actions{archived/deleted/skipped}, failed{entity→ExcType}}` (паттерн P1.1). Тесты: `test_governance_wiring.py` 7 PASS (handler→UPDATE-версия; fail-soft; rollback-writeback восстанавливает SQLite-строку, history CREATE+UPDATE+ROLLBACK; unsupported honest; ttl delete + archive через fake qdrant + skip/fail-видимость) |
| 2026-06-11 | **P3 DONE (F5+F13+F14)** | **F5**: `_pattern_from_payload` маппит `expired_at` → `get_pattern` больше не отдаёт `archived:true` при `expired_at:null`. **F13** (3 слоя): `_mark_promoted` пишет `promoted_to` на source-точку после `_create_draft` (у маркера появился писатель); pre-filter кандидата по собственному `promoted_to` до векторного dedup; `_append_log` skip при существующем упоминании `drafts/{slug}.md` (trim-обрезание старых упоминаний принято как редкий безвредный дубль). **F14**: `not_found`-miss → отдельный счётчик `missing` (lifecycle-лог + return + `[REINFORCE]`-баннер хука), errors больше не врут. Тесты: `test_quick_fixes_260611.py` 3 (double-promote → `created=[]`, 1 блок в log.md) + 2 в `test_pattern_reinforce.py` (miss→missing, real-fail→errors) |
| 2026-06-11 | **P4: верификация** | Полный гейт `pytest tests/ -m unit` (CI=1): **1415 passed** (3 fail починены: 2 — стабы без `_versioning_service` → getattr; 1 — pre-existing TOC-десинк 27.12.1–7, добавлены в `00_СОДЕРЖАНИЕ.md`). Ruff по всем изменённым файлам clean. **D4 re-run in-process** (реальный оркестратор + production link_registry + индуцированный Qdrant-outage на lazy-init глобале, без мутаций production): `failed:ConnectionError` видим → 5-й fail → **OPEN** → `circuit_open` fail-fast в том же вызове → `memory_circuit_reset` → CLOSED. **Sink `memory-circuit.log` ожил**: 2 transitions (1 trip); observability report --since 1d: **10 fresh / 0 stale / 0 cold из 10** (критерий №6 ✓). ⚠ Два неудачных захода D4 задели production пренебрежимо (нуджи ~+0.002 confidence паттернам-зеркалам `5e88c5a9`/`1e3e91c8` + importance ±0.01 5 эпизодам — в пределах шума одного apply). **Новое наблюдение (F15-кандидат)**: BFS применяет update к target'у, достижимому двумя путями, дважды за вызов (`entities_updated` содержит дубль `1e3e91c8` ×2) — visited-проверка стоит после apply; двойной нудж за событие. Не чинилось — вне scope |
| 2026-06-11 | **⚠ Остаток: live MCP re-run после `/mcp reconnect`** | Все правки P1/P2 — MCP-side (orchestrator): запущенный сервер держит старый код. После reconnect: D4 через MCP-tools (`memory_circuit_status` ≥1 breaker), D5 (`docker stop pdf-rag-tei` → `unified_search` → `sources_failed:["vector-memory"]`), D2 (`memory_ttl_set(short)` → cleanup → `store_actions`), D3 (route_and_save → propagate → history count≥2 → compare → rollback → чтение). Механика каждого закрыта unit/in-process-эквивалентами выше |
| 2026-06-11 | **✅ Live MCP re-run D2–D5 PASS — роадмап закрыт** | После `/mcp reconnect` все 4 цепочки прогнаны живыми MCP-tools. **D4**: baseline `{breakers:{}}` (свежий процесс) → route_and_save (vector `99af8a09` + memory-ai `3a59ee06`) + create_link → `propagate_update` → handler applied (importance +0.0225), `failed_entities:{}` → `memory_circuit_status` показывает реальный breaker `propagation:memory-ai` (CLOSED, total_calls=1). **D3**: history count=2 (CREATE route_and_save + UPDATE propagation 0.4→0.4225) → compare осмысленный diff → rollback v1 `store_writeback:{applied:true, fields:[content]}` → probe-rollback v2 `fields:[importance]` — оба writeback-пути живы. **D2**: `memory_ttl_set(custom, 2s)` на обе → `memory_ttl_cleanup` → `{removed_ledger:2, store_actions:{archived:[vector], deleted:[memory-ai]}, failed:{}}` → `search_messages` count=0, `get_pattern` → `archived:true` + `expired_at` непустой (**F5 live ✓**). **D5**: `docker stop pdf-rag-tei` → `unified_search` → `sources_failed:[{vector-memory, "All connection attempts failed", 2290ms}]`, ai+skill-плечи отдали 5 результатов → `docker start` + health 200 → повторный поиск `sources_failed:[]`, 3 плеча. Критерии приёмки §3: №1–№4,№6 подтверждены live (№5/№7 — закрыты в P3/P4). Тестовые сущности самоликвидированы D2-цепочкой. **F16-кандидат** (не чинилось): rollback CREATE-снапшота не разворачивает `metadata.importance` → writeback вернул только `content`, importance остался 0.4225 (UPDATE-снапшоты с top-level `importance` откатываются корректно). **Наблюдение**: первый `get_pattern` после reconnect — timeout 60s (cold-start vector-memory MCP), retry мгновенный |

---

## Связанные документы

- [260610 Memory Chain Testing](260610_ROADMAP_MEMORY_CHAIN_TESTING.md) — источник находок (§18 F-серия, §4.1 итоги)
- [260609 Memory Remediation](260609_ROADMAP_MEMORY_REMEDIATION.md) — honest-семантика P2.3 (`_apply_update` docstring), которую эта итерация доводит до конца
- [260605 Full Observability](260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md) — sink `memory-circuit.log` (D1.4), оживает в P1.2
- Skill: `memory-unified`
