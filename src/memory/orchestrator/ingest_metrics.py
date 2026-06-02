"""§26 P0 (D0.3) — Ingestion metrics: trace log + in-process counters.

P1 harvesters call :func:`record_ingest` on every write *attempt*. Two sinks:

1. **Persistent JSONL** ``.claude/cache/memory-ingestion.log`` — the cross-process
   source the §25 analyzer aggregates. Harvesters run as separate hook processes,
   so the in-memory :class:`MetricsCollector` singleton cannot span them; the log can.
2. **Best-effort in-process counters** on the global ``MetricsCollector`` for the
   live ``memory_metrics`` MCP tool, when called inside the orchestrator process.

Records are **metadata only** — store / action / content_hash / reason / counts —
never content bodies. Fail-soft (never raises), atomic size-rotation, opt-out
``MEMORY_INGEST_LOG_DISABLE=1``. Mirrors the §22/§24 trace-log conventions
(``vector_memory/lifecycle_log.py``).

Actions (the ``action`` arg) form the metric vocabulary:
  - ``saved``   — a new cube was written to the store
  - ``dup``     — skipped: content_hash already present (anti-flood / idempotency)
  - ``skipped`` — skipped for another gated reason (confidence floor, cap, opt-out)
  - ``error``   — write attempt failed
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOG_ENABLED = os.environ.get("MEMORY_INGEST_LOG_DISABLE") != "1"
_LOG_CAP_BYTES = 2_000_000

# Recognised actions; anything else is logged verbatim but not counter-bucketed.
ACTIONS = ("saved", "dup", "skipped", "error")


def _log_file() -> Path:
    """Path to memory-ingestion.log, honoring the CLAUDE_CACHE_DIR override."""
    cache_dir = os.environ.get("CLAUDE_CACHE_DIR")
    base = Path(cache_dir) if cache_dir else _PROJECT_ROOT / ".claude" / "cache"
    return base / "memory-ingestion.log"


def log_ingest(event: str, **fields: Any) -> None:
    """Append one JSON record to memory-ingestion.log. Fully fail-soft."""
    if not _LOG_ENABLED:
        return
    try:
        from datetime import datetime

        path = _log_file()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic size-rotation before append (keep the newest half).
        try:
            if path.exists() and path.stat().st_size > _LOG_CAP_BYTES:
                data = path.read_bytes()[-(_LOG_CAP_BYTES // 2):]
                idx = data.find(b"\n")
                if idx != -1:
                    data = data[idx + 1:]  # drop partial first line
                fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix="inglog-")
                try:
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(data)
                    os.replace(tmp_path, path)
                except Exception:
                    os.unlink(tmp_path)
                    raise
        except Exception:
            pass  # rotation failure never blocks the append

        record = {"ts": datetime.now().isoformat(timespec="milliseconds"), "event": event}
        record.update(fields)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # fully fail-soft


def _bump_counters(store: str, action: str) -> None:
    """Best-effort in-process counters; no-op if the collector import fails."""
    try:
        from src.memory.infrastructure.metrics import get_metrics_collector

        m = get_metrics_collector()
        m.counter(f"ingest_{action}")
        m.counter(f"ingest_{store}_{action}")
    except Exception:
        pass


def record_ingest(
    store: str,
    action: str,
    *,
    content_hash: str = "",
    reason: str | None = None,
    harvester: str | None = None,
    **extra: Any,
) -> None:
    """Record one ingestion attempt to both sinks (metadata only).

    Args:
        store: Target store ('learned_patterns' | 'memory-ai' | 'skill-learning' | ...).
        action: One of :data:`ACTIONS` (saved/dup/skipped/error).
        content_hash: The cross-store idempotency key (no content body).
        reason: Why skipped/errored (e.g. 'below_confidence_floor', 'session_cap').
        harvester: Which P1 harvester emitted this (for attribution).
        **extra: Extra JSON-serializable metadata (counts, ids) — no bodies.
    """
    fields: dict[str, Any] = {"store": store, "action": action}
    if content_hash:
        fields["content_hash"] = content_hash
    if reason:
        fields["reason"] = reason
    if harvester:
        fields["harvester"] = harvester
    fields.update(extra)
    log_ingest("ingest", **fields)
    _bump_counters(store, action)


def record_store_size(store: str, size: int) -> None:
    """Record a store's current size (gauge + log) for bounded-growth tracking."""
    try:
        from src.memory.infrastructure.metrics import get_metrics_collector

        get_metrics_collector().gauge(f"store_size_{store}", float(size))
    except Exception:
        pass
    log_ingest("store_size", store=store, size=size)


__all__ = ["ACTIONS", "log_ingest", "record_ingest", "record_store_size"]
