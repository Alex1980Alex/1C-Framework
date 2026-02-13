"""Collection management for Multi-Document KB (Phase 32).

Provides CRUD operations for document collections — groups of related documents
that can be searched together. Backed by SQLite for persistence.

Collections enable:
- Grouping PDFs by project/topic/department
- Collection-scoped search (search within a specific collection)
- Cross-document analysis within a collection
"""

import logging
import time
from pathlib import Path

import aiosqlite
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Collection(BaseModel):
    """A named collection of documents."""

    id: str
    name: str
    description: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    document_count: int = 0
    tags: list[str] = Field(default_factory=list)


class CollectionDocument(BaseModel):
    """Association between a collection and a document."""

    collection_id: str
    document_id: str
    added_at: float = 0.0


class CollectionStore:
    """SQLite-backed collection management.

    Manages collections (groups of documents) with CRUD operations
    and document-collection associations.
    """

    def __init__(self, db_path: str | Path = "data/collections.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables if not exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    tags TEXT DEFAULT '[]'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS collection_documents (
                    collection_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    added_at REAL NOT NULL,
                    PRIMARY KEY (collection_id, document_id),
                    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_cd_document
                ON collection_documents(document_id)
            """)

            await db.commit()

        self._initialized = True
        logger.info("[COLLECTIONS] Initialized: %s", self._db_path)

    async def create(
        self,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> Collection:
        """Create a new collection.

        Args:
            name: Unique collection name.
            description: Optional description.
            tags: Optional list of tags.

        Returns:
            Created Collection object.

        Raises:
            ValueError: If collection with this name already exists.
        """
        await self.initialize()

        import hashlib

        now = time.time()
        collection_id = hashlib.sha256(
            f"{name}_{now}".encode()
        ).hexdigest()[:12]
        tags_list = tags or []

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO collections (id, name, description, created_at, updated_at, tags) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (collection_id, name, description, now, now, str(tags_list)),
                )
                await db.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"Collection '{name}' already exists")

        logger.info("[COLLECTIONS] Created '%s' (id=%s)", name, collection_id)
        return Collection(
            id=collection_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            tags=tags_list,
        )

    async def get(self, collection_id: str) -> Collection | None:
        """Get a collection by ID."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM collections WHERE id = ?", (collection_id,)
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            # Count documents
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM collection_documents WHERE collection_id = ?",
                (collection_id,),
            )
            count_row = await count_cursor.fetchone()
            doc_count = count_row[0] if count_row else 0

        return Collection(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            document_count=doc_count,
            tags=_parse_tags(row["tags"]),
        )

    async def get_by_name(self, name: str) -> Collection | None:
        """Get a collection by name."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM collections WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM collection_documents WHERE collection_id = ?",
                (row["id"],),
            )
            count_row = await count_cursor.fetchone()
            doc_count = count_row[0] if count_row else 0

        return Collection(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            document_count=doc_count,
            tags=_parse_tags(row["tags"]),
        )

    async def list_all(self) -> list[Collection]:
        """List all collections with document counts."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT c.*, "
                "(SELECT COUNT(*) FROM collection_documents cd WHERE cd.collection_id = c.id) "
                "AS document_count "
                "FROM collections c ORDER BY c.updated_at DESC"
            )
            rows = await cursor.fetchall()

        return [
            Collection(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                document_count=row["document_count"],
                tags=_parse_tags(row["tags"]),
            )
            for row in rows
        ]

    async def update(
        self,
        collection_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Collection | None:
        """Update collection fields. Returns updated collection or None if not found."""
        await self.initialize()

        existing = await self.get(collection_id)
        if existing is None:
            return None

        now = time.time()
        new_name = name if name is not None else existing.name
        new_desc = description if description is not None else existing.description
        new_tags = tags if tags is not None else existing.tags

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "UPDATE collections SET name = ?, description = ?, tags = ?, updated_at = ? "
                    "WHERE id = ?",
                    (new_name, new_desc, str(new_tags), now, collection_id),
                )
                await db.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"Collection name '{new_name}' already taken")

        return await self.get(collection_id)

    async def delete(self, collection_id: str) -> bool:
        """Delete a collection and its document associations. Returns True if deleted."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            # CASCADE handles collection_documents
            cursor = await db.execute(
                "DELETE FROM collections WHERE id = ?", (collection_id,)
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("[COLLECTIONS] Deleted collection %s", collection_id)
        return deleted

    # ---- Document association ----

    async def add_document(self, collection_id: str, document_id: str) -> bool:
        """Add a document to a collection. Returns True if added (False if already in)."""
        await self.initialize()

        now = time.time()
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO collection_documents (collection_id, document_id, added_at) "
                    "VALUES (?, ?, ?)",
                    (collection_id, document_id, now),
                )
                # Touch collection updated_at
                await db.execute(
                    "UPDATE collections SET updated_at = ? WHERE id = ?",
                    (now, collection_id),
                )
                await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_document(self, collection_id: str, document_id: str) -> bool:
        """Remove a document from a collection."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM collection_documents WHERE collection_id = ? AND document_id = ?",
                (collection_id, document_id),
            )
            if cursor.rowcount > 0:
                await db.execute(
                    "UPDATE collections SET updated_at = ? WHERE id = ?",
                    (time.time(), collection_id),
                )
            await db.commit()
            return cursor.rowcount > 0

    async def get_document_ids(self, collection_id: str) -> list[str]:
        """Get all document IDs in a collection."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT document_id FROM collection_documents "
                "WHERE collection_id = ? ORDER BY added_at",
                (collection_id,),
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def get_collections_for_document(self, document_id: str) -> list[str]:
        """Get collection IDs that contain a document."""
        await self.initialize()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT collection_id FROM collection_documents WHERE document_id = ?",
                (document_id,),
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]


def _parse_tags(raw: str) -> list[str]:
    """Parse tags string from SQLite (stored as Python list repr)."""
    if not raw or raw == "[]":
        return []
    try:
        import ast
        result = ast.literal_eval(raw)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []
