"""Phase 17: Semantic Search Cache.

Caches SearchResponse objects keyed by query embedding similarity.
If a new query is >= threshold similar to a cached query with matching
parameters (strategy, k, filter, rerank), returns the cached result.

Storage: SQLite for persistence, in-memory numpy for fast similarity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from src.pdf_framework.schemas.documents import SearchResponse

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS semantic_cache (
    cache_id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding BLOB NOT NULL,
    strategy TEXT NOT NULL,
    k INTEGER NOT NULL,
    filter_hash TEXT NOT NULL,
    rerank INTEGER NOT NULL,
    response_json TEXT NOT NULL,
    document_ids TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_sc_expires ON semantic_cache(expires_at);
"""


class SemanticSearchCache:
    """Semantic similarity cache for search results.

    In-memory numpy matrix for fast dot-product similarity lookup,
    SQLite for persistent storage across restarts.
    """

    def __init__(
        self,
        db_path: str | Path = "data/cache/semantic_cache.db",
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 3600,
        max_entries: int = 5000,
    ) -> None:
        self._db_path = str(db_path)
        self._threshold = similarity_threshold
        self._ttl = ttl_seconds
        self._max_entries = max_entries

        # In-memory index (loaded from SQLite on init)
        self._embeddings: np.ndarray | None = None  # (N, dim) float32
        self._cache_ids: list[str] = []
        self._metadata: dict[str, dict[str, Any]] = {}

        # Stats
        self._hits = 0
        self._misses = 0

        self._initialized = False

    async def initialize(self) -> None:
        """Create table and load existing cache into memory."""
        if self._initialized:
            return

        import asyncio
        await asyncio.to_thread(self._init_sync)
        self._initialized = True

    def _init_sync(self) -> None:
        """Synchronous init: create table + load index."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_INDEX_SQL)
            conn.commit()

            # Cleanup expired entries
            now = time.time()
            conn.execute("DELETE FROM semantic_cache WHERE expires_at < ?", (now,))
            conn.commit()

            # Load into memory
            cursor = conn.execute(
                "SELECT cache_id, query_embedding, strategy, k, filter_hash, rerank "
                "FROM semantic_cache WHERE expires_at >= ? ORDER BY created_at",
                (now,),
            )
            rows = cursor.fetchall()

            if rows:
                embeddings_list = []
                for cache_id, emb_blob, strategy, k, filter_hash, rerank in rows:
                    emb = np.frombuffer(emb_blob, dtype=np.float32)
                    embeddings_list.append(emb)
                    self._cache_ids.append(cache_id)
                    self._metadata[cache_id] = {
                        "strategy": strategy,
                        "k": k,
                        "filter_hash": filter_hash,
                        "rerank": bool(rerank),
                    }
                self._embeddings = np.vstack(embeddings_list)

            logger.info(
                "[SEMANTIC_CACHE] Loaded %d entries from %s",
                len(self._cache_ids), Path(self._db_path).name,
            )
        finally:
            conn.close()

    async def get(
        self,
        query_embedding: list[float],
        strategy: str,
        k: int,
        filter: dict[str, Any] | None,
        rerank: bool,
    ) -> SearchResponse | None:
        """Check cache for semantically similar query with matching params."""
        if not self._initialized:
            await self.initialize()

        if self._embeddings is None or len(self._cache_ids) == 0:
            self._misses += 1
            return None

        query_vec = np.array(query_embedding, dtype=np.float32)
        similarities = self._embeddings @ query_vec  # (N,)

        # Filter by threshold
        candidates = np.where(similarities >= self._threshold)[0]
        if len(candidates) == 0:
            self._misses += 1
            return None

        # Check parameter compatibility
        filter_hash = self._hash_filter(filter)
        best_sim = -1.0
        best_cache_id: str | None = None

        for idx in candidates:
            cache_id = self._cache_ids[idx]
            meta = self._metadata[cache_id]
            if (
                meta["strategy"] == strategy
                and meta["k"] >= k
                and meta["filter_hash"] == filter_hash
                and meta["rerank"] == rerank
            ):
                sim = float(similarities[idx])
                if sim > best_sim:
                    best_sim = sim
                    best_cache_id = cache_id

        if best_cache_id is None:
            self._misses += 1
            return None

        # Load full response from SQLite
        import asyncio
        response = await asyncio.to_thread(self._load_response, best_cache_id)
        if response is None:
            self._misses += 1
            return None

        # Trim to requested k if cached k was larger
        if len(response.results) > k:
            response.results = response.results[:k]
            response.total_found = k

        response.metadata["cache_hit"] = True
        response.metadata["cache_similarity"] = round(best_sim, 4)

        self._hits += 1
        logger.debug(
            "[SEMANTIC_CACHE] HIT (sim=%.4f) for strategy=%s k=%d",
            best_sim, strategy, k,
        )
        return response

    def _load_response(self, cache_id: str) -> SearchResponse | None:
        """Load and deserialize a cached SearchResponse."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute(
                "SELECT response_json FROM semantic_cache WHERE cache_id = ?",
                (cache_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return SearchResponse.model_validate_json(row[0])
        except Exception as e:
            logger.warning("[SEMANTIC_CACHE] Failed to load cache_id=%s: %s", cache_id, e)
            return None
        finally:
            conn.close()

    async def set(
        self,
        query: str,
        query_embedding: list[float],
        strategy: str,
        k: int,
        filter: dict[str, Any] | None,
        rerank: bool,
        response: SearchResponse,
    ) -> None:
        """Store search response in cache."""
        if not self._initialized:
            await self.initialize()

        import asyncio
        await asyncio.to_thread(
            self._set_sync, query, query_embedding, strategy, k, filter, rerank, response,
        )

    def _set_sync(
        self,
        query: str,
        query_embedding: list[float],
        strategy: str,
        k: int,
        filter: dict[str, Any] | None,
        rerank: bool,
        response: SearchResponse,
    ) -> None:
        """Synchronous cache write."""
        cache_id = uuid.uuid4().hex[:16]
        now = time.time()
        expires = now + self._ttl
        filter_hash = self._hash_filter(filter)

        # Extract document_ids for invalidation tracking
        doc_ids = list({
            r.chunk.document_id
            for r in response.results
            if r.chunk.document_id
        })

        emb_array = np.array(query_embedding, dtype=np.float32)
        emb_blob = emb_array.tobytes()
        response_json = response.model_dump_json()

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO semantic_cache "
                "(cache_id, query_text, query_embedding, strategy, k, filter_hash, "
                "rerank, response_json, document_ids, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cache_id, query, emb_blob, strategy, k, filter_hash,
                    int(rerank), response_json, json.dumps(doc_ids),
                    now, expires,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # Update in-memory index
        self._cache_ids.append(cache_id)
        self._metadata[cache_id] = {
            "strategy": strategy,
            "k": k,
            "filter_hash": filter_hash,
            "rerank": rerank,
        }
        if self._embeddings is None:
            self._embeddings = emb_array.reshape(1, -1)
        else:
            self._embeddings = np.vstack([self._embeddings, emb_array.reshape(1, -1)])

        # Evict oldest if over max_entries
        if len(self._cache_ids) > self._max_entries:
            self._evict_oldest()

    def _evict_oldest(self) -> None:
        """Remove oldest entries to stay within max_entries."""
        excess = len(self._cache_ids) - self._max_entries
        if excess <= 0:
            return

        to_remove = self._cache_ids[:excess]
        self._cache_ids = self._cache_ids[excess:]
        if self._embeddings is not None:
            self._embeddings = self._embeddings[excess:]
        for cid in to_remove:
            self._metadata.pop(cid, None)

        # Remove from SQLite
        conn = sqlite3.connect(self._db_path)
        try:
            placeholders = ",".join("?" for _ in to_remove)
            conn.execute(
                f"DELETE FROM semantic_cache WHERE cache_id IN ({placeholders})",
                to_remove,
            )
            conn.commit()
        finally:
            conn.close()

        logger.debug("[SEMANTIC_CACHE] Evicted %d oldest entries", excess)

    async def invalidate_by_document(self, document_id: str) -> int:
        """Remove all cached entries that contain results from this document."""
        import asyncio
        return await asyncio.to_thread(self._invalidate_by_doc_sync, document_id)

    def _invalidate_by_doc_sync(self, document_id: str) -> int:
        """Synchronous document invalidation."""
        conn = sqlite3.connect(self._db_path)
        try:
            # Find entries containing this document_id
            cursor = conn.execute(
                "SELECT cache_id FROM semantic_cache WHERE document_ids LIKE ?",
                (f'%"{document_id}"%',),
            )
            to_remove = [row[0] for row in cursor.fetchall()]

            if not to_remove:
                return 0

            placeholders = ",".join("?" for _ in to_remove)
            conn.execute(
                f"DELETE FROM semantic_cache WHERE cache_id IN ({placeholders})",
                to_remove,
            )
            conn.commit()
        finally:
            conn.close()

        # Remove from in-memory index
        remove_set = set(to_remove)
        keep_indices = [
            i for i, cid in enumerate(self._cache_ids) if cid not in remove_set
        ]
        self._cache_ids = [self._cache_ids[i] for i in keep_indices]
        if self._embeddings is not None and keep_indices:
            self._embeddings = self._embeddings[keep_indices]
        elif not keep_indices:
            self._embeddings = None
        for cid in to_remove:
            self._metadata.pop(cid, None)

        logger.info(
            "[SEMANTIC_CACHE] Invalidated %d entries for document %s",
            len(to_remove), document_id,
        )
        return len(to_remove)

    async def invalidate_all(self) -> int:
        """Clear entire cache."""
        import asyncio
        return await asyncio.to_thread(self._invalidate_all_sync)

    def _invalidate_all_sync(self) -> int:
        """Synchronous full clear."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM semantic_cache")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM semantic_cache")
            conn.commit()
        finally:
            conn.close()

        self._cache_ids.clear()
        self._metadata.clear()
        self._embeddings = None

        logger.info("[SEMANTIC_CACHE] Cleared %d entries", count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "entries": len(self._cache_ids),
            "max_entries": self._max_entries,
            "threshold": self._threshold,
            "ttl_seconds": self._ttl,
        }

    @staticmethod
    def _hash_filter(filter: dict[str, Any] | None) -> str:
        """Deterministic hash of filter dict."""
        if not filter:
            return "none"
        normalized = json.dumps(filter, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# Module-level singleton
_semantic_cache: SemanticSearchCache | None = None


def get_semantic_cache(**kwargs: Any) -> SemanticSearchCache | None:
    """Get or create global semantic cache instance."""
    global _semantic_cache
    if _semantic_cache is None and kwargs:
        _semantic_cache = SemanticSearchCache(**kwargs)
    return _semantic_cache
