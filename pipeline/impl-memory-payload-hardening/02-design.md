# 02 — Дизайн: P0 hardening памяти

Статус: **approved** (пользователь дал go-ahead по роадмапу 260716 §4 P0 —
дизайн-решения ниже фиксируют отклонения от него).

## Д1. Дом коэрсера — `vector_memory/models.py`

`models.py` = контрактный модуль (enum + dataclasses + `from_dict`), stdlib-only
(`dataclasses/datetime/enum/typing/math`), никого не импортирует → его может
импортировать и `confidence.py`, и хук `pattern_harvest.py` (через `src` в
`sys.path`), и MCP-серверы. Цикла нет: `models` ← `confidence` ← `server`.

API:
- `PatternType.coerce(value) -> PatternType` — принимает enum/str/None/что угодно.
- `normalize_pattern_type(value) -> (canonical: str, original: str | None)` —
  `original` не None только когда коэрсия реально сработала (писатели кладут его
  в `metadata.original_pattern_type` — провенанс не теряется).
- `coerce_float/coerce_int/coerce_dt` — safe-парсеры payload-полей
  (`coerce_float` отсекает NaN/inf: они бы отравили сортировку).

Нормализация ключа: `strip().lower().replace("_","-")` → `Error_Fix` = `error-fix`.

## Д2. Alias-карта — единственный источник

Ключи (по факту дрейфа в коллекции, аудит §2) + категории memory-ai, ранее
задублированные в `normalize_light_patterns.CATEGORY_MAP` и
`reflection._CATEGORY_MAP` (оба резолвятся через коэрсер, третьего дубля нет).

`error-fix|bugfix|debugging` → `debugging-heuristic`;
`1c-bsl|bsl|1c-query-optimization|1c-metadata-pattern` → `bsl-pattern`;
`requirements|workflow|testing-workflow|preference|feedback` → `workflow-pattern`;
`refactor-pattern|implementation` → `code-convention`;
`architecture-lesson|decision` → `architectural-principle`;
`reference|project` → `project-structure`.

**Дефолт** (None / отсутствует / неизвестное) = `workflow-pattern`.
⚠ Отклонение от текущего кода: `_pattern_from_payload` для ОТСУТСТВУЮЩЕГО ключа
давал `code-convention` (2 точки). Оба не-инвариантны (архивируемы по staleness),
разница косметическая; выбран единый дефолт для None/missing/unknown — меньше
веток, совпадает с роадмапом.

## Д3. `save_pattern` остаётся строгим (fail-closed)

Асимметрия намеренная: `save_pattern` = явный MCP-вызов с enum в схеме → честная
ошибка полезна вызывающему (и это текущее поведение, ломать нечего).
Коэрсят три АВТОМАТИЧЕСКИХ пути (harvest на Stop, route-классификация,
capture из tool-use), где исключение = потеря факта, а не обратная связь.

## Д4. `is_invariant` коэрсит (канонический тип правит везде)

Точка с `1c-bsl` теперь инвариантна так же, как `bsl-pattern` — иначе поиск
показывает один тип, а ForgetGate судит по другому. Существующие тесты
(`""` → False) сохраняются: `""` → `workflow-pattern` → не инвариант.

## Д5. Content-floor в `route_and_save` — только пустой контент

⚠ Отклонение от роадмапа P0.3 («content-floor `MIN_CONTENT_LEN`»). При
реализации: `MIN_CONTENT_LEN=25` — политика анти-флуда ХАРВЕСТЕРА; тихо ронять
20-символьный легитимный факт из ЯВНОГО save-API хуже, чем его сохранить.
Гейтим только пустой/whitespace контент (однозначно сломан: бесполезный эмбеддинг
+ схлопывание в `Deduplicator` по md5 пустой строки), и честно — через
существующий `failed_targets`, не молча.

## Д6. Миграция — переиспользовать существующие тулы

Новый скрипт делает ТОЛЬКО `pattern_type` (Qdrant + `patterns.jsonl`).
`content_hash` backfill → `scripts/backfill_content_hash.py` (существует),
дубли контента → `scripts/dedupe_learned_patterns.py` (существует: backup,
суммирование succ/fail, restore). Меньше нового кода = меньше риска.

⚠ Граница: backfill проставляет ПОЛЕ `content_hash`, но НЕ переносит точку под
канонический `uuid5(hash)`-id (это оборвало бы ссылки link_registry/versioning).
Значит id-level дедуп для этих 4 точек не оживёт — только field-level потребители
(cross_store_sync, fact-trace, карантинный дедуп).

## Д7. Per-item изоляция — контракт

Цикл ловит исключение вокруг разбора ОДНОЙ точки → `logger.warning` + счётчик:
- `search_patterns`/`list_patterns` → аддитивный ключ `items_skipped` в JSON-ответе;
- `decay_confidence` → `errors` в ответе; sweep продолжается (частичная мутация
  больше не обрывает проход);
- `plan_forget` → новое поле `ForgetPlan.unreadable` (нечитаемое НЕ архивируем —
  консервативно);
- vector-плечо оркестратора → `logger.warning`, плечо живо (это и есть инцидент).
