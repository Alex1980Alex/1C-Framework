"""Document versioning system (Phase 12.5 + Phase 18 + Resilient Indexing).

Tracks document versions with rollback capability.
Phase 18: Adds incremental indexing — file-level status tracking and chunk delta computation.
Resilient Indexing: Adds checkpoint table for batched indexing with resume support.

Author: Claude Code
Version: 2.1.0 - Resilient Indexing: Checkpointing + Concurrency Guard
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field

from src.pdf_framework.schemas.documents import DocumentChunk

logger = logging.getLogger(__name__)


class ChunkDelta(BaseModel):
    """Result of computing diff between old and new chunks (Phase 18)."""

    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    unchanged: int = 0


class IndexingCheckpoint(BaseModel):
    """Checkpoint for resumable batched indexing."""

    file_path: str
    document_id: str
    file_hash: str
    status: str = "in_progress"  # in_progress | completed | failed
    started_at: float
    updated_at: float
    last_completed_batch: int = -1
    total_batches: int = 0
    total_chunks: int = 0


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

            # Phase 18: File tracking table for incremental indexing
            await db.execute("""
                CREATE TABLE IF NOT EXISTS file_versions (
                    file_path TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Phase 18: Chunk content hashes for delta computation
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chunk_hashes (
                    chunk_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (chunk_id, file_path)
                )
            """)

            # Resilient Indexing: Checkpoint table for batched indexing with resume
            await db.execute("""
                CREATE TABLE IF NOT EXISTS indexing_checkpoints (
                    file_path TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    started_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_completed_batch INTEGER NOT NULL DEFAULT -1,
                    total_batches INTEGER NOT NULL DEFAULT 0,
                    total_chunks INTEGER NOT NULL DEFAULT 0
                )
            """)

            await db.commit()

        self._initialized = True

    async def initialize(self) -> None:
        """Public initialize method (Phase 18)."""
        await self._ensure_tables()

    # ---- Phase 18: Incremental Indexing Methods ----

    @staticmethod
    def _file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _content_hash(content: str) -> str:
        """Compute SHA-256 hash of text content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def save_version(
        self,
        file_path: str,
        document_id: str,
        chunks: list[DocumentChunk],
    ) -> None:
        """Save file version and chunk hashes for incremental tracking."""
        await self._ensure_tables()

        fhash = self._file_hash(file_path)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO file_versions (file_path, document_id, file_hash, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (file_path, document_id, fhash, datetime.now(timezone.utc).timestamp()),
            )
            # Remove old chunk hashes for this file
            await db.execute("DELETE FROM chunk_hashes WHERE file_path = ?", (file_path,))
            # Store new chunk hashes
            for c in chunks:
                await db.execute(
                    "INSERT INTO chunk_hashes (chunk_id, file_path, content_hash) VALUES (?, ?, ?)",
                    (c.id, file_path, self._content_hash(c.content)),
                )
            await db.commit()

        logger.info(f"[VERSION] Saved version for {file_path} ({len(chunks)} chunks)")

    async def check_status(self, file_path: str) -> str:
        """Check file status: 'new', 'unchanged', or 'modified'."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT file_hash FROM file_versions WHERE file_path = ?",
                (file_path,),
            )
            row = await cursor.fetchone()

        if row is None:
            return "new"

        if not Path(file_path).exists():
            return "new"

        current_hash = self._file_hash(file_path)
        return "unchanged" if current_hash == row[0] else "modified"

    async def remove_version(self, file_path: str) -> None:
        """Remove file version tracking."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM file_versions WHERE file_path = ?", (file_path,))
            await db.execute("DELETE FROM chunk_hashes WHERE file_path = ?", (file_path,))
            await db.commit()

    async def compute_delta(
        self,
        file_path: str,
        new_chunks: list[DocumentChunk],
    ) -> ChunkDelta:
        """Compute what changed between stored and new chunks."""
        await self._ensure_tables()

        # Load old chunk hashes
        old_hashes: dict[str, str] = {}
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT chunk_id, content_hash FROM chunk_hashes WHERE file_path = ?",
                (file_path,),
            )
            rows = await cursor.fetchall()
            for cid, chash in rows:
                old_hashes[cid] = chash

        new_map = {c.id: self._content_hash(c.content) for c in new_chunks}

        added = [cid for cid in new_map if cid not in old_hashes]
        removed = [cid for cid in old_hashes if cid not in new_map]
        modified = [
            cid for cid in new_map
            if cid in old_hashes and new_map[cid] != old_hashes[cid]
        ]
        unchanged = sum(
            1 for cid in new_map
            if cid in old_hashes and new_map[cid] == old_hashes[cid]
        )

        return ChunkDelta(
            added=added,
            modified=modified,
            removed=removed,
            unchanged=unchanged,
        )

    # ---- Resilient Indexing: Checkpoint Methods ----

    _STALE_TIMEOUT = 3600  # 60 minutes — stale checkpoint threshold

    async def start_indexing(
        self,
        file_path: str,
        document_id: str,
        total_batches: int,
        total_chunks: int,
    ) -> IndexingCheckpoint | None:
        """Start indexing or resume from an existing checkpoint.

        If a checkpoint exists for the same file with the same file_hash
        and status 'in_progress', returns it for resume.
        If a different file is already in_progress (not stale), raises RuntimeError.

        Returns:
            Existing checkpoint for resume, or None for fresh start.
        """
        await self._ensure_tables()

        fhash = self._file_hash(file_path)
        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            # Check if ANY file is currently being indexed (concurrency guard)
            cursor = await db.execute(
                "SELECT file_path, file_hash, updated_at FROM indexing_checkpoints "
                "WHERE status = 'in_progress'",
            )
            row = await cursor.fetchone()

            if row is not None:
                existing_path, existing_hash, existing_updated = row
                is_stale = (now - existing_updated) > self._STALE_TIMEOUT

                if existing_path == file_path:
                    # Same file — check if same content (resume) or changed (restart)
                    if existing_hash == fhash and not is_stale:
                        # Resume: return existing checkpoint
                        return await self.get_checkpoint(file_path)
                    else:
                        # File changed or stale — clear old checkpoint and restart
                        await db.execute(
                            "DELETE FROM indexing_checkpoints WHERE file_path = ?",
                            (file_path,),
                        )
                elif not is_stale:
                    # Different file is actively indexing — block
                    raise RuntimeError(
                        f"Indexing already in progress for '{existing_path}'. "
                        f"Wait for completion or retry after {self._STALE_TIMEOUT // 60} min timeout."
                    )
                else:
                    # Other file's checkpoint is stale — mark as failed and proceed
                    await db.execute(
                        "UPDATE indexing_checkpoints SET status = 'failed', updated_at = ? "
                        "WHERE file_path = ?",
                        (now, existing_path),
                    )
                    logger.warning(
                        "[VERSION] Stale checkpoint for '%s' marked as failed", existing_path
                    )

            # Insert fresh checkpoint
            await db.execute(
                "INSERT OR REPLACE INTO indexing_checkpoints "
                "(file_path, document_id, file_hash, status, started_at, updated_at, "
                " last_completed_batch, total_batches, total_chunks) "
                "VALUES (?, ?, ?, 'in_progress', ?, ?, -1, ?, ?)",
                (file_path, document_id, fhash, now, now, total_batches, total_chunks),
            )
            await db.commit()

        logger.info(
            "[VERSION] Started indexing '%s' (%d batches, %d chunks)",
            file_path, total_batches, total_chunks,
        )
        return None

    async def get_checkpoint(self, file_path: str) -> IndexingCheckpoint | None:
        """Get checkpoint for a file, or None if not found."""
        await self._ensure_tables()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM indexing_checkpoints WHERE file_path = ?",
                (file_path,),
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return IndexingCheckpoint(
            file_path=row["file_path"],
            document_id=row["document_id"],
            file_hash=row["file_hash"],
            status=row["status"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            last_completed_batch=row["last_completed_batch"],
            total_batches=row["total_batches"],
            total_chunks=row["total_chunks"],
        )

    async def save_checkpoint(
        self,
        file_path: str,
        batch_index: int,
        batch_chunks: list[DocumentChunk],
    ) -> None:
        """Save progress after a batch completes.

        Updates last_completed_batch and stores chunk hashes for the batch.
        """
        await self._ensure_tables()

        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            # Update batch progress
            await db.execute(
                "UPDATE indexing_checkpoints "
                "SET last_completed_batch = ?, updated_at = ? "
                "WHERE file_path = ?",
                (batch_index, now, file_path),
            )

            # Store chunk hashes for this batch (for delta computation later)
            for c in batch_chunks:
                await db.execute(
                    "INSERT OR REPLACE INTO chunk_hashes (chunk_id, file_path, content_hash) "
                    "VALUES (?, ?, ?)",
                    (c.id, file_path, self._content_hash(c.content)),
                )

            await db.commit()

        logger.debug(
            "[VERSION] Checkpoint saved: batch %d for '%s' (%d chunks)",
            batch_index, file_path, len(batch_chunks),
        )

    async def complete_indexing(
        self,
        file_path: str,
        document_id: str,
        total_chunks: int,
    ) -> None:
        """Mark indexing as completed and update file_versions."""
        await self._ensure_tables()

        now = time.time()
        fhash = self._file_hash(file_path)

        async with aiosqlite.connect(self._db_path) as db:
            # Update checkpoint status
            await db.execute(
                "UPDATE indexing_checkpoints SET status = 'completed', updated_at = ? "
                "WHERE file_path = ?",
                (now, file_path),
            )

            # Update file_versions (atomic — inside same transaction)
            await db.execute(
                "INSERT OR REPLACE INTO file_versions "
                "(file_path, document_id, file_hash, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (file_path, document_id, fhash, now),
            )

            await db.commit()

        logger.info(
            "[VERSION] Indexing completed: '%s' (%d chunks)", file_path, total_chunks
        )

    async def fail_indexing(self, file_path: str) -> None:
        """Mark indexing as failed."""
        await self._ensure_tables()

        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE indexing_checkpoints SET status = 'failed', updated_at = ? "
                "WHERE file_path = ?",
                (now, file_path),
            )
            await db.commit()

        logger.warning("[VERSION] Indexing failed for '%s'", file_path)

    async def is_indexing_in_progress(self) -> bool:
        """Check if any non-stale indexing is in progress."""
        await self._ensure_tables()

        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT updated_at FROM indexing_checkpoints WHERE status = 'in_progress'",
            )
            row = await cursor.fetchone()

        if row is None:
            return False

        return (now - row[0]) < self._STALE_TIMEOUT

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
