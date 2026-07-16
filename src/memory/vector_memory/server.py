"""
Vector Memory MCP Server — Confidence-Weighted Pattern Learning.

MCP server for storing, searching, and managing learned patterns
with Qdrant backend, temporal decay, and evidence linking.

Migrated from D:\\1C-Enterprise_Framework\\vector-memory-mcp\\src\\server.py
Adapted: uses project's Qdrant instance (localhost:6333), collection 'learned_patterns'.
Uses 1024d vectors (multilingual-e5-large) instead of 768d.
"""

import asyncio
import json
import logging
import os
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

from ..orchestrator.content_hash import hash_content as _hash_content
from ..orchestrator.content_hash import point_id as _content_point_id
from .confidence import (
    LEGACY_SEED_CONFIDENCE,
    apply_to_payload,
    decay_counts,
    derive_confidence,
    payload_effective_confidence,
    seed_counts_from_legacy,
    should_archive,
    stability_adjusted_rate,
)
from .epoch import bump as _bump_epoch  # §24: surfacing-cache invalidation signal


def _record_ingest(store: str, action: str, **fields: Any) -> None:
    """Fail-soft §26 ingestion-metrics emit; never breaks an MCP handler."""
    try:
        from ..orchestrator.ingest_metrics import record_ingest

        record_ingest(store, action, **fields)
    except Exception:
        pass


def _log_lifecycle(event: str, **fields: Any) -> None:
    """Fail-soft §22 lifecycle trace; never breaks an MCP handler."""
    try:
        from .lifecycle_log import log_event

        log_event(event, **fields)
    except Exception:
        pass


# §27 cascade — apply_pattern → confidence propagation to linked neighbours.
# Closes the "cascade not wired into autonomous apply" gap (§22 P3 deferred the
# neighbour-aware link_registry gate; roadmap 260605 follow-up): the §10.2
# feedback-loop cascade step now fires on every apply_pattern. Depth-1, same-store
# (learned_patterns), fail-soft, bounded, gated MEMORY_APPLY_CASCADE_DISABLE=1.
# NOTE: a no-op until real pattern↔pattern links exist in link_registry (today's graph
# is integration-test fixtures only). MCP-side → needs /mcp reconnect to take effect.
_APPLY_CASCADE_MAX = 10  # max neighbours nudged per apply (rate-limit; mirrors PropagationEngine)
_APPLY_CASCADE_BASE = 1.0  # base pseudo-observation magnitude, then decayed


def _cascade_confidence(
    client: Any, pattern_id: str, success: bool, now: datetime
) -> dict[str, int]:
    """Propagate an apply's confidence delta to directly-linked neighbour patterns.

    Mirrors PropagationEngine decay — ``link_strength × distance(0.5^1) × time(max(0.5,1−days/365))``
    — but synchronous and scoped to ``learned_patterns``. Nudges each neighbour's Beta succ/fail
    (success→succ, fail→fail) and re-derives confidence. Fully fail-soft; returns trace stats.
    """
    stats = {"entities_updated": 0, "cascades_prevented": 0, "final_depth": 0, "errors": 0}
    if os.environ.get("MEMORY_APPLY_CASCADE_DISABLE") == "1":
        return stats
    import time as _time

    t0 = _time.monotonic()
    try:
        # Relative, NOT `from memory.orchestrator...` (roadmap 260716 P1.8). The server
        # runs as `-m src.memory.vector_memory.server`, so the absolute `memory.*`
        # namespace only resolves once `_get_embedding` has lazily put <root>/src on
        # sys.path — before that first embed call this import raised ModuleNotFoundError
        # straight into the function-level `except: pass` and the cascade was a silent
        # no-op; after it, the same import bound a SECOND copy of link_registry. The
        # cascade's behaviour depended on call order. Relative import closes both.
        from ..orchestrator.link_registry import LinkRegistry, LinkType
        from .confidence import derive_confidence, seed_counts_from_legacy

        # Forward-correlation links only — CONTRADICTS has inverse semantics
        # (excluded for v1). BASED_ON ретирован 2026-06-12 (ADR-L1).
        link_types = [LinkType.SUPPORTS, LinkType.EXTENDS, LinkType.DERIVES_FROM]
        registry = LinkRegistry()
        links = registry.get_links_from(pattern_id, link_types=link_types)
        # Orchestrator's create_link stores unified IDs ("semantic:vector-memory:<pid>");
        # without this second lookup such edges are invisible to the cascade
        # (F4, roadmap 260610 B2). seen-dedup below collapses bare/unified duplicates.
        links += registry.get_links_from(
            f"semantic:vector-memory:{pattern_id}", link_types=link_types
        )
        if not links:
            # P3.2 (roadmap 260612 LinkRegistry, L5): пустой каскад больше не
            # невидим — голодание графа видно в observability.
            try:
                from ..infrastructure.trace_log import write_trace

                write_trace(
                    "memory-links.log",
                    "cascade_empty",
                    disable_env="MEMORY_LINKS_LOG_DISABLE",
                    pattern_id=pattern_id,
                )
            except Exception:
                pass
            return stats  # cheap no-op for an empty/unlinked graph
        stats["final_depth"] = 1
        seen: set[str] = set()
        for link in links:
            if stats["entities_updated"] >= _APPLY_CASCADE_MAX:
                stats["cascades_prevented"] += 1
                continue
            # Per-item isolation (roadmap 260716 P0.2): before this, ONE bad
            # neighbour escaped to the function-level `except: pass` — aborting the
            # cascade for every remaining neighbour AND skipping _bump_epoch(), so
            # already-written neighbours sat behind a stale surfacing cache. Same
            # partial-mutation class the decay-sweep fix closed.
            try:
                nid = link.target_id
                if nid.startswith("semantic:vector-memory:"):
                    nid = nid.rsplit(":", 1)[-1]
                elif ":" in nid:
                    # cross-store neighbour — PropagationEngine's territory, not same-store cascade
                    stats["cascades_prevented"] += 1
                    continue
                if nid == pattern_id or nid in seen:
                    continue
                seen.add(nid)
                npts = client.retrieve(
                    collection_name=COLLECTION_NAME, ids=[nid], with_payload=True
                )
                if not npts:  # neighbour is not a learned_pattern → can't nudge
                    stats["cascades_prevented"] += 1
                    continue
                npay = npts[0].payload or {}
                ca = coerce_dt(link.created_at)
                age_days = 0 if ca is None else max(0, (now - ca).days)
                time_decay = max(0.5, 1.0 - age_days / 365.0)
                # 0.5 = dist^1
                delta = _APPLY_CASCADE_BASE * coerce_float(link.strength, 0.0) * 0.5 * time_decay
                if delta < 0.001:
                    stats["cascades_prevented"] += 1
                    continue
                raw_succ, raw_fail = npay.get("succ"), npay.get("fail")
                if raw_succ is None or raw_fail is None:
                    # coerce_*: a null confidence would raise here and silently abort
                    # the cascade for the REMAINING neighbours (roadmap 260716).
                    succ, fail = seed_counts_from_legacy(
                        coerce_float(npay.get("confidence"), LEGACY_SEED_CONFIDENCE),
                        coerce_int(npay.get("application_count"), 0),
                    )
                else:
                    # The present-but-garbage branch needs coercion just as much:
                    # a string succ raised in the arithmetic below.
                    succ = coerce_float(raw_succ, 0.0)
                    fail = coerce_float(raw_fail, 0.0)
                if success:
                    succ += delta
                else:
                    fail += delta
                client.set_payload(
                    collection_name=COLLECTION_NAME,
                    payload={
                        "succ": round(succ, 6),
                        "fail": round(fail, 6),
                        "confidence": round(derive_confidence(succ, fail), 6),
                        "updated_at": now.isoformat(),
                    },
                    points=[nid],
                )
                stats["entities_updated"] += 1
            except Exception as exc:
                stats["errors"] = stats.get("errors", 0) + 1
                logger.warning(f"cascade: skipped neighbour of {pattern_id}: {exc}")
        if stats["entities_updated"]:
            _bump_epoch()  # neighbour confidences changed → invalidate surfacing cache
    except Exception:
        pass
    try:
        from ..infrastructure.trace_log import write_trace

        write_trace(
            "memory-propagation.log",
            "propagate",
            disable_env="MEMORY_PROPAGATION_LOG_DISABLE",
            source=pattern_id,
            entities_updated=stats["entities_updated"],
            cascades_prevented=stats["cascades_prevented"],
            final_depth=stats["final_depth"],
            # Skipped neighbours must leave the function, not just the logger —
            # symmetry with items_skipped/errors/unreadable in the other loops.
            errors=stats.get("errors", 0),
            latency_ms=round((_time.monotonic() - t0) * 1000, 1),
        )
    except Exception:
        pass
    return stats


from .models import (
    EvidenceSource,
    LearnedPattern,
    PatternSearchResult,
    PatternType,
    coerce_dt,
    coerce_float,
    coerce_int,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("vector-memory")

# Qdrant configuration — shared instance with PDF framework
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("LEARNING_COLLECTION_NAME", "learned_patterns")
VECTOR_SIZE = int(
    os.getenv("LEARNING_VECTOR_SIZE", "4096")
)  # Qwen3-Embedding-8B (actual learned_patterns dim); was stale 1024 (multilingual-e5)
DECAY_RATE = float(os.getenv("LEARNING_DECAY_RATE", "0.05"))
MIN_CONFIDENCE = float(os.getenv("LEARNING_MIN_CONFIDENCE", "0.3"))

# Lazy-initialized clients
_qdrant_client: Any | None = None
# Guards lazy init against the warmup thread racing the first tool call
# (double client / _ensure_collection on a half-built global).
_qdrant_init_lock = threading.Lock()
# `_embedding_fn` is either the sentinel string "async" (use _embedding_provider)
# or a callable producing pseudo-embeddings (offline opt-in hash fallback).
_embedding_fn: str | Callable[[list[str]], list[list[float]]] | None = None
_embedding_provider: Any | None = None  # async E5 engine (if available)


def _get_qdrant() -> Any:
    """Lazy-init Qdrant client. Uses shared Qdrant at localhost:6333."""
    global _qdrant_client
    if _qdrant_client is None:
        with _qdrant_init_lock:
            if _qdrant_client is None:
                from qdrant_client import QdrantClient

                client = QdrantClient(
                    url=QDRANT_URL,
                    grpc_port=6334,
                    prefer_grpc=True,
                )
                _ensure_collection(client)
                # Publish only after ensure succeeded: a failed init leaves the
                # global None so the next call retries the full lazy path, and
                # fast-path readers outside the lock never see a client whose
                # collection isn't verified yet.
                _qdrant_client = client
    return _qdrant_client


def _warmup_qdrant() -> None:
    """S1-warmup (260611 §18, cold-start finding): pre-pay the heavy lazy import
    (`qdrant_client` → pydantic/grpc) + client init at server start, in a daemon
    thread. Post-`/mcp reconnect` many MCP servers import their stacks at once;
    under that contention the first tool call was burning its whole 60s client
    budget on import. Fail-soft: Qdrant being down must not kill the server —
    the next tool call retries via the same lazy path. Opt-out:
    MEMORY_VECTOR_NO_WARMUP=1.
    """
    try:
        _get_qdrant()
        logger.info("warmup: qdrant client ready (pid %d)", os.getpid())
    except Exception as exc:
        logger.warning("warmup skipped: %s", exc)


def _ensure_collection(client: Any) -> None:
    """Ensure learned_patterns collection exists with cosine 1024d vectors."""
    from qdrant_client.http import models as qmodels

    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )
        for field_name, field_type in [
            ("pattern_type", qmodels.PayloadSchemaType.KEYWORD),
            ("confidence", qmodels.PayloadSchemaType.FLOAT),
            ("tags", qmodels.PayloadSchemaType.KEYWORD),
        ]:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_type,
            )
        logger.info(f"Created collection {COLLECTION_NAME} ({VECTOR_SIZE}d cosine)")


async def _get_embedding(text: str) -> list[float]:
    """Get embedding using project's embedding provider.

    On provider init failure: raises RuntimeError by default — silent
    hash-based fallback was producing semantically-meaningless vectors
    which made pattern search effectively random (roadmap 260509 §4.3
    fix, 2026-05-16). To opt into the legacy fallback (e.g. for offline
    smoke testing where Qdrant + embedding model are both unavailable),
    set env `MEMORY_VECTOR_ALLOW_HASH_FALLBACK=1`. When opt-in is active,
    every embedding call emits a WARNING log line so the degraded mode
    is visible in operational logs.
    """
    global _embedding_fn, _embedding_provider
    if _embedding_fn is None:
        try:
            project_root = Path(__file__).parent.parent.parent.parent
            if str(project_root / "src") not in sys.path:
                sys.path.insert(0, str(project_root / "src"))
            from pdf_framework.embeddings import get_embedding_engine

            _embedding_provider = get_embedding_engine()
            _embedding_fn = "async"  # marker: use _embedding_provider
            logger.info(
                "Using project embedding provider: %s (%dd)",
                type(_embedding_provider).__name__,
                getattr(_embedding_provider, "get_dimensions", lambda: VECTOR_SIZE)(),
            )
        except Exception as exc:
            allow_fallback = os.environ.get(
                "MEMORY_VECTOR_ALLOW_HASH_FALLBACK", ""
            ).strip().lower() in ("1", "true", "yes")
            if not allow_fallback:
                logger.error(
                    "Embedding provider init failed: %s. "
                    "Silent hash-based fallback would corrupt pattern search "
                    "(roadmap 260509 §4.3). Set env "
                    "MEMORY_VECTOR_ALLOW_HASH_FALLBACK=1 to opt in for "
                    "offline/test environments.",
                    exc,
                )
                raise RuntimeError(
                    "Vector memory embedding provider unavailable and "
                    "MEMORY_VECTOR_ALLOW_HASH_FALLBACK is not set"
                ) from exc

            logger.warning(
                "Embedding provider init failed (%s) — falling back to "
                "hash-based pseudo-embeddings. Pattern search results will "
                "be semantically meaningless. Opt-in via "
                "MEMORY_VECTOR_ALLOW_HASH_FALLBACK=1 acknowledged.",
                exc,
            )
            import hashlib

            def _hash_embed(texts: list[str]) -> list[list[float]]:
                # Emit per-call WARN so degraded mode stays visible in
                # operational logs (not just init-time once).
                logger.warning(
                    "[HASH-FALLBACK] computing pseudo-embeddings for "
                    "%d text(s); results are NOT semantic",
                    len(texts),
                )
                results = []
                for t in texts:
                    h = hashlib.sha512(t.encode()).digest()
                    vec = [((b % 200) - 100) / 100.0 for b in h]
                    while len(vec) < VECTOR_SIZE:
                        h = hashlib.sha512(h).digest()
                        vec.extend([((b % 200) - 100) / 100.0 for b in h])
                    results.append(vec[:VECTOR_SIZE])
                return results

            _embedding_fn = _hash_embed

    if _embedding_fn == "async" and _embedding_provider is not None:
        result = await _embedding_provider.embed_batch([text])
        return result[0]  # type: ignore[no-any-return]
    assert callable(_embedding_fn), "embedding fn invariant violated"
    result = await asyncio.to_thread(_embedding_fn, [text])
    return result[0]  # type: ignore[no-any-return]


def _pattern_from_payload(point_id: str, payload: dict[str, Any] | None) -> LearnedPattern:
    """Convert Qdrant point payload to LearnedPattern. Never raises.

    The payload is UNTRUSTED (roadmap 260716 P0.2): 8+ producers write this
    collection. Until 2026-07-16 this function parsed strictly — a single point
    with `pattern_type: 'requirements'` (or a null confidence / garbage
    timestamp) raised out of the caller's loop and took down the entire
    search_patterns response and the unified_search vector arm with it. Every
    field now degrades on its own; per-item try/except in the loops is the
    backstop for anything not anticipated here.
    """
    payload = payload or {}
    evidence = [EvidenceSource.from_dict(e) for e in payload.get("evidence_sources", [])]

    # Lazy migration: seed succ/fail from legacy confidence + application_count
    # when the new fields are absent (points written before P0 migration).
    raw_succ = payload.get("succ")
    raw_fail = payload.get("fail")
    if raw_succ is None or raw_fail is None:
        succ, fail = seed_counts_from_legacy(
            coerce_float(payload.get("confidence"), LEGACY_SEED_CONFIDENCE),
            coerce_int(payload.get("application_count"), 0),
        )
    else:
        succ = coerce_float(raw_succ, 0.0)
        fail = coerce_float(raw_fail, 0.0)

    # last_decay_at: prefer explicit field, fall back through timestamp chain;
    # an unparsable value falls through to the next key instead of raising.
    last_decay_at: datetime | None = None
    for _key in ("last_decay_at", "last_applied", "updated_at", "created_at"):
        _parsed = coerce_dt(payload.get(_key))
        if _parsed is not None:
            last_decay_at = _parsed
            break

    return LearnedPattern(
        pattern_id=payload.get("pattern_id", point_id),
        pattern_type=PatternType.coerce(payload.get("pattern_type")),
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        content=payload.get("content", ""),
        # A missing denorm means "no observations recorded", which IS the prior — not
        # 0.5 (P1.9). The old literal made this reader disagree with the seed one branch
        # above it about the very same point.
        confidence=coerce_float(payload.get("confidence"), LEGACY_SEED_CONFIDENCE),
        evidence_sources=evidence,
        created_at=coerce_dt(payload.get("created_at")) or datetime.now(),
        updated_at=coerce_dt(payload.get("updated_at")) or datetime.now(),
        decay_rate=coerce_float(payload.get("decay_rate"), DECAY_RATE),
        application_count=coerce_int(payload.get("application_count"), 0),
        last_applied=coerce_dt(payload.get("last_applied")),
        succ=succ,
        fail=fail,
        last_decay_at=last_decay_at,
        # F5 (roadmap 260611 P3.1): without this mapping the model always
        # carried expired_at=None while the get_pattern response built
        # `archived` from the payload — archived:true with expired_at:null.
        expired_at=coerce_dt(payload.get("expired_at")),
        version=coerce_int(payload.get("version"), 1),
        tags=payload.get("tags", []),
        metadata=payload.get("metadata", {}),
    )


def _pattern_to_payload(pattern: LearnedPattern) -> dict[str, Any]:
    """Convert LearnedPattern to Qdrant payload dict."""
    return {
        "pattern_id": pattern.pattern_id,
        "pattern_type": pattern.pattern_type.value,
        "name": pattern.name,
        "description": pattern.description,
        "content": pattern.content,
        # §26 cross-store idempotency key — lets cross_store_sync / fact-trace match
        # this fact against the same content in other stores, and the §26 dedup path
        # detect re-saves. Stamped on every save path (mirrors the harvester payload).
        "content_hash": _hash_content(pattern.content),
        "confidence": pattern.confidence,
        "evidence_sources": [e.to_dict() for e in pattern.evidence_sources],
        "created_at": pattern.created_at.isoformat(),
        "updated_at": pattern.updated_at.isoformat(),
        "last_applied": pattern.last_applied.isoformat() if pattern.last_applied else None,
        "succ": pattern.succ,
        "fail": pattern.fail,
        "last_decay_at": pattern.last_decay_at.isoformat() if pattern.last_decay_at else None,
        "expired_at": pattern.expired_at.isoformat() if pattern.expired_at else None,
        "decay_rate": pattern.decay_rate,
        "application_count": pattern.application_count,
        "version": pattern.version,
        "tags": pattern.tags,
        "metadata": pattern.metadata,
    }


# ========== MCP Server ==========

app = Server("vector-memory")


@app.list_tools()  # type: ignore  # MCP decorator codes differ across mypy versions
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="save_pattern",
            description="Save or update a learned pattern with confidence score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {"type": "string", "enum": [pt.value for pt in PatternType]},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "content": {"type": "string"},
                    "confidence": {"type": "number", "default": 0.7},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "evidence_sources": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["pattern_type", "name", "content"],
            },
        ),
        Tool(
            name="search_patterns",
            description="Search learned patterns by semantic similarity with confidence filtering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "pattern_types": {"type": "array", "items": {"type": "string"}},
                    "min_confidence": {"type": "number", "default": 0.3},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="apply_pattern",
            description="Record pattern application; updates confidence via decayed Beta(7,3) posterior (success/failure counts) and revives if archived.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_id": {"type": "string"},
                    "success": {"type": "boolean", "default": True},
                    "context": {"type": "string"},
                },
                "required": ["pattern_id"],
            },
        ),
        Tool(
            name="get_pattern",
            description="Retrieve a specific pattern by ID.",
            inputSchema={
                "type": "object",
                "properties": {"pattern_id": {"type": "string"}},
                "required": ["pattern_id"],
            },
        ),
        Tool(
            name="delete_pattern",
            description="Delete a pattern by ID.",
            inputSchema={
                "type": "object",
                "properties": {"pattern_id": {"type": "string"}},
                "required": ["pattern_id"],
            },
        ),
        Tool(
            name="decay_confidence",
            description="Apply temporal decay to all patterns. Patterns below threshold are deleted.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="health_check",
            description="Check Qdrant connection and collection health.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_patterns",
            description=(
                "List/browse pattern CONTENT without a semantic query (scroll-based, "
                "no embedding). Filters: pattern_type, min_confidence (effective), grep "
                "(case-insensitive substring), limit, full (false=300-char preview)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {"type": "string"},
                    "min_confidence": {"type": "number", "default": 0.0},
                    "grep": {"type": "string"},
                    "limit": {"type": "integer", "default": 100},
                    "full": {"type": "boolean", "default": False},
                },
            },
        ),
    ]


@app.call_tool()  # type: ignore  # MCP decorator codes differ across mypy versions
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        handlers = {
            "save_pattern": handle_save_pattern,
            "search_patterns": handle_search_patterns,
            "apply_pattern": handle_apply_pattern,
            "get_pattern": handle_get_pattern,
            "delete_pattern": handle_delete_pattern,
            "decay_confidence": handle_decay_confidence,
            "health_check": handle_health_check,
            "list_patterns": handle_list_patterns,
        }
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return await handler(arguments)
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_save_pattern(args: dict[str, Any]) -> list[TextContent]:
    from qdrant_client.http import models as qmodels

    client = _get_qdrant()
    now = datetime.now()

    # §26 P1.3 write-contract: deterministic content-derived id so re-saving the
    # SAME content is an idempotent no-op (action=dup) rather than a duplicate
    # point — and so a manually-saved pattern collides with the harvested one.
    content_hash = _hash_content(args["content"])
    pattern_id = _content_point_id(content_hash)

    try:
        existing = client.retrieve(collection_name=COLLECTION_NAME, ids=[pattern_id])
    except Exception:
        existing = []
    if existing:
        # Idempotent: the fact is already stored — do NOT overwrite (would reset the
        # accrued succ/fail counts). Report it honestly as a dedup, not a fresh save.
        _record_ingest(
            "learned_patterns",
            "dup",
            content_hash=content_hash,
            pattern_id=pattern_id,
            harvester="save_pattern",
        )
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "success": True,
                        "action": "dup",
                        "pattern_id": pattern_id,
                        "content_hash": content_hash,
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    evidence = []
    for e in args.get("evidence_sources", []):
        evidence.append(EvidenceSource.from_dict(e) if isinstance(e, dict) else e)

    # Confidence is derived from Beta counts (§22.9.1); the advisory `confidence`
    # arg is ignored here — counts grow via apply_pattern, not via save_pattern.
    pattern = LearnedPattern(
        pattern_id=pattern_id,
        pattern_type=PatternType(args["pattern_type"]),
        name=args["name"],
        description=args.get("description", ""),
        content=args["content"],
        confidence=derive_confidence(0.0, 0.0),  # = 0.70 (Beta prior mean)
        succ=0.0,
        fail=0.0,
        last_decay_at=now,
        evidence_sources=evidence,
        created_at=now,
        updated_at=now,
        tags=args.get("tags", []),
    )

    embed_text = f"{pattern.name}: {pattern.content}"
    vector = await _get_embedding(embed_text)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            qmodels.PointStruct(id=pattern_id, vector=vector, payload=_pattern_to_payload(pattern))
        ],
    )

    _bump_epoch()  # §24: new/updated pattern -> invalidate surfacing cache
    _log_lifecycle("save", pattern_id=pattern_id, confidence=round(float(pattern.confidence), 4))
    _record_ingest(
        "learned_patterns",
        "saved",
        content_hash=content_hash,
        pattern_id=pattern_id,
        harvester="save_pattern",
    )
    logger.info(f"Saved pattern {pattern_id}: {pattern.name} (confidence={pattern.confidence})")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "action": "saved",
                    "pattern_id": pattern_id,
                    "name": pattern.name,
                    "confidence": pattern.confidence,
                    "content_hash": content_hash,
                },
                ensure_ascii=False,
            ),
        )
    ]


def search_pattern_points(
    client: Any,
    vector: list[float],
    *,
    min_confidence: float = 0.3,
    limit: int = 10,
    pattern_types: list[str] | None = None,
) -> tuple[list[PatternSearchResult], int]:
    """Semantic search over ``learned_patterns`` — THE retrieval policy for this collection.

    Exported, not private, on purpose (roadmap 260716 M4/P1.4): the unified_search
    vector arm used to re-implement this query and drifted away from it — it prefiltered
    on the STORED confidence and never excluded archived points, so `unified_search`
    surfaced patterns that `search_patterns` deliberately hid. Two readers of one
    collection with two policies is the defect; a shared function is the fix, and a
    tuned filter here would only have postponed the next divergence.

    Policy, in order:
      * NO server-side `confidence` Range prefilter. With count-based decay the
        effective confidence drifts toward the prior 0.70, so it can be HIGHER than the
        stored value for fail-heavy idle patterns — a stored-confidence prefilter is
        not a safe superset of the effective threshold and would silently drop valid
        results. Client-side effective filtering (below) is authoritative.
      * over-fetch (limit×5, floor 50) to survive that client-side filtering;
      * §24.2.4 hard-exclude archived (`expired_at`), unless MEMORY_INCLUDE_ARCHIVED=1;
      * per-item isolation (P0.2): an unreadable point costs that point, not the caller.

    Returns:
        ``(results sorted by combined_score desc and truncated to *limit*, skipped)``.
        ``skipped`` > 0 means the collection holds points this build cannot read.
    """
    from qdrant_client.http import models as qmodels

    conditions: list[Any] = []
    if pattern_types:
        conditions.append(
            qmodels.FieldCondition(key="pattern_type", match=qmodels.MatchAny(any=pattern_types))
        )

    fetch_limit = max(limit * 5, 50)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=qmodels.Filter(must=conditions) if conditions else None,
        limit=fetch_limit,
        with_payload=True,
    )

    search_results: list[PatternSearchResult] = []
    skipped = 0
    include_archived = os.getenv("MEMORY_INCLUDE_ARCHIVED") == "1"
    for point in results.points:
        # Per-item isolation (roadmap 260716 P0.2): one unreadable point must cost
        # exactly that point, not the whole response. Before this, a single drifted
        # payload raised here and the caller (incl. the unified_search vector arm)
        # saw a total failure — the 2026-07-16 incident.
        try:
            payload = point.payload or {}
            eff = payload_effective_confidence(payload)
            if eff < min_confidence:
                continue
            if payload.get("expired_at") and not include_archived:
                continue
            pattern = _pattern_from_payload(str(point.id), payload)
            similarity = point.score if point.score else 0.0
            search_results.append(
                PatternSearchResult(
                    pattern=pattern,
                    similarity_score=similarity,
                    adjusted_confidence=eff,
                    combined_score=similarity * eff,
                )
            )
        except Exception as exc:
            skipped += 1
            logger.warning(f"search_patterns: skipped unreadable point {point.id}: {exc}")

    search_results.sort(key=lambda r: r.combined_score, reverse=True)
    return (search_results[:limit], skipped)


async def handle_search_patterns(args: dict[str, Any]) -> list[TextContent]:
    client = _get_qdrant()
    query = args["query"]
    vector = await _get_embedding(query)

    search_results, skipped = search_pattern_points(
        client,
        vector,
        min_confidence=args.get("min_confidence", 0.3),
        limit=args.get("limit", 10),
        pattern_types=args.get("pattern_types"),
    )
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "query": query,
                    "count": len(search_results),
                    # Additive, honest: non-zero means the collection holds points
                    # this build cannot read (see logs for ids).
                    "items_skipped": skipped,
                    "results": [r.to_dict() for r in search_results],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


async def handle_apply_pattern(args: dict[str, Any]) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    success = args.get("success", True)

    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[pattern_id], with_payload=True)
    if not points:
        return [
            TextContent(
                type="text", text=json.dumps({"success": False, "error": "Pattern not found"})
            )
        ]

    payload = points[0].payload or {}
    # Coerced, not raw (roadmap 260716 M5): a null/string `confidence` used to raise
    # in the round()/f-string below — AFTER set_payload had already mutated the
    # point, so the caller saw an error for a write that actually landed and the
    # lifecycle record was lost.
    old_confidence = coerce_float(payload.get("confidence"), 0.5)

    updates = apply_to_payload(payload, success, datetime.now())
    client.set_payload(collection_name=COLLECTION_NAME, payload=updates, points=[pattern_id])
    _bump_epoch()  # §24: confidence changed -> invalidate surfacing cache
    _log_lifecycle(
        "apply",
        pattern_id=pattern_id,
        success=success,
        old_confidence=round(float(old_confidence), 4),
        new_confidence=round(float(updates["confidence"]), 4),
        application_count=updates.get("application_count"),
    )

    # §27 cascade: propagate the confidence delta to directly-linked neighbour patterns.
    cascade = _cascade_confidence(client, pattern_id, success, datetime.now())

    logger.info(
        f"Applied pattern {pattern_id}: {old_confidence:.3f} -> {updates['confidence']:.3f}"
    )
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "pattern_id": pattern_id,
                    "old_confidence": old_confidence,
                    "new_confidence": updates["confidence"],
                    "application_count": updates["application_count"],
                    "cascaded": cascade["entities_updated"],
                    # Honest partial result, as decay_confidence already reports:
                    # neighbours the cascade could not read are skipped, and the MCP
                    # client must see that — not just the server log.
                    "cascade_errors": cascade.get("errors", 0),
                }
            ),
        )
    ]


async def handle_get_pattern(args: dict[str, Any]) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[pattern_id], with_payload=True)
    if not points:
        return [
            TextContent(
                type="text", text=json.dumps({"success": False, "error": "Pattern not found"})
            )
        ]
    pattern = _pattern_from_payload(str(points[0].id), points[0].payload)
    eff = payload_effective_confidence(points[0].payload or {})
    archived = bool((points[0].payload or {}).get("expired_at"))
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "pattern": pattern.to_dict(),
                    "effective_confidence": eff,
                    "archived": archived,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


async def handle_delete_pattern(args: dict[str, Any]) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    client.delete(collection_name=COLLECTION_NAME, points_selector=[pattern_id])
    _bump_epoch()  # §24: pattern removed -> invalidate surfacing cache
    _log_lifecycle("delete", pattern_id=pattern_id)
    logger.info(f"Deleted pattern {pattern_id}")
    return [TextContent(type="text", text=json.dumps({"success": True, "pattern_id": pattern_id}))]


async def handle_list_patterns(args: dict[str, Any]) -> list[TextContent]:
    """Browse pattern content without a semantic query (scroll + filters, no embedding).

    Read-only listing for inspection: filter by pattern_type / effective min_confidence /
    grep substring; content is preview-truncated unless ``full=true``. No TEI roundtrip,
    so it is not subject to the embedding-provider cold-start that gates search_patterns.
    """
    client = _get_qdrant()
    type_filter = args.get("pattern_type")
    min_conf = float(args.get("min_confidence", 0.0) or 0.0)
    grep = (args.get("grep") or "").lower()
    limit = int(args.get("limit", 100) or 100)
    full = bool(args.get("full", False))

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=max(limit, 1000),
        with_payload=True,
        with_vectors=False,
    )
    rows = []
    skipped = 0
    for p in points:
        # Per-item isolation (P0.2). This is the diagnostic browse tool: it must
        # survive exactly the points an operator opens it to find.
        try:
            pl = p.payload or {}
            content = pl.get("content") or pl.get("description") or ""
            ptype = pl.get("pattern_type") or pl.get("category") or "?"
            if type_filter and ptype != type_filter:
                continue
            if grep and grep not in content.lower():
                continue
            eff = payload_effective_confidence(pl)
            if min_conf > 0.0 and eff < min_conf:
                continue
            rows.append(
                {
                    "pattern_id": str(p.id),
                    # Raw stored value on purpose — this view exists to SHOW drift;
                    # `canonical` is what every reader resolves it to.
                    "pattern_type": ptype,
                    "canonical_type": PatternType.coerce(pl.get("pattern_type")).value,
                    "effective_confidence": round(eff, 4),
                    "application_count": pl.get("application_count"),
                    "created_at": pl.get("created_at", ""),
                    "archived": bool(pl.get("expired_at")),
                    "content": content if full else content[:300],
                }
            )
        except Exception as exc:
            skipped += 1
            logger.warning(f"list_patterns: skipped unreadable point {p.id}: {exc}")
    rows.sort(key=lambda r: str(r["created_at"]))
    rows = rows[:limit]
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "count": len(rows),
                    "collection": COLLECTION_NAME,
                    "items_skipped": skipped,
                    "patterns": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


async def handle_decay_confidence(args: dict[str, Any]) -> list[TextContent]:
    """Apply temporal decay: confidence * exp(-decay_rate * days/30).

    # Note: hard-delete removed — Graphiti invalidate-not-delete, §22 P3.
    # Patterns below MIN_CONFIDENCE are archived (expired_at set) rather than
    # deleted.  Any subsequent apply() call revives them (clears expired_at).
    """
    client = _get_qdrant()
    decayed = 0
    archived = 0  # renamed from deleted — patterns are never hard-deleted here
    revived = (
        0  # previously-archived patterns recovered by decay sweeping counts back above thresholds
    )
    errors = 0  # points the sweep could not read/write — skipped, never fatal (P0.2)

    offset = None
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        points, next_offset = result

        for point in points:
            # Per-item isolation (roadmap 260716 P0.2). This loop MUTATES: an
            # exception mid-sweep used to abort the whole pass, leaving the
            # collection half-decayed (points before the bad one written, the rest
            # untouched) with no epoch bump. One bad point now costs one point.
            try:
                payload = point.payload or {}

                # Resolve last_decay_at — prefer explicit field, fall back to updated_at.
                last_decay_at = coerce_dt(payload.get("last_decay_at")) or coerce_dt(
                    payload.get("updated_at")
                )
                if last_decay_at is None:
                    continue

                now = datetime.now()
                days_since = (now - last_decay_at).total_seconds() / 86400
                if days_since < 1:
                    continue

                decay_rate = stability_adjusted_rate(
                    coerce_float(payload.get("decay_rate"), DECAY_RATE),
                    coerce_int(payload.get("application_count"), 0),
                )

                # Resolve succ/fail — lazy migration for legacy points without the fields.
                raw_succ = payload.get("succ")
                raw_fail = payload.get("fail")
                if raw_succ is None or raw_fail is None:
                    succ, fail = seed_counts_from_legacy(
                        coerce_float(payload.get("confidence"), LEGACY_SEED_CONFIDENCE),
                        coerce_int(payload.get("application_count"), 0),
                    )
                else:
                    succ = coerce_float(raw_succ, 0.0)
                    fail = coerce_float(raw_fail, 0.0)

                succ, fail = decay_counts(succ, fail, last_decay_at, now, decay_rate)
                new_conf = derive_confidence(succ, fail)

                # Build post-decay payload fields.
                set_fields: dict[str, Any] = {
                    "succ": succ,
                    "fail": fail,
                    "last_decay_at": now.isoformat(),
                    "confidence": new_conf,
                    "updated_at": now.isoformat(),
                }

                # Determine archival: merge post-decay fields over original payload and
                # evaluate should_archive (§22 P3 invalidate-not-delete).
                # The sweep manages archival state in BOTH directions:
                #   • should_archive=True  → set expired_at (archive)
                #   • should_archive=False AND was archived → clear expired_at (un-archive)
                #   • otherwise           → leave expired_at untouched
                candidate = {**payload, **set_fields}
                if should_archive(candidate, now):
                    set_fields["expired_at"] = now.isoformat()
                    archived += 1
                    logger.debug(
                        f"Archived pattern {point.id} "
                        f"(type={payload.get('pattern_type', '?')}, "
                        f"conf={new_conf:.3f})"
                    )
                elif payload.get("expired_at"):
                    # Pattern was archived but counts have decayed back above thresholds
                    # (e.g. fail-counts decayed → effective confidence recovered).
                    set_fields["expired_at"] = None
                    revived += 1
                    logger.debug(
                        f"Un-archived pattern {point.id} "
                        f"(type={payload.get('pattern_type', '?')}, "
                        f"conf={new_conf:.3f})"
                    )

                client.set_payload(
                    collection_name=COLLECTION_NAME,
                    payload=set_fields,
                    points=[str(point.id)],
                )
                decayed += 1
            except Exception as exc:
                errors += 1
                logger.warning(f"decay_confidence: skipped point {point.id}: {exc}")

        if next_offset is None:
            break
        offset = next_offset

    if decayed or archived or revived:
        _bump_epoch()  # §24: confidence/archive state changed -> invalidate surfacing cache
        _log_lifecycle(
            "decay_sweep", decayed=decayed, archived=archived, revived=revived, errors=errors
        )
    logger.info(
        f"Decay complete: {decayed} decayed, {archived} archived, "
        f"{revived} revived, {errors} skipped"
    )
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "decayed": decayed,
                    "archived": archived,
                    "revived": revived,
                    # Honest partial result: the sweep completed, these points did not.
                    "errors": errors,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        )
    ]


async def handle_health_check(args: dict[str, Any]) -> list[TextContent]:
    health: dict[str, Any] = {"qdrant": False, "collection": False, "count": 0}
    try:
        client = _get_qdrant()
        collections = [c.name for c in client.get_collections().collections]
        health["qdrant"] = True
        health["collection"] = COLLECTION_NAME in collections
        if health["collection"]:
            info = client.get_collection(COLLECTION_NAME)
            health["count"] = info.points_count
    except Exception as e:
        health["error"] = str(e)

    return [TextContent(type="text", text=json.dumps(health, indent=2))]


async def main() -> None:
    logger.info("Starting Vector-Memory MCP Server...")
    # §22/#2: stamp the lifecycle trace at process start so the log shows when the
    # MCP code actually (re)loaded -- makes the "/mcp reconnect needed" caveat
    # observable instead of silent. pid distinguishes pre/post-reconnect processes.
    _log_lifecycle("server_start", pid=os.getpid(), collection=COLLECTION_NAME)
    if os.environ.get("MEMORY_VECTOR_NO_WARMUP") != "1":
        threading.Thread(target=_warmup_qdrant, name="qdrant-warmup", daemon=True).start()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
