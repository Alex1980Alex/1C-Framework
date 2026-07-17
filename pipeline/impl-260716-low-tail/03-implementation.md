# 03 — Исполнение

5 фиксов + 1 задокументированный defer. Все минимальные, того же класса, что P0/P1.

| # | Файл | Изменение |
|---|---|---|
| 1 | [`ai_memory/server.py`](../../src/memory/ai_memory/server.py) `get_categories` | `round(row[2],2) if row[2] is not None else None` — NULL-safe |
| 2 | [`ai_memory/server.py`](../../src/memory/ai_memory/server.py) `delete_message` | `_cleanup_links`+`_record_ingest` каждый в свой `try/except Exception` + `logger.warning`; delete-успех не зависит от cleanup |
| 3 | [`maintenance/dashboard.py`](../../src/memory/maintenance/dashboard.py) `compute_docs_freshness` | оба операнда → naive-local (`x.astimezone().replace(tzinfo=None) if x.tzinfo else x`) |
| 5 | [`orchestrator/memcube.py`](../../src/memory/orchestrator/memcube.py) | `normalize_pattern_type(...)[0]` на обеих границах + import |
| 6 | [`unified_id.py`](../../src/memory/orchestrator/unified_id.py) ×2 + [`link_registry.py`](../../src/memory/orchestrator/link_registry.py) | `ValueError(... . Valid: {[m.value for m in cls]})` — остаётся ValueError |
| 4 | [`orchestrator/unified_search.py`](../../src/memory/orchestrator/unified_search.py) | **defer**: поясняющий комментарий (логика не тронута) |

## Замер по item 4 (RRF) — обоснование defer

`unified_search` на 10 запросах: 2/93 результата (2.2%) имели кросс-store дубль. Дубли —
почти всегда MIRRORS (один факт, синхронизированный `cross_store_sync`), не независимое
подтверждение → суммирование рангов бустило бы избыточность, не корроборацию. Валидатора
релевантности `unified_search` нет. Вывод: НЕ чинить, задокументировать (комментарий в коде
+ §18), чтобы будущий «фикс» не сломал намеренное поведение.

## Проверка отсутствия циклического импорта

memcube (orchestrator) → `..vector_memory.models` (stdlib-only контракт P0.1). Импорт-смоук
прошёл, `normalize_pattern_type(None)[0]=workflow-pattern`, `('requirements')[0]=workflow-pattern`.
