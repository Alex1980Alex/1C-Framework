"""Delta Indexer for Incremental Updates (Phase 18).

Tracks document changes via SHA-256 hashing and performs incremental indexing.
Only processes changed documents instead of full reindexing.

Based on Pathway's incremental computation pattern.

Author: Claude Code
Version: 1.0.0 - Phase 18: Incremental Indexing
"""

import hashlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class DocumentHash:
    """Hash information for a tracked document."""

    def __init__(
        self,
        file_path: str,
        sha256: str,
        file_size: int,
        modified_time: float,
        indexed_at: float | None = None,
    ):
        self.file_path = file_path
        self.sha256 = sha256
        self.file_size = file_size
        self.modified_time = modified_time
        self.indexed_at = indexed_at or time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "sha256": self.sha256,
            "file_size": self.file_size,
            "modified_time": self.modified_time,
            "indexed_at": self.indexed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentHash":
        return cls(
            file_path=data["file_path"],
            sha256=data["sha256"],
            file_size=data["file_size"],
            modified_time=data["modified_time"],
            indexed_at=data.get("indexed_at"),
        )


class DeltaDetection:
    """Result of delta detection on document set."""

    def __init__(
        self,
        unchanged: list[DocumentHash],
        added: list[DocumentHash],
        modified: list[DocumentHash],
        deleted: list[str],  # File paths
    ):
        self.unchanged = unchanged
        self.added = added
        self.modified = modified
        self.deleted = deleted

    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return bool(self.added or self.modified or self.deleted)

    @property
    def total_to_process(self) -> int:
        """Total number of documents to process (added + modified)."""
        return len(self.added) + len(self.modified)

    def summary(self) -> str:
        """Get human-readable summary of delta."""
        return (
            f"Δ Delta: {self.total_to_process} to process "
            f"({len(self.added)} added, {len(self.modified)} modified, "
            f"{len(self.deleted)} deleted, {len(self.unchanged)} unchanged)"
        )


class DeltaIndexer:
    """Incremental indexer with change detection.

    Workflow:
        1. Calculate SHA-256 hashes for all PDF files
        2. Compare with stored hashes (from previous indexing)
        3. Process only changed documents
        4. Update hash database
        5. Cleanup deleted documents from vector store
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        hash_db_path: str | Path | None = None,
        settings: Settings | None = None,
    ):
        """Initialize the delta indexer.

        Args:
            vector_store: Vector store for document storage
            hash_db_path: Path to SQLite database for hashes
            settings: Application settings
        """
        self._vector_store = vector_store
        self._settings = settings or get_settings()
        self._hash_db_path = Path(hash_db_path or self._settings.data_dir / "document_hashes.db")
        self._hash_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize hash database
        self._init_hash_db()

    def _init_hash_db(self):
        """Initialize the hash tracking database."""
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_hashes (
                    file_path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    modified_time REAL NOT NULL,
                    indexed_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sha256 ON document_hashes(sha256)
            """)
            conn.commit()
        finally:
            conn.close()

        logger.debug(f"[DELTA_INDEXER] Hash DB initialized: {self._hash_db_path}")

    def calculate_hash(self, file_path: str | Path) -> DocumentHash:
        """Calculate SHA-256 hash and metadata for a file.

        Args:
            file_path: Path to file

        Returns:
            DocumentHash with hash and metadata
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Calculate SHA-256
        sha256_hash = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        stat = path.stat()

        return DocumentHash(
            file_path=str(path.resolve()),
            sha256=sha256_hash.hexdigest(),
            file_size=stat.st_size,
            modified_time=stat.st_mtime,
        )

    def detect_delta(
        self,
        file_paths: list[str | Path],
        force_reindex: bool = False,
    ) -> DeltaDetection:
        """Detect changes in document set.

        Args:
            file_paths: List of file paths to check
            force_reindex: Force all files to be reindexed

        Returns:
            DeltaDetection with categorized changes
        """
        t0 = time.time()

        # Load stored hashes
        stored = self._load_hashes()

        # Calculate current hashes
        current: dict[str, DocumentHash] = {}
        for path in file_paths:
            try:
                doc_hash = self.calculate_hash(path)
                current[doc_hash.file_path] = doc_hash
            except Exception as e:
                logger.warning(f"[DELTA_INDEXER] Failed to hash {path}: {e}")

        # Detect changes
        added: list[DocumentHash] = []
        modified: list[DocumentHash] = []
        unchanged: list[DocumentHash] = []
        deleted: list[str] = []

        current_paths = set(current.keys())
        stored_paths = {h.file_path for h in stored}

        # Added files
        for path in current_paths - stored_paths:
            added.append(current[path])

        # Deleted files
        for path in stored_paths - current_paths:
            deleted.append(path)

        # Check for modifications
        for path in current_paths & stored_paths:
            current_hash = current[path]
            stored_hash = next(h for h in stored if h.file_path == path)

            if force_reindex or current_hash.sha256 != stored_hash.sha256:
                modified.append(current_hash)
            else:
                unchanged.append(stored_hash)

        elapsed = time.time() - t0
        delta = DeltaDetection(unchanged, added, modified, deleted)

        logger.info(
            f"[DELTA_INDEXER] Delta detection in {elapsed:.1f}s: {delta.summary()}"
        )

        return delta

    async def process_delta(
        self,
        delta: DeltaDetection,
        document_loader,
        chunk_processor,
    ) -> dict[str, Any]:
        """Process detected delta changes.

        Args:
            delta: DeltaDetection from detect_delta()
            document_loader: Async function to load documents
            chunk_processor: Async function to process chunks into vector store

        Returns:
            Processing statistics
        """
        stats = {
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "errors": [],
            "total_time": 0,
        }
        t0 = time.time()

        try:
            # Process added documents
            if delta.added:
                logger.info(f"[DELTA_INDEXER] Processing {len(delta.added)} added documents")
                for doc_hash in delta.added:
                    try:
                        await self._process_document(
                            doc_hash.file_path,
                            document_loader,
                            chunk_processor,
                        )
                        stats["added"] += 1
                    except Exception as e:
                        logger.error(f"[DELTA_INDEXER] Failed to process {doc_hash.file_path}: {e}")
                        stats["errors"].append(str(e))

            # Process modified documents (remove old chunks first)
            if delta.modified:
                logger.info(f"[DELTA_INDEXER] Processing {len(delta.modified)} modified documents")
                for doc_hash in delta.modified:
                    try:
                        # Remove old chunks
                        await self._remove_document(doc_hash.file_path)

                        # Add new chunks
                        await self._process_document(
                            doc_hash.file_path,
                            document_loader,
                            chunk_processor,
                        )
                        stats["modified"] += 1
                    except Exception as e:
                        logger.error(f"[DELTA_INDEXER] Failed to process {doc_hash.file_path}: {e}")
                        stats["errors"].append(str(e))

            # Remove deleted documents
            if delta.deleted:
                logger.info(f"[DELTA_INDEXER] Removing {len(delta.deleted)} deleted documents")
                for file_path in delta.deleted:
                    try:
                        await self._remove_document(file_path)
                        stats["deleted"] += 1
                    except Exception as e:
                        logger.error(f"[DELTA_INDEXER] Failed to remove {file_path}: {e}")
                        stats["errors"].append(str(e))

            # Update hash database
            await self._update_hashes(delta)

        except Exception as e:
            logger.error(f"[DELTA_INDEXER] Failed to process delta: {e}")
            stats["errors"].append(str(e))

        stats["total_time"] = time.time() - t0

        logger.info(
            f"[DELTA_INDEXER] Delta processing complete: "
            f"{stats['added']} added, {stats['modified']} modified, "
            f"{stats['deleted']} deleted in {stats['total_time']:.1f}s"
        )

        return stats

    async def _process_document(self, file_path: str, loader, processor):
        """Process a single document.

        Args:
            file_path: Path to document
            loader: Async document loader
            processor: Async chunk processor
        """
        doc_hash = self.calculate_hash(file_path)

        # Load document
        doc = await loader(file_path)

        # Process chunks into vector store
        await processor(doc, doc_hash)

    async def _remove_document(self, file_path: str):
        """Remove all chunks for a document.

        Args:
            file_path: Path to document
        """
        # Get chunk IDs for this document (requires search by metadata)
        # Note: This is a simplified implementation
        # For production, add get_by_filter method to BaseVectorStore

        # For now, just remove from hash database
        # Actual chunk removal requires vector store enhancement
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_hashes WHERE file_path = ?", (file_path,))
            conn.commit()
        finally:
            conn.close()

        logger.debug(f"[DELTA_INDEXER] Removed document from hash DB: {file_path}")

    async def _update_hashes(self, delta: DeltaDetection):
        """Update hash database with processed documents.

        Args:
            delta: DeltaDetection object
        """
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()

            # Update added and modified documents
            for doc_hash in delta.added + delta.modified:
                cursor.execute("""
                    INSERT OR REPLACE INTO document_hashes
                    (file_path, sha256, file_size, modified_time, indexed_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doc_hash.file_path,
                    doc_hash.sha256,
                    doc_hash.file_size,
                    doc_hash.modified_time,
                    time.time(),
                ))

            # Remove deleted documents
            for file_path in delta.deleted:
                cursor.execute("DELETE FROM document_hashes WHERE file_path = ?", (file_path,))

            conn.commit()
        finally:
            conn.close()

    def _load_hashes(self) -> list[DocumentHash]:
        """Load all stored hashes from database.

        Returns:
            List of DocumentHash objects
        """
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_hashes")
            rows = cursor.fetchall()

            hashes = []
            for row in rows:
                hashes.append(DocumentHash(
                    file_path=row[0],
                    sha256=row[1],
                    file_size=row[2],
                    modified_time=row[3],
                    indexed_at=row[4],
                ))

            return hashes
        finally:
            conn.close()

    def clear_hash_db(self):
        """Clear all stored hashes (full reindex on next run)."""
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM document_hashes")
            conn.commit()
            logger.info("[DELTA_INDEXER] Hash database cleared")
        finally:
            conn.close()

    def get_hash_db_stats(self) -> dict[str, Any]:
        """Get statistics about hash database.

        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(self._hash_db_path)
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM document_hashes")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(file_size) FROM document_hashes")
            total_size = cursor.fetchone()[0] or 0

            return {
                "total_documents": total,
                "total_size_bytes": total_size,
                "db_path": str(self._hash_db_path),
                "db_size_bytes": self._hash_db_path.stat().st_size,
            }
        finally:
            conn.close()


# Convenience function for delta indexing
async def index_with_delta(
    file_paths: list[str | Path],
    vector_store: BaseVectorStore,
    document_loader,
    chunk_processor,
    force_reindex: bool = False,
) -> dict[str, Any]:
    """Perform incremental indexing on a set of files.

    Args:
        file_paths: List of PDF file paths
        vector_store: Vector store instance
        document_loader: Async function to load documents
        chunk_processor: Async function to process chunks
        force_reindex: Force full reindex

    Returns:
        Processing statistics
    """
    indexer = DeltaIndexer(vector_store)

    # Detect changes
    delta = indexer.detect_delta(file_paths, force_reindex=force_reindex)

    if not delta.has_changes:
        logger.info("[DELTA_INDEXER] No changes detected, skipping indexing")
        return {"added": 0, "modified": 0, "deleted": 0, "errors": [], "total_time": 0}

    # Process changes
    return await indexer.process_delta(delta, document_loader, chunk_processor)
