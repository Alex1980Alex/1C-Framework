# 03 — Реализация: P1 роадмапа 260716

Все 9 пунктов P1 реализованы. M5 и M8 из §3.2 оказались уже закрытыми в P0
(итерации ревью 1 и 2) — проверено чтением кода, не переделывались.

## Что сделано

| # | Файл | Правка |
|---|---|---|
| P1.9 | [`confidence.py`](../../src/memory/vector_memory/confidence.py) | `LEGACY_SEED_CONFIDENCE = PRIOR_SUCCESS/(PRIOR_SUCCESS+PRIOR_FAILURE)` — **выведен** из prior, не литерал. Параметр `default_confidence` удалён (существовал только из-за расщепления). 4 call-site (`_pattern_from_payload` seed + денорм, decay-sweep, каскад) переведены на константу |
| P1.8 | [`server.py`](../../src/memory/vector_memory/server.py) | 3 импорта в `_cascade_confidence`: `memory.*` → относительные |
| P1.1 | [`merge_patterns.py`](../../src/memory/skill_learning/merge_patterns.py) | `PatternRecord.extra` (unknown-passthrough, известные поля выигрывают merge); `_load_patterns` → `(records, unreadable)`; непарсящиеся строки возвращаются на диск |
| P1.2 | [`unified_search.py`](../../src/memory/orchestrator/unified_search.py) | `max_rrf` суммируется только по плечам с хитами |
| P1.3 | [`unified_search.py`](../../src/memory/orchestrator/unified_search.py) + [`memory_orchestrator.py`](../../src/memory/orchestrator/memory_orchestrator.py) | `SourceError.error_type`; `resolve_after_hard_timeout` (чистая); breakers `search:<source>` через `allow_request()` до создания корутины; `sources_failed_detail` в trace; реестр общий с propagation |
| P1.4 | [`server.py`](../../src/memory/vector_memory/server.py) + [`memory_orchestrator.py`](../../src/memory/orchestrator/memory_orchestrator.py) | `search_pattern_points` — единственный владелец политики; тул и плечо оба зовут её |
| P1.6 | [`reinforce.py`](../../src/memory/vector_memory/reinforce.py) | `_default_client()` — процессный синглтон + `reset_default_client()` |
| M6 | [`ai_memory/server.py`](../../src/memory/ai_memory/server.py) | `_importance_expr()` — SQL-выражение, **выведенное** из `_IMPORTANCE_LABELS`; coerce на выходе |
| M7 | [`memory-first-hook.py`](../../.claude/hooks/memory-first-hook.py) | `_safe_float`; per-hit `try` в dense-арме |
| M9 | [`unified_search.py`](../../src/memory/orchestrator/unified_search.py) | `_naive(dt)` в `ScoreNormalizer` |
| M10 | [`normalize_light_patterns.py`](../../scripts/normalize_light_patterns.py) | `content_hash` в `normalize_payload` |
| P1.7 | [`dedupe_learned_patterns.py`](../../scripts/dedupe_learned_patterns.py) | `canonical_from_links` (mirror-chain), canonical-aware `pick_survivor`, `plan_link_moves`, `apply_link_plan`, бэкап+restore рёбер, fail-closed в `main()`, инвариант `dangling_links` |

## Отклонения от дизайна (осознанные)

**Д1 — P1.3 salvage: тест через чистую функцию + шов `HARD_TIMEOUT_FACTOR`.**
Дизайн предполагал прямой тест ветки. Замер показал: ветка почти недостижима —
корутина, глотающая `CancelledError`, побеждает и `wait_for`, **и** внешний
`asyncio.timeout` (проба: 1.03 с при потолке 0.15 с, TimeoutError не поднялся). При
исправных адаптерах все плечи разрешаются на 1.0× таймаута, то есть ДО потолка 1.5×.
Решение вынесено в чистую `resolve_after_hard_timeout`, а множитель потолка стал
константой-швом — тест инвертирует его и доводит движок до реальной ветки
детерминированно. Побочно: **находка** — комментарий у потолка обещает защиту от
«misbehaving wait_for», которой он не даёт (см. §18 роадмапа).

**Д2 — P1.1: сохранение непарсящихся строк.** Сверх буквы P1.1 (та требует только
passthrough полей). Тот же класс «прочитал и не вернул», что ревьюер P0 нашёл в
скрипте миграции (F6), в той же функции: джоб перезаписывает силос целиком, поэтому
«пропустить при чтении» = «удалить с диска».

**Д3 — M6 чинится в другую сторону, чем описано в аудите.** Роадмап: «TEXT-importance
молча выпадает (`TEXT >= 0.5` = false)». Замерено на sqlite3 — неверно: в SQLite
TEXT > любого REAL, поэтому такая строка (а) проходит фильтр всегда и (б) встаёт
ПЕРВОЙ в `ORDER BY importance DESC` (`'low'` обгоняет `0.99`). Живых TEXT-строк
0 из 154 → дефект латентный. Чинил реальный, а не описанный; разовая миграция
колонки не нужна (мигрировать нечего).

**Д4 — P1.7: `--apply` разблокирован, но не запущен** (решение A1 архитектуры).
Задача среза — снять запрет; запуск дедупа на живой коллекции = отдельное решение.

**Д5 — P1.9 без замера ранжирования.** Дизайн допускал, что нужен замер. Проба:
`default_confidence` реально решает у **0 из 153** точек (12 идут в legacy-ветку, но
у всех числовой `confidence`) → изменение ранжирования на текущих данных ровно нулевое.

## Найденное при реализации

**Собственный баг, пойманный тестом:** в `plan_link_moves` распаковка была
`src, tgt, ltype = lk["source_id"], lk["link_type"], lk["target_id"]` — имена и
значения разъехались, `tgt` получал ТИП связи. Следствие: intra-group рёбра не
схлопывались, ключи дедупа были мусорными, план плодил репойнты вместо удалений.
Поймано `test_repoint_collapses_into_an_existing_edge` до любого прогона на данных.
