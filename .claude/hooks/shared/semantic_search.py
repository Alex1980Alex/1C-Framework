"""Shared semantic search utilities for Claude Code hooks.

Provides fast, timeout-bounded vector search over Qdrant collections
(skill_library, learned_patterns, ...) via TEI HTTP backend (Phase 9.1
alignment with main retrieval stack — Qwen3-Embedding-8B 4096d).

All functions fail gracefully (return empty/None) so hooks never block.

Note (2026-06-03, §26 Q1 ADR): experience_embeddings / conversation_memory
were deprecated/dropped. ``search_experiences_semantic`` is retained for the
existing test but is no longer wired into surfacing; it fail-soft returns []
now that the collection is gone.

Migration (2026-04-30, Phase 9.1):
  - Ollama nomic-embed-text 768d -> TEI Qwen3-Embedding-8B 4096d
  - search_experiences_semantic: bug fix collection name 'experience_bank' -> 'experience_embeddings'
  - Default timeout bumped 0.4s -> 1.5s (TEI cold ~600ms first call, ~80ms warm)
"""

import json
import os
import urllib.request

# TEI configuration (matches src/framework_search/embedder.py defaults).
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)


def _is_disabled() -> bool:
    return os.environ.get("SKILL_ROUTER_SEMANTIC_DISABLED") == "1"


def embed_query_tei(text: str, timeout: float = 1.5) -> list[float] | None:
    """Embed text via TEI HTTP /embed. Returns 4096-dim Qwen3 vector or None on error.

    Prepends QUERY_INSTRUCTION (default web-retrieval template — Qwen3 calibration
    requires this prefix; deviations break alignment, see roadmap §21.10 H1 ablation).
    Truncates input to 8000 chars to stay under TEI MAX_INPUT_LENGTH=4096 tokens.
    """
    if _is_disabled():
        return None

    try:
        body = QUERY_INSTRUCTION + text[:8000]
        payload = json.dumps(
            {
                "inputs": [body],
                "normalize": True,
                "truncate": True,
                "truncation_direction": "Right",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            TEI_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # TEI returns either [[...]] or {"embeddings": [[...]]}
            if isinstance(data, list) and data and isinstance(data[0], list):
                return data[0]
            if isinstance(data, dict) and "embeddings" in data:
                vecs = data["embeddings"]
                if vecs and isinstance(vecs[0], list):
                    return vecs[0]
            return None
    except Exception:
        return None


# Backwards-compat alias — older hook code may import embed_query_ollama by name.
embed_query_ollama = embed_query_tei


def search_qdrant_semantic(
    collection: str,
    embedding: list[float],
    limit: int = 3,
    timeout: float = 0.5,
) -> list[dict]:
    """Search Qdrant collection by vector. Returns list of {id, score, payload}."""
    if _is_disabled():
        return []

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="127.0.0.1", port=6333, timeout=max(1, int(timeout)))
        response = client.query_points(
            collection_name=collection,
            query=embedding,
            limit=limit,
            with_payload=True,
        )
        results = []
        for point in response.points:
            results.append(
                {
                    "id": str(point.id),
                    "score": point.score,
                    "payload": point.payload or {},
                }
            )
        return results
    except Exception:
        return []


def search_skills_semantic(query: str, limit: int = 3, total_timeout: float = 0.5) -> list[dict]:
    """High-level: embed query + search skill_library collection.

    Returns list of {skill_name, score, description, matched_by: "semantic"}.
    """
    if _is_disabled():
        return []

    try:
        embed = embed_query_tei(query, timeout=total_timeout * 0.7)
        if not embed:
            return []

        results = search_qdrant_semantic("skill_library", embed, limit, timeout=total_timeout * 0.4)

        formatted = []
        for result in results:
            payload = result.get("payload", {})
            formatted.append(
                {
                    "skill_name": payload.get("skill_name", payload.get("name", "")),
                    "score": result.get("score", 0.0),
                    "description": payload.get("description", ""),
                    "matched_by": "semantic",
                }
            )
        return formatted
    except Exception:
        return []


def search_experiences_semantic(
    query: str, limit: int = 5, total_timeout: float = 2.0
) -> list[dict]:
    """Search experience_embeddings collection.

    Bug fix 2026-04-30: was querying 'experience_bank' (does not exist);
    actual collection is 'experience_embeddings'.

    Returns list of {experience_id, score, insight, matched_by}.
    """
    if _is_disabled():
        return []

    try:
        embed = embed_query_tei(query, timeout=total_timeout * 0.7)
        if not embed:
            return []

        results = search_qdrant_semantic(
            "experience_embeddings", embed, limit, timeout=total_timeout * 0.3
        )

        formatted = []
        for result in results:
            payload = result.get("payload", {})
            exp_id = payload.get("experience_id", str(result.get("id", "")))
            formatted.append(
                {
                    "experience_id": exp_id,
                    "score": result.get("score", 0.0),
                    "insight": payload.get("insight", ""),
                    "matched_by": "semantic",
                }
            )
        return formatted
    except Exception:
        return []
