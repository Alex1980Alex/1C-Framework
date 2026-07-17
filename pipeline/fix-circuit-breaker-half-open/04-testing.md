# 04 — Тестирование

## Новый `tests/unit/test_circuit_breaker_half_open.py` — 9 тестов (детерминированные, rewind часов)

reject до таймаута (+`total_rejected`, raw цел) · **ядро R1** — пожизненные успехи не душат пробу и переход реален (raw HALF_OPEN) · probe-cap с честным reject-учётом · освобождение слота при успехе ниже порога · threshold → CLOSED (+сбросы, гейт снова открыт) · fail-проба → OPEN со свежим окном + повторный цикл · `call_async` полный цикл восстановления (OPEN-reject → проба → CLOSED → повторное открытие) · общий probe-бюджет sync/async гейтов · чистота view-property (без гейта raw не мутирует).

## Регресс

**137 passed**: `test_memory_p1_resilience` (R1-пины: recovery плеча после rewind, circuit_open typed reject, wiring реестра), `test_propagation_honest`, `test_infrastructure`, `test_unified_search_honest`, integration `test_circuit_breaker` (llm_rotation-эталон, не тронут), `test_p1_infrastructure`. Ruff clean.

## Сабботаж

Фикс уже был в HEAD (auto-save `407643a5b`) → откат к `407643a5b~1` (по уроку [[feedback-sabotage-stash-autosave-trap]]): 3 ядровых теста **FAILED** (проба задушена / CLOSED недостижим / probe-бюджет отсутствует), фикс восстановлен из HEAD.

## Read-only ревью (субагент code-verify)

**ВЕРДИКТ: PARTIAL → все находки закрыты ремедиацией.** Ядро R1 подтверждено корректным (машина, view/commit-контракт, потребители, `total_rejected` без потерь/дублей, propagation-деградация честная в `failed_entities`), но probe-бюджет внёс liveness-дыру того же класса:

- **№1 MEDIUM — ИСПРАВЛЕН:** потерянный исход пробы (CancelledError в `call_async` не ловится `except Exception`; смерть потребителя `allow_request`) клинил raw HALF_OPEN навсегда — без временнóго выхода, невидимо для health (degraded только по `open`). Фикс: **age-based re-arm** в `_sync_state` (raw HALF_OPEN ∧ бюджет исчерпан ∧ `last_state_change` старше `reset_timeout` → слоты освобождаются). Пин: `test_stale_probe_budget_rearms_after_timeout`.
- **№2 LOW — ИСПРАВЛЕН:** освобождение слота декрементом (`max(0, probes-1)`), не обнулением — при `max_probes>1` сброс впускал новый полный бюджет при пробах в полёте. Пин: `test_success_release_is_decrement_not_reset`.
- **№3 LOW — ИСПРАВЛЕН:** `stats` дополнен `raw_state`/`consecutive_successes` (wedge отличим от «готов пробовать»); `_transition_to(OPEN)` сбрасывает probe-residue. Пин: `test_open_transition_clears_probe_residue`.
- **№4 LOW — ИСПРАВЛЕН:** устаревший докстринг R1-теста переписан историческим («HISTORICAL: v2.0…»).
- **№5 INFO — закрыты 5a/5b/5d:** async 2-шаговое закрытие (`test_call_async_default_two_step_closure`), `reset()` из HALF_OPEN, сценарий №1; 5c (trace-событие) — принят как непокрытый (fail-soft, низкая ценность).
- **№6 INFO — ИСПРАВЛЕН:** текст reject'а плеча — «refused the arm (open or probe budget exhausted)» (машинный `error_type=circuit_open` не тронут).
- **№7 INFO — задокументирован:** single-event-loop допущение в докстринге класса (unlocked sync-гейт атомарен per-turn; вызовы из потоков не поддерживаются).

## Итог после ремедиации

**14/14** тестов машины + **137** регрессионных, ruff clean. Сабботаж ×2: ядро (3 теста красные на pre-fix `407643a5b~1`) + ремедиация (3 теста красные на pre-remediation `407643a5b`).
