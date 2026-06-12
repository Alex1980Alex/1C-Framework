# 260612 — LinkRegistry Full Verification (связи между записями всех store'ов)

> Третий блок семейства full-verification (после
> [260612 memory-ai](260612_ROADMAP_MEMORY_AI_FULL_VERIFICATION.md) и
> [260612 pdf-docs](260612_ROADMAP_PDF_DOCS_FULL_VERIFICATION.md)).
> Объект: `LinkRegistry` — SQLite `data/link_registry.db`, колонка «не контент,
> а связи» в карте [27.12](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md).
> Методика 260610: каждая цепочка вход→store-инвариант→выход исполняема, отказы честные.

## 1. Инвентаризация (фактическое состояние 2026-06-12, live-снятие)

**Хранилище:** SQLite, 4 таблицы — `entity_links` (**32 ребра**), `link_history`
(61, только `create`), `link_stats` (73 сущности), `schema_info`. Env-override
`LINK_REGISTRY_PATH` (тест-изоляция 260609 P0.2). Даты рёбер: 2026-04-04 … 2026-06-11.

**Живые рёбра по типам:** `mirrors` 24 (creator `cross-store-sync`),
`derives_from` 6 (`reflection`), `supports` 2 (`system`). **7 из 10 заявленных
`LinkType` — 0 рёбер за всю историю** (`based_on`, `contradicts`, `extends`,
`session_context`, `promoted_to`, `superseded_by`, `graph_node`).

**Писатели (6):**
| # | Писатель | Тип рёбер | Состояние |
|---|----------|-----------|-----------|
| W1 | `cross_store_sync` (§26 P3, maintenance job) | MIRRORS (mirror→canonical) | **живой основной** (24/32) |
| W2 | reflection (§26 P2) | DERIVES_FROM | живой (6) |
| W3 | MCP `create_link` (orchestrator, ручной/агентский) | любой | живой, но редкий (3, `system`) |
| W4 | `route_and_save` авто-link ([memory_orchestrator.py:648](../../src/memory/orchestrator/memory_orchestrator.py)) | SESSION_CONTEXT | **подозрение на спящий**: код есть, 0 рёбер |
| W5 | `WikiPromoter` ([wiki_promoter.py:184](../../src/memory/librarian/wiki_promoter.py)) | PROMOTED_TO | **спящий**: opt-in `link_registry` не подключён в production-вызовах (F13 сделал payload-маркер каноном) |
| W6 | TTL-cascade `delete_links_for_entity` (P2.G5 260612 memory-ai) | удаление | живой (отрицательный писатель) |

**Читатели (8):**
| # | Читатель | Канал | Состояние |
|---|----------|-------|-----------|
| R1 | `get_related` / `get_full_context` (BFS) | MCP | живой |
| R2 | `LinkEnricher` → `linked_entities[]` в `unified_search` | hot path | живой (виден в каждой выдаче) |
| R3 | `memory_research` (relationships/anomalies/clusters) | MCP | живой |
| R4 | `memory_graph_analyze` (PageRank/centrality/communities) | MCP | живой, но **декоративный на 32 рёбрах** |
| R5 | `_cascade_confidence` (vector_memory, горячий `apply_pattern`) | SUPPORTS/EXTENDS/BASED_ON/DERIVES_FROM | живой код, но **рабочих рёбер этих типов 2** → каскад почти всегда no-op |
| R6 | `PropagationEngine` BFS (типизированные веса) | `propagate_update` | живой |
| R7 | maintenance dashboard «link stats» | отчёт | живой |
| R8 | `roadmap_progress_log.py links` (CI lint wikilink'ов) | ci.yml | живой |

## 2. Проблема (что нашла инвентаризация)

- **L1 — типология обещает больше, чем существует**: 7/10 `LinkType` без единого
  production-ребра; у 4 из них (`based_on`, `contradicts`, `superseded_by`,
  `graph_node`) нет вообще ни одного писателя в коде, кроме ручного `create_link`.
  Карта 27.12 и skill `memory-unified` перечисляют все 10 как живую типологию.
  Прямой аналог D2/D4 из pdf-docs: заявлено — не существует.
- **L2 — 3 ребра с сырыми UUID** вместо unified-ID (`49362a90-…`, без
  `type:source:` префикса; creator `system`, эпоха до тест-изоляции 260609).
  Для TTL-cascade они `unparseable_id`, для BFS — слепые узлы, для
  `cross_store_index` — невидимы. Класс G1: легаси-формат тихо живёт в store.
- **L3 — history однобокий**: `link_history` журналирует только `create`
  (61 создано, 32 живо → **29 удалений прошли мимо журнала**: test-pollution
  cleanup 260609 + `delete_links_for_entity`). Провенанс связей неполный —
  «почему ребро исчезло» невосстановимо.
- **L4 — `link_stats` рассинхронизирован**: 73 сущности при 32 рёбрах
  (≤64 endpoint'ов) — таблица не чистится при удалениях, счётчики стале.
- **L5 — каскад/propagation голодают**: R5/R6 зависят от типов
  `supports/extends/based_on/derives_from`, которых живых 8 — каскады
  confidence почти всегда no-op, и это **молча** (нет метрики «каскад пуст»).
- **L6 — спящие авто-писатели**: W4 (SESSION_CONTEXT) — код в `route_and_save`
  есть, рёбер 0 (условие не срабатывает или путь мёртв); W5 (PROMOTED_TO) —
  параметр не передаётся. Либо подключить, либо ретирировать тип.
- **L7 — наблюдаемость**: операции с рёбрами не эмитятся в §27 trace_log
  (есть только dashboard-счётчики); fact-trace не показывает рождение/смерть связи.
- **Тестовое покрытие**: unit'ы registry есть, но e2e цепочек
  (sync→ребро→enrichment / link→cascade) и контракта честных отказов — нет.

Целевая модель: **каждый заявленный LinkType либо имеет живого писателя и
исполняемую цепочку до читателя, либо ретирован ADR'ом; все рёбра в unified-ID
формате; history полный (create+delete); рассинхрон stats невозможен или чинится
maintenance-джобом; пустой каскад виден в метриках.**

## 3. Тест-карта цепочек вход→выход

### Блок A — входы
| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| A1 | W1 mirrors | `cross_store_sync --apply` на знаемом дубле → ребро | idempotent (re-run = 0 новых), mirror→canonical направление, unified-ID оба конца |
| A2 | W2 derives_from | reflection-джоб на свежем семантическом факте | ребро semantic→episodic, виден в `get_related` |
| A3 | W3 manual | `create_link` валидный/невалидный ID | валидный — ребро+history; невалидный — честная ошибка (не тихий приём сырого UUID — см. L2) |
| A4 | W4 session_context | `route_and_save` с условием авто-линка | либо ребро появляется, либо ADR-ретирование типа |
| A5 | W6 cascade-delete | `memory_ttl_cleanup` сущности с рёбрами | рёбра удалены + `links_removed` в ответе + **запись delete в history (после P0.3)** |

### Блок B — выходы
| # | Цепочка | Шаги | Критерий |
|---|---------|------|----------|
| B1 | R1 BFS | created-ребро → `get_related` depth 1-2 | находится, strength/direction честные |
| B2 | R2 enrichment | `unified_search` по контенту с ребром | `linked_entities[]` несёт ребро |
| B3 | R5 cascade | `apply_pattern` на паттерне с `supports`-ребром | confidence соседа сдвинулся; на паттерне без рёбер — **метрика «cascade_empty»** (после P3) |
| B4 | R4 graph | `memory_graph_analyze` | числа согласованы с entity_links (не с link_stats до P0.2) |
| B5 | R8 CI lint | wikilink на несуществующую память | lint падает (регресс-защита уже в ci.yml — подтвердить живым прогоном) |

### Блок C — отказы (honest-failure, контракт 260611)
| # | Цепочка | Критерий |
|---|---------|----------|
| C1 | БД залочена/отсутствует | читатели отдают честную ошибку/пустоту с reason, hot-path `unified_search` не падает (enrichment fail-soft в `sources_failed`/лог) |
| C2 | Ребро на удалённую сущность (dangling) | BFS/enrichment не врут контентом: dangling помечен или отфильтрован осознанно |
| C3 | Сырой UUID (legacy L2) | TTL/propagation отвечают `unparseable_id`, не exception |

## 4. Фазы

### P0 — Гигиена store (фундамент)
| # | Задача | Критерий |
|---|--------|----------|
| P0.1 | **L2**: миграция/чистка 3 raw-UUID рёбер — резолвить в unified-ID по `cross_store_index`, неразрешимые удалить с записью в history; `create_link` валидирует формат ID (reject сырых UUID) | 0 unparseable рёбер; вход защищён |
| P0.2 | **L4**: rebuild `link_stats` из `entity_links` (idempotent-скрипт) + пересчёт в maintenance-каденсе | stats == агрегат рёбер |
| P0.3 | **L3**: `delete_links_for_entity`/`delete_link` пишут `action=delete` в `link_history` (+`changed_by`) | удаления журналируются |
| P0.4 | Baseline-снятие: счётчики по типам/креаторам в §18 (повторить после фаз) | числа в §18 |

### P1 — ВХОД: цепочки A1-A5 + ADR-типология
| # | Задача | Критерий |
|---|--------|----------|
| P1.1 | A1/A2/A3 живыми прогонами + unit на идемпотентность sync | PASS |
| P1.2 | **ADR-L1 (главное решение)**: каждый из 7 пустых типов → подключить писателя (W4 session_context, W5 promoted_to — уже написаны) ИЛИ ретирировать из `LinkType`+карты+скилла. Дефолт по образцу ADR-D2: ретирование без доказанного спроса; `based_on` уже non-goal по линии pdf-docs D4 | типология в коде == типологии в доке == живым рёбрам |
| P1.3 | По итогам ADR: либо включить W4/W5 (+live-цепочка), либо удалить спящий код | нет спящих писателей |

### P2 — ВЫХОД: цепочки B1-B5
- Live: B1/B2/B4 на данных P1; B3 — изготовить паттерн с `supports`-ребром и
  прогнать `apply_pattern` (заодно первый production-каскад); B5 — негативный
  прогон CI lint.
- Unit: BFS depth/strength-фильтры, enrichment fail-soft (C1) — без Qdrant.

### P3 — Наблюдаемость (§27-паритет)
| # | Задача | Критерий |
|---|--------|----------|
| P3.1 | `write_trace` события `link_create`/`link_delete` (sink `memory-links.log`) + регистрация в `known_sinks` | fact-trace тредит жизнь ребра |
| P3.2 | Метрика «cascade_empty» в `_cascade_confidence` + счётчик в dashboard | пустые каскады видны (L5) |
| P3.3 | Dashboard: link stats из `entity_links` (после P0.2), по типам и креаторам | отчёт честный |

### P4 — Acceptance (2 недели, каркас `acceptance_common.py` — 4-й потребитель)
0 unparseable рёбер; history delete-полный; stats синхронны; типология без
пустых деклараций (ADR-L1 исполнен); B1-B3 smoke зелёные; C1-C3 честные;
link-события в observability-отчёте.

## 5. Порядок и оценка

P0 (0.5d) → P1 (0.5-1d, **ADR прежде кода** — ретирование может закрыть половину
без строчки) → P2 (0.5d) → P3 (0.5d) → P4 (0.5d каркас + 2 недели). Перед каждой
фазой — повторная инвентаризация ([[project-roadmap-audit-pattern]]: блок крошечный,
32 ребра, оценки скорее завышены).

## 6. Риски

- **Чистка L2 необратима** — перед удалением неразрешимых рёбер: dump в
  `data/reports/memory/link_registry_pre_p0_dump.json` (32 ребра — копия дёшева).
- **Ретирование типов** ломает enum-импорты — grep по `LinkType.<X>` перед
  удалением (R5/R6 перечисляют типы в весах — обновить синхронно).
- **W4/W5 включение** = новые писатели в hot-path (`route_and_save`) — fail-soft
  обязателен, по образцу D7-проводки (ошибка реестра не роняет основную операцию).
- **history-рост**: журналирование delete на крошечном объёме безопасно; cap не нужен.

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-12 | Roadmap создан | Live-инвентаризация: 32 ребра (mirrors 24 / derives_from 6 / supports 2; креаторы cross-store-sync/reflection/system), 7/10 LinkType пусты, 3 raw-UUID ребра (до-изоляционная эпоха), history только create (61 created vs 32 live — 29 удалений вне журнала), link_stats 73 сущности при ≤64 endpoint'ах; писатели W1-W6 (W4/W5 спящие), читатели R1-R8 (R4 декоративен, R5 голодает — L5); findings L1-L7; тест-карта A1-A5 / B1-B5 / C1-C3 |
