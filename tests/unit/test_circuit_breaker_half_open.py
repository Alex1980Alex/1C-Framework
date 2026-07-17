"""Unit: memory CircuitBreaker v2.1 — реальная HALF_OPEN-машина (R1 / 260716 §3.3).

До фикса: `_transition_to(HALF_OPEN)` не имел вызывающих (raw-state OPEN навсегда),
`record_success` сверял raw → цепь никогда не закрывалась, `allow_request` гейтил
пробы по ПОЖИЗНЕННОМУ success_count, `call_async` после таймаута пропускал весь
трафик без probe-лимита. Всё детерминировано: вместо sleep — rewind
`last_failure_time`. Пайплайн fix-circuit-breaker-half-open.
"""

from __future__ import annotations

import asyncio

import pytest

from src.memory.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)

pytestmark = pytest.mark.unit


def _tripped(
    *, lifetime_successes: int = 0, threshold: int = 2, success_threshold: int = 2
) -> CircuitBreaker:
    """Breaker, доведённый до OPEN (опционально — с историей успехов до этого)."""
    cb = CircuitBreaker(
        "t",
        CircuitBreakerConfig(
            failure_threshold=threshold,
            success_threshold=success_threshold,
            reset_timeout=60.0,
            half_open_max_probes=1,
        ),
    )
    for _ in range(lifetime_successes):
        cb.record_success()
    for _ in range(threshold):
        cb.record_failure("down")
    assert cb._stats.state is CircuitState.OPEN
    return cb


def _rewind(cb: CircuitBreaker, seconds: float = 61.0) -> None:
    cb._stats.last_failure_time -= seconds


def test_open_rejects_before_timeout():
    cb = _tripped()
    assert cb.allow_request() is False
    assert cb._stats.total_rejected == 1
    assert cb._stats.state is CircuitState.OPEN  # raw не дрогнул


def test_probe_allowed_despite_lifetime_successes_and_transition_is_real():
    """Ядро R1: пожизненные успехи (> max_probes) не должны душить пробу, а
    переход OPEN→HALF_OPEN обязан коммититься в raw-state (v2.0: виртуальный)."""
    cb = _tripped(lifetime_successes=5)
    _rewind(cb)

    assert cb.allow_request() is True  # v2.0: success_count(5) < max_probes(1) → False навсегда
    assert cb._stats.state is CircuitState.HALF_OPEN  # v2.0: raw оставался OPEN
    assert cb._stats.half_open_probes == 1


def test_probe_cap_in_half_open():
    cb = _tripped()
    _rewind(cb)
    assert cb.allow_request() is True  # слот занят
    rejected_before = cb._stats.total_rejected
    assert cb.allow_request() is False  # бюджет (1) исчерпан, исход пробы не записан
    assert cb._stats.total_rejected == rejected_before + 1  # v2.0 тут reject не считал


def test_probe_success_below_threshold_releases_slot():
    """success_threshold=2, max_probes=1: первый успех обязан освободить слот,
    иначе второй пробе некуда войти и цепь висит в HALF_OPEN навсегда."""
    cb = _tripped()
    _rewind(cb)
    assert cb.allow_request() is True
    cb.record_success()
    assert cb._stats.state is CircuitState.HALF_OPEN  # порог 2 не достигнут
    assert cb.allow_request() is True  # слот освобождён — вторая проба входит


def test_success_threshold_closes_circuit():
    cb = _tripped()
    _rewind(cb)
    cb.allow_request()
    cb.record_success()
    cb.allow_request()
    cb.record_success()
    assert cb._stats.state is CircuitState.CLOSED  # v2.0: недостижимо (raw был OPEN)
    assert cb._stats.failure_count == 0
    assert cb._stats.half_open_probes == 0
    assert cb.allow_request() is True


def test_probe_failure_reopens_with_fresh_window():
    cb = _tripped()
    _rewind(cb)
    cb.allow_request()
    cb.record_failure("still down")
    assert cb._stats.state is CircuitState.OPEN
    assert cb.allow_request() is False  # свежее окно — снова ждём таймаут
    _rewind(cb)
    assert cb.allow_request() is True  # и снова пробуемся: цикл живой


def test_call_async_full_recovery_cycle():
    async def scenario():
        cb = _tripped(success_threshold=1)

        async def ok():
            return "up"

        async def boom():
            raise RuntimeError("down")

        with pytest.raises(CircuitBreakerError):
            await cb.call_async(ok())  # OPEN до таймаута — reject

        _rewind(cb)
        assert await cb.call_async(ok()) == "up"  # проба прошла и закрыла цепь
        assert cb._stats.state is CircuitState.CLOSED

        # Регресс на повторный цикл: падение снова открывает
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call_async(boom())
        assert cb._stats.state is CircuitState.OPEN

    asyncio.run(scenario())


def test_call_async_respects_probe_budget():
    """Слоты общие для sync- и async-гейтов: занятый allow_request-слот
    отклоняет call_async (v2.0 пропускал ВЕСЬ трафик после таймаута)."""

    async def scenario():
        cb = _tripped()
        _rewind(cb)
        assert cb.allow_request() is True  # слот занят, исход не записан

        async def ok():
            return "up"

        with pytest.raises(CircuitBreakerError, match="probe budget"):
            await cb.call_async(ok())

    asyncio.run(scenario())


def test_stale_probe_budget_rearms_after_timeout():
    """Ревью, находка 1 (liveness): исход пробы потерян (CancelledError в
    call_async не ловится `except Exception`; потребитель allow_request умер) —
    без age-based re-arm raw клинил в HALF_OPEN навсегда: гейты вечно reject,
    record_failure не случается (reject исход не пишет), самоисцеления нет."""
    cb = _tripped()
    _rewind(cb)
    assert cb.allow_request() is True  # слот взят...
    # ...и исход НИКОГДА не записан (проба отменена/потребитель умер)
    assert cb.allow_request() is False  # бюджет исчерпан — пока честно

    cb._stats.last_state_change -= 61.0  # прошло ещё reset_timeout
    assert cb.allow_request() is True  # re-arm: плечо снова пробуется
    assert cb._stats.state is CircuitState.HALF_OPEN


def test_success_release_is_decrement_not_reset():
    """Ревью, находка 2: при max_probes>1 сброс в 0 впускал бы новый полный
    бюджет при незавершённых пробах в полёте."""
    cb = CircuitBreaker(
        "t",
        CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=5,
            reset_timeout=60.0,
            half_open_max_probes=2,
        ),
    )
    cb.record_failure("down")
    _rewind(cb)
    assert cb.allow_request() is True  # проба 1
    assert cb.allow_request() is True  # проба 2 — бюджет (2) исчерпан
    cb.record_success()  # исход пробы 1, порог (5) не достигнут
    assert cb._stats.half_open_probes == 1  # декремент: 2-я всё ещё в полёте
    assert cb.allow_request() is True  # ровно ОДИН новый слот
    assert cb.allow_request() is False


def test_call_async_default_two_step_closure():
    """Ревью, находка 5a: async-путь дефолтного 2-шагового закрытия — без
    освобождения слота вторая проба упёрлась бы в «probe budget exhausted»."""

    async def scenario():
        cb = _tripped()  # success_threshold=2, max_probes=1
        _rewind(cb)

        async def ok():
            return "up"

        assert await cb.call_async(ok()) == "up"  # проба 1: слот взят и освобождён
        assert cb._stats.state is CircuitState.HALF_OPEN
        assert await cb.call_async(ok()) == "up"  # проба 2: входит и закрывает
        assert cb._stats.state is CircuitState.CLOSED

    asyncio.run(scenario())


def test_reset_from_half_open():
    """Ревью, находка 5b: ручной memory_circuit_reset из HALF_OPEN."""
    cb = _tripped()
    _rewind(cb)
    cb.allow_request()
    cb.reset()
    assert cb._stats.state is CircuitState.CLOSED
    assert cb._stats.half_open_probes == 0
    assert cb.allow_request() is True


def test_open_transition_clears_probe_residue():
    """Ревью, находка 3: после провала пробы probes-residue не должен пережить
    OPEN-окно (wedge был неотличим от «готов пробовать» в stats)."""
    cb = _tripped()
    _rewind(cb)
    cb.allow_request()
    cb.record_failure("still down")  # HALF_OPEN → OPEN
    assert cb._stats.half_open_probes == 0
    assert cb.stats["raw_state"] == "open"  # оператору видно raw≠view


def test_state_property_is_pure_view():
    """Property показывает HALF_OPEN («готов пробовать»), но raw не мутирует —
    коммит делают только гейты."""
    cb = _tripped()
    _rewind(cb)
    assert cb.state is CircuitState.HALF_OPEN  # view
    assert cb._stats.state is CircuitState.OPEN  # raw цел: status-чтение без побочек
    cb.allow_request()
    assert cb._stats.state is CircuitState.HALF_OPEN  # гейт закоммитил
