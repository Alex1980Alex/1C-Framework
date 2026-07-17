# 01 — Анализ: CircuitBreaker HALF_OPEN не работает ни для одного потребителя

Источник: roadmap 260716 §18 (находка R1 ревью P1) + §3.3 LOW «общая инфраструктура,
отдельное решение». Файл: `src/memory/infrastructure/circuit_breaker.py` (v2.0).

## Дефект (4 сцепленных факта)

1. **`state` — виртуальное представление.** Property возвращает HALF_OPEN по elapsed,
   но `_stats.state` (raw) остаётся OPEN навсегда: `_transition_to(HALF_OPEN)` не имеет
   вызывающих.
2. **`record_success` сверяет raw** → ветка «HALF_OPEN → CLOSED» мертва: цепь никогда
   не закрывается обратно (до `reset()`/`/mcp reconnect`).
3. **`allow_request` в HALF_OPEN гейтит по пожизненному `success_count`**
   (`success_count < half_open_max_probes`), который ничто не сбрасывает → breaker с
   любой историей успехов отвергает пробы навсегда (ядро R1).
4. **`call_async` после таймаута пропускает ВЕСЬ трафик** (виртуальный HALF_OPEN ≠ OPEN,
   probe-лимита нет), фейл лишь освежает `last_failure_time` — цепь болтается raw-OPEN
   вечно, статус/trace врут.

## Потребители

- `propagation_engine.py:343,571` — `call_async` (propagation:<source>).
- `unified_search.py:161` — `_circuit_is_open` = **R1-обход** (reject только raw OPEN),
  докстринг прямо ссылается на этот дефект и обещает переход на `allow_request()` после
  фикса машины; `:570` — `_record` даёт обратную связь record_success/failure.
- `memory_orchestrator.py` — реестр + `memory_circuit_status`/`memory_circuit_reset`.

## Эталон в репо

`src/shared/llm_rotation/circuit_breaker.py` — **исправная** машина того же дизайна:
`can_execute()` коммитит OPEN→HALF_OPEN реальным переходом, success/failure ветки живые;
запинена `tests/integration/test_circuit_breaker.py` (16 тестов, зелёные). Фикс memory-
варианта — та же семантика при сохранении его API (allow_request/call_async/registry/
trace-log переходов).

## Пины, которые нельзя сломать

`test_memory_p1_resilience.py`: R1-тест «после rewind таймаута плечо пробуется снова,
sources_failed=[]» + reject c `error_type=circuit_open` при OPEN; propagation-тесты
call_async. Integration-тесты llm_rotation-эталона не задеваются (другой класс).
