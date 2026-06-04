"""Unit tests for §27 P1 — generic trace_log writer + circuit-breaker logging (D1.4).

The shared `write_trace` underpins all P1 process logs (routing / read /
propagation / circuit). These tests pin: it writes metadata records, honors the
per-log opt-out + global kill-switch, and that the circuit breaker logs real
state transitions (not no-ops) to `memory-circuit.log`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.memory.infrastructure.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from src.memory.infrastructure.trace_log import write_trace

pytestmark = pytest.mark.unit


def _read(tmp_path: Path, name: str) -> list[dict]:
    log = tmp_path / name
    if not log.exists():
        return []
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


class TestWriteTrace:
    def test_writes_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.delenv("MEMORY_TRACE_DISABLE", raising=False)
        write_trace("t.log", "ev", a=1, b="x")
        evs = _read(tmp_path, "t.log")
        assert len(evs) == 1
        assert evs[0]["event"] == "ev" and evs[0]["a"] == 1 and evs[0]["b"] == "x"
        assert "ts" in evs[0]

    def test_per_log_optout(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.delenv("MEMORY_TRACE_DISABLE", raising=False)
        monkeypatch.setenv("MY_LOG_DISABLE", "1")
        write_trace("t.log", "ev", disable_env="MY_LOG_DISABLE")
        assert _read(tmp_path, "t.log") == []

    def test_global_killswitch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.setenv("MEMORY_TRACE_DISABLE", "1")
        write_trace("t.log", "ev")
        assert _read(tmp_path, "t.log") == []


class TestCircuitBreakerLog:
    def test_open_transition_logged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.delenv("MEMORY_TRACE_DISABLE", raising=False)
        cb = CircuitBreaker("t", CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure("boom1")  # count 1 < threshold → stays CLOSED (no transition)
        cb.record_failure("boom2")  # count 2 ≥ threshold → CLOSED→OPEN (logged)
        trans = [e for e in _read(tmp_path, "memory-circuit.log") if e["event"] == "transition"]
        assert any(
            e["old"] == "closed" and e["new"] == "open" and e["circuit"] == "t" for e in trans
        )

    def test_noop_transition_not_logged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.delenv("MEMORY_TRACE_DISABLE", raising=False)
        cb = CircuitBreaker("t2", CircuitBreakerConfig())
        cb.reset()  # already CLOSED → CLOSED: no-op transition, must not log
        assert _read(tmp_path, "memory-circuit.log") == []
