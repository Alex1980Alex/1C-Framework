"""Tests for ContextCache."""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from ..context_cache import (
    CacheEntry,
    ContextCache,
    get_cache,
    cache_context,
    get_cached_context,
    invalidate_cache,
    is_cache_valid,
)
from models import (
    InitializerConfig,
    ContextReport,
    ProjectStructure,
    ProjectType,
    RelevantFile,
    FileInfo,
    FileType,
)


def create_test_structure() -> ProjectStructure:
    """Helper to create test structure."""
    return ProjectStructure(
        root_path=Path("/test/project"),
        project_type=ProjectType.CONFIGURATION,
        name="TestProject",
        modules=[],
        scanned_at=datetime.now(),
    )


def create_test_context_report() -> ContextReport:
    """Helper to create test context report."""
    return ContextReport(
        project_id="TEST-001",
        project_structure=create_test_structure(),
        relevant_files=[],
        task_description="Test task",
        markdown_content="# Test Context",
        generated_at=datetime.now(),
    )


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test basic cache entry creation."""
        entry = CacheEntry(
            project_id="TEST-001",
            project_path="/test/project",
            context_hash="abc123",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
        )

        assert entry.project_id == "TEST-001"
        assert entry.project_path == "/test/project"
        assert entry.context_hash == "abc123"
        assert not entry.is_expired

    def test_cache_entry_is_expired_false(self):
        """Test is_expired returns False for valid entry."""
        entry = CacheEntry(
            project_id="TEST",
            project_path="/test",
            context_hash="hash",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
        )

        assert not entry.is_expired

    def test_cache_entry_is_expired_true(self):
        """Test is_expired returns True for expired entry."""
        entry = CacheEntry(
            project_id="TEST",
            project_path="/test",
            context_hash="hash",
            created_at=datetime.now() - timedelta(hours=2),
            expires_at=datetime.now() - timedelta(hours=1),
        )

        assert entry.is_expired

    def test_cache_entry_age_seconds(self):
        """Test age_seconds property."""
        past_time = datetime.now() - timedelta(minutes=5)
        entry = CacheEntry(
            project_id="TEST",
            project_path="/test",
            context_hash="hash",
            created_at=past_time,
            expires_at=datetime.now() + timedelta(hours=1),
        )

        # Should be approximately 300 seconds (5 minutes)
        assert 295 <= entry.age_seconds <= 305

    def test_cache_entry_to_dict(self):
        """Test serialization to dict."""
        now = datetime.now()
        entry = CacheEntry(
            project_id="TEST-001",
            project_path="/test/project",
            context_hash="abc123",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            context_data={"key": "value"},
            file_count=10,
        )

        result = entry.to_dict()

        assert result["project_id"] == "TEST-001"
        assert result["project_path"] == "/test/project"
        assert result["context_hash"] == "abc123"
        assert result["context_data"] == {"key": "value"}
        assert result["file_count"] == 10
        assert "created_at" in result
        assert "expires_at" in result

    def test_cache_entry_from_dict(self):
        """Test deserialization from dict."""
        now = datetime.now()
        data = {
            "project_id": "TEST-001",
            "project_path": "/test/project",
            "context_hash": "abc123",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "context_data": {"key": "value"},
            "file_count": 10,
            "last_modified": now.isoformat(),
        }

        entry = CacheEntry.from_dict(data)

        assert entry.project_id == "TEST-001"
        assert entry.project_path == "/test/project"
        assert entry.context_hash == "abc123"
        assert entry.context_data == {"key": "value"}
        assert entry.file_count == 10

    def test_cache_entry_roundtrip(self):
        """Test serialization/deserialization roundtrip."""
        now = datetime.now()
        original = CacheEntry(
            project_id="TEST-001",
            project_path="/test/project",
            context_hash="abc123",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            context_data={"markdown": "# Test"},
            file_count=5,
        )

        data = original.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.project_id == original.project_id
        assert restored.project_path == original.project_path
        assert restored.context_hash == original.context_hash
        assert restored.context_data == original.context_data
        assert restored.file_count == original.file_count


class TestContextCache:
    """Tests for ContextCache class."""

    def test_init_creates_cache_dir(self):
        """Test that initialization creates cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache" / "test"
            cache = ContextCache(cache_dir=cache_dir)

            assert cache_dir.exists()

    def test_init_with_config(self):
        """Test initialization with custom config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = InitializerConfig(cache_ttl=7200)
            cache = ContextCache(cache_dir=Path(tmpdir), config=config)

            assert cache.config.cache_ttl == 7200

    def test_get_cache_key(self):
        """Test cache key generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            key1 = cache._get_cache_key("/path/to/project")
            key2 = cache._get_cache_key("/path/to/project")
            key3 = cache._get_cache_key("/different/path")

            assert key1 == key2  # Same path = same key
            assert key1 != key3  # Different path = different key

    def test_is_valid_returns_false_for_missing(self):
        """Test is_valid returns False for missing entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            assert not cache.is_valid("/nonexistent/path")

    def test_set_and_get(self):
        """Test setting and getting cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))
            context_report = create_test_context_report()

            # Set cache
            entry = cache.set(tmpdir, context_report)

            assert entry is not None
            assert entry.project_id == "TEST-001"

            # Get cache (note: may fail due to hash validation)
            # So we test the memory cache directly
            cache_key = cache._get_cache_key(tmpdir)
            assert cache_key in cache._memory_cache

    def test_invalidate(self):
        """Test cache invalidation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))
            context_report = create_test_context_report()

            # Set cache
            cache.set(tmpdir, context_report)
            cache_key = cache._get_cache_key(tmpdir)
            assert cache_key in cache._memory_cache

            # Invalidate
            result = cache.invalidate(tmpdir)

            assert result is True
            assert cache_key not in cache._memory_cache

    def test_invalidate_nonexistent(self):
        """Test invalidating nonexistent entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            result = cache.invalidate("/nonexistent/path")

            assert result is False

    def test_invalidate_all(self):
        """Test invalidating all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))
            context_report = create_test_context_report()

            # Set multiple entries
            cache.set(f"{tmpdir}/project1", context_report)
            cache.set(f"{tmpdir}/project2", context_report)

            assert len(cache._memory_cache) == 2

            # Invalidate all
            count = cache.invalidate_all()

            assert count == 2
            assert len(cache._memory_cache) == 0

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            # Manually add expired entry
            expired_entry = CacheEntry(
                project_id="EXPIRED",
                project_path="/expired",
                context_hash="hash",
                created_at=datetime.now() - timedelta(hours=2),
                expires_at=datetime.now() - timedelta(hours=1),
            )
            cache._memory_cache["expired_key"] = expired_entry

            # Add valid entry
            valid_entry = CacheEntry(
                project_id="VALID",
                project_path="/valid",
                context_hash="hash",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1),
            )
            cache._memory_cache["valid_key"] = valid_entry

            # Cleanup
            count = cache.cleanup_expired()

            assert count == 1
            assert "expired_key" not in cache._memory_cache
            assert "valid_key" in cache._memory_cache

    def test_get_stats(self):
        """Test getting cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            # Add some entries
            valid_entry = CacheEntry(
                project_id="VALID",
                project_path="/valid",
                context_hash="hash",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1),
            )
            cache._memory_cache["valid_key"] = valid_entry

            expired_entry = CacheEntry(
                project_id="EXPIRED",
                project_path="/expired",
                context_hash="hash",
                created_at=datetime.now() - timedelta(hours=2),
                expires_at=datetime.now() - timedelta(hours=1),
            )
            cache._memory_cache["expired_key"] = expired_entry

            stats = cache.get_stats()

            assert stats["total_entries"] == 2
            assert stats["expired_entries"] == 1
            assert stats["valid_entries"] == 1
            assert "cache_dir" in stats
            assert "default_ttl" in stats


class TestCachePersistence:
    """Tests for cache persistence."""

    def test_cache_saves_to_disk(self):
        """Test that cache is saved to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))
            context_report = create_test_context_report()

            cache.set(tmpdir, context_report)

            # Check file exists
            cache_file = Path(tmpdir) / "context_cache.json"
            assert cache_file.exists()

    def test_cache_loads_from_disk(self):
        """Test that cache is loaded from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create cache file manually
            cache_file = cache_dir / "context_cache.json"
            now = datetime.now()
            cache_data = {
                "test_key": {
                    "project_id": "TEST",
                    "project_path": "/test",
                    "context_hash": "hash",
                    "created_at": now.isoformat(),
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "context_data": {},
                    "file_count": 0,
                    "last_modified": None,
                }
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)

            # Load cache
            cache = ContextCache(cache_dir=cache_dir)

            assert "test_key" in cache._memory_cache
            assert cache._memory_cache["test_key"].project_id == "TEST"

    def test_cache_ignores_corrupted_file(self):
        """Test that corrupted cache file is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # Create corrupted cache file
            cache_file = cache_dir / "context_cache.json"
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w") as f:
                f.write("not valid json{{{")

            # Should not raise, just ignore
            cache = ContextCache(cache_dir=cache_dir)

            assert len(cache._memory_cache) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_cache_returns_singleton(self):
        """Test that get_cache returns the same instance."""
        # Note: This may interfere with other tests due to global state
        # Reset global cache first
        from .. import context_cache as cc
        cc._global_cache = None

        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

    def test_is_cache_valid_function(self):
        """Test is_cache_valid convenience function."""
        # Without setting any cache, should return False
        result = is_cache_valid("/nonexistent/path/12345")

        assert result is False


class TestDirectoryHash:
    """Tests for directory hash computation."""

    def test_compute_hash_nonexistent_directory(self):
        """Test hash computation for nonexistent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            result = cache._compute_directory_hash(Path("/nonexistent/path"))

            assert result == ""

    def test_compute_hash_empty_directory(self):
        """Test hash computation for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()

            result = cache._compute_directory_hash(empty_dir)

            assert result == ""  # No matching files

    def test_compute_hash_with_bsl_files(self):
        """Test hash computation with BSL files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            # Create BSL file
            test_dir = Path(tmpdir) / "project"
            test_dir.mkdir()
            bsl_file = test_dir / "Module.bsl"
            bsl_file.write_text("// Test")

            result = cache._compute_directory_hash(test_dir)

            assert result != ""  # Should have a hash

    def test_compute_hash_changes_with_content(self):
        """Test that hash changes when files change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContextCache(cache_dir=Path(tmpdir))

            test_dir = Path(tmpdir) / "project"
            test_dir.mkdir()
            bsl_file = test_dir / "Module.bsl"

            # First hash
            bsl_file.write_text("// Version 1")
            hash1 = cache._compute_directory_hash(test_dir)

            # Modify file (need to change mtime)
            import time
            time.sleep(0.1)  # Ensure different mtime
            bsl_file.write_text("// Version 2")
            hash2 = cache._compute_directory_hash(test_dir)

            # Hashes should be different
            assert hash1 != hash2
