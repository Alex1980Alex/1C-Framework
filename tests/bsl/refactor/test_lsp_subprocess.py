from __future__ import annotations

from typing import Any

import pytest

from src.bsl.semantic_search.refactor.circuit_breaker import CircuitBreaker
from src.bsl.semantic_search.refactor.lsp_subprocess import (
    LspState,
    LspSubprocess,
    as_lsp_client,
)
from src.bsl.semantic_search.refactor.types import BackendError


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def monotonic(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


class _FakeProcess:
    def __init__(
        self,
        responses: list[Any] | None = None,
        crash_on_send: bool = False,
        alive: bool = True,
    ) -> None:
        self._responses = list(responses) if responses else []
        self._idx = 0
        self._crash_on_send = crash_on_send
        self._alive = alive
        self.terminated = False
        self.sent: list[tuple[str, dict]] = []

    def send_request(self, method: str, params: dict) -> Any:
        self.sent.append((method, params))
        if self._crash_on_send:
            self._alive = False
            raise RuntimeError("process crashed")
        if self._idx >= len(self._responses):
            return {}
        r = self._responses[self._idx]
        self._idx += 1
        return r

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive


def test_breaker_starts_closed() -> None:
    b = CircuitBreaker()
    assert b.is_open() is False
    assert b.failure_count == 0


def test_breaker_trips_after_threshold() -> None:
    b = CircuitBreaker(fail_threshold=3)
    b.record_failure()
    b.record_failure()
    assert b.is_open() is False
    b.record_failure()
    assert b.is_open() is True


def test_breaker_auto_resets_after_timeout() -> None:
    clock = _FakeClock()
    b = CircuitBreaker(fail_threshold=2, reset_timeout=30.0)
    b._clock = clock
    b.record_failure()
    b.record_failure()
    assert b.is_open() is True
    clock.advance(29.9)
    assert b.is_open() is True
    clock.advance(0.2)
    assert b.is_open() is False
    assert b.failure_count == 0


def test_breaker_prunes_old_failures() -> None:
    clock = _FakeClock()
    b = CircuitBreaker(fail_threshold=3, window_seconds=10.0)
    b._clock = clock
    b.record_failure()
    clock.advance(15.0)
    b.record_failure()
    assert b.failure_count == 1


def test_breaker_success_clears_failures() -> None:
    b = CircuitBreaker(fail_threshold=3)
    b.record_failure()
    b.record_failure()
    b.record_success()
    assert b.failure_count == 0


def test_breaker_force_open_and_reset() -> None:
    b = CircuitBreaker()
    b.force_open("test")
    assert b.is_open() is True
    b.reset()
    assert b.is_open() is False
    assert b.failure_count == 0


def test_subprocess_starts_and_becomes_ready() -> None:
    sp = LspSubprocess(process_factory=lambda: _FakeProcess())
    sp.start()
    assert sp.state == LspState.READY
    assert sp.is_ready is True


def test_subprocess_send_returns_response() -> None:
    sp = LspSubprocess(process_factory=lambda: _FakeProcess(responses=[{"changes": {}}]))
    result = sp.send("textDocument/rename", {"foo": "bar"})
    assert result == {"changes": {}}


def test_subprocess_crash_trips_breaker_after_n() -> None:
    def factory() -> _FakeProcess:
        return _FakeProcess(crash_on_send=True)

    breaker = CircuitBreaker(fail_threshold=3)
    sp = LspSubprocess(process_factory=factory, breaker=breaker)

    for _ in range(3):
        with pytest.raises(BackendError):
            sp.send("x", {})

    assert breaker.is_open() is True

    with pytest.raises(BackendError) as exc:
        sp.send("x", {})
    assert exc.value.code == "breaker_open"


def test_subprocess_breaker_open_blocks_start() -> None:
    breaker = CircuitBreaker()
    breaker.force_open("manual")
    sp = LspSubprocess(process_factory=lambda: _FakeProcess(), breaker=breaker)
    with pytest.raises(BackendError) as exc:
        sp.start()
    assert exc.value.code == "breaker_open"


def test_subprocess_reset_allows_restart() -> None:
    breaker = CircuitBreaker()
    breaker.force_open("manual")
    sp = LspSubprocess(process_factory=lambda: _FakeProcess(), breaker=breaker)
    breaker.reset()
    sp.start()
    assert sp.state == LspState.READY


def test_subprocess_stop_terminates() -> None:
    proc = _FakeProcess()
    sp = LspSubprocess(process_factory=lambda: proc)
    sp.start()
    sp.stop()
    assert proc.terminated is True
    assert sp.state == LspState.STOPPED


def test_subprocess_factory_exception_wrapped() -> None:
    def factory() -> Any:
        raise OSError("exec failed")

    sp = LspSubprocess(process_factory=factory)
    with pytest.raises(BackendError) as exc:
        sp.start()
    assert exc.value.code == "spawn_failed"


def test_subprocess_health_check_failure() -> None:
    sp = LspSubprocess(
        process_factory=lambda: _FakeProcess(),
        health_check=lambda p: False,
    )
    with pytest.raises(BackendError) as exc:
        sp.start()
    assert exc.value.code == "health_check"


def test_as_lsp_client_adapter_calls_rename() -> None:
    proc = _FakeProcess(responses=[{"changes": {}}])
    sp = LspSubprocess(process_factory=lambda: proc)
    client = as_lsp_client(sp)
    result = client.rename({"textDocument": {"uri": "file:///x.bsl"}})
    assert result == {"changes": {}}
    assert proc.sent[0][0] == "textDocument/rename"


def test_subprocess_auto_restart_on_dead_process() -> None:
    processes = [
        _FakeProcess(alive=False),
        _FakeProcess(responses=[{"ok": True}]),
    ]

    def factory() -> _FakeProcess:
        return processes.pop(0)

    breaker = CircuitBreaker(fail_threshold=10)
    sp = LspSubprocess(process_factory=factory, breaker=breaker)
    result = sp.send("x", {})
    assert result == {"ok": True}


def test_subprocess_context_manager() -> None:
    proc = _FakeProcess()
    with LspSubprocess(process_factory=lambda: proc) as sp:
        assert sp.is_ready is True
    assert proc.terminated is True
