"""Parent Document Store using SQLite.

Stores parent chunks separately from child chunks for efficient retrieval
during auto-merge search operations.

Author: Claude Code
Version: 0.8.0 - Phase 7.2: Parent Document Store
"""

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.pdf_framework.schemas.documents import DocumentChunk

logger = logging.getLogger(__name__)


class ParentDocumentStore:
    """
    SQLite-based storage for parent document chunks.

    Stores parent chunks separately from the vector store to enable
    efficient retrieval during auto-merge operations.
    """

    def __init__(self, db_path: Path | None = None):
        """
        Initialize parent document store.

        Args:
            db_path: Path to SQLite database file.
                    If None, uses data/parent_store.db
        """
        if db_path is None:
            db_path = Path.cwd() / "data" / "parent_store.db"

        self._db_path = db_path
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the database and create tables.

        Should be called before any other operations.
        """
        if self._initialized:
            return

        await asyncio.to_thread(self._create_table)
        self._initialized = True

        logger.info(f"[PARENT_STORE] Initialized: {self._db_path}")

    def _create_table(self) -> None:
        """Create the parent_documents table if it doesn't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_documents (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    chunk_index INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create index for document_id lookups
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_document_id
                ON parent_documents(document_id)
                """
            )

            conn.commit()
            logger.debug("[PARENT_STORE] Table created successfully")

        finally:
            conn.close()

    async def add_parents(self, chunks: list[DocumentChunk]) -> None:
        """
        Add parent chunks to the store.

        Args:
            chunks: List of parent chunks to store
        """
        if not chunks:
            return

        await asyncio.to_thread(self._add_parents_sync, chunks)
        logger.info(f"[PARENT_STORE] Added {len(chunks)} parent chunks")

    def _add_parents_sync(self, chunks: list[DocumentChunk]) -> None:
        """Synchronous implementation of add_parents."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            for chunk in chunks:
                metadata_json = json.dumps(chunk.metadata, ensure_ascii=False)

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO parent_documents
                    (id, document_id, content, metadata, chunk_index, char_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.content,
                        metadata_json,
                        chunk.chunk_index,
                        len(chunk.content),
                    ),
                )

            conn.commit()

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"[PARENT_STORE] Error adding parents: {e}")
            raise
        finally:
            conn.close()

    async def get_parent(self, parent_id: str) -> DocumentChunk | None:
        """
        Retrieve a single parent chunk by ID.

        Args:
            parent_id: ID of the parent chunk

        Returns:
            DocumentChunk if found, None otherwise
        """
        return await asyncio.to_thread(self._get_parent_sync, parent_id)

    def _get_parent_sync(self, parent_id: str) -> DocumentChunk | None:
        """Synchronous implementation of get_parent."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, document_id, content, metadata, chunk_index
                FROM parent_documents
                WHERE id = ?
                """,
                (parent_id,),
            )

            row = cursor.fetchone()
            if row:
                return self._row_to_chunk(row)

            return None

        finally:
            conn.close()

    async def get_parents(self, parent_ids: list[str]) -> list[DocumentChunk]:
        """
        Retrieve multiple parent chunks by their IDs.

        Args:
            parent_ids: List of parent chunk IDs

        Returns:
            List of DocumentChunk objects (only those found)
        """
        if not parent_ids:
            return []

        return await asyncio.to_thread(self._get_parents_sync, parent_ids)

    def _get_parents_sync(self, parent_ids: list[str]) -> list[DocumentChunk]:
        """Synchronous implementation of get_parents."""
        if not parent_ids:
            return []

        conn = sqlite3.connect(self._db_path)
        try:
            placeholders = ",".join("?" * len(parent_ids))
            query = f"""
                SELECT id, document_id, content, metadata, chunk_index
                FROM parent_documents
                WHERE id IN ({placeholders})
            """

            cursor = conn.cursor()
            cursor.execute(query, parent_ids)

            chunks = []
            for row in cursor.fetchall():
                chunks.append(self._row_to_chunk(row))

            return chunks

        finally:
            conn.close()

    async def get_parents_by_document(self, document_id: str) -> list[DocumentChunk]:
        """
        Retrieve all parent chunks for a specific document.

        Args:
            document_id: Document ID

        Returns:
            List of parent chunks ordered by chunk_index
        """
        return await asyncio.to_thread(self._get_parents_by_document_sync, document_id)

    def _get_parents_by_document_sync(self, document_id: str) -> list[DocumentChunk]:
        """Synchronous implementation of get_parents_by_document."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, document_id, content, metadata, chunk_index
                FROM parent_documents
                WHERE document_id = ?
                ORDER BY chunk_index
                """,
                (document_id,),
            )

            chunks = []
            for row in cursor.fetchall():
                chunks.append(self._row_to_chunk(row))

            return chunks

        finally:
            conn.close()

    async def delete(self, parent_ids: list[str]) -> int:
        """
        Delete parent chunks by their IDs.

        Args:
            parent_ids: List of parent chunk IDs to delete

        Returns:
            Number of chunks deleted
        """
        if not parent_ids:
            return 0

        return await asyncio.to_thread(self._delete_sync, parent_ids)

    def _delete_sync(self, parent_ids: list[str]) -> int:
        """Synchronous implementation of delete."""
        conn = sqlite3.connect(self._db_path)
        try:
            placeholders = ",".join("?" * len(parent_ids))
            query = f"DELETE FROM parent_documents WHERE id IN ({placeholders})"

            cursor = conn.cursor()
            cursor.execute(query, parent_ids)
            deleted_count = cursor.rowcount
            conn.commit()

            logger.debug(f"[PARENT_STORE] Deleted {deleted_count} parent chunks")
            return deleted_count

        finally:
            conn.close()

    async def delete_by_document(self, document_id: str) -> int:
        """
        Delete all parent chunks for a specific document.

        Args:
            document_id: Document ID

        Returns:
            Number of chunks deleted
        """
        return await asyncio.to_thread(self._delete_by_document_sync, document_id)

    def _delete_by_document_sync(self, document_id: str) -> int:
        """Synchronous implementation of delete_by_document."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM parent_documents WHERE document_id = ?",
                (document_id,),
            )
            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"[PARENT_STORE] Deleted {deleted_count} chunks for document {document_id}")
            return deleted_count

        finally:
            conn.close()

    async def clear(self) -> None:
        """Delete all parent chunks from the store."""
        await asyncio.to_thread(self._clear_sync)
        logger.info("[PARENT_STORE] Cleared all parent chunks")

    def _clear_sync(self) -> None:
        """Synchronous implementation of clear."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("DELETE FROM parent_documents")
            conn.commit()
        finally:
            conn.close()

    async def count(self) -> int:
        """
        Get the total number of parent chunks in the store.

        Returns:
            Number of parent chunks
        """
        return await asyncio.to_thread(self._count_sync)

    def _count_sync(self) -> int:
        """Synchronous implementation of count."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM parent_documents")
            count = cursor.fetchone()[0]
            return count
        finally:
            conn.close()

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the parent document store.

        Returns:
            Statistics dictionary
        """
        return await asyncio.to_thread(self._get_statistics_sync)

    def _get_statistics_sync(self) -> dict[str, Any]:
        """Synchronous implementation of get_statistics."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) FROM parent_documents")
            total_count = cursor.fetchone()[0]

            # Count by document
            cursor.execute(
                """
                SELECT document_id, COUNT(*) as count
                FROM parent_documents
                GROUP BY document_id
                """
            )
            docs_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Average char count
            cursor.execute("SELECT AVG(char_count) FROM parent_documents")
            avg_size = cursor.fetchone()[0] or 0

            return {
                "total_parents": total_count,
                "documents_count": len(docs_counts),
                "avg_char_count": round(avg_size, 1),
                "parents_by_document": docs_counts,
            }

        finally:
            conn.close()

    def _row_to_chunk(self, row: tuple) -> DocumentChunk:
        """Convert a database row to a DocumentChunk."""
        id_, document_id, content, metadata_json, chunk_index = row

        return DocumentChunk(
            id=id_,
            document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            metadata=json.loads(metadata_json),
        )
