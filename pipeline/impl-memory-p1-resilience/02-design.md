# 02 — Дизайн: P1 роадмапа 260716

Порядок реализации — снизу вверх по зависимостям: сперва общие контракты
(`confidence`, `models`), затем читатели, затем скрипты.

## P1.9 — единый seed-дефолт (первым: меняет контракт `_resolve_state`)

`confidence.py`:

```python
# Сев легаси-точки от prior — единственный самосогласованный выбор: derive_confidence
# от (c·n, (1−c)·n) равен ровно c при c = prior. Сев от 0.5 тянул легаси-точку ПОД prior
# (n=4: 0.643 вместо 0.70), т.е. занижал её в ранжировании read-path'ом.
LEGACY_SEED_CONFIDENCE: float = PRIOR_SUCCESS / (PRIOR_SUCCESS + PRIOR_FAILURE)  # 0.70
```

- `_resolve_state(...)` — параметр `default_confidence` **удаляется**, внутри
  `coerce_float(payload.get("confidence"), LEGACY_SEED_CONFIDENCE)`.
- Call-site `memory_orchestrator.py:876` → `_resolve_state(pay)` (аргумент лишний).
- `server.py:413` (`_pattern_from_payload` seed) `0.7` → константа.
- `server.py:436` (`confidence=` денорм) `0.5` → константа. Обоснование: отсутствие
  денорма означает «нет наблюдений» = prior, а не «0.5».
- `server.py:1019` (decay-sweep) `0.5` → константа.
- `server.py:160` (каскад) `0.70` → константа.

**Замер:** 0/153 точек затронуты (probe) → изменения ранжирования на текущих данных нет.
Тест-пин `test_pattern_type_contract.py:503` (`_resolve_state({"application_count": 4})
== (2.0, 2.0)`) ожидаемо станет `(2.8, 1.2)` — правится вместе с кодом, это и есть
предмет P1.9.

## P1.8 — импорты каскада

`server.py` `_cascade_confidence`: `from memory.orchestrator.link_registry import ...`
→ `from ..orchestrator.link_registry import ...`; то же для двух
`from memory.infrastructure.trace_log import write_trace`.

Сервер запускается `-m src.memory.vector_memory.server` → пакет `src.memory.*`.
Абсолютный `memory.*` не только падал до первого `_get_embedding` (который лениво
кладёт `src` в `sys.path`), но и создавал **второй экземпляр модуля** после — два
`LinkRegistry`-класса в одном процессе. Относительный импорт закрывает оба.

## P1.1 — merge не теряет полей

`PatternRecord`:
- `+ extra: dict[str, Any] = field(default_factory=dict)`
- `from_dict`: известные поля (кроме самого `extra`) → в конструктор; **всё
  остальное** → в `extra`.
- `to_dict`: `{**self.extra, <известные поля>}` — известные выигрывают, стухший дубль
  в `extra` не может перебить.

`PatternMerger._load_patterns` / `_write_patterns`:
- непарсящаяся строка больше **не выбрасывается**: сохраняется как есть
  (`_RawLine`) и пишется обратно на своей позиции. Джоб работает в каденсе и
  перезаписывает силос — «пропустить при чтении» здесь означает «удалить с диска».
- `to_thread`-функция `_load` больше не может упасть на не-dict JSON (строка/список
  в файле) — такая строка тоже raw.

`_merge_records`: `extra` победителя сохраняется как есть. Заливать поля лоузеров
НЕ будем: `archived: true` у лоузера не должен архивировать победителя.

## P1.2 — RRF: пустые плечи вон из знаменателя

`RRFMerger.fuse`:

```python
# Только плечи, реально давшие хиты. Упавшие сюда не попадают вовсе (они в
# sources_failed) — пустые обязаны трактоваться так же, иначе знаменатель растёт
# от плеча, которое ничего не сказало, и хит из единственного плеча тонет под
# min_score (3 плеча, 1 с хитом: base 0.33 при пороге 0.3).
max_rrf = sum(w(src) for src, res in source_results.items() if res) / (k+1)
```

## P1.3 — честные причины и breakers

1. **hard-timeout salvage** — задача, завершившаяся ИСКЛЮЧЕНИЕМ, получает своё
   исключение, а не ярлык `hard_timeout`:
   ```python
   if task.done() and not task.cancelled():
       exc = task.exception()
       if exc is None: <salvage результат>
       else: SourceError(source, str(exc), error_type=type(exc).__name__)
   ```
2. **`SourceError.error_type`** — аддитивное поле (`"timeout"` / `"hard_timeout"` /
   `"circuit_open"` / `type(e).__name__`); в `to_dict` и в trace
   `memory-read.log` (`sources_failed_detail={src: error_type}`).
3. **breakers `search:<source>`** — `UnifiedSearchEngine(link_registry, breaker_registry=None)`;
   при наличии реестра:
   - до создания корутины `breaker.allow_request()` → False ⇒ `SourceError(error_type="circuit_open")`,
     плечо не запускается (fail-fast вместо 5с таймаута);
   - `record_success()` / `record_failure(str(e))` по факту.
   Оркестратор передаёт `self._circuit_registry` — тот же, что у propagation
   ⇒ `memory_circuit_status` / `memory_circuit_reset` управляют и поиском.

## P1.4 — общее ядро поиска

`server.py` — новая экспортируемая функция (единственный владелец политики):

```python
def search_pattern_points(client, vector, *, min_confidence, limit,
                          pattern_types=None, now=None) -> tuple[list[PatternSearchResult], int]:
    """Query + effective-confidence фильтр + hard-exclude archived + per-item изоляция.
    Возвращает (results, skipped). НЕТ server-side prefilter по confidence — с
    count-decay effective может быть ВЫШЕ stored, prefilter не safe superset."""
```

- `handle_search_patterns` = embed → `search_pattern_points` → сериализация.
- `VectorMemorySearchAdapter.search` = embed → `search_pattern_points` → маппинг в
  `SearchResultItem`; `raw_score = r.combined_score` (similarity × **effective**),
  `metadata.confidence = r.adjusted_confidence`.

Закрывает M4 целиком: плечо получает и effective-фильтр, и исключение archived, и
`fetch_limit`-переоценку — потому что это больше не его код.

## P1.5 — медиум-хвост

**M6** (`ai_memory/server.py`) — фикс в сторону реального дефекта (см. 01):
выражение сортировки/фильтра строится ИЗ `_IMPORTANCE_LABELS` (единственный источник,
без дрейфа SQL↔Python):

```python
def _importance_sql() -> str:
    """TEXT-importance не должен обгонять числовую: в SQLite TEXT > любого REAL,
    поэтому 'low' вставал выше 0.99 и всегда проходил фильтр. Переводим метку в
    число ТЕМ ЖЕ отображением, что и writer."""
```
→ `WHERE {expr} >= ?` + `ORDER BY {expr} DESC`; на выходе `_coerce_importance(row[2])`.

**M7** (`memory-first-hook.py`):
- `_pattern_effective_confidence` except-ветка: `float(payload.get("confidence", 0.5))`
  → локальный `_safe_float` (импортировать `coerce_float` нельзя — мы уже в except
  провалившегося импорта).
- дельта-фикс к тому же: сам `_pattern_score_gate` вызывается из dense-арма внутри
  большого `try`, чей `except` ставит `tei: down` → payload-баг маскировался под
  недоступность TEI. Обработка одного хита оборачивается своим `try` →
  `_trace_gate("unreadable")`, ярлык TEI остаётся честным.

**M9** (`unified_search.py`): `ScoreNormalizer.normalize` — `datetime.now() -
item.created_at` падает на одной tz-aware дате ПОСЛЕ сбора плеч (вне per-adapter
защиты) ⇒ весь поиск. Локальный `_naive(dt)` (aware → `astimezone().replace(tzinfo=None)`).

**M10** (`normalize_light_patterns.py`): `normalize_payload` кладёт `content_hash`
(из `content_hash.hash_content`, как остальные писатели); `overwrite_payload` больше
не стирает хеш → повторный save того же контента коллапсит в ту же точку.

## P1.6 — один Qdrant-клиент на процесс

`reinforce.py`: `client=None` → ленивый **процессный** синглтон `_default_client()`
вместо `QdrantClient(...)` на каждый вызов. `reinforce_session` гоняет до 10 паттернов
подряд → было до 10 соединений → 10 живых `reinforce_error` (WinError 10048,
исчерпание эфемерных портов) 2026-07-01. Хук короткоживущий, процессный кеш безопасен;
`reset_default_client()` для тестов.

## P1.7 — дедуп, уважающий графы

`dedupe_learned_patterns.py` — планировщик становится link-aware. Правила:

1. **Канон старше эвристики.** Если внутри группы есть ребро `mirrors: A → B`
   (семантика `cross_store_sync`: «A зеркалит канон B») и B в группе — **survivor = B**.
   Иначе — старый `pick_survivor`. Конфликт фиксируется в плане (`canonical_source`).
2. **Рёбра лоузера переезжают на выжившего**, не исчезают:
   - другой конец ребра **внутри группы** → ребро описывало отношение дублей,
     которого больше нет → **удалить**;
   - иначе → **re-point** L→S; если эквивалентное ребро (source, target, type) уже
     есть у выжившего → **удалить дубль**, не плодить.
3. Бэкап расширяется затронутыми рёбрами; `--restore` их восстанавливает.

Проверка на живых данных (probe): группы 1 и 2 — канон = «молодая» точка, эвристика
выбирала «старую» ⇒ удалила бы канон; группа 3 — совпадают. После фикса: 6 рёбер
схлопываются как внутренние/дубли, 1 (`derives_from` лоузера в группе 3) переезжает
на выжившего. Висячих — 0.

`--apply` разблокируется, но **в этом срезе не запускается** (A4).

## Тесты (план)

| Область | Тест |
|---|---|
| P1.9 | seed = prior; `derive_confidence` от seed'а == prior (свойство, а не число) |
| P1.8 | `_cascade_confidence` работает при чистом `sys.path` (без предварительного `_get_embedding`) |
| P1.1 | `archived`/`content_hash` переживают merge; непарсящаяся строка остаётся в файле |
| P1.2 | хит из 1 плеча при 3 зарегистрированных не тонет под `min_score=0.3` |
| P1.3 | реальная ошибка вместо `hard_timeout`; `error_type` в trace; OPEN-breaker ⇒ fail-fast + плечо не звалось |
| P1.4 | плечо не отдаёт archived; плечо фильтрует по effective (не stored) |
| P1.5 | M6: TEXT не обгоняет числовую; M7: `confidence: None` не рушит lexical-арм и не врёт «tei down»; M9: tz-aware дата не роняет поиск; M10: `content_hash` на месте |
| P1.6 | один клиент на N вызовов |
| P1.7 | канон из `mirrors` побеждает эвристику; рёбра лоузера переехали; висячих 0 |

**Саботаж-проверка обязательна** (урок P0 итераций 2–4: тест, который не краснеет от
отката фикса, ничего не пинит).
