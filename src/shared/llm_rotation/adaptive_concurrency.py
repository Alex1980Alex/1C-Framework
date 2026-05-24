"""Adaptive concurrency controller for batch LLM workloads.

Roadmap 260516 Phase 3.2 — "maximum adaptivity" variant.

**Why**: Subscription rate limits (Anthropic CLI) are unpublished. Batch
workloads (indexing 200 chunks, eval grounding 73 items) can blow through
RPM without warning, triggering 429 storms and circuit-breaker cascades.
Static concurrency=N requires guessing. This controller learns.

**How**: Per-provider concurrency cap, starts at conservative default,
auto-reduces ÷2 on ANY adverse signal (CB open, 429, 5xx, slow_call),
gradually recovers +1 after 30 minutes of clean runs.

**Signals (any triggers reduce)**:
- ``cb_opened``        — provider's CircuitBreaker opened (3+ consecutive errors)
- ``http_429``         — rate limit response
- ``http_5xx``         — server error / overload
- ``slow_call``        — latency above threshold (default p95 > 30s sustained)

**Tuning** (env vars):
- ``LLM_ROTATION_BATCH_CONCURRENCY``       — initial value (default 3)
- ``LLM_ROTATION_BATCH_MIN_CONCURRENCY``   — floor (default 1)
- ``LLM_ROTATION_BATCH_MAX_CONCURRENCY``   — ceiling (default 10)
- ``LLM_ROTATION_BATCH_RECOVERY_MINUTES``  — clean window before +1 (default 30)
- ``LLM_ROTATION_BATCH_SLOW_THRESHOLD_S``  — latency threshold for slow_call (default 30)

**Persistent state**: ``data/llm-rotation-adaptive-concurrency.json``
survives process restarts; learned values carry over between sessions.

Usage:
    ctrl = AdaptiveConcurrencyController()
    cc = ctrl.get_concurrency("claude-cli-haiku")  # → 3 initially
    # ... batch run ...
    ctrl.record_event("claude-cli-haiku", "http_429")  # auto-reduces to 1-2
    cc = ctrl.get_concurrency("claude-cli-haiku")  # → halved
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

EventType = Literal["cb_opened", "http_429", "http_5xx", "slow_call"]

_DEFAULT_STATE_PATH = Path("data") / "llm-rotation-adaptive-concurrency.json"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass
class ProviderConcurrencyState:
    """Per-provider adaptive state."""

    provider: str
    current_concurrency: int
    last_event_at: datetime | None = None
    last_recovery_at: datetime | None = None
    events: list[dict] = field(default_factory=list)  # recent N events for diagnostics
    total_reductions: int = 0
    total_recoveries: int = 0


class AdaptiveConcurrencyController:
    """Track per-provider adaptive concurrency with multi-signal reduction.

    Thread-safety: not designed for multi-threaded use; intended for
    single-process async batch workloads. State persistence is best-effort
    (atomic JSON write via tmp + replace).
    """

    def __init__(
        self,
        initial: int | None = None,
        floor: int | None = None,
        ceiling: int | None = None,
        recovery_minutes: float | None = None,
        slow_threshold_s: float | None = None,
        state_path: Path | None = None,
    ) -> None:
        self._initial: int = (
            initial if initial is not None else _env_int("LLM_ROTATION_BATCH_CONCURRENCY", 3)
        )
        self._floor: int = (
            floor if floor is not None else _env_int("LLM_ROTATION_BATCH_MIN_CONCURRENCY", 1)
        )
        self._ceiling: int = (
            ceiling if ceiling is not None else _env_int("LLM_ROTATION_BATCH_MAX_CONCURRENCY", 10)
        )
        self._recovery_minutes: float = (
            recovery_minutes
            if recovery_minutes is not None
            else _env_float("LLM_ROTATION_BATCH_RECOVERY_MINUTES", 30.0)
        )
        self._slow_threshold_s: float = (
            slow_threshold_s
            if slow_threshold_s is not None
            else _env_float("LLM_ROTATION_BATCH_SLOW_THRESHOLD_S", 30.0)
        )
        self._state_path: Path = state_path or _DEFAULT_STATE_PATH
        self._state: dict[str, ProviderConcurrencyState] = {}
        self._load()

    @property
    def slow_threshold_s(self) -> float:
        """Latency threshold (seconds) for slow_call event classification."""
        return self._slow_threshold_s

    def get_concurrency(self, provider: str) -> int:
        """Return current concurrency cap for provider.

        Auto-applies pending recovery: if clean window elapsed since last
        event, increments concurrency by 1 (capped at ceiling).
        """
        state = self._state.get(provider)
        if state is None:
            state = ProviderConcurrencyState(
                provider=provider,
                current_concurrency=self._initial,
            )
            self._state[provider] = state
            return state.current_concurrency

        # Gradual recovery: +1 per recovery_minutes of clean window
        now = datetime.now()
        last_signal = state.last_event_at
        if (
            last_signal is not None
            and state.current_concurrency < self._initial
            and (now - last_signal) >= timedelta(minutes=self._recovery_minutes)
        ):
            # Avoid double-bump within same recovery window
            since_recovery = (
                (now - state.last_recovery_at) if state.last_recovery_at else timedelta(days=1)
            )
            if since_recovery >= timedelta(minutes=self._recovery_minutes):
                new_cc = min(self._ceiling, state.current_concurrency + 1)
                if new_cc > state.current_concurrency:
                    logger.info(
                        "[ADAPTIVE] %s recovered: concurrency %d → %d (clean window: %.1f min)",
                        provider,
                        state.current_concurrency,
                        new_cc,
                        (now - last_signal).total_seconds() / 60,
                    )
                    state.current_concurrency = new_cc
                    state.last_recovery_at = now
                    state.total_recoveries += 1
                    self._save()

        return state.current_concurrency

    def record_event(self, provider: str, event_type: EventType) -> None:
        """Record adverse signal. Triggers ÷2 reduction (floor=1)."""
        state = self._state.get(provider)
        if state is None:
            state = ProviderConcurrencyState(
                provider=provider,
                current_concurrency=self._initial,
            )
            self._state[provider] = state

        now = datetime.now()
        state.last_event_at = now
        state.events.append(
            {
                "ts": now.isoformat(),
                "type": event_type,
                "concurrency_before": state.current_concurrency,
            }
        )
        # Cap diagnostic event log at 50 most-recent
        if len(state.events) > 50:
            state.events = state.events[-50:]

        old_cc = state.current_concurrency
        new_cc = max(self._floor, old_cc // 2)
        if new_cc < old_cc:
            logger.warning(
                "[ADAPTIVE] %s signal=%s → concurrency %d → %d (floor=%d)",
                provider,
                event_type,
                old_cc,
                new_cc,
                self._floor,
            )
            state.current_concurrency = new_cc
            state.total_reductions += 1
        else:
            logger.debug(
                "[ADAPTIVE] %s signal=%s but already at floor=%d (no reduction)",
                provider,
                event_type,
                self._floor,
            )

        self._save()

    def record_latency(self, provider: str, elapsed_s: float) -> None:
        """Latency-based signal: if elapsed > slow_threshold_s, treat as slow_call.

        Lightweight wrapper; caller can also call record_event directly.
        """
        if elapsed_s > self._slow_threshold_s:
            self.record_event(provider, "slow_call")

    def get_stats(self, provider: str | None = None) -> dict:
        """Return diagnostic snapshot.

        Args:
            provider: if None, returns all-providers summary. If provider name,
                      returns per-provider detail including recent events.
        """
        if provider is None:
            return {
                "config": {
                    "initial": self._initial,
                    "floor": self._floor,
                    "ceiling": self._ceiling,
                    "recovery_minutes": self._recovery_minutes,
                    "slow_threshold_s": self._slow_threshold_s,
                },
                "providers": {
                    name: {
                        "current": s.current_concurrency,
                        "reductions": s.total_reductions,
                        "recoveries": s.total_recoveries,
                        "last_event": s.last_event_at.isoformat() if s.last_event_at else None,
                    }
                    for name, s in self._state.items()
                },
            }

        s = self._state.get(provider)
        if s is None:
            return {"provider": provider, "current": self._initial, "events": []}
        return {
            "provider": provider,
            "current": s.current_concurrency,
            "reductions": s.total_reductions,
            "recoveries": s.total_recoveries,
            "last_event": s.last_event_at.isoformat() if s.last_event_at else None,
            "last_recovery": s.last_recovery_at.isoformat() if s.last_recovery_at else None,
            "recent_events": s.events[-10:],
        }

    def reset(self, provider: str | None = None) -> None:
        """Reset state. If provider=None, reset all."""
        if provider is None:
            self._state = {}
        else:
            self._state.pop(provider, None)
        self._save()

    def _save(self) -> None:
        """Atomic JSON write to state file. Best-effort — never raises."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                name: {
                    "provider": s.provider,
                    "current_concurrency": s.current_concurrency,
                    "last_event_at": s.last_event_at.isoformat() if s.last_event_at else None,
                    "last_recovery_at": s.last_recovery_at.isoformat()
                    if s.last_recovery_at
                    else None,
                    "events": s.events,
                    "total_reductions": s.total_reductions,
                    "total_recoveries": s.total_recoveries,
                }
                for name, s in self._state.items()
            }
            tmp = self._state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._state_path)
        except OSError as e:
            logger.debug("[ADAPTIVE] state save failed: %s", e)

    def _load(self) -> None:
        """Load state from disk if available. Best-effort."""
        try:
            if not self._state_path.is_file():
                return
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            for name, entry in data.items():
                self._state[name] = ProviderConcurrencyState(
                    provider=entry.get("provider", name),
                    current_concurrency=int(entry.get("current_concurrency", self._initial)),
                    last_event_at=_parse_iso(entry.get("last_event_at")),
                    last_recovery_at=_parse_iso(entry.get("last_recovery_at")),
                    events=entry.get("events", []),
                    total_reductions=int(entry.get("total_reductions", 0)),
                    total_recoveries=int(entry.get("total_recoveries", 0)),
                )
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.debug("[ADAPTIVE] state load failed: %s", e)
            self._state = {}


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
