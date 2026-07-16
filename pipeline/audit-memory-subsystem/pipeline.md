# Аудит слабых мест подсистемы памяти (research-only)

Дата: 2026-07-16. Тип: исследование, продуктовый код НЕ менялся.

## Триггер

`unified_search` вернул vector-плечо в `sources_failed`:
`'requirements' is not a valid PatternType` - одна точка Qdrant с типом вне enum
валит весь `search_patterns` (строгий `PatternType(...)` в
`src/memory/vector_memory/server.py:405` без per-item защиты).

## Метод

3 параллельных субагента-аудитора (read-пути / write-пути / оркестратор)
+ живая проба всех 153 точек `learned_patterns` (scratchpad-скрипт probe_lp.py,
read-only scroll).

## Итог (~25 дефектов, полный отчёт в транскрипте сессии)

Корневые классы:
1. **Read-side хрупкость**: `_pattern_from_payload` + `confidence._resolve_state`
   строгие (enum, 5× fromisoformat, float()) и переиспользуются 5 read-путями
   (search/list/get/decay-sweep/ForgetGate) без per-item изоляции - одна битая
   точка кладёт все инструменты. decay-sweep падает с частичной мутацией.
2. **Write-side без валидации**: из 8+ писателей enum проверяет только
   `save_pattern`. Дыры: `capture_pattern`→`confirm`→detach-harvest
   (skill_learning/server.py:182,303,424 - источник заражения при промоуте-73
   от 2026-07-06), Stop-харвест `pattern_harvest.py:311` (реинфекция из
   patterns.jsonl), `route_and_save` memory_orchestrator.py:1929 (пишет None).
3. **Merge-каденс стрипает поля силоса**: `PatternRecord` (merge_patterns.py)
   не знает `archived`/`content_hash`/`evidence_sources` - `--apply` воскрешает
   архивные и ослепляет дедуп.

Живые данные: 11 точек с невалидным `pattern_type`, 2 без типа/имени,
4 без `content_hash`, 3 дубля по `content_hash`. Даты/confidence чистые.
Плюс: RRF-дилюция пустыми плечами (unified_search.py:230), рассинхрон
vector-плеча оркестратора с server-фильтрацией (raw confidence, archived не
исключён), 10 `reinforce_error` WinError 10048 в lifecycle-логе за 2026-07-01.

## Решение

Фикс - отдельная задача (complex, 5+ файлов), двумя срезами:
- P0: `PatternType.coerce()` + per-item try в 5 циклах + валидация 3 писателей
  + миграция 13 грязных точек.
- P1: merge-passthrough неизвестных полей, RRF-дилюция, breaker для плеч,
  medium-хвост.
