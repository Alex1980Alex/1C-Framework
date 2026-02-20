"""Tenant-isolated vector store manager (Phase 12.1, Phase 60).

Each tenant gets a separate ChromaDB collection for complete data isolation.
Phase 60: Added quota enforcement and tenant management API.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from src.pdf_framework.schemas.tenant import TenantQuota

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from pydantic import BaseModel

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class TenantMetadata(BaseModel):
    """Metadata about a tenant."""

    tenant_id: str
    collection_name: str
    created_at: str
    document_count: int
    storage_bytes: int
    last_activity: str


class TenantVectorStoreManager:
    """
    Manages isolated vector stores per tenant.

    Each tenant gets a separate ChromaDB collection:
    - Complete data isolation
    - Lazy initialization (collection created on first use)
    - In-memory cache for fast access
    - SQLite metadata registry
    """

    def __init__(
        self,
        settings: VectorStoreSettings | None = None,
        metadata_db: str | Path = "data/tenants/tenants.db",
    ):
        """
        Initialize tenant vector store manager.

        Args:
            settings: Vector store settings for creating stores
            metadata_db: Path to SQLite metadata database
        """
        from src.pdf_framework.vector_store.providers.chroma import ChromaVectorStore

        self._settings = settings or VectorStoreSettings()
        self._metadata_db = Path(metadata_db)
        self._metadata_db.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache of active stores
        self._store_cache: dict[str, BaseVectorStore] = {}
        self._store_lock = asyncio.Lock()

        # Base store class for creating new tenant stores
        self._store_class = ChromaVectorStore

    def _sanitize_tenant_id(self, tenant_id: str) -> str:
        """
        Sanitize tenant ID for use in collection names.

        Only alphanumeric and underscore allowed.

        Args:
            tenant_id: Raw tenant ID

        Returns:
            Sanitized tenant ID
        """
        # Replace non-alphanumeric with underscore
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", tenant_id)
        # Limit length
        return sanitized[:63]  # ChromaDB collection name limit

    def _get_collection_name(self, tenant_id: str) -> str:
        """Get ChromaDB collection name for tenant."""
        sanitized = self._sanitize_tenant_id(tenant_id)
        return f"tenant_{sanitized}"

    async def _ensure_metadata_table(self) -> None:
        """Create metadata table if not exists."""
        async with aiosqlite.connect(self._metadata_db) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    collection_name TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    document_count INTEGER DEFAULT 0,
                    storage_bytes INTEGER DEFAULT 0,
                    last_activity TEXT NOT NULL
                )
            """)
            await db.commit()

    async def get_store(self, tenant_id: str) -> BaseVectorStore:
        """
        Get or create vector store for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Vector store instance for tenant
        """
        # Check cache first
        if tenant_id in self._store_cache:
            await self._update_last_activity(tenant_id)
            return self._store_cache[tenant_id]

        async with self._store_lock:
            # Double-check after acquiring lock
            if tenant_id in self._store_cache:
                return self._store_cache[tenant_id]

            # Create new store
            collection_name = self._get_collection_name(tenant_id)

            # Create tenant-specific settings
            tenant_settings = VectorStoreSettings(
                provider=self._settings.provider,
                collection_name=collection_name,
                persist_dir=self._settings.persist_dir,
                distance_metric=self._settings.distance_metric,
            )

            store = self._store_class(tenant_settings)
            await store.initialize()

            # Cache store
            self._store_cache[tenant_id] = store

            # Update metadata
            await self._ensure_metadata_table()
            await self._register_tenant(tenant_id, collection_name)

            logger.info(f"[TENANT] Created vector store for tenant '{tenant_id}' (collection: {collection_name})")

            return store

    async def _register_tenant(self, tenant_id: str, collection_name: str) -> None:
        """Register tenant in metadata database."""
        async with aiosqlite.connect(self._metadata_db) as db:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("""
                INSERT OR IGNORE INTO tenants
                (tenant_id, collection_name, created_at, last_activity)
                VALUES (?, ?, ?, ?)
            """, (tenant_id, collection_name, now, now))
            await db.commit()

    async def _update_last_activity(self, tenant_id: str) -> None:
        """Update last activity timestamp for tenant."""
        async with aiosqlite.connect(self._metadata_db) as db:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("""
                UPDATE tenants SET last_activity = ? WHERE tenant_id = ?
            """, (now, tenant_id))
            await db.commit()

    async def create_tenant(self, tenant_id: str) -> TenantMetadata:
        """
        Explicitly create a tenant (also happens lazily on first access).

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant metadata
        """
        await self.get_store(tenant_id)  # Lazy creation
        return await self.get_tenant_metadata(tenant_id)

    async def delete_tenant(self, tenant_id: str) -> None:
        """
        Delete tenant and all data (GDPR right to erasure).

        Args:
            tenant_id: Tenant to delete
        """
        async with self._store_lock:
            # Get store
            store = self._store_cache.get(tenant_id)
            if store:
                # Clear and delete collection
                await store.clear()
                del self._store_cache[tenant_id]

            # Delete from metadata
            await self._ensure_metadata_table()
            async with aiosqlite.connect(self._metadata_db) as db:
                await db.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
                await db.commit()

            logger.info(f"[TENANT] Deleted tenant '{tenant_id}' and all data")

    async def list_tenants(self) -> list[str]:
        """
        List all tenant IDs.

        Returns:
            List of tenant IDs
        """
        await self._ensure_metadata_table()
        async with aiosqlite.connect(self._metadata_db) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT tenant_id FROM tenants ORDER BY tenant_id")
            rows = await cursor.fetchall()
            return [row["tenant_id"] for row in rows]

    async def get_tenant_metadata(self, tenant_id: str) -> TenantMetadata | None:
        """
        Get metadata for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant metadata or None if not found
        """
        await self._ensure_metadata_table()
        async with aiosqlite.connect(self._metadata_db) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM tenants WHERE tenant_id = ?
            """, (tenant_id,))
            row = await cursor.fetchone()

            if row:
                return TenantMetadata(
                    tenant_id=row["tenant_id"],
                    collection_name=row["collection_name"],
                    created_at=row["created_at"],
                    document_count=row["document_count"],
                    storage_bytes=row["storage_bytes"],
                    last_activity=row["last_activity"],
                )
            return None

    async def get_all_tenants_metadata(self) -> list[TenantMetadata]:
        """
        Get metadata for all tenants.

        Returns:
            List of tenant metadata
        """
        await self._ensure_metadata_table()
        async with aiosqlite.connect(self._metadata_db) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM tenants ORDER BY tenant_id
            """)
            rows = await cursor.fetchall()

            return [
                TenantMetadata(
                    tenant_id=row["tenant_id"],
                    collection_name=row["collection_name"],
                    created_at=row["created_at"],
                    document_count=row["document_count"],
                    storage_bytes=row["storage_bytes"],
                    last_activity=row["last_activity"],
                )
                for row in rows
            ]

    async def iterate_tenants(self) -> AsyncIterator[tuple[str, BaseVectorStore]]:
        """
        Iterate over all active tenant stores.

        Yields:
            (tenant_id, vector_store) tuples
        """
        for tenant_id in await self.list_tenants():
            store = await self.get_store(tenant_id)
            yield tenant_id, store

    async def shutdown(self) -> None:
        """Cleanup and close all stores."""
        async with self._store_lock:
            self._store_cache.clear()
            logger.info("[TENANT] Shutdown complete, all stores cleared")

    # Phase 60: Quota enforcement methods

    async def set_quota(self, tenant_id: str, quota: TenantQuota) -> None:
        """Set quota for tenant.

        Args:
            tenant_id: Tenant ID
            quota: Quota limits
        """
        async with aiosqlite.connect(self._metadata_db) as db:
            # Add quota column if not exists
            try:
                await db.execute("""
                    ALTER TABLE tenants ADD COLUMN quota_json TEXT
                """)
            except Exception:
                pass  # Column already exists

        # Store quota as JSON
        import json
        async with aiosqlite.connect(self._metadata_db) as db:
            await db.execute("""
                UPDATE tenants SET quota_json = ? WHERE tenant_id = ?
            """, (quota.model_dump_json(), tenant_id))
            await db.commit()

    async def get_quota(self, tenant_id: str) -> Optional[TenantQuota]:
        """Get quota for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            TenantQuota or default quota
        """
        import json
        async with aiosqlite.connect(self._metadata_db) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT quota_json FROM tenants WHERE tenant_id = ?
            """, (tenant_id,))
            row = await cursor.fetchone()

            if row and row["quota_json"]:
                return TenantQuota.model_validate_json(row["quota_json"])

            # Return default quota
            return TenantQuota()

    async def check_quota(self, tenant_id: str) -> list[str]:
        """Check if tenant has exceeded any quotas.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of exceeded quota names
        """
        metadata = await self.get_tenant_metadata(tenant_id)
        if not metadata:
            return ["Tenant not found"]

        quota = await self.get_quota(tenant_id)
        exceeded = []

        if metadata.document_count >= quota.max_documents:
            exceeded.append("max_documents")
        if metadata.storage_bytes >= quota.max_storage_mb * 1024 * 1024:
            exceeded.append("max_storage_mb")

        return exceeded

    async def increment_query_count(self, tenant_id: str) -> bool:
        """Increment daily query count for tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            True if within quota, False if exceeded
        """
        quota = await self.get_quota(tenant_id)

        # Check daily query quota
        today = datetime.now(timezone.utc).date().isoformat()

        async with aiosqlite.connect(self._metadata_db) as db:
            # Ensure query_stats table exists
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tenant_query_stats (
                    tenant_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    query_count INTEGER DEFAULT 0,
                    PRIMARY KEY (tenant_id, date)
                )
            """)

            # Get current count
            cursor = await db.execute("""
                SELECT query_count FROM tenant_query_stats
                WHERE tenant_id = ? AND date = ?
            """, (tenant_id, today))
            row = await cursor.fetchone()

            current_count = row[0] if row else 0

            if current_count >= quota.max_queries_per_day:
                return False

            # Increment count
            await db.execute("""
                INSERT INTO tenant_query_stats (tenant_id, date, query_count)
                VALUES (?, ?, 1)
                ON CONFLICT (tenant_id, date) DO UPDATE SET
                query_count = query_count + 1
            """, (tenant_id, today))
            await db.commit()

        return True


# Global tenant store manager instance
_tenant_store_manager: TenantVectorStoreManager | None = None


def get_tenant_store_manager(**kwargs) -> TenantVectorStoreManager:
    """Get or create global tenant store manager instance."""
    global _tenant_store_manager
    if _tenant_store_manager is None:
        _tenant_store_manager = TenantVectorStoreManager(**kwargs)
    return _tenant_store_manager
