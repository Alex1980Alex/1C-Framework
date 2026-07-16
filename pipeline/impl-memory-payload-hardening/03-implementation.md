# 03 — Реализация P0

Полная запись — [роадмап 260716 §18](../../docs/roadmap/260716_ROADMAP_MEMORY_PAYLOAD_HARDENING.md).

## Что легло (16 файлов, +1425/−273)

| Шаг | Файлы |
|---|---|
| P0.1 коэрсер | `vector_memory/models.py` (+`PatternType.coerce`, `normalize_pattern_type`, `coerce_float/int/dt`, alias-карта) |
| P0.2 толерантный read | `confidence.py`, `server.py`, `forget_gate.py`, `memory_orchestrator.py` (vector-плечо) |
| P0.3 писатели | `pattern_harvest.py` (`_build_payload` + `quarantine_items`), `memory_orchestrator._save_to_target` (2 ветки), `skill_learning/server.py` |
| single-source | `normalize_light_patterns.py`, `reflection.py` — карты стали производными |
| P0.4 миграция | `scripts/migrate_pattern_types.py` (новый) |
| P0.5 тесты | `tests/unit/test_pattern_type_contract.py` (33) |

## Сообщение коммита

```
fix(memory): payload из store = недоверенный вход (роадмап 260716 P0)

Инцидент: одна точка learned_patterns с pattern_type 'requirements'
роняла весь search_patterns и клала vector-плечо unified_search в
sources_failed — строгий PatternType() в цикле без per-item защиты.

Два независимых дефекта, оба закрыты:
- READ: единый PatternType.coerce + coerce_float/int/dt (models.py) во
  всех парсерах payload; per-item try в 5 циклах (search/list/decay/
  plan_forget/vector-плечо) с честными счётчиками items_skipped/errors/
  unreadable. decay-sweep больше не обрывается посреди прохода.
- WRITE: 3 автоматических писателя нормализуют тип на границе записи
  (harvest, route_and_save обе ветки, capture_pattern) + провенанс в
  metadata.original_pattern_type. save_pattern намеренно строгий.

Alias-карта единственная: CATEGORY_MAP в normalize_light_patterns и
reflection стали производными (бит-в-бит совпали с прежними).

Данные: migrate_pattern_types.py (dry-run + backup + идемпотентно)
ре-штамповал 20 точек Qdrant, 16/76 patterns.jsonl, 7/42 pending;
backfill_content_hash — 4 хеша. Дедуп 3 дублей НЕ применён: тул слеп к
link_registry и удалил бы канон cross_store_sync (роадмап P1.7,
предупреждение в докстринге).

Тесты: 33 новых, весь unit-сьют 2289 зелёный. Live: до миграции 20
грязных точек читались без исключения, после — 0. Заодно починен
предсуществующий тест-таймбомб test_memory_first_surfacing (_T0
2026-01-01 «recent», за 196 дней распад перешагнул порог).
```
