"""Tests for tenant vector store manager (Phase 12.1)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.multitenancy.tenant_store import (
    TenantMetadata,
    TenantVectorStoreManager,
    get_tenant_store_manager,
)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "tenants.db"


@pytest.fixture
def manager(tmp_db, tmp_path):
    """Create a TenantVectorStoreManager with mocked ChromaVectorStore."""
    settings = VectorStoreSettings(persist_dir=tmp_path / "vector_db")

    mgr = TenantVectorStoreManager(settings=settings, metadata_db=tmp_db)

    # Mock the store class to avoid real ChromaDB — return fresh mock per call
    def _make_store(*args, **kwargs):
        store = AsyncMock()
        store.initialize = AsyncMock()
        store.count = AsyncMock(return_value=0)
        store.clear = AsyncMock()
        return store

    mgr._store_class = MagicMock(side_effect=_make_store)
    return mgr


# ---------------------------------------------------------------------------
# sanitize_tenant_id
# ---------------------------------------------------------------------------

class TestSanitizeTenantId:
    def test_alphanumeric_passthrough(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._sanitize_tenant_id("tenant123") == "tenant123"

    def test_special_chars_replaced(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._sanitize_tenant_id("org@domain.com") == "org_domain_com"

    def test_length_limited_to_63(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        long_id = "a" * 100
        assert len(mgr._sanitize_tenant_id(long_id)) == 63

    def test_hyphens_preserved(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._sanitize_tenant_id("my-org") == "my-org"

    def test_underscores_preserved(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._sanitize_tenant_id("my_org") == "my_org"


# ---------------------------------------------------------------------------
# get_collection_name
# ---------------------------------------------------------------------------

class TestGetCollectionName:
    def test_prefix(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._get_collection_name("org1") == "tenant_org1"

    def test_sanitized(self):
        mgr = TenantVectorStoreManager.__new__(TenantVectorStoreManager)
        assert mgr._get_collection_name("my@org") == "tenant_my_org"


# ---------------------------------------------------------------------------
# get_store
# ---------------------------------------------------------------------------

class TestGetStore:
    @pytest.mark.asyncio
    async def test_creates_store_on_first_access(self, manager):
        store = await manager.get_store("tenant-a")
        assert store is not None
        manager._store_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_caches_store(self, manager):
        store1 = await manager.get_store("tenant-a")
        store2 = await manager.get_store("tenant-a")
        assert store1 is store2
        # Should only create once
        assert manager._store_class.call_count == 1

    @pytest.mark.asyncio
    async def test_different_tenants_get_different_stores(self, manager):
        store_a = await manager.get_store("tenant-a")
        store_b = await manager.get_store("tenant-b")
        assert store_a is not store_b

    @pytest.mark.asyncio
    async def test_store_initialized(self, manager):
        store = await manager.get_store("tenant-a")
        store.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_settings_with_correct_persist_dir(self, manager, tmp_path):
        await manager.get_store("tenant-a")
        call_args = manager._store_class.call_args
        settings_arg = call_args[0][0]
        assert isinstance(settings_arg, VectorStoreSettings)
        assert settings_arg.persist_dir == tmp_path / "vector_db"


# ---------------------------------------------------------------------------
# create_tenant / list_tenants / get_tenant_metadata
# ---------------------------------------------------------------------------

class TestTenantCRUD:
    @pytest.mark.asyncio
    async def test_create_tenant_returns_metadata(self, manager):
        metadata = await manager.create_tenant("org-1")
        assert isinstance(metadata, TenantMetadata)
        assert metadata.tenant_id == "org-1"
        assert metadata.collection_name == "tenant_org-1"

    @pytest.mark.asyncio
    async def test_list_tenants_empty(self, manager):
        tenants = await manager.list_tenants()
        assert tenants == []

    @pytest.mark.asyncio
    async def test_list_tenants_after_create(self, manager):
        await manager.create_tenant("org-1")
        await manager.create_tenant("org-2")
        tenants = await manager.list_tenants()
        assert "org-1" in tenants
        assert "org-2" in tenants

    @pytest.mark.asyncio
    async def test_get_tenant_metadata(self, manager):
        await manager.create_tenant("org-test")
        metadata = await manager.get_tenant_metadata("org-test")
        assert metadata is not None
        assert metadata.tenant_id == "org-test"
        assert metadata.document_count == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_metadata(self, manager):
        metadata = await manager.get_tenant_metadata("nonexistent")
        assert metadata is None


# ---------------------------------------------------------------------------
# delete_tenant
# ---------------------------------------------------------------------------

class TestDeleteTenant:
    @pytest.mark.asyncio
    async def test_delete_removes_from_cache(self, manager):
        await manager.create_tenant("org-del")
        assert "org-del" in manager._store_cache
        await manager.delete_tenant("org-del")
        assert "org-del" not in manager._store_cache

    @pytest.mark.asyncio
    async def test_delete_removes_from_metadata(self, manager):
        await manager.create_tenant("org-del")
        await manager.delete_tenant("org-del")
        metadata = await manager.get_tenant_metadata("org-del")
        assert metadata is None

    @pytest.mark.asyncio
    async def test_delete_calls_clear_on_store(self, manager):
        await manager.create_tenant("org-del")
        store = manager._store_cache["org-del"]
        await manager.delete_tenant("org-del")
        store.clear.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_all_tenants_metadata
# ---------------------------------------------------------------------------

class TestGetAllTenantsMetadata:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self, manager):
        result = await manager.get_all_tenants_metadata()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all(self, manager):
        await manager.create_tenant("a")
        await manager.create_tenant("b")
        result = await manager.get_all_tenants_metadata()
        assert len(result) == 2
        ids = [m.tenant_id for m in result]
        assert "a" in ids
        assert "b" in ids


# ---------------------------------------------------------------------------
# shutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    @pytest.mark.asyncio
    async def test_clears_cache(self, manager):
        await manager.create_tenant("org-1")
        assert len(manager._store_cache) > 0
        await manager.shutdown()
        assert len(manager._store_cache) == 0


# ---------------------------------------------------------------------------
# TenantMetadata model
# ---------------------------------------------------------------------------

class TestTenantMetadata:
    def test_model_fields(self):
        tm = TenantMetadata(
            tenant_id="org",
            collection_name="tenant_org",
            created_at="2024-01-01T00:00:00",
            document_count=42,
            storage_bytes=1024,
            last_activity="2024-01-02T00:00:00",
        )
        assert tm.tenant_id == "org"
        assert tm.document_count == 42


# ---------------------------------------------------------------------------
# get_tenant_store_manager singleton
# ---------------------------------------------------------------------------

class TestGetTenantStoreManager:
    def test_returns_instance(self):
        import src.pdf_framework.multitenancy.tenant_store as mod
        mod._tenant_store_manager = None

        mgr = get_tenant_store_manager()
        assert isinstance(mgr, TenantVectorStoreManager)

        # Cleanup
        mod._tenant_store_manager = None

    def test_returns_same_instance(self):
        import src.pdf_framework.multitenancy.tenant_store as mod
        mod._tenant_store_manager = None

        m1 = get_tenant_store_manager()
        m2 = get_tenant_store_manager()
        assert m1 is m2

        # Cleanup
        mod._tenant_store_manager = None
