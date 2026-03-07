"""
Context Cache for INITIALIZER Agent.

Caches project context to avoid repeated scanning.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from agents.initializer.models import ContextReport, InitializerConfig


@dataclass
class CacheEntry:
    """Cache entry for project context."""

    project_id: str
    project_path: str
    context_hash: str
    created_at: datetime
    expires_at: datetime
    context_data: dict = field(default_factory=dict)
    file_count: int = 0
    last_modified: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > self.expires_at

    @property
    def age_seconds(self) -> float:
        """Get age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,
            "context_hash": self.context_hash,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "context_data": self.context_data,
            "file_count": self.file_count,
            "last_modified": (
                self.last_modified.isoformat()
                if self.last_modified else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            project_id=data["project_id"],
            project_path=data["project_path"],
            context_hash=data["context_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            context_data=data.get("context_data", {}),
            file_count=data.get("file_count", 0),
            last_modified=(
                datetime.fromisoformat(data["last_modified"])
                if data.get("last_modified") else None
            ),
        )


class ContextCache:
    """
    Cache manager for project contexts.

    Features:
    - File-based persistent cache
    - TTL-based expiration
    - Directory hash for invalidation
    - Memory cache for fast access
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        config: Optional[InitializerConfig] = None,
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files
            config: Configuration with TTL settings
        """
        self.config = config or InitializerConfig()
        self.cache_dir = cache_dir or Path("cache/initializer")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._memory_cache: dict[str, CacheEntry] = {}

        # Load existing cache
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        cache_file = self.cache_dir / "context_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for key, entry_data in data.items():
                    try:
                        entry = CacheEntry.from_dict(entry_data)
                        if not entry.is_expired:
                            self._memory_cache[key] = entry
                    except (KeyError, ValueError):
                        continue

            except (json.JSONDecodeError, IOError):
                pass

    def _save_cache(self) -> None:
        """Save cache to disk."""
        cache_file = self.cache_dir / "context_cache.json"

        # Filter out expired entries
        valid_entries = {
            k: v.to_dict()
            for k, v in self._memory_cache.items()
            if not v.is_expired
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(valid_entries, f, ensure_ascii=False, indent=2)
        except IOError:
            pass

    def _get_cache_key(self, project_path: str) -> str:
        """Generate cache key from project path."""
        return hashlib.md5(
            project_path.encode("utf-8")
        ).hexdigest()

    def _compute_directory_hash(self, directory: Path) -> str:
        """
        Compute hash of directory contents.

        Uses file names and modification times for quick hash.
        """
        if not directory.exists():
            return ""

        hash_parts = []

        try:
            for root, dirs, files in os.walk(directory):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in sorted(files):
                    if file.endswith((".bsl", ".xml", ".mdo")):
                        file_path = Path(root) / file
                        try:
                            stat = file_path.stat()
                            hash_parts.append(
                                f"{file_path}:{stat.st_mtime}:{stat.st_size}"
                            )
                        except OSError:
                            continue

        except OSError:
            pass

        if not hash_parts:
            return ""  # No matching files found

        combined = "\n".join(hash_parts)
        return hashlib.md5(combined.encode()).hexdigest()

    def is_valid(self, project_path: str) -> bool:
        """
        Check if cache is valid for project.

        Args:
            project_path: Path to project directory

        Returns:
            True if cache is valid and not expired
        """
        cache_key = self._get_cache_key(project_path)
        entry = self._memory_cache.get(cache_key)

        if not entry:
            return False

        if entry.is_expired:
            return False

        # Check if directory contents changed
        current_hash = self._compute_directory_hash(Path(project_path))
        if current_hash != entry.context_hash:
            return False

        return True

    def get(self, project_path: str) -> Optional[CacheEntry]:
        """
        Get cached entry.

        Args:
            project_path: Path to project directory

        Returns:
            CacheEntry if valid, None otherwise
        """
        if not self.is_valid(project_path):
            return None

        cache_key = self._get_cache_key(project_path)
        return self._memory_cache.get(cache_key)

    def set(
        self,
        project_path: str,
        context_report: ContextReport,
        ttl: Optional[int] = None,
    ) -> CacheEntry:
        """
        Cache context report.

        Args:
            project_path: Path to project directory
            context_report: Context report to cache
            ttl: Time to live in seconds (uses config default if None)

        Returns:
            Created cache entry
        """
        ttl = ttl or self.config.cache_ttl
        cache_key = self._get_cache_key(project_path)

        # Compute directory hash
        context_hash = self._compute_directory_hash(Path(project_path))

        # Create entry
        entry = CacheEntry(
            project_id=context_report.project_id,
            project_path=project_path,
            context_hash=context_hash,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=ttl),
            context_data={
                "markdown_content": context_report.markdown_content,
                "task_description": context_report.task_description,
                "relevant_files_count": len(context_report.relevant_files),
            },
            file_count=context_report.project_structure.total_files,
            last_modified=datetime.now(),
        )

        # Store in memory and disk
        self._memory_cache[cache_key] = entry
        self._save_cache()

        return entry

    def invalidate(self, project_path: str) -> bool:
        """
        Invalidate cache for project.

        Args:
            project_path: Path to project directory

        Returns:
            True if entry was removed
        """
        cache_key = self._get_cache_key(project_path)

        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            self._save_cache()
            return True

        return False

    def invalidate_all(self) -> int:
        """
        Invalidate all cache entries.

        Returns:
            Number of entries removed
        """
        count = len(self._memory_cache)
        self._memory_cache.clear()
        self._save_cache()
        return count

    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if v.is_expired
        ]

        for key in expired_keys:
            del self._memory_cache[key]

        if expired_keys:
            self._save_cache()

        return len(expired_keys)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = len(self._memory_cache)
        expired = sum(
            1 for v in self._memory_cache.values()
            if v.is_expired
        )
        valid = total - expired

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired,
            "cache_dir": str(self.cache_dir),
            "default_ttl": self.config.cache_ttl,
        }


# Global cache instance
_global_cache: Optional[ContextCache] = None


def get_cache(
    cache_dir: Optional[Path] = None,
    config: Optional[InitializerConfig] = None,
) -> ContextCache:
    """Get or create global cache instance."""
    global _global_cache

    if _global_cache is None:
        _global_cache = ContextCache(cache_dir, config)

    return _global_cache


def cache_context(
    project_path: str,
    context_report: ContextReport,
    ttl: Optional[int] = None,
) -> CacheEntry:
    """
    Cache context report.

    Convenience function using global cache.

    Args:
        project_path: Path to project
        context_report: Report to cache
        ttl: Optional TTL override

    Returns:
        Created cache entry
    """
    cache = get_cache()
    return cache.set(project_path, context_report, ttl)


def get_cached_context(project_path: str) -> Optional[CacheEntry]:
    """
    Get cached context.

    Convenience function using global cache.

    Args:
        project_path: Path to project

    Returns:
        CacheEntry if valid, None otherwise
    """
    cache = get_cache()
    return cache.get(project_path)


def invalidate_cache(project_path: str) -> bool:
    """
    Invalidate cache for project.

    Convenience function using global cache.

    Args:
        project_path: Path to project

    Returns:
        True if entry was removed
    """
    cache = get_cache()
    return cache.invalidate(project_path)


def is_cache_valid(project_path: str) -> bool:
    """
    Check if cache is valid.

    Convenience function using global cache.

    Args:
        project_path: Path to project

    Returns:
        True if cache is valid
    """
    cache = get_cache()
    return cache.is_valid(project_path)
