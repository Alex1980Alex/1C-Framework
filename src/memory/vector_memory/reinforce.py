"""Thin Qdrant wrapper around apply_to_payload for pattern reinforcement.

Provides a fail-soft reinforce_pattern() function that retrieves a Qdrant
point, applies the Beta-posterior confidence update, and writes back the
updated payload fields. All Qdrant I/O is isolated here; the math lives in
confidence.py.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from .confidence import apply_to_payload


def reinforce_pattern(
    pattern_id: str,
    success: bool,
    *,
    client: Any = None,
    collection: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply a success/failure observation to a stored pattern's confidence.

    Retrieves the Qdrant point identified by *pattern_id*, computes updated
    Beta-posterior confidence via :func:`apply_to_payload`, and writes the
    updates back with ``set_payload``.  All errors are caught and returned as
    a structured failure dict so callers can proceed without crashing.

    Args:
        pattern_id: Qdrant point ID of the pattern to update.
        success: True = positive outcome observed; False = negative outcome.
        client: Pre-constructed QdrantClient instance.  When *None* a new
            client is built from ``QDRANT_HOST`` / ``QDRANT_PORT`` env vars
            (defaults: ``127.0.0.1`` / ``6333``), timeout 2 s.
        collection: Qdrant collection name.  Defaults to the
            ``LEARNING_COLLECTION_NAME`` env var or ``"learned_patterns"``.
        now: Datetime reference for decay/timestamp fields.  Defaults to
            :func:`datetime.now`.

    Returns:
        On success::

            {"success": True, "pattern_id": ..., "old_confidence": ...,
             "new_confidence": ..., "application_count": ...}

        On failure (pattern not found or any exception)::

            {"success": False, "error": "...", "pattern_id": ...}
    """
    collection = collection or os.getenv("LEARNING_COLLECTION_NAME", "learned_patterns")
    now = now or datetime.now()

    if client is None:
        from qdrant_client import QdrantClient  # lazy import — optional dep

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "127.0.0.1"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            timeout=2,
        )

    try:
        points = client.retrieve(
            collection_name=collection,
            ids=[pattern_id],
            with_payload=True,
        )
        if not points:
            return {
                "success": False,
                "error": "pattern not found",
                "pattern_id": pattern_id,
            }

        payload: dict[str, Any] = points[0].payload or {}
        updates = apply_to_payload(payload, success, now)

        client.set_payload(
            collection_name=collection,
            payload=updates,
            points=[pattern_id],
        )

        # §24: confidence mutated in Qdrant -> invalidate the surfacing cache.
        try:
            from .epoch import bump as _bump_epoch

            _bump_epoch()
        except Exception:  # noqa: BLE001
            pass

        return {
            "success": True,
            "pattern_id": pattern_id,
            "old_confidence": payload.get("confidence", 0.5),
            "new_confidence": updates["confidence"],
            "application_count": updates["application_count"],
        }

    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "pattern_id": pattern_id,
        }
