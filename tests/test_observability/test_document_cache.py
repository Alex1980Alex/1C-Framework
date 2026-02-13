"""Tests for DocumentProcessingCache (Phase 11.4).

Tests file-hash based document cache with pickle storage.
"""

import pickle
from pathlib import Path

import pytest

from src.pdf_framework.processing.cache import (
    CachedDocument,
    DocumentProcessingCache,
    _hash_file,
    get_document_cache,
)


# ── _hash_file Tests ───────────────────────────────────────────


class TestHashFile:
    """Test file hashing utility."""

    def test_hash_returns_hex(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = _hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")
        h1 = _hash_file(f)
        h2 = _hash_file(f)
        assert h1 == h2

    def test_hash_changes_with_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("version 1")
        h1 = _hash_file(f)
        f.write_text("version 2")
        h2 = _hash_file(f)
        assert h1 != h2

    def test_hash_different_files_same_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same content")
        f2.write_text("same content")
        assert _hash_file(f1) == _hash_file(f2)

    def test_hash_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        h = _hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_large_file(self, tmp_path):
        f = tmp_path / "large.bin"
        # Write > 8192 bytes (chunk size) to test chunked reading
        f.write_bytes(b"x" * 20000)
        h = _hash_file(f)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_binary_file(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(bytes(range(256)))
        h = _hash_file(f)
        assert isinstance(h, str)


# ── CachedDocument Tests ──────────────────────────────────────


class TestCachedDocument:
    """Test CachedDocument model."""

    def test_creation(self):
        doc = CachedDocument(
            file_hash="abc123",
            file_path="/test/doc.pdf",
            chunks=[{"content": "chunk1"}],
            embeddings=[[0.1, 0.2]],
            metadata={"source": "test"},
            cached_at="2024-01-01T00:00:00Z",
            file_size_bytes=1024,
        )
        assert doc.file_hash == "abc123"
        assert len(doc.chunks) == 1
        assert doc.file_size_bytes == 1024

    def test_is_stale_file_deleted(self, tmp_path):
        doc = CachedDocument(
            file_hash="abc",
            file_path=str(tmp_path / "deleted.pdf"),
            chunks=[],
            embeddings=[],
            metadata={},
            cached_at="2024-01-01T00:00:00Z",
            file_size_bytes=0,
        )
        assert doc.is_stale() is True

    def test_is_stale_file_unchanged(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("content")
        file_hash = _hash_file(f)

        doc = CachedDocument(
            file_hash=file_hash,
            file_path=str(f),
            chunks=[],
            embeddings=[],
            metadata={},
            cached_at="2024-01-01T00:00:00Z",
            file_size_bytes=7,
        )
        assert doc.is_stale() is False

    def test_is_stale_file_changed(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("original")
        old_hash = _hash_file(f)

        f.write_text("modified")

        doc = CachedDocument(
            file_hash=old_hash,
            file_path=str(f),
            chunks=[],
            embeddings=[],
            metadata={},
            cached_at="2024-01-01T00:00:00Z",
            file_size_bytes=8,
        )
        assert doc.is_stale() is True

    def test_is_stale_with_explicit_path(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("content")
        file_hash = _hash_file(f)

        doc = CachedDocument(
            file_hash=file_hash,
            file_path="/nonexistent/path",  # Wrong path
            chunks=[],
            embeddings=[],
            metadata={},
            cached_at="2024-01-01T00:00:00Z",
            file_size_bytes=7,
        )
        # Check against actual file path
        assert doc.is_stale(f) is False


# ── DocumentProcessingCache Tests ──────────────────────────────


class TestDocumentProcessingCacheInit:
    """Test DocumentProcessingCache initialization."""

    def test_creates_cache_dir(self, tmp_path):
        cache_dir = tmp_path / "cache" / "docs"
        cache = DocumentProcessingCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_initial_stats(self, tmp_path):
        cache = DocumentProcessingCache(cache_dir=tmp_path)
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["stale"] == 0


class TestDocumentProcessingCacheGetSet:
    """Test get/set operations."""

    @pytest.fixture
    def cache(self, tmp_path):
        return DocumentProcessingCache(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def sample_file(self, tmp_path):
        f = tmp_path / "sample.pdf"
        f.write_text("PDF content here")
        return f

    def test_get_nonexistent_returns_none(self, cache, tmp_path):
        f = tmp_path / "nonexistent.pdf"
        result = cache.get(f)
        assert result is None

    def test_get_uncached_returns_none(self, cache, sample_file):
        result = cache.get(sample_file)
        assert result is None

    def test_set_and_get(self, cache, sample_file):
        chunks = [{"content": "chunk1"}, {"content": "chunk2"}]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        metadata = {"source": "test"}

        cache.set(sample_file, chunks, embeddings, metadata)
        result = cache.get(sample_file)

        assert result is not None
        assert len(result.chunks) == 2
        assert result.chunks[0]["content"] == "chunk1"
        assert result.embeddings == embeddings
        assert result.metadata["source"] == "test"

    def test_get_stale_returns_none(self, cache, sample_file):
        cache.set(sample_file, [{"c": "1"}], [[1.0]], {})

        # Modify file to make cache stale
        sample_file.write_text("MODIFIED content")

        result = cache.get(sample_file)
        assert result is None

    def test_get_increments_hit_counter(self, cache, sample_file):
        cache.set(sample_file, [], [], {})
        cache.get(sample_file)
        assert cache.get_stats()["hits"] == 1

    def test_get_miss_increments_miss_counter(self, cache, sample_file):
        cache.get(sample_file)
        assert cache.get_stats()["misses"] == 1

    def test_modified_file_is_cache_miss(self, cache, sample_file):
        """When file content changes, the hash changes, so it's a new miss."""
        cache.set(sample_file, [], [], {})
        sample_file.write_text("changed!")
        result = cache.get(sample_file)
        assert result is None
        # New hash → no cache file → counts as miss
        assert cache.get_stats()["misses"] == 1

    def test_cached_document_has_file_size(self, cache, sample_file):
        cache.set(sample_file, [], [], {})
        result = cache.get(sample_file)
        assert result.file_size_bytes == sample_file.stat().st_size

    def test_cached_document_has_file_hash(self, cache, sample_file):
        cache.set(sample_file, [], [], {})
        result = cache.get(sample_file)
        assert result.file_hash == _hash_file(sample_file)

    def test_cached_document_has_file_path(self, cache, sample_file):
        cache.set(sample_file, [], [], {})
        result = cache.get(sample_file)
        assert result.file_path == str(sample_file)


class TestDocumentProcessingCacheClear:
    """Test clearing the cache."""

    @pytest.fixture
    def cache(self, tmp_path):
        return DocumentProcessingCache(cache_dir=tmp_path / "cache")

    def test_clear_all(self, cache, tmp_path):
        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_text("aaa")
        f2.write_text("bbb")

        cache.set(f1, [], [], {})
        cache.set(f2, [], [], {})

        count = cache.clear()
        assert count == 2

        assert cache.get(f1) is None
        assert cache.get(f2) is None

    def test_clear_with_pattern(self, cache, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        cache.set(f, [], [], {})

        file_hash = _hash_file(f)
        count = cache.clear(pattern=f"{file_hash}.pkl")
        assert count == 1

    def test_clear_empty_returns_zero(self, cache):
        count = cache.clear()
        assert count == 0


class TestDocumentProcessingCacheStats:
    """Test cache statistics."""

    def test_stats_copy(self, tmp_path):
        cache = DocumentProcessingCache(cache_dir=tmp_path)
        stats = cache.get_stats()
        # Should be a copy, not the original
        stats["hits"] = 999
        assert cache.get_stats()["hits"] == 0

    def test_stats_accumulate(self, tmp_path):
        cache = DocumentProcessingCache(cache_dir=tmp_path / "cache")
        f = tmp_path / "doc.txt"
        f.write_text("content")

        cache.get(f)  # miss (no cache file)
        cache.set(f, [], [], {})
        cache.get(f)  # hit (cached)
        f.write_text("new")
        cache.get(f)  # miss again (new hash, no cache file)

        stats = cache.get_stats()
        assert stats["misses"] == 2  # Two misses: initial + after content change
        assert stats["hits"] == 1
        assert stats["stale"] == 0  # Hash-based: changed file = new miss, not stale


# ── get_document_cache Singleton ───────────────────────────────


class TestGetDocumentCache:
    """Test get_document_cache singleton."""

    def test_returns_cache(self):
        cache = get_document_cache()
        assert isinstance(cache, DocumentProcessingCache)
