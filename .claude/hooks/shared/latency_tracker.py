"""
Shared latency tracker for PostToolUse hooks.
Adds @track_latency decorator that logs timing to data/hook-latency.jsonl.
Budget: p95 < 200ms. Warns at 160ms (80% budget).
"""

import json
import os
import time
from datetime import datetime
from functools import wraps

_HOOK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DIR = os.path.dirname(os.path.dirname(_HOOK_DIR))
_LATENCY_LOG = os.path.join(_PROJECT_DIR, "data", "hook-latency.jsonl")
_BUDGET_MS = 200
_WARN_MS = int(_BUDGET_MS * 0.8)


def track_latency(func):
    """Decorator: measure and log hook execution latency."""
    @wraps(func)
    def wrapper(self, inp, *args, **kwargs):
        start = time.monotonic()
        try:
            result = func(self, inp, *args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            hook_name = type(self).__name__
            tool_name = getattr(inp, "tool_name", "unknown")
            _log_latency(hook_name, tool_name, elapsed_ms)
            if elapsed_ms > _WARN_MS:
                import sys
                msg = (
                    f"[LATENCY] {hook_name} took {elapsed_ms:.0f}ms "
                    f"(budget {_BUDGET_MS}ms, warn at {_WARN_MS}ms)"
                )
                print(msg, file=sys.stderr)

    return wrapper


def _log_latency(hook_name: str, tool_name: str, elapsed_ms: float):
    """Log latency to SQLite (fallback: JSONL)."""
    try:
        from shared.db_writer import log_latency as db_log_latency
        db_log_latency(
            hook_name=hook_name,
            tool_name=tool_name,
            latency_ms=elapsed_ms,
            over_budget=elapsed_ms > _BUDGET_MS,
        )
    except Exception:
        # Fallback to JSONL
        entry = {
            "ts": datetime.now().isoformat(),
            "hook": hook_name,
            "tool": tool_name,
            "latency_ms": round(elapsed_ms, 1),
            "over_budget": elapsed_ms > _BUDGET_MS,
        }
        try:
            os.makedirs(os.path.dirname(_LATENCY_LOG), exist_ok=True)
            with open(_LATENCY_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass


def get_latency_stats(last_n: int = 100) -> dict:
    """Get latency statistics from SQLite (fallback: JSONL)."""
    # Try SQLite first
    try:
        from shared.db_writer import get_latency_stats as db_get_stats
        result = db_get_stats(last_n)
        if result.get("count", 0) > 0:
            return result
    except Exception:
        pass

    # Fallback to JSONL
    try:
        entries = []
        if not os.path.isfile(_LATENCY_LOG):
            return {"count": 0}
        with open(_LATENCY_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if not entries:
            return {"count": 0}
        entries = entries[-last_n:]
        latencies = [e["latency_ms"] for e in entries if "latency_ms" in e]
        if not latencies:
            return {"count": 0}
        latencies.sort()
        n = len(latencies)
        return {
            "count": n,
            "p50": latencies[n // 2],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[int(n * 0.99)],
            "max": latencies[-1],
            "over_budget": sum(1 for l in latencies if l > _BUDGET_MS),
        }
    except Exception:
        return {"count": 0}
