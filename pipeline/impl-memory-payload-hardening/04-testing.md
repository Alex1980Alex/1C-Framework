# 04 — Тестирование и верификация P0

## Автотесты

| Прогон | Результат |
|---|---|
| `tests/unit/test_pattern_type_contract.py` (новый) | **36 тестов** зелёные |
| Весь unit-сьют (`-m unit`) | **2292 passed**, 2 skipped |
| ruff по затронутым файлам | чисто (4 остаточные ошибки — предсуществующие в `gate_policy.py`/`sonar_*`, не мои) |
| compile-smoke `scripts` + `.claude/hooks` | ok |
| Import-smoke 3 MCP-серверов + 2 хуков | ok (риск новых импортов снят) |

## Тесты не проходят вхолостую (проверено саботажем)

Порча ассерта/откат фикса → тест краснеет, возврат → зелёный:

| Откат | Что покраснело |
|---|---|
| `items_skipped == 1` → `999` | async-тест изоляции (доказывает, что async реально исполняются) |
| `expired_at=coerce_dt(...)` → строгий `fromisoformat` | `test_pattern_from_payload_survives_every_defect`, `test_get_pattern_survives_poisoned_point` |
| else-ветка `coerce_float(raw_succ)` → `float(raw_succ)` | `test_garbage_counts_branch_is_tolerant` (F4) |

## Live-верификация (реальный Qdrant, in-process)

MCP-серверы держат старый код до `/mcp reconnect`, поэтому новый код проверялся
импортом в процесс — это честнее, чем гонять устаревший сервер.

**До миграции** (грязные данные на месте — главное доказательство):
- 20 точек вне enum → `_pattern_from_payload` прочитал **20/20 без исключения**;
- `search_patterns` → count=5, `items_skipped`=0;
- `VectorMemorySearchAdapter` (плечо, падавшее в инциденте) → 5 items, no raise;
- точка `GMFM-6470` с `'requirements'` (та самая) вернулась первой как
  `workflow-pattern`.

**После миграции:** 0 грязных точек, поиск живой.

## Критерии приёмки §5 роадмапа

| # | Критерий | Статус |
|---|---|---|
| 1 | Битая точка → инструменты живы, точка в skip | ✅ (unit + live) |
| 2 | Мусорный тип от писателя → в store только coerced + `original_pattern_type` | ✅ (3 писателя, тесты) |
| 3 | 0 точек вне enum / 0 без `content_hash` | ✅ Qdrant 0/153, силосы 0/76 и 0/42; хеши добиты |
| 3 | 0 дублей hash | ⚠ **НЕ выполнен осознанно** — тул дедупа удалил бы канон `cross_store_sync` (P1.7) |
| 4 | `merge --apply` не теряет `archived` | ⏭ P1.1 (вне P0) |
| 5 | `sources_failed` пусто при живом Qdrant | ✅ |

## Ревью

3 итерации, 4 независимых ревьюера-субагента (read-only контракт):
- **Итерация 1** (2 ревьюера, bug-fix-validation + quality-review) → оба PARTIAL,
  совпавшие находки (строгий `expired_at` в функции с докстрингом «Never raises»,
  `int()` на `application_count`, M5 в `reinforce.py`, миграция теряла строки,
  неполная фикстура) → все исправлены.
- **Итерация 2** → 9/9 подтверждены, регрессий нет; найдено F1-F7 (инертный яд в
  фикстуре, инцидент-класс в skill-learning-плече, непокрытая ветка каскада) →
  все исправлены.
- **Итерация 3** → финальная проверка F1-F7.

## Известные ограничения

- `/mcp reconnect` обязателен: живые `search_patterns`/`unified_search` до него на
  старом коде.
- 3 пары байт-дублей остаются (P1.7) — избыточны, но безвредны.
