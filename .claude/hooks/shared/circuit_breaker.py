"""
Circuit Breaker for hooks.

States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- CLOSED: normal execution, counting failures
- OPEN: skip hook entirely (too many failures)
- HALF_OPEN: try one probe after cooldown

State stored in .claude/cache/circuit-breaker-state.json
"""

import json
import time
from functools import wraps
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"
_STATE_FILE = _CACHE_DIR / "circuit-breaker-state.json"

# Defaults (overridable per-hook)
FAILURE_THRESHOLD = 5
RESET_TIMEOUT = 300  # seconds before HALF_OPEN
SUCCESS_THRESHOLD = 2  # successes in HALF_OPEN to CLOSE


def _read_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _write_state(state: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def get_state(hook_name: str) -> dict:
    """Get circuit breaker state for a hook."""
    all_state = _read_state()
    return all_state.get(hook_name, {
        "state": "CLOSED",
        "failures": 0,
        "successes": 0,
        "last_failure": 0,
        "last_error": "",
    })


def _save_hook_state(hook_name: str, hook_state: dict) -> None:
    all_state = _read_state()
    all_state[hook_name] = hook_state
    _write_state(all_state)


def is_open(hook_name: str) -> bool:
    """Check if circuit is OPEN. If timeout expired, transition to HALF_OPEN."""
    hs = get_state(hook_name)
    if hs["state"] == "CLOSED":
        return False
    if hs["state"] == "OPEN":
        elapsed = time.time() - hs.get("last_failure", 0)
        if elapsed >= RESET_TIMEOUT:
            hs["state"] = "HALF_OPEN"
            hs["successes"] = 0
            _save_hook_state(hook_name, hs)
            return False  # allow probe
        return True  # still OPEN
    # HALF_OPEN — allow probe
    return False


def record_success(hook_name: str) -> None:
    """Record successful execution."""
    hs = get_state(hook_name)
    if hs["state"] == "HALF_OPEN":
        hs["successes"] = hs.get("successes", 0) + 1
        if hs["successes"] >= SUCCESS_THRESHOLD:
            hs["state"] = "CLOSED"
            hs["failures"] = 0
            hs["successes"] = 0
            hs["last_error"] = ""
        _save_hook_state(hook_name, hs)
    elif hs["state"] == "CLOSED" and hs.get("failures", 0) > 0:
        # Reset failure count on success in CLOSED state
        hs["failures"] = max(0, hs["failures"] - 1)
        _save_hook_state(hook_name, hs)


def record_failure(hook_name: str, error: str = "") -> None:
    """Record failed execution. May transition to OPEN."""
    hs = get_state(hook_name)
    hs["failures"] = hs.get("failures", 0) + 1
    hs["last_failure"] = time.time()
    hs["last_error"] = error[:200]

    if hs["state"] == "HALF_OPEN":
        # Probe failed -> back to OPEN
        hs["state"] = "OPEN"
    elif hs["state"] == "CLOSED" and hs["failures"] >= FAILURE_THRESHOLD:
        hs["state"] = "OPEN"

    _save_hook_state(hook_name, hs)


def with_circuit_breaker(hook_name: str):
    """Decorator: skip execution if circuit is OPEN, track success/failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if is_open(hook_name):
                return None  # skip silently
            try:
                result = func(*args, **kwargs)
                record_success(hook_name)
                return result
            except Exception as e:
                record_failure(hook_name, str(e))
                return None  # graceful degradation
        return wrapper
    return decorator
