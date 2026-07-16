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

### P1 - устойчивость оркестратора и каденса (второй срез)

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
