# 02 — Дизайн фикса

## Принцип: view ≠ commit

- `state` property остаётся **чистым представлением** (для `stats`/`memory_circuit_status`
  показывает «готов пробовать» без побочек).
- Реальный переход OPEN→HALF_OPEN коммитят **гейты**: `allow_request()` и `call_async()`
  через приватный `_sync_state()` (elapsed ≥ reset_timeout → `_transition_to(HALF_OPEN)`
  — переход настоящий: raw-state, trace-event, сброс эпизодных счётчиков). Семантика
  эталона `llm_rotation.can_execute`.

## Машина

- `CircuitStats.half_open_probes: int = 0` — **эпизодный** счётчик проб (не пожизненный).
- `allow_request()`: `_sync_state()`; CLOSED → True; HALF_OPEN → слот
  (`half_open_probes < half_open_max_probes` → +1, True; иначе `total_rejected+=1`,
  False — прежний код в этой ветке rejected НЕ считал); OPEN → `total_rejected+=1`, False.
- `call_async()`: под lock тот же гейт (raw OPEN → CircuitBreakerError; raw HALF_OPEN →
  слот или CircuitBreakerError) — probe-лимит теперь и у async-пути.
- `record_success()`: raw HALF_OPEN (ветка ожила) → `consecutive_successes >=
  success_threshold` → CLOSED; иначе освободить слот (`half_open_probes = 0`) — иначе
  при max_probes=1 и threshold=2 цепь зависала бы в HALF_OPEN навсегда.
- `record_failure()`: ветки прежние — теперь достижимые (HALF_OPEN → OPEN со свежим окном).
- `_transition_to`: HALF_OPEN и CLOSED сбрасывают `half_open_probes`; `stats` дополнен.
- Пожизненный `success_count` остаётся телеметрией — в гейтинге больше не участвует.

## `unified_search._circuit_is_open`

Тело → `not breaker.allow_request()`; докстринг переписывается: R1-обход ушёл, машина
починена (ссылка на этот пайплайн), плечо получает probe-cap и честный учёт reject'ов.
R1-тест обязан остаться зелёным (rewind → проба → success → слот освобождён).

## Тесты

Новый `tests/unit/test_circuit_breaker_half_open.py` (детерминированный, rewind часов):
R1-ядро (пожизненные успехи НЕ душат пробу; переход настоящий — raw HALF_OPEN), probe-cap
(+total_rejected), release-slot-below-threshold, threshold→CLOSED (+сбросы), probe-fail→
OPEN со свежим окном + повторный цикл, call_async полный цикл восстановления, call_async
уважает занятый слот, чистота view-property (без commit'а raw не меняется).
Сабботаж: откат circuit_breaker.py → ядровые тесты красные. Регресс: p1_resilience,
propagation_honest, infrastructure, llm_rotation integration.

Approve: прямой мандат пользователя «приступай к реализации».
