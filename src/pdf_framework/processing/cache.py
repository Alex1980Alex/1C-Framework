"""Document processing cache for faster re-indexing (Phase 11).

Caches processed documents by file hash to avoid reprocessing unchanged files.

Author: Claude Code
Version: 1.2.0 - Phase 11.4: Document Processing Cache
"""

import hashlib
import json
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CachedDocument(BaseModel):
    """Cached document data."""

    file_hash: str
    file_path: str
    chunks: list[dict]
    embeddings: list[list[float]]
    metadata: dict
    cached_at: str
    file_size_bytes: int

    def is_stale(self, current_path: Path | None = None) -> bool:
        """Check if cached document is stale (file changed)."""
        if current_path is None:
            current_path = Path(self.file_path)

        if not current_path.exists():
            return True  # File deleted = stale

        current_hash = _hash_file(current_path)
        return current_hash != self.file_hash


class DocumentProcessingCache:
    """
    Cache for processed documents.

    Key: SHA-256 hash of file contents
    Value: chunks + embeddings + metadata (pickle)
    Storage: data/cache/documents/{file_hash}.pkl
    """

    def __init__(
        self,
        cache_dir: str | Path = "data/cache/documents",
    ):
        """
        Initialize document processing cache.

        Args:
            cache_dir: Directory for cached documents
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._stats = {
            "hits": 0,
            "misses": 0,
            "stale": 0,
        }

    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for a file hash."""
        return self._cache_dir / f"{file_hash}.pkl"

    def get(self, file_path: str | Path) -> CachedDocument | None:
        """
        Get cached document if available and fresh.

        Args:
            file_path: Path to document file

        Returns:
            CachedDocument or None
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return None

        file_hash = _hash_file(file_path)
        cache_path = self._get_cache_path(file_hash)

        if not cache_path.exists():
            self._stats["misses"] += 1
            return None

        try:
            with open(cache_path, "rb") as f:
                cached_doc = pickle.load(f)

            # Check if stale
            if cached_doc.is_stale(file_path):
                self._stats["stale"] += 1
                # Delete stale cache
                cache_path.unlink(missing_ok=True)
                logger.info(f"[DOC_CACHE] Stale cache for {file_path.name}")
                return None

            self._stats["hits"] += 1
            logger.debug(f"[DOC_CACHE] Cache hit for {file_path.name}")
            return cached_doc

        except Exception as e:
            logger.error(f"[DOC_CACHE] Error loading cache: {e}")
            self._stats["misses"] += 1
            return None

    def set(
        self,
        file_path: str | Path,
        chunks: list[dict],
        embeddings: list[list[float]],
        metadata: dict,
    ) -> None:
        """
        Store processed document in cache.

        Args:
            file_path: Path to document
            chunks: Document chunks
            embeddings: Embedding vectors
            metadata: Document metadata
        """
        file_path = Path(file_path)
        file_hash = _hash_file(file_path)

        cache_path = self._get_cache_path(file_hash)

        cached_doc = CachedDocument(
            file_hash=file_hash,
            file_path=str(file_path),
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadata,
            cached_at=datetime.now(timezone.utc).isoformat(),
            file_size_bytes=file_path.stat().st_size,
        )

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(cached_doc, f)

            logger.info(f"[DOC_CACHE] Cached {file_path.name} ({len(chunks)} chunks)")

        except Exception as e:
            logger.error(f"[DOC_CACHE] Error saving cache: {e}")

    def clear(self, pattern: str | None = None) -> int:
        """
        Clear cached documents.

        Args:
            pattern: Optional glob pattern to filter files

        Returns:
            Number of entries removed
        """
        count = 0

        if pattern:
            # Clear matching files
            for cache_file in self._cache_dir.glob(pattern):
                cache_file.unlink(missing_ok=True)
                count += 1
        else:
            # Clear all
            for cache_file in self._cache_dir.glob("*.pkl"):
                cache_file.unlink(missing_ok=True)
                count += 1

        logger.info(f"[DOC_CACHE] Cleared {count} cached documents")
        return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return self._stats.copy()


def _hash_file(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of file contents.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal hash string
    """
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b""):
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


# Global document cache instance
_document_cache: DocumentProcessingCache | None = None


def get_document_cache(**kwargs) -> DocumentProcessingCache:
    """Get or create global document cache instance."""
    global _document_cache
    if _document_cache is None:
        _document_cache = DocumentProcessingCache(**kwargs)
    return _document_cache
