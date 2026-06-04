"""§27 P3 (D3.1) — Canonical event envelope + reader-adapter for memory logs.

The §27 observability layer writes per-process JSONL across many sinks, each with
its own ad-hoc schema (confidence-lifecycle, surfacing, ingestion, routing, read,
propagation, circuit, metrics, maintenance, audit). To correlate one fact across
all of them (D3.2) and query them together in DuckDB (P3), every raw record is
projected into ONE canonical CloudEvents-style envelope.

Per roadmap Q3 the existing sinks are **not** migrated — this is a *reader-adapter*:
on-disk formats stay untouched; :func:`normalize` projects each record into the
canonical shape at read time. :func:`make_envelope` is the forward helper a new
writer may use to emit already-canonical fields (CloudEvents v1.0 envelope,
mirroring ``.claude/hooks/shared/invocation_logger.py`` §15).

Canonical fields (all flat — DuckDB ``union_by_name`` friendly):
  ts             ISO timestamp (carried through verbatim)
  source         short sink label ("ingestion", "lifecycle", ...)
  type           event type within the sink ("ingest", "save", "route", ...)
  correlation_id best-effort cross-event id ("" when absent)
  content_hash   cross-store fact key ("" when absent) — the primary D3.2 thread
  + a small set of common scalar passthroughs (store/action/outcome/latency_ms/...)

**Metadata only** — never carries prompt/pattern bodies (the source logs already
enforce this; we project only scalar metadata).

Roadmap: ``docs/roadmap/260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md`` (§27 P3).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# --- Sink registry ------------------------------------------------------------
# Maps each known memory JSONL sink (filename) -> canonical source label.
# This is the single source of truth for "which sinks exist" — used by the
# DuckDB query layer (P3) and the observability report's freshness/regression
# detector (P4), so adding a sink here wires it into both.

CACHE_LOGS: dict[str, str] = {
    "confidence-lifecycle.log": "lifecycle",
    "memory-first-surfacing.log": "surfacing",
    "memory-ingestion.log": "ingestion",
    "memory-routing.log": "routing",
    "memory-read.log": "read",
    "memory-propagation.log": "propagation",
    "memory-circuit.log": "circuit",
    "memory-metrics.jsonl": "metrics",
    "memory-maintenance-runs.jsonl": "maintenance",
}

# Audit lives outside .claude/cache with a richer dataclass schema.
AUDIT_REL_PATH = ("data", "services", "audit.jsonl")
AUDIT_LABEL = "audit"

# All canonical source labels (the "expected set" for regression detection).
SOURCE_LABELS: tuple[str, ...] = tuple(CACHE_LOGS.values()) + (AUDIT_LABEL,)

# Stable core columns ALWAYS present in a normalized record (None when absent).
# A fixed core keeps the DuckDB union-by-name schema stable: read_json_auto only
# materializes columns that appear in ≥1 line, so a predefined view referencing
# e.g. ``outcome`` would error whenever no record happened to carry it. Seeding
# the core guarantees every column the query views reference always exists.
CORE_KEYS = (
    "ts", "source", "type", "correlation_id", "content_hash", "pattern_id",
    "store", "action", "outcome", "latency_ms", "success",
)

# Scalar metadata projected verbatim for the generic (trace_log-style) sinks.
# Bodies / dicts-of-bodies are intentionally excluded; small dict/list metadata
# (e.g. arm_hits, targets) is kept since it is counts-only.
_GENERIC_PASSTHROUGH = (
    "store", "action", "harvester", "reason", "size",
    "latency_ms", "circuit", "old", "new", "method", "targets",
    "final", "min_score", "rrf", "arm_hits", "sources_searched", "sources_failed",
    "entities_updated", "cascades_prevented", "final_depth",
    "failure_count", "total_failures", "applied", "outcome",
    "pattern_id", "old_confidence", "new_confidence", "application_count",
    "total_facts", "cross_store_dup_rate", "forget", "jobs", "store_sizes",
    "pid", "collection",
)


def known_sinks(project_root: str | Path) -> list[tuple[str, Path]]:
    """Return ``[(source_label, path)]`` for every known memory sink.

    The list is the authoritative expected-set for the freshness / observability
    regression detector — a sink that exists here but has gone silent is flagged.
    Paths may not exist yet (cold sinks / MCP-side logs before first run).
    """
    root = Path(project_root)
    cache = root / ".claude" / "cache"
    out = [(label, cache / fname) for fname, label in CACHE_LOGS.items()]
    out.append((AUDIT_LABEL, root.joinpath(*AUDIT_REL_PATH)))
    return out


def _first_str(*vals: Any) -> str:
    for v in vals:
        if v:
            return str(v)
    return ""


def normalize(source: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Project a raw record from sink ``source`` into the canonical envelope.

    Fail-soft: a non-dict / unexpected record yields a minimal envelope rather
    than raising (the DuckDB layer pre-filters, but callers may pass anything).

    Args:
        source: canonical source label (see :data:`SOURCE_LABELS`).
        raw: one decoded JSON record from that sink.

    Returns:
        Flat dict with at least ``ts/source/type/correlation_id/content_hash``.
    """
    env: dict[str, Any] = dict.fromkeys(CORE_KEYS)  # stable schema, None-seeded
    env["source"] = source
    env["type"] = ""
    env["correlation_id"] = ""
    env["content_hash"] = ""
    if not isinstance(raw, dict):
        return env

    env["ts"] = _first_str(raw.get("ts"), raw.get("timestamp"), raw.get("time"))
    env["correlation_id"] = _first_str(raw.get("correlationid"), raw.get("correlation_id"))
    env["content_hash"] = _first_str(raw.get("content_hash"))

    if source == AUDIT_LABEL:
        env["type"] = _first_str(raw.get("action"))
        env["action"] = raw.get("action")
        env["correlation_id"] = env["correlation_id"] or _first_str(raw.get("session_id"))
        env["resource_type"] = raw.get("resource_type")
        env["resource_id"] = raw.get("resource_id")
        env["success"] = raw.get("success")
        env["latency_ms"] = raw.get("duration_ms")
        env["error"] = bool(raw.get("error_message"))
        md = raw.get("metadata")
        if not env["content_hash"] and isinstance(md, dict):
            env["content_hash"] = _first_str(md.get("content_hash"))
        return env

    if source == "surfacing":
        # Surfacing has no `event` key — its records are keyed by `outcome`.
        env["type"] = _first_str(raw.get("outcome"), "surface")
        env["outcome"] = raw.get("outcome")
        env["latency_ms"] = raw.get("duration_ms")
        env["cache"] = raw.get("cache")
        env["tei"] = raw.get("tei")
        env["merged_count"] = raw.get("merged_count")
        return env

    # Generic trace_log / lifecycle / ingestion style: keyed by `event`.
    env["type"] = _first_str(raw.get("event"))
    for k in _GENERIC_PASSTHROUGH:
        if k in raw:
            env[k] = raw[k]
    return env


def make_envelope(
    source: str,
    event_type: str,
    *,
    ts: str | None = None,
    correlation_id: str = "",
    causation_id: str = "",
    content_hash: str = "",
    **meta: Any,
) -> dict[str, Any]:
    """Build a forward CloudEvents v1.0 envelope for a new canonical writer.

    Mirrors the §15 ``invocation_logger`` envelope (specversion/id/source/type/
    time + correlation/causation extensions) but for the memory-observability
    domain. New P1/P2 writers MAY emit through this; the reader-adapter
    (:func:`normalize`) keeps legacy sinks readable without it.
    """
    now = datetime.now().isoformat(timespec="milliseconds")
    rec: dict[str, Any] = {
        "specversion": "1.0",
        "id": str(uuid.uuid4()),
        "source": source,
        "type": event_type,
        "time": ts or now,
        "ts": ts or now,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "content_hash": content_hash,
    }
    rec.update(meta)
    return rec


__all__ = [
    "AUDIT_LABEL",
    "CACHE_LOGS",
    "SOURCE_LABELS",
    "known_sinks",
    "make_envelope",
    "normalize",
]
