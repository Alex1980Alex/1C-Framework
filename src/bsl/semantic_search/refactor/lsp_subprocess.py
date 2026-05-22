from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from .circuit_breaker import CircuitBreaker
from .types import BackendError


class LspState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


@runtime_checkable
class ProcessHandle(Protocol):
    """A process handle supporting send_request / terminate / is_alive."""

    def send_request(self, method: str, params: dict) -> Any: ...
    def terminate(self) -> None: ...
    def is_alive(self) -> bool: ...


ProcessFactory = Callable[[], ProcessHandle]
HealthCheck = Callable[[ProcessHandle], bool]


@dataclass
class LspSubprocess:
    process_factory: ProcessFactory
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    health_check: HealthCheck | None = None
    _process: ProcessHandle | None = field(default=None, init=False)
    _state: LspState = field(default=LspState.IDLE, init=False)

    def start(self) -> None:
        """Spawn the process; raise BackendError(code='breaker_open') when breaker is open."""
        if self._state in (LspState.READY, LspState.STARTING):
            return
        if self.breaker.is_open():
            raise BackendError("circuit breaker is open", code="breaker_open")
        self._state = LspState.STARTING
        try:
            self._process = self.process_factory()
            if self.health_check and not self.health_check(self._process):
                raise BackendError("health check failed", code="health_check")
            self._state = LspState.READY
        except BackendError:
            self._state = LspState.FAILED
            self.breaker.record_failure()
            self._process = None
            raise
        except Exception as exc:
            self._state = LspState.FAILED
            self.breaker.record_failure()
            self._process = None
            raise BackendError(f"process spawn failed: {exc!r}", code="spawn_failed") from exc

    def stop(self) -> None:
        """Terminate the process; idempotent and best-effort."""
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
        self._state = LspState.STOPPED

    def send(self, method: str, params: dict) -> Any:
        """Forward request; auto-start, auto-restart once on crash, bounded by breaker."""
        if self.breaker.is_open():
            raise BackendError("circuit breaker is open", code="breaker_open")
        if self._state in (LspState.IDLE, LspState.STOPPED, LspState.FAILED):
            self.start()
        if self._process is None or not self._process.is_alive():
            self.breaker.record_failure()
            self._discard_process()
            self._state = LspState.FAILED
            if self.breaker.is_open():
                raise BackendError("circuit breaker opened after crash", code="breaker_open")
            self.start()
            if self._process is None:
                raise BackendError("process unavailable after restart", code="restart_failed")
        try:
            result = self._process.send_request(method, params)
            self.breaker.record_success()
            return result
        except Exception as exc:
            self.breaker.record_failure()
            self._discard_process()
            self._state = LspState.FAILED
            raise BackendError(f"request failed: {exc!r}", code="request_failed") from exc

    def _discard_process(self) -> None:
        """Best-effort terminate + null out the current process handle."""
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None

    @property
    def state(self) -> LspState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return (
            self._state == LspState.READY and self._process is not None and self._process.is_alive()
        )

    def __enter__(self) -> LspSubprocess:
        self.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.stop()


def as_lsp_client(subprocess: LspSubprocess) -> Any:
    """Wrap LspSubprocess into an object exposing .rename(params) for MultilspyBackend."""

    class _Adapter:
        def __init__(self, sp: LspSubprocess) -> None:
            self._sp = sp

        def rename(self, params: dict) -> Any:
            return self._sp.send("textDocument/rename", params)

    return _Adapter(subprocess)
