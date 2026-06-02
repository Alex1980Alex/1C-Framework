"""Canonical content-hash for cross-store dedup & idempotency (§26 P0).

Single source of truth for the dedup key shared across every memory store.
Reuses the exact algorithm already used by ``scripts/dedupe_learned_patterns.py``
(``sha256(content)[:16]``) so the same fact hashes identically whether it lives
in learned_patterns (Qdrant), memory-ai (SQLite), skill-learning (JSONL) or wiki.

Roadmap: ``docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md`` (§26 P0, D0.1).

Why a dedicated module instead of importing from the script:
  - ``src/`` code must not import from ``scripts/`` (not a package, path-hacky).
  - The script now delegates here, so there is exactly one implementation.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Number of hex chars kept from the sha256 digest. 16 hex = 64 bits — collision
# probability is negligible at our scale (thousands of patterns) and the short
# key is convenient as a Qdrant payload filter value. Matches the historical
# dedupe key width; DO NOT change without a migration (re-stamps every store).
HASH_WIDTH = 16


def content_text(payload: dict[str, Any]) -> str:
    """Extract the canonical content string from a store payload.

    Prefers ``content`` then falls back to ``description`` — the two fields that
    carry the human-meaningful text across our payload schemas.
    """
    return payload.get("content") or payload.get("description") or ""


def hash_content(text: str) -> str:
    """Hash a raw content string -> shared idempotency key.

    ``errors="replace"`` keeps this total over arbitrary input (Cyrillic, broken
    surrogates) so it never raises on the hot path.
    """
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:HASH_WIDTH]


def content_key(payload: dict[str, Any]) -> str:
    """Idempotency key for a store payload dict (content/description aware)."""
    return hash_content(content_text(payload))


__all__ = ["HASH_WIDTH", "content_key", "content_text", "hash_content"]
