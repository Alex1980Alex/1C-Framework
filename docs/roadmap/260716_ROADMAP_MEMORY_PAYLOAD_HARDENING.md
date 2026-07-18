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

> ⚠ Счёт исправлен при реализации P0.4: изначально в этой таблице стояло «11»
> — сложены только `error-fix` ×9 + `requirements` ×2, а 7 одиночных значений
> не добавлены. Реальный масштаб — **18 точек вне enum + 2 без ключа = 20**
> (подтверждено планом миграции).

| Дефект данных | Кол-во | Комментарий |
|---|---|---|
| `pattern_type` вне enum | **18** | `error-fix` ×9, `requirements` ×2 + 7 одиночных (`1c-bsl`, `workflow`, `architecture-lesson`, `refactor-pattern`, `testing-workflow`, `1c-query-optimization`, `1c-metadata-pattern`) |
| `pattern_type` отсутствует (и `name` пуст) | 2 | источник - `route_and_save` с `metadata.pattern_type=None` |
| `content_hash` отсутствует | 4 | вне дедуп-контракта §26 P1.3 |
| Дубли по `content_hash` | 3 пары | дедуп-инвариант уже нарушен |
| Даты / confidence / счётчики | чисто | tz-aware дат нет, битых ISO нет |

Силосы skill-learning (найдено при P0.4, в аудите не измерялось):
`patterns.jsonl` 16 из 76 записей вне enum, `pending_patterns.jsonl` 7 из 42
(включая ранее не встречавшиеся `debugging`, `solution`) — прямое подтверждение
H7 (Stop-харвест pass-through): силос и коллекция дрейфовали синхронно.

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

> **СТАТУС 2026-07-18: LOW-хвост закрыт срезом `pipeline/impl-260716-low-tail/`.**
> Исправлены: `get_categories round(None)`, `delete_message` (post-commit side-effects +
> non-dict metadata), `dashboard.compute_docs_freshness` tz, `memcube` coerce, 3×
> `from_string` message. **RRF кросс-store дублей — measured DEFER** (2/93 результата,
> дубли = MIRRORS ≠ корроборация; см. §18 2026-07-18). Уже были закрыты ранее:
> `LearnedPattern.from_dict` (P0.2), `forget_gate._days_idle` (F7). **Остаётся открытым
> только вопрос потолка hard-timeout** (design-вопрос, L-new ниже) — не код-фикс.

**L-new (найдено при P1.3, 2026-07-17):** hard-timeout salvage-ветка
[`unified_search.py`](../../src/memory/orchestrator/unified_search.py) почти
недостижима, а её комментарий обещает защиту, которой нет: потолок 1.5× написан на
случай «per-adapter `wait_for` misbehaves (thread pool exhaustion, event loop
starvation)», но корутина, глотающая `CancelledError`, побеждает и `wait_for`, и
внешний `asyncio.timeout` одинаково (замер: 1.03 с при потолке 0.15 с, TimeoutError
не поднялся). При исправных адаптерах все плечи разрешаются на 1.0×, то есть ДО
потолка. Ветка живёт только при starvation ИЗВНЕ движка. Решение вынесено в чистую
`resolve_after_hard_timeout` (тестируется), множитель — константа-шов
`HARD_TIMEOUT_FACTOR`. Вопрос «нужен ли потолок в текущем виде» — открыт.

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

### P0 - закрыть инцидент и класс — ✅ РЕАЛИЗОВАНО 2026-07-16 (детали в §18)

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

### P1 - устойчивость оркестратора и каденса (второй срез) — ✅ РЕАЛИЗОВАНО 2026-07-17 (детали в §18)

> Правки по факту реализации: **M5/M8 уже были закрыты в P0** (итерации ревью 1 и 2);
> **M6 чинился в противоположную сторону** — диагноз в §3.2 перевёрнут, разовая
> миграция колонки отменена (0 строк); **P1.7 `--apply` разблокирован, но не запущен**
> (отдельное решение). Формулировки ниже — как планировалось, фактическое — в §18.

| Шаг | Содержание | Закрывает |
|---|---|---|
| P1.1 | Merge-fix: passthrough неизвестных полей в `PatternRecord` (`extra: dict` + сериализация обратно), сохранение `archived`/`content_hash`/`evidence_sources`; регресс-тест «merge не теряет поля» | H9 |
| P1.2 | RRF: пустые плечи вон из знаменателя `max_rrf` (симметрия с упавшими); тест «хит из 1 плеча при 3 зарегистрированных не тонет под min_score» | M1 |
| P1.3 | Honest-failure хвост: hard-timeout сохраняет реальную ошибку задачи (`task.exception()` прежде `hard_timeout`); `error_type` в trace `memory-read.log`; search-плечи в breaker-реестр `search:<source>` (симметрия с `propagation:<source>`) | M2, M3 |
| P1.4 | Сведение vector-плеча оркестратора с server-логикой: фильтр по effective confidence + исключение `expired_at` (или экспорт общей функции поиска из `server.py` вместо дубля) | M4 |
| P1.5 | Медиум-хвост vector_memory/memory-ai/hook: `apply_pattern` лог-формат до мутации (M5), TEXT-importance read-time coerce + разовая миграция колонки (M6), `float(None)`-фолбэк и честный trace dense-арма (M7), guard `created_at` в skill-learning-плече (M8), tz-normalize в `ScoreNormalizer` (M9), `content_hash` в `normalize_payload` (M10) | M5-M10 |
| P1.6 | Reinforce-мост: один QdrantClient на прогон (не per-pattern) - убрать WinError 10048 | M11 |
| P1.9 | **Расщеплённый дефолт seed-confidence** (находка при самопроверке итерации 3): при отсутствующем/null `confidence` легаси-точка сеется по-разному — `_resolve_state` (read-path) даёт 0.5, `_pattern_from_payload`/`_vector_memory_handler` — 0.70, decay-sweep — 0.5. Самосогласован **prior 0.70**: сев от него, `derive_confidence` остаётся РОВНО на prior (n=4 → 0.70), а от 0.5 тянет вниз (0.643) — т.е. read-path занижает легаси-точки в ранжировании. Сейчас расщепление сделано ЯВНЫМ (`_resolve_state(..., default_confidence=)`, дефолт 0.5 = поведение не изменено), унификация на prior — отдельная правка (трогает ранжирование → нужен замер) | новое |
| P1.8 | **Каскад молча выключен от порядка вызовов** (находка итерации 3, НОВОЕ): [`_cascade_confidence`](../../src/memory/vector_memory/server.py) импортирует `memory.orchestrator.link_registry` (namespace `memory.*`, НЕ `src.memory.*`), но `<repo>/src` попадает в `sys.path` **только внутри `_get_embedding`** (лениво). Значит `apply_pattern` до первого эмбед-вызова в процессе → `ModuleNotFoundError` → функциональный `except: pass` → каскад тихо no-op; после — работает. Порядок-зависимое поведение, скрытое широким except. Фикс: явный path-setup на уровне модуля либо `from ..orchestrator.link_registry import ...` (относительный, как `.models`). Тест `test_cascade_survives_bad_neighbour` вынужденно воспроизводит path-состояние — комментарий там же | новое |
| P1.7 | **Link-aware дедуп** (находка P0.4, НОВОЕ): [`dedupe_learned_patterns.py`](../../scripts/dedupe_learned_patterns.py) слеп к `link_registry` — (а) удаляет точки, на которые есть рёбра (живая проверка: все 3 delete-кандидата несли `derives_from`+`mirrors` → 10 висячих рёбер), (б) **противоречит** `cross_store_sync`: ребро `mirrors: A→B` означает «B канон», а `pick_survivor` выбирал A и удалил бы канон B. Фикс = RE-POINT рёбер лоузеров на выжившего + уважение существующего canonical-назначения, НЕ «удалить и рёбра». До фикса `--apply` запрещён (предупреждение в докстринге тула); 3 пары дублей остаются — они избыточны, но не вредны | §2 дубли |

LOW-хвост (§3.3) - без отдельного среза, по мере касания файлов.

### Не-цели

- Семантический (не байтовый) дедуп в Qdrant - остаётся за merge-каденсом.
- Версионирование прямых писателей MCP-серверов (ADR-V wire-minimal не
  пересматривается).
- Автmiграция legacy TEXT-importance «на лету» при каждом чтении - только
  разовый скрипт + read-time coerce.

## §5 Acceptance

> **СТАТУС 2026-07-17: все 5 пунктов закрыты.** §5.1/5.2/5.4 запинены тестами;
> §5.3 закрыт запуском `dedupe_learned_patterns.py --apply` на живой коллекции
> (154→151, 0 дублей hash), §5.5 подтверждён live (`sources_failed=[]`). Детали — §18
> (запись 2026-07-17 ночь-2). Роадмап 260716 выполнен полностью.

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

### 2026-07-18 - §3.3 LOW-хвост закрыт (5 фиксов + measured-defer RRF)

Пайплайн `pipeline/impl-260716-low-tail/`. Каждый пункт СВЕРЕН с кодом до правки
(роадмап сам документировал перевёрнутые диагнозы — M6/P1.9/P1.3 — verify-before-fix
обязателен).

**Исправлено (5, все sabotage-verified):**
- **Item 1** [`ai_memory/server.py`](../../src/memory/ai_memory/server.py) `get_categories` —
  `round(AVG(importance))` падал `TypeError` на группе со всеми-NULL (`AVG→NULL`); теперь
  `None` (JSON null).
- **Item 2** `delete_message` — post-`commit()` side-effects (`_cleanup_links`/`_record_ingest`)
  роняли уже совершённый delete в ошибку клиенту; теперь каждый в своём `try` + warning.
  **+ находка ревьюера** (тот же класс рядом): metadata = валидный НЕ-dict JSON (`[...]`) →
  `(x or {}).get` `AttributeError` мимо узкого except → тоже закрыто (`isinstance(parsed, dict)`,
  [[feedback-payload-untrusted-input]]).
- **Item 3** [`dashboard.py`](../../src/memory/maintenance/dashboard.py) `compute_docs_freshness` —
  naive-dt + aware-now стрипал tzinfo без конверсии фрейма (сдвиг на tz-offset); теперь оба
  операнда → naive-local (паттерн M9). Все 4 комбо aware/naive верны.
- **Item 5** [`memcube.py`](../../src/memory/orchestrator/memcube.py) — недоверенный
  `metadata.pattern_type` коэрсится (`normalize_pattern_type`, P0.3 writer-контракт); дефолты
  выровнены на канонический. Конвертеры orphaned → live-эффект 0, цикла импорта нет.
- **Item 6** [`unified_id.py`](../../src/memory/orchestrator/unified_id.py) ×2 +
  [`link_registry.py`](../../src/memory/orchestrator/link_registry.py) `from_string` — `ValueError`
  теперь перечисляет valid-значения (остаётся ValueError → вызывающие не сломаны).

**Item 4 (RRF кросс-store дубли) — measured DEFER, НЕ фикс.** Замер `unified_search`
(scratchpad, 10 запросов): **2/93 результата** (2.2%) имели кросс-store дубль. Root-cause:
дубли здесь — почти всегда **MIRRORS** (один факт, синхронизированный `cross_store_sync`),
а не независимое подтверждение → суммирование RRF-рангов бустило бы избыточность, не
корроборацию; валидатора релевантности `unified_search` нет. Логика НЕ тронута, добавлен
поясняющий комментарий у `rrf_scores[item.unified_id]`, чтобы будущий «фикс» не сломал
намеренное поведение.

**hard-timeout потолок (L-new)** — design-вопрос «нужен ли потолок», не код-фикс; оставлен открытым.

**Тесты:** [`test_memory_low_tail_260716.py`](../../tests/unit/test_memory_low_tail_260716.py)
11, все sabotage-verified (откат 5 фиксов → 8/10 краснеют; 2 green — намеренные
invariant-guards; non-dict guard reddens отдельно). Memory-touching регресс **208 passed**.
**code-verify PASS** (read-only reviewer, bug-fix + quality; нашёл non-dict gap → закрыт).
`/mcp reconnect` для рантайма MCP (правки vector_memory/orchestrator/ai_memory-серверов).

### 2026-07-17 (ночь-2) - §5.3 закрыт: dedupe --apply на живой коллекции → роадмап выполнен

Единственный открытый acceptance-пункт (§5 критерий 3, «0 дублей hash») закрыт.
Пайплайн `pipeline/close-memory-dedupe-acceptance/`. Правок кода нет — исполнение уже
реализованного и запинтованного в срезе P1 инструмента
[`dedupe_learned_patterns.py`](../../scripts/dedupe_learned_patterns.py) (link-aware, P1.7).
Пользователь подтвердил живую мутацию («применить с бэкапом»).

**Прогон `--apply`** (2026-07-17 22:56): `learned_patterns` 154 → **151** точки.
- 3 дубля-**зеркала** удалены; счётчики (succ/fail/application_count) слиты в 2
  канонических выживших, confidence пересчитан (§22 Beta(7,3)).
- Рёбра: 47 касающихся → **1 repoint + 5 drop**, **dangling 0**.
- **Канон из `mirrors` победил эвристику в 2 из 3 групп** — ровно тот дефект, ради
  которого P1.7 сделал дедуп link-aware (эвристика удалила бы канон).
- Бэкап ДО мутации: `data/memory/backups/learned_patterns_20260717_225637.json`
  (154 pts + векторы + 47 рёбер, целостность проверена). Откат: `--restore … --apply`.

**Live-верификация ПОСЛЕ** (in-process, `scratchpad/verify_dedupe_acceptance.py`, ALL PASS):
- §2/§5.3 — 0 точек вне enum, 0 без `content_hash`, **0 дублей hash** (re-dry-run
  `dup_groups=0`, идемпотентность подтверждена).
- §5.5 — `unified_search` → **`sources_failed=[]`**, 10 результатов, 3 плеча.
- M4 (плечо == тул) — `search_patterns` и vector-плечо зовут единую
  `search_pattern_points` → **10 точек в одном порядке, contents идентичны**, skipped=0.
- `link_registry` — **0 висячих рёбер** на концах learned_patterns.

**Регресс:** `test_dedupe_learned_patterns` (7) + `test_pattern_type_contract` (41) +
`test_memory_p1_resilience` (48) = **96 passed**. `/mcp reconnect` НЕ требовался
(правок кода MCP нет; серверы читают ту же Qdrant вживую). **Роадмап 260716 закрыт
полностью (P0/P1/§5/CircuitBreaker).**

### 2026-07-17 (ночь) - CircuitBreaker HALF_OPEN починен отдельным срезом (§3.3 LOW закрыт)

Пайплайн `pipeline/fix-circuit-breaker-half-open/`, файл
[`infrastructure/circuit_breaker.py`](../../src/memory/infrastructure/circuit_breaker.py) v2.1.
Гейты (`allow_request`/`call_async`) коммитят OPEN→HALF_OPEN через `_sync_state()`
(property `state` - чистое view), пробы бюджетируются эпизодным `half_open_probes`
(пожизненный `success_count` низведён до телеметрии), ветки recovery ожили;
`_circuit_is_open` в `unified_search` переведён с R1-обхода на `allow_request()`.
Ревью PARTIAL → ремедиация: **age-based re-arm** потерянной пробы (CancelledError
не ловится `except Exception` - слот утекал, raw клинил в HALF_OPEN навсегда,
невидимо для health), декремент слота вместо обнуления (over-admission при
max_probes>1), `raw_state` в stats (wedge отличим), residue-сброс на OPEN,
single-event-loop допущение в докстринге. 14 unit (сабботаж ×2: ядро + ремедиация)
+ 137 регрессионных. ⚠ Рантайм MCP - после `/mcp reconnect`. Эталон семантики -
исправный сиблинг `src/shared/llm_rotation/circuit_breaker.py`.

### 2026-07-17 (вечер) - Аудит-верификация реализации (по запросу пользователя)

Независимая сверка заявленного в §18 с кодом и живыми данными:

- **Код: 22/22 ключевых артефактов P0/P1 на месте** (coerce/aliases, items_skipped,
  3 писателя, LEGACY_SEED_CONFIDENCE, относительные импорты каскада во всех 3
  серверах, PatternRecord.extra, RRF-знаменатель, SourceError + `search:<source>`
  breakers + R1 `_circuit_is_open`, экспорт `search_pattern_points` + вызов из плеча,
  синглтон Qdrant в reinforce, `resolve_after_hard_timeout`/`HARD_TIMEOUT_FACTOR`,
  `_safe_float` в хуке, `READ_UNKNOWN_IMPORTANCE`, link-aware дедуп). `CATEGORY_MAP`
  в `normalize_light_patterns.py` производен через `PatternType.coerce` (сноска: свип
  по имени `normalize_pattern_type` его не находит - производность через coerce).
- **Тесты:** `test_pattern_type_contract.py` 41 + P1-файлы (`test_memory_p1_resilience`,
  `test_apply_cascade`, `test_dedupe_learned_patterns`, `test_unified_search_honest`)
  62 - все зелёные.
- **Живые данные:** `migrate_pattern_types.py` dry-run → **0** к перештамповке во всех
  трёх хранилищах (Qdrant / patterns.jsonl 76 / pending 44); §5.1-5.2 запинены тестами;
  §5.5 подтверждён на работающем сервере - `unified_search` → `sources_failed=[]`, 3 плеча.
- **Открытое:** dedupe dry-run → `total=154, dup_groups=3` (delete 3 зеркала, 47 рёбер
  → 1 repoint + 5 drops, canonical-override работает, dangling 0) - **§5.3 «0 дублей
  hash» остаётся единственным незакрытым acceptance-пунктом**; закрывается запуском
  `dedupe_learned_patterns.py --apply` с бэкапом (отдельное решение, как и заявлено).
- **LOW-хвост уточнён:** `LearnedPattern.from_dict`/`EvidenceSource.from_dict` (толерантны,
  P0.2) и `forget_gate._days_idle` (coerce_dt, F7) - фактически закрыты; живые остатки:
  `get_categories` `round(row[2],2)` на возможном NULL, `delete_message` узкий except,
  `dashboard.compute_docs_freshness` tz-смещение, RRF-ранги кросс-store дублей,
  `memcube.py`, `SourceServer`/`LinkType.from_string`, вопрос потолка hard-timeout,
  и **CircuitBreaker HALF_OPEN** (общая инфраструктура, вне скоупа 260716).

Пайплайн `pipeline/impl-memory-p1-resilience/`. Нить среза: P0 закрыл **вход**
(битый payload не должен убивать читателя), P1 — **выход**: пути, которые не падают,
а тихо врут.

**Замеры ДО проектирования** (роадмап требует их там, где правка трогает ранжирование
или ссылочную целостность) — два из трёх изменили план:

- **P1.9 — blast radius 0.** `default_confidence` реально решает только там, где нет
  `succ`/`fail` И нет числового `confidence`: **0 из 153** точек (12 идут в legacy-ветку,
  но у всех confidence числовой). Унификация на prior = no-op на текущих данных →
  замер ранжирования не нужен, правка чисто защитная.
- **P1.7 — диагноз подтверждён и уточнён.** Конфликт `pick_survivor` ↔ canonical есть
  не во всех группах: **2 из 3** (в них survivor = зеркало, канон удалялся бы).
- **M6 — диагноз роадмапа ПЕРЕВЁРНУТ.** §3.2 утверждал: «легаси TEXT-importance молча
  выпадает (`TEXT >= 0.5` = false)». Проверено на sqlite3 напрямую: в SQLite порядок
  классов хранения `NULL < REAL/INTEGER < TEXT < BLOB`, поэтому TEXT **всегда больше**
  любого числа. Реальный дефект противоположен: такая строка (а) проходит фильтр
  ВСЕГДА, независимо от смысла метки, и (б) в `ORDER BY importance DESC` встаёт **выше
  любой** числовой — `'low'` обгоняет `0.99`. Не «тихая потеря», а «тихий захват топа».
  Живых TEXT-строк **0 из 154** → дефект латентный. Чинил реальный, а не описанный;
  разовая миграция колонки из §4 P1.5 **не нужна** (мигрировать нечего).

**Сделано:**

- **P1.9** — `LEGACY_SEED_CONFIDENCE = PRIOR_SUCCESS/(PRIOR_SUCCESS+PRIOR_FAILURE)`,
  **выведен** из prior, не литерал: «сев от дефолта не двигает confidence» стало
  свойством конструкции. Параметр `default_confidence` удалён (существовал ровно
  из-за расщепления), 4 call-site сведены на константу.
- **P1.8** — 3 импорта каскада `memory.*` → относительные. Дефект был шире, чем в §4:
  сервер живёт как `-m src.memory.vector_memory.server`, поэтому абсолютный `memory.*`
  не только падал ДО первого `_get_embedding` (ленивый `sys.path`), но и связывал
  **второй экземпляр** `link_registry` ПОСЛЕ него.
- **P1.1** — `PatternRecord.extra` (passthrough, известные поля выигрывают merge) +
  **сверх плана**: непарсящиеся строки возвращаются на диск (джоб перезаписывает силос
  целиком → «skip при чтении» = «delete с диска»; тот же класс, что F6 в P0).
- **P1.2** — пустые плечи вон из знаменателя `max_rrf` (упавшие туда и не попадали —
  асимметрия).
- **P1.3** — `SourceError.error_type`; `sources_failed_detail` в `memory-read.log`;
  breakers `search:<source>` на общем с propagation реестре (`allow_request()` ДО
  создания корутины — иначе `wait_for` закрывается непроверенным и внутренняя корутина
  остаётся un-awaited).
- **P1.4** — `search_pattern_points` экспортирована из `server.py`; тул и плечо зовут
  ЕЁ. M4 закрыт целиком: политика больше не дублируется, а значит не может разойтись.
- **P1.6** — процессный синглтон Qdrant-клиента (+`reset_default_client`).
- **M7** — `_safe_float` + per-hit `try` в dense-арме (payload-баг больше не
  рапортуется как `tei: down`). **M9** — `_naive(dt)`. **M10** — `content_hash` в
  `normalize_payload`. **M5/M8** — оказались уже закрыты в P0 (итерации 1 и 2),
  проверено чтением, не переделывались.
- **P1.7** — `canonical_from_links` (mirror-chain `A→B→C ⇒ C`), canonical-aware
  `pick_survivor`, `plan_link_moves` (re-point / drop-intra-group / collapse-duplicate),
  `apply_link_plan` (create-before-delete), бэкап+restore рёбер, **fail-closed** в
  `main()` («реестр нечитаем» ≠ «рёбер нет»), инвариант `dangling_links` с ABORT.

**Живая верификация** (in-process; MCP держат старый код до `/mcp reconnect`):
`search_patterns` count=5 / `items_skipped`=0 и vector-плечо отдают **одни и те же
точки в том же порядке**; `unified_search` → 10 результатов, 3 плеча, **`sources_failed=[]`**
(критерий §5.5 — регрессия исходного инцидента), breakers зарегистрированы как
`search:memory-ai|vector-memory|skill-learning`. Дедуп-план на живых данных: 3 группы →
delete `[5e88c5a9, e30914b1, aed98df7]` (**зеркала**, а не каноны), 46 рёбер → 1 repoint
+ 5 deletes, **dangling 0**, 2 конфликта канон↔эвристика зафиксированы в плане.

**Тесты: 2325 зелёных** (+28). **Саботаж-харнесс: 15/15** фиксов краснеют при откате.
Он же поймал **2 вакуумных теста** по ходу: тест «реальная ошибка вместо hard_timeout»
гонял движок с падающим+висящим адаптером, но падающий ловится ОБЫЧНЫМ циклом —
salvage-ветка его не видела, и тест проходил без фикса.

**Находка (новое, в §3.3 LOW):** hard-timeout salvage-ветка `unified_search`
**почти недостижима** и её комментарий врёт. Комментарий обещает потолок на случай
«per-adapter `wait_for` misbehaves (thread pool exhaustion, event loop starvation)»,
но замер показал: корутина, глотающая `CancelledError`, побеждает и `wait_for`, **и**
внешний `asyncio.timeout` (проба: 1.03 с при потолке 0.15 с, TimeoutError не поднялся) —
ровно в том случае, ради которого потолок написан. При исправных адаптерах все плечи
разрешаются на 1.0× таймаута, то есть ДО потолка 1.5×. Ветка живёт только при
starvation ИЗВНЕ движка. Решение вынесено в чистую `resolve_after_hard_timeout`,
множитель стал константой-швом `HARD_TIMEOUT_FACTOR` (тест инвертирует его и доходит
до реальной ветки детерминированно).

**Собственный баг, пойманный тестом до данных:** в `plan_link_moves` распаковка
`src, tgt, ltype = lk["source_id"], lk["link_type"], lk["target_id"]` — имена и
значения разъехались, `tgt` получал ТИП связи → intra-group рёбра не схлопывались,
ключи дедупа были мусорными.

**Отклонения:** P1.7 `--apply` **разблокирован, но не запущен** — задача среза снять
запрет, а запуск дедупа на живой коллекции = отдельное решение с бэкапом (§5 критерий 3
остаётся открытым осознанно). Миграция `importance` отменена (нечего мигрировать).

**Итерация ревью (2 независимых read-only ревьюера: корректность + честность тестов) —
14 находок, все закрыты. Обе линзы независимо нашли одну корневую регрессию, внесённую
этим срезом:**

- **R1 (HIGH, обе линзы) — breaker убивал плечо НАВСЕГДА.** `allow_request()` в
  HALF_OPEN возвращает `success_count < half_open_max_probes`, где `success_count` —
  **пожизненный** счётчик, который ничто не сбрасывает (`_transition_to(HALF_OPEN)` не
  имеет вызывающих; `record_success` сверяет сырой `_stats.state`, который HALF_OPEN не
  бывает). Замерено: плечо с любой историей успехов после срабатывания отвергается
  навсегда — до `/mcp reconnect`. Транзиентный рестарт TEI превращался бы из «медленного
  плеча» (что P1.3 и чинил) в перманентную потерю семантического арма — **строго хуже
  исходной проблемы**. Фикс: `_circuit_is_open` зеркалит `call_async` (отказ только на
  сыром OPEN) → ущерб ограничен `reset_timeout`, семантика совпадает с propagation.
- **R2 (HIGH) — инверсия `archived` в merge.** Победитель выбирается по confidence →
  архивная запись 0.9 бьёт живую 0.4 → группа схлопывалась в **архивную**, живая копия
  удалялась из силоса, `pattern_harvest` пропускал факт совсем. До P1.1 тот же вход
  воскрешал архивную. Оба поведения неверны, **и мой тест пинил неверное направление**.
  Правило по §22 revive-on-recurrence: живой дубль = факт вернулся → merged архивен,
  только если архивны ВСЕ.
- **R3 (HIGH) — кросс-групповое ребро планировалось дважды** с противоречивыми концами
  (`x1→y2` и `x2→y1` при верном `x1→y1`), оба висели; инвариант не ловил, т.к. спрашивал
  «было ли ребро запланировано» — неверно запланированное считается запланированным.
  Фикс: глобальный remap одним проходом + инвариант по **финальным концам**.
- **R4 (HIGH) — `except ValueError: pass` уничтожал ребро.** `create_link` кидает
  ValueError не только на «уже есть» (не-unified id, неизвестный тип, self-link) →
  легаси bare-uuid ребро отвергалось, оригинал удалялся безусловно, прогон печатал
  «1 repointed». Потеря провенанса под видом успеха — ровно то, ради чего P1.7 и делался.
- **R5** — dedupe × drop_test: выживший мог сам быть purge-целью и уносил унаследованные
  рёбра в никуда. Тест-записи резолвятся ПЕРВЫМИ, маркер чистит группу целиком.
- **R6** — M6 починен у 1 читателя из 3: `search_messages` (×2) и, хуже всего,
  `AiMemorySearchAdapter.search` — там это **отбор кандидатов** без фильтра, TEXT-строка
  занимала верх окна и вытесняла реальные совпадения из плеча.
- **R7** — bare-uuid lookup в `load_links_for` был **инертен** (все сравнения по
  `uid(...)`) → «страховка» жила только в докстринге; bare-конец теперь нормализуется.
- **R8** — **M10 чинил не тот дефект**: write-time дедуп идёт по производному point id,
  а не по полю payload → повторный save плодит точку и с полем, и без. Поле ценно
  read-time потребителям; утверждение исправлено, поле оставлено. Заодно хеш больше не
  берётся из payload (P0 наоборот: чужое поле недоверенно), а всегда выводится.
- **R9** — P1.8 починен у 1 сервера из 3: `ai_memory` и `skill_learning` несли тот же
  абсолютный `memory.*`, где проглоченный импорт стоит самого write-contract (нет хеша →
  запись молча вне §26-дедупа).
- **R10–R14 (пины):** `_record` (обратная связь плеча в breaker) не пинился — удаление
  ВСЕХ вызовов оставляло сьют зелёным; проводка реестра в оркестраторе не пинилась;
  M7 и M10 не покрыты вовсе; фолбэк хука 0.5 вместо prior = ~40% перекос surfacing-скора;
  дрейф SQL↔Python на неизвестной метке (0.0 против 0.7) → `READ_UNKNOWN_IMPORTANCE`.

Итог после ремедиации: **2345 unit** (+48), **саботаж 27/27**. Харнесс поймал и ошибку
в себе самом (якорь `ORDER BY {imp}` встречается 4×, саботаж бил по чужой функции —
тест был честным) и вакуумный тест M6 (сортировал результат в Python = тавтология;
переписан через шов `SEARCH_WINDOW`). Живая верификация повторена: `sources_failed=[]`,
плечо == тул, дедуп-план 0 висячих.

**Новое в §3.3 LOW (общая инфраструктура, предсуществующее):** `CircuitBreaker`
HALF_OPEN не работает ни для одного потребителя — `_transition_to(HALF_OPEN)` без
вызывающих, `record_success` сверяет сырой `_stats.state`, `success_count` монотонен.
Propagation это не задевает (использует `call_async`, который в HALF_OPEN пропускает),
но цепь не закрывается обратно никогда. Отдельное решение — не в скоупе 260716.

### 2026-07-16 (вечер) - P0 реализован и верифицирован на живых данных

**Сделано** (пайплайн `pipeline/impl-memory-payload-hardening/`):

- **P0.1** — `PatternType.coerce` + `normalize_pattern_type` + `coerce_float/int/dt`
  в [`models.py`](../../src/memory/vector_memory/models.py) (stdlib-only контракт).
  Alias-карта — единственная: `normalize_light_patterns.CATEGORY_MAP` и
  `reflection._CATEGORY_MAP` стали **производными** от неё (проверено: обе
  бит-в-бит совпали с прежними хардкодами).
- **P0.2** — толерантное чтение (`_pattern_from_payload`, `_resolve_state`,
  `should_archive`, `LearnedPattern.from_dict`, `EvidenceSource.from_dict`) +
  per-item try в 5 циклах со счётчиками `items_skipped`/`errors`/`unreadable`.
  decay-sweep больше не обрывается посреди прохода (была частичная мутация).
- **P0.3** — 3 писателя коэрсят (`pattern_harvest._build_payload` **и**
  `quarantine_items` — второй пропустил бы силос; `route_and_save` обе ветки +
  clamp confidence; `capture_pattern` схема-enum + coerce в handler). Провенанс —
  `metadata.original_pattern_type`. `save_pattern` намеренно остался строгим.
- **P0.4** — [`migrate_pattern_types.py`](../../scripts/migrate_pattern_types.py):
  **20** точек Qdrant + 16/76 `patterns.jsonl` + 7/42 `pending_patterns.jsonl`
  ре-штампованы (backup + идемпотентно, повторный прогон = no-op).
  `backfill_content_hash.py` проставил 4 недостающих хеша.
- **P0.5** — [`test_pattern_type_contract.py`](../../tests/unit/test_pattern_type_contract.py)
  (33 теста), весь unit-сьют **2289 зелёных**.

**Верификация на живых данных** (in-process, MCP держат старый код до `/mcp reconnect`):
до миграции — 20 грязных точек, все 20 прочитаны без исключения, `search_patterns`
count=5 / `items_skipped`=0, vector-плечо живо; точка `GMFM-6470` с `'requirements'`
(та самая, что роняла плечо) возвращается первой как `workflow-pattern`.
После миграции — 0 грязных точек. Критерии §5 закрыты (кроме дублей, см. P1.7).

**Отклонения от плана (осознанные, детали — [02-design.md](../../pipeline/impl-memory-payload-hardening/02-design.md)):**
- **Д5**: вместо `MIN_CONTENT_LEN` в `route_and_save` — гейт только пустого
  контента. Длина = анти-флуд политика ХАРВЕСТЕРА; ронять 20-символьный
  легитимный факт из явного save-API хуже, чем сохранить.
- **Д6/P1.7**: дедуп 3 пар НЕ применён — тул оказался несовместим с
  `link_registry` (см. P1.7). Не «почти сделано», а сознательный стоп: чинить
  ссылочную целостность в обмен на косметику дублей — плохая сделка.
- **§2**: счёт грязных точек исправлен 13 → **20** (в аудите недосчитал).

**Ревью:** 2 независимых ревьюера (bug-fix-validation + quality-review) → оба
**PARTIAL** с одинаковыми находками: в самой пофикшенной функции остался строгий
`fromisoformat(payload["expired_at"])` при докстринге «Never raises»; `int()` на
`application_count` в `apply_to_payload`; M5 не починен в sibling-пути
`reinforce.py` (продовый путь хука); миграция молча удаляла непарсящиеся строки
вопреки докстрингу; фикстура «every defect» не покрывала оставшиеся дефекты.
**Все исправлены**, тесты на каждую дыру добавлены (проверено откатом фикса →
2 теста краснеют).

**Итерация 2 ревью:** 9/9 подтверждены исправленными, регрессий нет, тесты
честные, инвариант fail-closed цел → но найдено ещё 7 (F1-F7), все закрыты:
- **F4 (корневая):** фикстура «every defect» несла **инертный** яд — `fail: None`
  короткозамыкал ВСЕХ потребителей в seed-ветку, поэтому `succ: "abc"` никогда не
  доходил до `coerce_float`. Это и прикрыло F1/F2. Развёл на две фикстуры
  (`_poisoned_payload` = seed-ветка, `_garbage_counts_payload` = present-but-garbage);
  проверено откатом → новый тест краснеет.
- **F3 (инцидент-класс в соседнем плече):** `SkillLearningSearchAdapter.search` —
  `fromisoformat(item["created_at"])` без per-item try: одна битая запись
  `patterns.jsonl` роняла skill-learning-плечо в `sources_failed`. Ровно механика
  16.07, но в другом плече (аудит M8). Закрыт.
- **F1:** `_cascade_confidence` — непокрытая else-ветка счётчиков + цикл соседей
  без per-item try (падение обрывало остальных и пропускало `_bump_epoch()` —
  тот же класс «частичная мутация без bump», что чинили в decay-sweep).
- **F2** seed-ветка `_vector_memory_handler`; **F5** пин строгости `save_pattern`
  (иначе рефактор «коэрсить везде» снёс бы инвариант молча); **F6** тест
  сохранности непарсящихся строк миграции; **F7** `_days_idle` через `coerce_dt`.

**Итерация 3 ревью:** F1-F7 подтверждены (6/7 чисто), но найден **блокер D1** —
F2 был исправлен наполовину: `_vector_memory_handler` коэрсил только seed-ветку,
а строкой ниже остался `float(succ)` на сыром payload. Усиление: хендлер работает
за circuit breaker'ом → одна точка с `succ:"abc"` тикала `propagation:vector-memory`
к OPEN и затем валила **всё** плечо как `failed:circuit_open`. Фикс — устранение
корня (дублирования): хендлер делегирует резолв в `confidence._resolve_state`,
который коэрсит обе ветки. Плюс **D2** (счётчик `errors` каскада не выходил
наружу — асимметрия с тремя другими циклами) и **D3** (4 правки без пинов):
добавлены `test_cascade_survives_bad_neighbour` (сосед-нечитаемый → остальные
живы + `_bump_epoch` вызван), `test_propagation_handler_survives_garbage_counts`
(прогоняет САМ хендлер), `test_skill_learning_arm_survives_bad_record`. Все три
проверены саботажем (откат фикса → краснеют).

Итог: **2295 unit-тестов**, ruff по своим файлам чист, live-проверка повторена.

**Итерация 4 ревью (дельта):** дефектов и регрессий в фиксах НЕ найдено
(делегация корректна, здоровые payload не затронуты, `default_confidence=0.70`
делает её строго behaviour-preserving, keyword-only параметр не спутать с
позиционным). Но **N1** — тот же капкан этажом выше: гард, ради которого делалась
итерация 4, **не был запинен** (тест проверял хелпер, а фикстура теста хендлера
имела оба счётчика → legacy-seed недостижим, `confidence: None` инертен → удаление
гарда оставляло сьют зелёным). Переписан на пин call-site через фейк-Qdrant с
`{"application_count": 4}` + ассерт `succ == 2.8+1.0`; проверено саботажем.
Плюс **N2** (`cascade_errors` доведён до MCP-ответа — симметрия с
`decay_confidence`, как обещал комментарий), **N3** (`errors` добавлен в
`_GENERIC_PASSTHROUGH` — счётчик, невидимый слою §27, честен лишь наполовину),
**N4** (докстринг `Args`). **N6**: прогон повторён на текущем коде — **2297**.

**Самопроверка после итерации 3 (→ P1.9):** делегирование в `_resolve_state`
внесло ТИХИЙ регресс — хендлер сеял легаси-точки от prior 0.70, а `_resolve_state`
от 0.5 (при `confidence` missing/null и `application_count>0`: (2.8,1.2) → (2.0,2.0),
что тянет confidence с 0.70 до 0.643). Поймано сравнением старой и новой веток на
таблице кейсов. Фикс без возврата дублирования: `_resolve_state(..., *,
default_confidence=0.5)` — хендлер передаёт 0.70, read-path не тронут; оба
поведения запинены тестом. Расщепление дефолтов — предсуществующее, вынесено в P1.9.

**Побочная находка → P1.8:** `_cascade_confidence` импортирует `memory.*`, а `src`
кладётся в `sys.path` лениво внутри `_get_embedding` → каскад работает или молча
не работает в зависимости от порядка вызовов в процессе (широкий `except: pass`
это прячет). Вне скоупа P0 (не payload), но того же рода «тихая деградация».

**Побочно:** починен предсуществующий тест-таймбомб
[`test_memory_first_surfacing.py`](../../tests/unit/hooks/test_memory_first_surfacing.py)
(`_T0 = datetime(2026,1,1)` при комментарии «recent enough that decay is near-zero»;
за 196 дней распад поднял eff 0.117→0.152 через порог 0.15 → тест падал на чистом
HEAD, подтверждено прогоном в изолированном worktree). Не связан с P0 — просто
истёк.

**Операционка:** правки MCP-серверов требуют `/mcp reconnect` — до него живые
tools `search_patterns`/`unified_search` работают на старом коде. Хуки
(pattern_harvest/reflection) подхватывают новый код сразу — они спавнятся заново.

### 2026-07-16 - Роадмап создан по итогам аудита

- Триггер-инцидент воспроизведён, корень подтверждён (строгий enum в
  `_pattern_from_payload` + невалидированные писатели).
- 3 параллельных код-аудита (read/write/orchestrator) + проба 153 точек:
  ~25 дефектов, реестр в §3, данные в §2.
- План: P0 (коэрсер + толерантный read + 3 писателя + миграция) → P1
  (merge-fix, RRF, breakers, medium-хвост). Реализация НЕ начата.
- Research-артефакт: `pipeline/audit-memory-subsystem/pipeline.md`; память:
  `project-memory-payload-audit-fix-pending`.
