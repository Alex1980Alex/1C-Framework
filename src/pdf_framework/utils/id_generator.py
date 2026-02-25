"""Deterministic ID generation for documents and chunks.

Replaces uuid4()-based IDs with SHA-256 hashes so that the same input
always produces the same ID.  This is critical for:
  - Qdrant upsert idempotency (same chunk_id → same UUID5 → overwrite)
  - Resumable indexing (checkpoint can match already-stored chunks)
  - Incremental indexing delta computation (stable IDs for comparison)
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def generate_document_id(file_path: str) -> str:
    """Deterministic document ID from absolute file path.

    Uses SHA-256 of the resolved (absolute) path.
    Returns 16-char hex string (same length as old ``uuid4().hex[:16]``).
    """
    resolved = str(Path(file_path).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def generate_chunk_id(
    document_id: str,
    chunk_index: int | str,
    content_prefix: str,
) -> str:
    """Deterministic chunk ID from document ID, index, and content prefix.

    Args:
        document_id: Parent document ID (16-char hex).
        chunk_index: Integer index or string label
            (e.g. ``0``, ``"parent_3"``, ``"child_2_5"``).
        content_prefix: First 100 characters of chunk content
            (for collision avoidance when index is the same but text differs).

    Returns:
        16-char hex string.

    Example:
        >>> generate_chunk_id("abc123", 0, "Hello world")
        'e5c1e2f3...'
    """
    raw = f"{document_id}:{chunk_index}:{content_prefix[:100]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
