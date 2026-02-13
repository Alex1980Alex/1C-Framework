"""Disk-based embedding cache.

Caches embedding vectors to avoid recomputation for previously seen texts.
Uses SHA-256 hash of text as the cache key, stored as individual JSON files.
"""

import hashlib
import json
from pathlib import Path

from src.pdf_framework.config import EmbeddingSettings


class FileEmbeddingCache:
    """Cache embeddings on disk using text content hashes."""

    def __init__(self, settings: EmbeddingSettings | None = None):
        self._settings = settings or EmbeddingSettings()
        self._cache_dir = Path(self._settings.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def get(self, text: str) -> list[float] | None:
        """Look up a cached embedding. Returns None on miss."""
        path = self._path(self._key(text))
        if path.exists():
            self._hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self._misses += 1
        return None

    def put(self, text: str, embedding: list[float]) -> None:
        """Store an embedding in the cache."""
        path = self._path(self._key(text))
        path.write_text(json.dumps(embedding), encoding="utf-8")

    def get_batch(self, texts: list[str]) -> tuple[list[list[float] | None], list[int]]:
        """Look up a batch of texts. Returns (results, miss_indices).

        results[i] is the embedding if cached, else None.
        miss_indices contains indices where cache missed.
        """
        results: list[list[float] | None] = []
        misses: list[int] = []
        for i, text in enumerate(texts):
            cached = self.get(text)
            results.append(cached)
            if cached is None:
                misses.append(i)
        return results, misses

    def put_batch(self, texts: list[str], embeddings: list[list[float]]) -> None:
        """Store a batch of embeddings."""
        for text, emb in zip(texts, embeddings):
            self.put(text, emb)

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}

    def clear(self) -> None:
        """Remove all cached embeddings."""
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
        self._hits = 0
        self._misses = 0
