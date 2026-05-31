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
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

from .confidence import (
    apply_to_payload,
    decay_counts,
    derive_confidence,
    payload_effective_confidence,
    seed_counts_from_legacy,
    should_archive,
    stability_adjusted_rate,
)
from .epoch import bump as _bump_epoch  # §24: surfacing-cache invalidation signal
from .models import (
    EvidenceSource,
    LearnedPattern,
    PatternSearchResult,
    PatternType,
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
# `_embedding_fn` is either the sentinel string "async" (use _embedding_provider)
# or a callable producing pseudo-embeddings (offline opt-in hash fallback).
_embedding_fn: str | Callable[[list[str]], list[list[float]]] | None = None
_embedding_provider: Any | None = None  # async E5 engine (if available)


def _get_qdrant() -> Any:
    """Lazy-init Qdrant client. Uses shared Qdrant at localhost:6333."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        _qdrant_client = QdrantClient(
            url=QDRANT_URL,
            grpc_port=6334,
            prefer_grpc=True,
        )
        _ensure_collection()
    return _qdrant_client


def _ensure_collection() -> None:
    """Ensure learned_patterns collection exists with cosine 1024d vectors."""
    from qdrant_client.http import models as qmodels

    client = _qdrant_client
    assert client is not None, "_ensure_collection called before _get_qdrant init"
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
            logger.info("Using project embedding provider (E5 1024d)")
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


def _pattern_from_payload(point_id: str, payload: dict[str, Any]) -> LearnedPattern:
    """Convert Qdrant point payload to LearnedPattern."""
    evidence = [EvidenceSource.from_dict(e) for e in payload.get("evidence_sources", [])]

    # Lazy migration: seed succ/fail from legacy confidence + application_count
    # when the new fields are absent (points written before P0 migration).
    raw_succ = payload.get("succ")
    raw_fail = payload.get("fail")
    if raw_succ is None or raw_fail is None:
        succ, fail = seed_counts_from_legacy(
            payload.get("confidence", 0.7),
            payload.get("application_count", 0),
        )
    else:
        succ = float(raw_succ)
        fail = float(raw_fail)

    # last_decay_at: prefer explicit field, fall back through timestamp chain.
    raw_lda = payload.get("last_decay_at")
    if raw_lda:
        last_decay_at: datetime | None = datetime.fromisoformat(raw_lda)
    elif payload.get("last_applied"):
        last_decay_at = datetime.fromisoformat(payload["last_applied"])
    elif payload.get("updated_at"):
        last_decay_at = datetime.fromisoformat(payload["updated_at"])
    elif payload.get("created_at"):
        last_decay_at = datetime.fromisoformat(payload["created_at"])
    else:
        last_decay_at = None

    return LearnedPattern(
        pattern_id=payload.get("pattern_id", point_id),
        pattern_type=PatternType(payload.get("pattern_type", "code-convention")),
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        content=payload.get("content", ""),
        confidence=payload.get("confidence", 0.5),
        evidence_sources=evidence,
        created_at=datetime.fromisoformat(payload["created_at"])
        if payload.get("created_at")
        else datetime.now(),
        updated_at=datetime.fromisoformat(payload["updated_at"])
        if payload.get("updated_at")
        else datetime.now(),
        decay_rate=payload.get("decay_rate", DECAY_RATE),
        application_count=payload.get("application_count", 0),
        last_applied=datetime.fromisoformat(payload["last_applied"])
        if payload.get("last_applied")
        else None,
        succ=succ,
        fail=fail,
        last_decay_at=last_decay_at,
        version=payload.get("version", 1),
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
    pattern_id = str(uuid.uuid4())
    now = datetime.now()

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
    logger.info(f"Saved pattern {pattern_id}: {pattern.name} (confidence={pattern.confidence})")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "pattern_id": pattern_id,
                    "name": pattern.name,
                    "confidence": pattern.confidence,
                },
                ensure_ascii=False,
            ),
        )
    ]


async def handle_search_patterns(args: dict[str, Any]) -> list[TextContent]:
    from qdrant_client.http import models as qmodels

    client = _get_qdrant()
    query = args["query"]
    min_confidence = args.get("min_confidence", 0.3)
    limit = args.get("limit", 10)

    vector = await _get_embedding(query)

    # NOTE: The server-side `confidence` Range prefilter is intentionally
    # omitted here.  With count-based decay, effective confidence drifts
    # toward the prior 0.70, so it can be HIGHER than the stored value for
    # fail-heavy idle patterns.  A stored-confidence prefilter is therefore
    # NOT a safe superset for the effective-confidence threshold and would
    # silently discard valid results.  Client-side filtering on effective
    # confidence (below) is authoritative.
    conditions: list[Any] = []
    pattern_types = args.get("pattern_types")
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

    search_results = []
    for point in results.points:
        eff = payload_effective_confidence(point.payload or {})
        if eff < min_confidence:
            continue
        pattern = _pattern_from_payload(str(point.id), point.payload)
        similarity = point.score if point.score else 0.0
        combined = similarity * eff
        # §24.2.4 hard-exclude archived patterns (consistency with hook-side gate).
        # Use MEMORY_INCLUDE_ARCHIVED=1 to override (e.g. for revive workflows).
        if (point.payload or {}).get("expired_at") and os.getenv("MEMORY_INCLUDE_ARCHIVED") != "1":
            continue
        search_results.append(
            PatternSearchResult(
                pattern=pattern,
                similarity_score=similarity,
                adjusted_confidence=eff,
                combined_score=combined,
            )
        )

    search_results.sort(key=lambda r: r.combined_score, reverse=True)
    search_results = search_results[:limit]
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "query": query,
                    "count": len(search_results),
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
    old_confidence = payload.get("confidence", 0.5)

    updates = apply_to_payload(payload, success, datetime.now())
    client.set_payload(collection_name=COLLECTION_NAME, payload=updates, points=[pattern_id])
    _bump_epoch()  # §24: confidence changed -> invalidate surfacing cache

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
    logger.info(f"Deleted pattern {pattern_id}")
    return [TextContent(type="text", text=json.dumps({"success": True, "pattern_id": pattern_id}))]


async def handle_decay_confidence(args: dict[str, Any]) -> list[TextContent]:
    """Apply temporal decay: confidence * exp(-decay_rate * days/30).

    # Note: hard-delete removed — Graphiti invalidate-not-delete, §22 P3.
    # Patterns below MIN_CONFIDENCE are archived (expired_at set) rather than
    # deleted.  Any subsequent apply() call revives them (clears expired_at).
    """
    client = _get_qdrant()
    decayed = 0
    archived = 0  # renamed from deleted — patterns are never hard-deleted here
    revived = 0   # previously-archived patterns recovered by decay sweeping counts back above thresholds

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
            payload = point.payload

            # Resolve last_decay_at — prefer explicit field, fall back to updated_at.
            raw_lda = payload.get("last_decay_at") or payload.get("updated_at")
            if not raw_lda:
                continue
            last_decay_at: datetime = datetime.fromisoformat(raw_lda)

            now = datetime.now()
            days_since = (now - last_decay_at).total_seconds() / 86400
            if days_since < 1:
                continue

            decay_rate = stability_adjusted_rate(
                float(payload.get("decay_rate", DECAY_RATE)),
                int(payload.get("application_count", 0)),
            )

            # Resolve succ/fail — lazy migration for legacy points without the fields.
            raw_succ = payload.get("succ")
            raw_fail = payload.get("fail")
            if raw_succ is None or raw_fail is None:
                succ, fail = seed_counts_from_legacy(
                    payload.get("confidence", 0.5),
                    payload.get("application_count", 0),
                )
            else:
                succ = float(raw_succ)
                fail = float(raw_fail)

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

        if next_offset is None:
            break
        offset = next_offset

    if decayed or archived or revived:
        _bump_epoch()  # §24: confidence/archive state changed -> invalidate surfacing cache
    logger.info(f"Decay complete: {decayed} decayed, {archived} archived, {revived} revived")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "decayed": decayed,
                    "archived": archived,
                    "revived": revived,
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
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
