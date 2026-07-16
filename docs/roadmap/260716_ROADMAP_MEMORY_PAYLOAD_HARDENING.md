# 260716 - Hardening подсистемы памяти: payload = недоверенный вход

> Триггер: живой инцидент 2026-07-16 - `unified_search` вернул vector-плечо в
> `sources_failed` с ошибкой `'requirements' is not a valid PatternType`. Разбор
> показал: баг не единичный, а представитель системного класса «payload из
> store читается как доверенный вход». Факты собраны тремя параллельными
> код-аудитами (read-пути / write-пути / оркестраторный слой, все ссылки
> file:line подтверждены чтением кода) + живой пробой всех 153 точек
> `learned_patterns` (scroll, read-only). Research-артефакт:
> [`pipeline/audit-memory-subsystem/pipeline.md`](../../pipeline/audit-memory-subsystem/pipeline.md).
> Связанные роадмапы: 260609 (write-contract P1), 260611 (honest-failure),
> 260602 §26 (ingestion/sync), 260605 §27 (observability).

## §1 Инцидент и корневые классы

Одна точка Qdrant с `pattern_type` вне enum валит весь `search_patterns`
(строгий `PatternType(...)` в
[`server.py:405`](../../src/memory/vector_memory/server.py) без per-item
защиты) → оркестратор кладёт vector-плечо в `sources_failed`, поиск деградирует
до memory-ai + skill-learning.

Три корневых класса (все подтверждены кодом и данными):

1. **Read-side хрупкость.** Строгие десериализаторы `_pattern_from_payload`
   ([`server.py:373-434`](../../src/memory/vector_memory/server.py)) и
   `confidence._resolve_state` / `should_archive`
   ([`confidence.py:197-208, 281`](../../src/memory/vector_memory/confidence.py))
   переиспользуются пятью read-путями БЕЗ per-item изоляции - одна битая точка
   кладёт сразу: `search_patterns`, `list_patterns`, `get_pattern`,
   `decay_confidence`-sweep, `ForgetGate.plan_forget`, surfacing
   `memory-first-hook` и vector-плечо `unified_search`.
2. **Write-side без валидации.** Из 8+ писателей в `learned_patterns` enum
   проверяет ровно один (`save_pattern`). Остальные - pass-through произвольных
   строк и даже `None`.
3. **Merge-каденс стрипает поля силоса.** `PatternRecord`
   ([`merge_patterns.py:33-73`](../../src/memory/skill_learning/merge_patterns.py))
   не знает `archived`/`content_hash`/`evidence_sources` - `--apply`
   перезаписывает `patterns.jsonl` без них: архивные записи воскресают
   (и снова харвестятся в Qdrant), карантинный дедуп по `content_hash` слепнет.

## §2 Состояние данных (проба 153 точек, 2026-07-16)

| Дефект данных | Кол-во | Комментарий |
|---|---|---|
| `pattern_type` вне enum | 11 | `error-fix` ×9... фактически 13 значений-нарушителей суммарно c разовыми (`requirements` ×2, `1c-bsl`, `workflow`, `architecture-lesson`, `refactor-pattern`, `testing-workflow`, `1c-query-optimization`, `1c-metadata-pattern`) |
| `pattern_type` отсутствует (и `name` пуст) | 2 | источник - `route_and_save` с `metadata.pattern_type=None` |
| `content_hash` отсутствует | 4 | вне дедуп-контракта §26 P1.3 |
| Дубли по `content_hash` | 3 пары | дедуп-инвариант уже нарушен |
| Даты / confidence / счётчики | чисто | tz-aware дат нет, битых ISO нет |

## §3 Реестр находок

### 3.1 HIGH

| # | Находка | Где | Класс |
|---|---|---|---|
| H1 | `search_patterns` падает ДВАЖДЫ на битой точке: сперва `payload_effective_confidence` (строгие `float()`/`fromisoformat`), затем `_pattern_from_payload` (enum + 5× `fromisoformat` + `float(succ/fail)`). Фиксить обе, иначе фикс enum бесполезен | [`server.py:725, 405`](../../src/memory/vector_memory/server.py), [`confidence.py:197-208`](../../src/memory/vector_memory/confidence.py) | read |
| H2 | `handle_decay_confidence` - sweep всей коллекции без per-item try; падение посреди прохода = **частичная мутация** (часть точек decayed/archived, epoch не бампнут). Плюс `payload = point.payload` без `or {}` | [`server.py:936-984`](../../src/memory/vector_memory/server.py) | read+mutate |
| H3 | `list_patterns` - «диагностический browse» валится от той же битой точки, которую должен помогать находить (к enum толерантен, к битым датам/None-полям - нет) | [`server.py:882`](../../src/memory/vector_memory/server.py) | read |
| H4 | `ForgetGate.plan_forget` - локальный `_days_idle` ловит ошибки, но делегат `should_archive` строгий → весь maintenance-план не строится | [`forget_gate.py:92-98`](../../src/memory/maintenance/forget_gate.py) | read |
| H5 | Vector-плечо оркестратора - тот же цикл без изоляции (сам инцидент). In-process импорт `_pattern_from_payload` - парсер общий, а запрос/фильтрация продублированы | [`memory_orchestrator.py:309-328`](../../src/memory/orchestrator/memory_orchestrator.py) | read |
| H6 | `capture_pattern`→`confirm`→detach-harvest: `pattern_type` свободная строка по всей цепочке (схема `"type":"string"` без enum). Именно так промоут 73 паттернов 2026-07-06 занёс мусорные типы | [`skill_learning/server.py:182, 303, 424`](../../src/memory/skill_learning/server.py) | write (root cause) |
| H7 | Stop-харвест - pass-through типов из `patterns.jsonl` в Qdrant на каждом Stop → **реинфекция** после любой чистки коллекции, пока грязен силос | [`pattern_harvest.py:311, 327`](../../.claude/hooks/shared/pattern_harvest.py) | write |
| H8 | `route_and_save`→vector-memory: `metadata["pattern_type"]` пишется как есть (вкл. `None` - источник 2 безымянных точек); `confidence` без clamp; `content` без floor; при провале импорта `hash_content` - точка под uuid4 БЕЗ `content_hash` (тихий выход из дедупа) | [`memory_orchestrator.py:1846, 1908, 1929, 1934`](../../src/memory/orchestrator/memory_orchestrator.py) | write |
| H9 | Merge-каденс (§1 класс 3): воскрешение архивных + слепой дедуп. Job живой - каденс §БП G2 | [`merge_patterns.py:33-73, 279`](../../src/memory/skill_learning/merge_patterns.py), [`memory_maintenance.py:264`](../../../scripts/memory_maintenance.py) | write |

### 3.2 MEDIUM

| # | Находка | Где |
|---|---|---|
| M1 | RRF-дилюция пустыми плечами: `max_rrf` суммируется по всем зарегистрированным источникам, вкл. вернувшие 0 - хит из одного плеча при трёх получает базу ~0.33 и может уйти под `min_score=0.3` (упавшие плечи из знаменателя исключены, пустые - нет; несимметрично) | [`unified_search.py:230, 463`](../../src/memory/orchestrator/unified_search.py) |
| M2 | Hard-timeout salvage подменяет реальную ошибку плеча строкой `hard_timeout` - честная причина теряется | [`unified_search.py:423-438`](../../src/memory/orchestrator/unified_search.py) |
| M3 | Упавшие search-плечи не подключены к circuit breaker (breakers только у propagation) и в `memory-read.log` уходят без причины (только имена) | [`unified_search.py:417-422, 497`](../../src/memory/orchestrator/unified_search.py) |
| M4 | Vector-плечо оркестратора разошлось с `search_patterns`: фильтр по сырому `confidence` (не effective) и НЕ исключает архивные (`expired_at`) - через `unified_search` всплывает то, что прямой поиск прячет | [`memory_orchestrator.py:296-320`](../../src/memory/orchestrator/memory_orchestrator.py) |
| M5 | `apply_pattern` - TypeError в форматировании лога ПОСЛЕ `set_payload`: мутация прошла, клиент получил Error, lifecycle-запись потеряна | [`server.py:785, 794`](../../src/memory/vector_memory/server.py) |
| M6 | memory-ai: легаси TEXT-importance молча выпадает из `get_important_messages` (SQLite type ordering: `TEXT >= 0.5` = false); `_coerce_importance` защищает только новые записи | [`ai_memory/server.py:42, 210-222`](../../src/memory/ai_memory/server.py) |
| M7 | memory-first-hook: фолбэк `float(payload.get("confidence", 0.5))` падает на явном `None` ИЗ except-ветки; в lexical-арме тихо обрезает выдачу, в dense-арме маскирует payload-баг под `tei: down` (ложная диагностика) | [`memory-first-hook.py:481, 551, 698`](../../.claude/hooks/memory-first-hook.py) |
| M8 | `SkillLearningSearchAdapter` - `fromisoformat(created_at)` per-строка без guard (C2-фикс сделан только в memory-ai-плече) | [`memory_orchestrator.py:383-385`](../../src/memory/orchestrator/memory_orchestrator.py) |
| M9 | `ScoreNormalizer.normalize` - `datetime.now() - item.created_at`: одна tz-aware дата валит ВЕСЬ unified_search (после сбора плеч, вне per-adapter защиты). Данные сейчас чистые - мина | [`unified_search.py:160`](../../src/memory/orchestrator/unified_search.py) |
| M10 | `normalize_light_patterns` при `overwrite_payload` теряет `content_hash` → повторный save того же контента создаст дубль | [`normalize_light_patterns.py:123-149, 262`](../../../scripts/normalize_light_patterns.py) |
| M11 | 10 живых `reinforce_error` (WinError 10048, исчерпание эфемерных портов) в lifecycle-логе 2026-07-01 - reinforce-мост создаёт соединение на паттерн | [`reinforce.py`](../../src/memory/vector_memory/reinforce.py), лог `confidence-lifecycle.log` |

### 3.3 LOW (по мере касания)

`models.py:136` `LearnedPattern.from_dict` - спящий дубль строгого парса
(KeyError + enum; in-repo вызовов нет); `ai_memory get_categories`
`round(None,2)`; `delete_message` - узкий except после commit;
`forget_gate._days_idle` early-return 0 обрывает цепочку фолбэков;
`dashboard.compute_docs_freshness` aware/naive смещение на tz-offset;
RRF не суммирует ранги кросс-store дублей (ключ - unified_id с префиксом
источника, multi-source подтверждение не бустит); `memcube.py:213,234` -
небезопасные дефолты + не-content-derived id (конвертеры orphaned, latent);
`SourceServer`/`LinkType.from_string` - голый ValueError вместо
структурированной ошибки.

## §4 Дорожная карта

### P0 - закрыть инцидент и класс (один срез, ~5 файлов + тесты)

| Шаг | Содержание | Закрывает |
|---|---|---|
| P0.1 | **Канонический коэрсер** `PatternType.coerce(value)` в [`models.py`](../../src/memory/vector_memory/models.py): alias-карта (`error-fix`→`debugging-heuristic`, `1c-bsl`→`bsl-pattern`, `requirements`/`workflow`/`testing-workflow`→`workflow-pattern`, `architecture-lesson`→`architectural-principle`, `1c-query-*`/`1c-metadata-*`→`bsl-pattern`), `None`/неизвестное → `workflow-pattern` + оригинал в `original_pattern_type`. Единственный источник соответствий - свести сюда дубли карт из `normalize_light_patterns.py:51` и `reflection.py:57` | H1, H6-H8 (фундамент) |
| P0.2 | **Толерантный read**: `_pattern_from_payload` - safe-parse (coerce + fromisoformat/float под защитой); `_resolve_state`/`should_archive` - защита от явных `None` (`.get(k, d)` не покрывает `null`); per-item try/except + счётчик `items_skipped` в 5 циклах-потребителях (search/list/decay/forget_gate/оркестраторное плечо). Битая точка = skip с логом, НЕ смерть инструмента. decay-sweep дополнительно: `payload or {}`, bump epoch по факту сделанного | H1-H5 |
| P0.3 | **Валидация на 3 писателях**: `pattern_harvest._build_payload` (закрывает Stop-харвест, confirm-harvest, quarantine), `route_and_save._save_to_target` (оба target'а: coerce + clamp confidence [0,1] + content-floor `MIN_CONTENT_LEN`), схема+handler `capture_pattern` (enum в inputSchema + coerce в handler - грязь не попадает даже в pending) | H6-H8 |
| P0.4 | **Миграция данных**: скрипт по образцу `normalize_light_patterns.py` (dry-run default, backup): перештамповка 13 точек с невалидным/отсутствующим типом через ту же alias-карту, backfill `content_hash` 4 точкам, разбор 3 пар дублей (keep по большему `application_count`); чистка `pattern_type` в `data/skill_learning/patterns.jsonl` (иначе реинфекция H7 до первого Stop) | данные §2 |
| P0.5 | **Тесты + верификация**: unit на coerce (все alias + None + неизвестное), per-item skip (битая точка среди здоровых - N-1 результатов), запрет записи невалидного типа всеми 3 писателями; live-прогон `search_patterns` и `unified_search` ДО миграции (толерантность к текущей грязи) и ПОСЛЕ (0 skip). `/mcp reconnect` обязателен (MCP-side правки) | - |

Инвариант P0: коэрсер один, импортируется всеми писателями и читателями;
read-side толерантен даже к тому, что write-side теперь не пропускает
(защита от старых данных и будущих писателей).

### P1 - устойчивость оркестратора и каденса (второй срез)

| Шаг | Содержание | Закрывает |
|---|---|---|
| P1.1 | Merge-fix: passthrough неизвестных полей в `PatternRecord` (`extra: dict` + сериализация обратно), сохранение `archived`/`content_hash`/`evidence_sources`; регресс-тест «merge не теряет поля» | H9 |
| P1.2 | RRF: пустые плечи вон из знаменателя `max_rrf` (симметрия с упавшими); тест «хит из 1 плеча при 3 зарегистрированных не тонет под min_score» | M1 |
| P1.3 | Honest-failure хвост: hard-timeout сохраняет реальную ошибку задачи (`task.exception()` прежде `hard_timeout`); `error_type` в trace `memory-read.log`; search-плечи в breaker-реестр `search:<source>` (симметрия с `propagation:<source>`) | M2, M3 |
| P1.4 | Сведение vector-плеча оркестратора с server-логикой: фильтр по effective confidence + исключение `expired_at` (или экспорт общей функции поиска из `server.py` вместо дубля) | M4 |
| P1.5 | Медиум-хвост vector_memory/memory-ai/hook: `apply_pattern` лог-формат до мутации (M5), TEXT-importance read-time coerce + разовая миграция колонки (M6), `float(None)`-фолбэк и честный trace dense-арма (M7), guard `created_at` в skill-learning-плече (M8), tz-normalize в `ScoreNormalizer` (M9), `content_hash` в `normalize_payload` (M10) | M5-M10 |
| P1.6 | Reinforce-мост: один QdrantClient на прогон (не per-pattern) - убрать WinError 10048 | M11 |

LOW-хвост (§3.3) - без отдельного среза, по мере касания файлов.

### Не-цели

- Семантический (не байтовый) дедуп в Qdrant - остаётся за merge-каденсом.
- Версионирование прямых писателей MCP-серверов (ADR-V wire-minimal не
  пересматривается).
- Автmiграция legacy TEXT-importance «на лету» при каждом чтении - только
  разовый скрипт + read-time coerce.

## §5 Acceptance

1. Точка с `pattern_type='requirements'`, `confidence=null`, битым `created_at`
   в коллекции → `search_patterns`/`list_patterns`/`decay_confidence`/
   `plan_forget`/`unified_search` живы, точка в `items_skipped`, остальные
   результаты полные.
2. `capture_pattern`/`route_and_save` с мусорным `pattern_type` → в store
   попадает только coerced-значение (+ `original_pattern_type`).
3. Проба §2 после миграции: 0 точек вне enum, 0 без `content_hash`,
   0 дублей hash.
4. `merge --apply` на силосе с `archived=true` записью → поле переживает merge.
5. `sources_failed` при живом Qdrant и текущих данных - пусто (regression
   исходного инцидента).

## §18 Progress Log

> Append-only, reverse-chronological. Новые записи - СВЕРХУ.

### 2026-07-16 - Роадмап создан по итогам аудита

- Триггер-инцидент воспроизведён, корень подтверждён (строгий enum в
  `_pattern_from_payload` + невалидированные писатели).
- 3 параллельных код-аудита (read/write/orchestrator) + проба 153 точек:
  ~25 дефектов, реестр в §3, данные в §2.
- План: P0 (коэрсер + толерантный read + 3 писателя + миграция) → P1
  (merge-fix, RRF, breakers, medium-хвост). Реализация НЕ начата.
- Research-артефакт: `pipeline/audit-memory-subsystem/pipeline.md`; память:
  `project-memory-payload-audit-fix-pending`.
