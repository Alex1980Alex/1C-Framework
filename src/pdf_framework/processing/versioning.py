"""Document versioning system (Phase 12.5).

Tracks document versions with rollback capability.

Author: Claude Code
Version: 1.3.0 - Phase 12.5: Document Versioning
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VersionInfo(BaseModel):
    """Information about a document version."""

    version_id: str
    document_id: str
    file_hash: str
    indexed_at: str
    chunk_count: int
    previous_version_id: str | None
    metadata: dict[str, Any]
    file_size_bytes: int


class DocumentVersionManager:
    """
    Manages document versions with rollback capability.

    - Tracks each indexing as a new version
    - Stores chunk data in cache for rollback
    - Maintains version chain (linked list)
    """

    def __init__(
        self,
        db_path: str | Path = "data/versions/versions.db",
        cache_dir: str | Path = "data/versions/chunks",
    ):
        """
        Initialize version manager.

        Args:
            db_path: Path to SQLite version database
            cache_dir: Directory for chunk cache (for rollback)
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = False

    async def _ensure_tables(self) -> None:
        """Create version tables if not exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self._db_path) as db:
            # Versions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_versions (
                    version_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    chunk_count INTEGER DEFAULT 0,
                    previous_version_id TEXT,
                    metadata TEXT,
                    file_size_bytes INTEGER,
                    FOREIGN KEY (previous_version_id) REFERENCES document_versions(version_id)
                )
            """)

            # Index for document lookups
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_versions_document
                ON document_versions(document_id, indexed_at DESC)
            """)

            await db.commit()

        self._initialized = True

    async def create_version(
        self,
        document_id: str,
        chunks: list[dict],
        embeddings: list[list[float]] | None = None,
        metadata: dict | None = None,
    ) -> VersionInfo:
        """
        Create a new document version.

        Args:
            document_id: Document identifier
            chunks: Document chunks
            embeddings: Embedding vectors (optional, for rollback)
            metadata: Additional metadata

        Returns:
            VersionInfo for the new version
        """
        await self._ensure_tables()

        # Calculate file hash from chunks
        content = json.dumps(chunks, sort_keys=True)
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Get latest version for this document
        latest_version = await self.get_latest_version(document_id)

        # Create version ID
        version_id = f"{document_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        # Save chunks to cache for potential rollback
        cache_file = self._cache_dir / f"{version_id}.json"
        version_data = {
            "chunks": chunks,
            "embeddings": embeddings,
            "metadata": metadata,
        }
        with open(cache_file, "w") as f:
            json.dump(version_data, f)

        # Create version record
        version_info = VersionInfo(
            version_id=version_id,
            document_id=document_id,
            file_hash=file_hash,
            indexed_at=datetime.now(timezone.utc).isoformat(),
            chunk_count=len(chunks),
            previous_version_id=latest_version.version_id if latest_version else None,
            metadata=metadata or {},
            file_size_bytes=len(content.encode()),
        )

        # Store in database
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO document_versions
                (version_id, document_id, file_hash, indexed_at, chunk_count,
                 previous_version_id, metadata, file_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version_info.version_id,
                version_info.document_id,
                version_info.file_hash,
                version_info.indexed_at,
                version_info.chunk_count,
                version_info.previous_version_id,
                json.dumps(version_info.metadata),
                version_info.file_size_bytes,
            ))
            await db.commit()

        logger.info(
            f"[VERSION] Created version {version_id} for document {document_id} "
            f"({len(chunks)} chunks)"
        )

        return version_info

    async def get_versions(self, document_id: str) -> list[VersionInfo]:
        """
        Get all versions for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of versions, newest first
        """
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM document_versions
                WHERE document_id = ?
                ORDER BY indexed_at DESC
            """, (document_id,))
            rows = await cursor.fetchall()

            return [
                VersionInfo(
                    version_id=row["version_id"],
                    document_id=row["document_id"],
                    file_hash=row["file_hash"],
                    indexed_at=row["indexed_at"],
                    chunk_count=row["chunk_count"],
                    previous_version_id=row["previous_version_id"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    file_size_bytes=row["file_size_bytes"],
                )
                for row in rows
            ]

    async def get_latest_version(self, document_id: str) -> VersionInfo | None:
        """
        Get the latest version for a document.

        Args:
            document_id: Document identifier

        Returns:
            Latest VersionInfo or None
        """
        versions = await self.get_versions(document_id)
        return versions[0] if versions else None

    async def get_version(self, version_id: str) -> VersionInfo | None:
        """
        Get a specific version.

        Args:
            version_id: Version identifier

        Returns:
            VersionInfo or None
        """
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM document_versions WHERE version_id = ?
            """, (version_id,))
            row = await cursor.fetchone()

            if row:
                return VersionInfo(
                    version_id=row["version_id"],
                    document_id=row["document_id"],
                    file_hash=row["file_hash"],
                    indexed_at=row["indexed_at"],
                    chunk_count=row["chunk_count"],
                    previous_version_id=row["previous_version_id"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    file_size_bytes=row["file_size_bytes"],
                )
            return None

    async def get_version_chunks(self, version_id: str) -> dict | None:
        """
        Get cached chunks for a version.

        Args:
            version_id: Version identifier

        Returns:
            Dict with chunks, embeddings, metadata or None
        """
        cache_file = self._cache_dir / f"{version_id}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[VERSION] Error loading version chunks: {e}")
            return None

    async def rollback(
        self,
        document_id: str,
        version_id: str | None = None,
    ) -> tuple[list[dict], list[list[float]] | None, dict]:
        """
        Rollback document to a previous version.

        Args:
            document_id: Document identifier
            version_id: Target version ID (None for previous)

        Returns:
            (chunks, embeddings, metadata) for the rolled-back version

        Raises:
            ValueError: If version not found
        """
        # Find target version
        if version_id is None:
            # Get previous version
            latest = await self.get_latest_version(document_id)
            if latest and latest.previous_version_id:
                version_id = latest.previous_version_id
            else:
                raise ValueError("No previous version found")

        # Get version info
        version_info = await self.get_version(version_id)
        if version_info is None:
            raise ValueError(f"Version {version_id} not found")

        # Load chunks from cache
        version_data = await self.get_version_chunks(version_id)
        if version_data is None:
            raise ValueError(f"Version data not available for {version_id}")

        chunks = version_data.get("chunks", [])
        embeddings = version_data.get("embeddings")
        metadata = version_data.get("metadata", {})

        logger.info(
            f"[VERSION] Rolled back document {document_id} to version {version_id} "
            f"({len(chunks)} chunks)"
        )

        return chunks, embeddings, metadata

    async def delete_document(self, document_id: str) -> int:
        """
        Delete all versions for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of versions deleted
        """
        await self._ensure_tables()

        # Get versions to clean up cache
        versions = await self.get_versions(document_id)

        # Delete from database
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("""
                DELETE FROM document_versions WHERE document_id = ?
            """, (document_id,))
            await db.commit()
            count = cursor.rowcount

        # Delete cache files
        for version in versions:
            cache_file = self._cache_dir / f"{version.version_id}.json"
            cache_file.unlink(missing_ok=True)

        logger.info(f"[VERSION] Deleted {count} versions for document {document_id}")

        return count


# Global version manager instance
_version_manager: DocumentVersionManager | None = None


def get_version_manager(**kwargs) -> DocumentVersionManager:
    """Get or create global version manager instance."""
    global _version_manager
    if _version_manager is None:
        _version_manager = DocumentVersionManager(**kwargs)
    return _version_manager
