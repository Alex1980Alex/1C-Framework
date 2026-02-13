"""Document metadata registry for Multi-Document KB (Phase 32).

Stores enhanced metadata for indexed documents: title, description, tags,
file info. This supplements the vector store metadata (which stores per-chunk info)
with per-document metadata for browsing, filtering, and collection management.
"""

import logging
import time
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DocumentRecord(BaseModel):
    """Registered document with rich metadata."""

    document_id: str
    source_path: str
    filename: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    chunk_count: int = 0
    page_count: int = 0
    file_size_bytes: int = 0
    indexed_at: float = 0.0
    updated_at: float = 0.0
    status: str = "indexed"  # indexed | indexing | failed
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentRegistry:
    """SQLite-backed document metadata registry.

    Tracks all indexed documents with their metadata, status, and associations.
    Works alongside the vector store — the registry stores document-level info
    while the vector store stores chunk-level data.
    """

    def __init__(self, db_path: str | Path = "data/document_registry.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables if not exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    filename TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',
                    chunk_count INTEGER DEFAULT 0,
                    page_count INTEGER DEFAULT 0,
                    file_size_bytes INTEGER DEFAULT 0,
                    indexed_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    status TEXT DEFAULT 'indexed',
                    extra TEXT DEFAULT '{}'
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_docs_source
                ON documents(source_path)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_docs_status
                ON documents(status)
            """)

            await db.commit()

        self._initialized = True
        logger.info("[REGISTRY] Initialized: %s", self._db_path)

    async def register(
        self,
        document_id: str,
        source_path: str,
        chunk_count: int = 0,
        page_count: int = 0,
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
        status: str = "indexed",
    ) -> DocumentRecord:
        """Register or update a document in the registry.

        Uses INSERT OR REPLACE — re-indexing the same document updates the record.
        """
        await self.initialize()

        now = time.time()
        filename = Path(source_path).name if source_path else ""
        file_size = 0
        if source_path and Path(source_path).exists():
            file_size = Path(source_path).stat().st_size

        tags_list = tags or []

        async with aiosqlite.connect(self._db_path) as db:
            # Check if exists to preserve user-set fields
            cursor = await db.execute(
                "SELECT title, description, tags FROM documents WHERE document_id = ?",
                (document_id,),
            )
            existing = await cursor.fetchone()

            if existing:
                # Preserve user-set title/description/tags if not provided
                title = title or existing[0] or ""
                description = description or existing[1] or ""
                if not tags:
                    tags_list = _parse_tags(existing[2])

            await db.execute(
                "INSERT OR REPLACE INTO documents "
                "(document_id, source_path, filename, title, description, tags, "
                " chunk_count, page_count, file_size_bytes, indexed_at, updated_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document_id, source_path, filename, title, description,
                    str(tags_list), chunk_count, page_count, file_size,
                    now, now, status,
                ),
            )
            await db.commit()

        logger.info(
            "[REGISTRY] Registered '%s' (%d chunks, %d pages)",
            filename, chunk_count, page_count,
        )
        return DocumentRecord(
            document_id=document_id,
            source_path=source_path,
            filename=filename,
            title=title,
            description=description,
            tags=tags_list,
            chunk_count=chunk_count,
            page_count=page_count,
            file_size_bytes=file_size,
            indexed_at=now,
            updated_at=now,
            status=status,
        )

    async def get(self, document_id: str) -> DocumentRecord | None:
        """Get document record by ID."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return _row_to_record(row)

    async def get_by_source(self, source_path: str) -> DocumentRecord | None:
        """Get document record by source path."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM documents WHERE source_path = ?", (source_path,)
            )
            row = await cursor.fetchone()

        if row is None:
            return None

        return _row_to_record(row)

    async def list_all(self, status: str | None = None) -> list[DocumentRecord]:
        """List all registered documents, optionally filtered by status."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM documents WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM documents ORDER BY updated_at DESC"
                )
            rows = await cursor.fetchall()

        return [_row_to_record(row) for row in rows]

    async def update_metadata(
        self,
        document_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> DocumentRecord | None:
        """Update user-facing metadata for a document."""
        await self.initialize()

        existing = await self.get(document_id)
        if existing is None:
            return None

        now = time.time()
        new_title = title if title is not None else existing.title
        new_desc = description if description is not None else existing.description
        new_tags = tags if tags is not None else existing.tags

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE documents SET title = ?, description = ?, tags = ?, updated_at = ? "
                "WHERE document_id = ?",
                (new_title, new_desc, str(new_tags), now, document_id),
            )
            await db.commit()

        return await self.get(document_id)

    async def update_status(self, document_id: str, status: str) -> None:
        """Update document status (indexed/indexing/failed)."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE documents SET status = ?, updated_at = ? WHERE document_id = ?",
                (status, time.time(), document_id),
            )
            await db.commit()

    async def update_chunk_count(self, document_id: str, chunk_count: int) -> None:
        """Update chunk count after indexing."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE documents SET chunk_count = ?, updated_at = ? WHERE document_id = ?",
                (chunk_count, time.time(), document_id),
            )
            await db.commit()

    async def delete(self, document_id: str) -> bool:
        """Delete a document record. Returns True if deleted."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM documents WHERE document_id = ?", (document_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def count(self, status: str | None = None) -> int:
        """Count registered documents."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            if status:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM documents WHERE status = ?", (status,)
                )
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM documents")
            row = await cursor.fetchone()

        return row[0] if row else 0


def _parse_tags(raw: str | None) -> list[str]:
    """Parse tags from SQLite storage."""
    if not raw or raw == "[]":
        return []
    try:
        import ast
        result = ast.literal_eval(raw)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []


def _parse_extra(raw: str | None) -> dict[str, Any]:
    """Parse extra JSON from SQLite storage."""
    if not raw or raw == "{}":
        return {}
    try:
        import json
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def _row_to_record(row: aiosqlite.Row) -> DocumentRecord:
    """Convert SQLite row to DocumentRecord."""
    return DocumentRecord(
        document_id=row["document_id"],
        source_path=row["source_path"],
        filename=row["filename"],
        title=row["title"],
        description=row["description"],
        tags=_parse_tags(row["tags"]),
        chunk_count=row["chunk_count"],
        page_count=row["page_count"],
        file_size_bytes=row["file_size_bytes"],
        indexed_at=row["indexed_at"],
        updated_at=row["updated_at"],
        status=row["status"],
        extra=_parse_extra(row["extra"]),
    )
