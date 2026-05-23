"""Shared semantic search utilities for Claude Code hooks.

Provides fast, timeout-bounded vector search over skill_library and
experience_bank Qdrant collections using Ollama embeddings.
All functions fail gracefully (return empty/None) so hooks never block.
"""

import json
import os
import urllib.request


def _is_disabled() -> bool:
    return os.environ.get("SKILL_ROUTER_SEMANTIC_DISABLED") == "1"


def embed_query_ollama(
    text: str, model: str = "nomic-embed-text", timeout: float = 0.4
) -> list[float] | None:
    """Embed text via Ollama HTTP API. Returns 768-dim vector or None on error."""
    if _is_disabled():
        return None

    try:
        payload = json.dumps({"model": model, "prompt": text[:4000]}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("embedding")
    except Exception:
        return None


def search_qdrant_semantic(
    collection: str,
    embedding: list[float],
    limit: int = 3,
    timeout: float = 0.3,
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
        embed = embed_query_ollama(query, timeout=total_timeout * 0.6)
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
    query: str, limit: int = 5, total_timeout: float = 0.5
) -> list[dict]:
    """Search experience_bank collection.

    Returns list of {experience_id, score, insight, matched_by}.
    """
    if _is_disabled():
        return []

    try:
        embed = embed_query_ollama(query, timeout=total_timeout * 0.6)
        if not embed:
            return []

        results = search_qdrant_semantic(
            "experience_bank", embed, limit, timeout=total_timeout * 0.4
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
