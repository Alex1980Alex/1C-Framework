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
import math
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp import stdio_server
from mcp.types import Tool, TextContent

from .models import (
    LearnedPattern,
    PatternType,
    EvidenceSource,
    PatternSearchResult,
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
VECTOR_SIZE = 1024  # multilingual-e5-large (project standard)
DECAY_RATE = float(os.getenv("LEARNING_DECAY_RATE", "0.05"))
MIN_CONFIDENCE = float(os.getenv("LEARNING_MIN_CONFIDENCE", "0.3"))

# Lazy-initialized clients
_qdrant_client = None
_embedding_fn = None


def _get_qdrant():
    """Lazy-init Qdrant client. Uses shared Qdrant at localhost:6333."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        _qdrant_client = QdrantClient(url=QDRANT_URL)
        _ensure_collection()
    return _qdrant_client


def _ensure_collection():
    """Ensure learned_patterns collection exists with cosine 1024d vectors."""
    from qdrant_client.http import models as qmodels
    client = _qdrant_client
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


async def _get_embedding(text: str) -> List[float]:
    """Get embedding using project's embedding provider or hash fallback."""
    global _embedding_fn
    if _embedding_fn is None:
        try:
            project_root = Path(__file__).parent.parent.parent.parent
            if str(project_root / "src") not in sys.path:
                sys.path.insert(0, str(project_root / "src"))
            from pdf_framework.embeddings import get_embedding_provider
            provider = get_embedding_provider()
            _embedding_fn = provider.embed_texts
            logger.info("Using project embedding provider (E5 1024d)")
        except Exception:
            import hashlib

            def _hash_embed(texts: List[str]) -> List[List[float]]:
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
            logger.warning("Using hash-based fallback embeddings")

    result = await asyncio.to_thread(_embedding_fn, [text])
    return result[0]


def _pattern_from_payload(point_id: str, payload: Dict[str, Any]) -> LearnedPattern:
    """Convert Qdrant point payload to LearnedPattern."""
    evidence = [EvidenceSource.from_dict(e) for e in payload.get("evidence_sources", [])]
    return LearnedPattern(
        pattern_id=payload.get("pattern_id", point_id),
        pattern_type=PatternType(payload.get("pattern_type", "code-convention")),
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        content=payload.get("content", ""),
        confidence=payload.get("confidence", 0.5),
        evidence_sources=evidence,
        created_at=datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else datetime.now(),
        updated_at=datetime.fromisoformat(payload["updated_at"]) if payload.get("updated_at") else datetime.now(),
        decay_rate=payload.get("decay_rate", DECAY_RATE),
        application_count=payload.get("application_count", 0),
        last_applied=datetime.fromisoformat(payload["last_applied"]) if payload.get("last_applied") else None,
        version=payload.get("version", 1),
        tags=payload.get("tags", []),
        metadata=payload.get("metadata", {}),
    )


def _pattern_to_payload(pattern: LearnedPattern) -> Dict[str, Any]:
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
        "decay_rate": pattern.decay_rate,
        "application_count": pattern.application_count,
        "version": pattern.version,
        "tags": pattern.tags,
        "metadata": pattern.metadata,
    }


# ========== MCP Server ==========

app = Server("vector-memory")


@app.list_tools()
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
            description="Record pattern application and update confidence (success +0.02, failure -0.01).",
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


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
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


async def handle_save_pattern(args: dict) -> list[TextContent]:
    from qdrant_client.http import models as qmodels

    client = _get_qdrant()
    pattern_id = str(uuid.uuid4())
    now = datetime.now()

    evidence = []
    for e in args.get("evidence_sources", []):
        evidence.append(EvidenceSource.from_dict(e) if isinstance(e, dict) else e)

    pattern = LearnedPattern(
        pattern_id=pattern_id,
        pattern_type=PatternType(args["pattern_type"]),
        name=args["name"],
        description=args.get("description", ""),
        content=args["content"],
        confidence=args.get("confidence", 0.7),
        evidence_sources=evidence,
        created_at=now,
        updated_at=now,
        tags=args.get("tags", []),
    )

    embed_text = f"{pattern.name}: {pattern.content}"
    vector = await _get_embedding(embed_text)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[qmodels.PointStruct(id=pattern_id, vector=vector, payload=_pattern_to_payload(pattern))],
    )

    logger.info(f"Saved pattern {pattern_id}: {pattern.name} (confidence={pattern.confidence})")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "pattern_id": pattern_id, "name": pattern.name, "confidence": pattern.confidence,
    }, ensure_ascii=False))]


async def handle_search_patterns(args: dict) -> list[TextContent]:
    from qdrant_client.http import models as qmodels

    client = _get_qdrant()
    query = args["query"]
    min_confidence = args.get("min_confidence", 0.3)
    limit = args.get("limit", 10)

    vector = await _get_embedding(query)

    conditions = [qmodels.FieldCondition(key="confidence", range=qmodels.Range(gte=min_confidence))]
    pattern_types = args.get("pattern_types")
    if pattern_types:
        conditions.append(qmodels.FieldCondition(key="pattern_type", match=qmodels.MatchAny(any=pattern_types)))

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=qmodels.Filter(must=conditions),
        limit=limit,
        with_payload=True,
    )

    search_results = []
    for point in results.points:
        pattern = _pattern_from_payload(str(point.id), point.payload)
        similarity = point.score if point.score else 0.0
        search_results.append(PatternSearchResult(
            pattern=pattern, similarity_score=similarity,
            adjusted_confidence=pattern.confidence, combined_score=similarity * pattern.confidence,
        ))

    search_results.sort(key=lambda r: r.combined_score, reverse=True)
    return [TextContent(type="text", text=json.dumps({
        "query": query, "count": len(search_results),
        "results": [r.to_dict() for r in search_results],
    }, ensure_ascii=False, indent=2))]


async def handle_apply_pattern(args: dict) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    success = args.get("success", True)

    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[pattern_id], with_payload=True)
    if not points:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": "Pattern not found"}))]

    payload = points[0].payload
    delta = 0.02 if success else -0.01
    new_confidence = max(0.0, min(1.0, payload.get("confidence", 0.5) + delta))
    new_count = payload.get("application_count", 0) + 1

    client.set_payload(
        collection_name=COLLECTION_NAME,
        payload={
            "confidence": new_confidence,
            "application_count": new_count,
            "last_applied": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        points=[pattern_id],
    )

    logger.info(f"Applied pattern {pattern_id}: {payload.get('confidence', 0.5):.2f} -> {new_confidence:.2f}")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "pattern_id": pattern_id,
        "old_confidence": payload.get("confidence", 0.5),
        "new_confidence": new_confidence, "application_count": new_count,
    }))]


async def handle_get_pattern(args: dict) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    points = client.retrieve(collection_name=COLLECTION_NAME, ids=[pattern_id], with_payload=True)
    if not points:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": "Pattern not found"}))]
    pattern = _pattern_from_payload(str(points[0].id), points[0].payload)
    return [TextContent(type="text", text=json.dumps({"success": True, "pattern": pattern.to_dict()}, ensure_ascii=False, indent=2))]


async def handle_delete_pattern(args: dict) -> list[TextContent]:
    client = _get_qdrant()
    pattern_id = args["pattern_id"]
    client.delete(collection_name=COLLECTION_NAME, points_selector=[pattern_id])
    logger.info(f"Deleted pattern {pattern_id}")
    return [TextContent(type="text", text=json.dumps({"success": True, "pattern_id": pattern_id}))]


async def handle_decay_confidence(args: dict) -> list[TextContent]:
    """Apply temporal decay: confidence * exp(-decay_rate * days/30).
    Patterns below MIN_CONFIDENCE threshold are deleted.
    """
    client = _get_qdrant()
    decayed = 0
    deleted = 0

    offset = None
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME, limit=100, offset=offset, with_payload=True,
        )
        points, next_offset = result

        for point in points:
            payload = point.payload
            updated_at = payload.get("updated_at")
            if not updated_at:
                continue

            days_since = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds() / 86400
            if days_since < 1:
                continue

            decay_rate = payload.get("decay_rate", DECAY_RATE)
            old_conf = payload.get("confidence", 0.5)
            new_conf = old_conf * math.exp(-decay_rate * days_since / 30)

            if new_conf < MIN_CONFIDENCE:
                client.delete(collection_name=COLLECTION_NAME, points_selector=[str(point.id)])
                deleted += 1
            else:
                client.set_payload(
                    collection_name=COLLECTION_NAME,
                    payload={"confidence": new_conf, "updated_at": datetime.now().isoformat()},
                    points=[str(point.id)],
                )
                decayed += 1

        if next_offset is None:
            break
        offset = next_offset

    logger.info(f"Decay complete: {decayed} decayed, {deleted} deleted")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "decayed": decayed, "deleted": deleted, "timestamp": datetime.now().isoformat(),
    }))]


async def handle_health_check(args: dict) -> list[TextContent]:
    health = {"qdrant": False, "collection": False, "count": 0}
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


async def main():
    logger.info("Starting Vector-Memory MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
