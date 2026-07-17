# 03 — Реализация

## `src/memory/infrastructure/circuit_breaker.py` → v2.1

- `state` property — чистое **view** (HALF_OPEN по elapsed для статуса, без мутаций).
- `_sync_state()` — недостающий вызывающий `_transition_to(HALF_OPEN)`: коммитит переход (raw-state, trace-событие, сброс эпизодных счётчиков) из гейтов.
- `CircuitStats.half_open_probes` — эпизодный probe-счётчик; пожизненный `success_count` низведён до телеметрии.
- `allow_request()` — sync-гейт: `_sync_state()` → CLOSED pass / HALF_OPEN слот (`< half_open_max_probes`) / OPEN reject; reject в исчерпанном HALF_OPEN теперь честно считается в `total_rejected` (v2.0 не считал).
- `call_async()` — тот же probe-бюджет под локом (v2.0 после таймаута пропускал весь трафик); reject закрывает неawaited корутину.
- `record_success()` — ветка HALF_OPEN ожила: threshold → CLOSED, ниже порога — освобождение слота (иначе при max_probes=1 + threshold=2 цепь зависает в HALF_OPEN).
- `_transition_to()` — сброс `half_open_probes` на входах CLOSED/HALF_OPEN; `stats` дополнен полем.

## `src/memory/orchestrator/unified_search.py`

`_circuit_is_open` = `not breaker.allow_request()` — R1-обход (reject только raw OPEN) выведен из эксплуатации, докстринг переписан с историей. Search-плечи получили probe-cap и настоящий цикл восстановления через существующий `_record`-фидбэк.

## Процесс

Три ядровых фрагмента (>15 строк) сгенерированы делегированием `llm_complete` (Token Economy, гард z-ai-write-guard), отревьюны против дизайна 02 и внесены без правок по существу. Эталон семантики — исправный сиблинг `src/shared/llm_rotation/circuit_breaker.py`.

⚠ Рантайм MCP-оркестратора держит старый код до `/mcp reconnect`.
