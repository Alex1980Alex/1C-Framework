"""Tests for tenant graph store (Phase 12.2)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.multitenancy.tenant_graph import (
    TenantGraphManager,
    TenantGraphStore,
    _sanitize_tenant_id,
    get_tenant_graph_manager,
)
from src.pdf_framework.schemas.entities import Entity, Relation, SubGraph


# ---------------------------------------------------------------------------
# _sanitize_tenant_id
# ---------------------------------------------------------------------------

class TestSanitizeTenantId:
    def test_simple(self):
        assert _sanitize_tenant_id("org123") == "org123"

    def test_special_chars(self):
        assert _sanitize_tenant_id("a@b.c") == "a_b_c"

    def test_max_length(self):
        assert len(_sanitize_tenant_id("x" * 100)) == 63

    def test_hyphens_kept(self):
        assert _sanitize_tenant_id("my-org") == "my-org"


# ---------------------------------------------------------------------------
# TenantGraphStore init
# ---------------------------------------------------------------------------

class TestTenantGraphStoreInit:
    def test_creates_graph_dir(self, tmp_path):
        graph_dir = tmp_path / "graphs"
        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance._persist_path = None
        mock_class.return_value = mock_instance

        store = TenantGraphStore("t1", mock_class, graph_dir=graph_dir)
        assert graph_dir.exists()

    def test_sets_persist_path(self, tmp_path):
        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance._persist_path = Path("old_path")
        mock_class.return_value = mock_instance

        store = TenantGraphStore("t1", mock_class, graph_dir=tmp_path)
        expected_path = tmp_path / "tenant_t1.json"
        assert mock_instance._persist_path == expected_path

    def test_graph_path_uses_sanitized_id(self, tmp_path):
        mock_class = MagicMock()
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        store = TenantGraphStore("org@domain", mock_class, graph_dir=tmp_path)
        assert store._graph_path == tmp_path / "tenant_org_domain.json"


# ---------------------------------------------------------------------------
# TenantGraphStore methods with real NetworkX
# ---------------------------------------------------------------------------

class TestTenantGraphStoreIntegration:
    """Integration tests using real NetworkXGraphStore."""

    @pytest.fixture
    def store(self, tmp_path):
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        return TenantGraphStore(
            tenant_id="tenant-a",
            base_store_class=NetworkXGraphStore,
            graph_dir=tmp_path / "graphs",
        )

    @pytest.fixture
    def other_store(self, tmp_path):
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        return TenantGraphStore(
            tenant_id="tenant-b",
            base_store_class=NetworkXGraphStore,
            graph_dir=tmp_path / "graphs",
        )

    @pytest.mark.asyncio
    async def test_initialize(self, store):
        await store.initialize()
        assert store._initialized is True

    @pytest.mark.asyncio
    async def test_double_initialize_is_noop(self, store):
        await store.initialize()
        await store.initialize()  # Should not error
        assert store._initialized is True

    @pytest.mark.asyncio
    async def test_add_entity(self, store):
        await store.initialize()
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        result = await store.add_entity(entity)
        assert result == "e1"

    @pytest.mark.asyncio
    async def test_add_entity_sets_tenant_id(self, store):
        await store.initialize()
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        # Verify tenant_id is in properties
        retrieved = await store.get_entity("e1")
        assert retrieved is not None
        assert retrieved.properties.get("tenant_id") == "tenant-a"

    @pytest.mark.asyncio
    async def test_get_entity_filters_by_tenant(self, store, other_store):
        await store.initialize()
        await other_store.initialize()

        # Add to tenant-a's store
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        # tenant-a can see it
        result_a = await store.get_entity("e1")
        assert result_a is not None

        # tenant-b cannot (different store file, so entity doesn't exist at all)
        result_b = await other_store.get_entity("e1")
        assert result_b is None

    @pytest.mark.asyncio
    async def test_add_relation(self, store):
        await store.initialize()
        e1 = Entity(id="e1", name="A", entity_type="CONCEPT")
        e2 = Entity(id="e2", name="B", entity_type="CONCEPT")
        await store.add_entity(e1)
        await store.add_entity(e2)

        rel = Relation(
            id="r1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="RELATED_TO",
        )
        result = await store.add_relation(rel)
        assert result == "r1"

    @pytest.mark.asyncio
    async def test_find_entities(self, store):
        await store.initialize()
        for i in range(3):
            entity = Entity(id=f"e{i}", name=f"Entity {i}", entity_type="CONCEPT")
            await store.add_entity(entity)

        results = await store.find_entities(name="Entity")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_find_entities_respects_limit(self, store):
        await store.initialize()
        for i in range(10):
            entity = Entity(id=f"e{i}", name=f"Entity {i}", entity_type="CONCEPT")
            await store.add_entity(entity)

        results = await store.find_entities(name="Entity", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_neighbors(self, store):
        await store.initialize()
        e1 = Entity(id="e1", name="A", entity_type="CONCEPT")
        e2 = Entity(id="e2", name="B", entity_type="CONCEPT")
        await store.add_entity(e1)
        await store.add_entity(e2)

        rel = Relation(
            id="r1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="RELATED_TO",
        )
        await store.add_relation(rel)

        subgraph = await store.get_neighbors("e1")
        assert isinstance(subgraph, SubGraph)
        assert len(subgraph.entities) >= 1

    @pytest.mark.asyncio
    async def test_get_neighbors_nonexistent_entity(self, store):
        await store.initialize()
        subgraph = await store.get_neighbors("nonexistent")
        assert isinstance(subgraph, SubGraph)
        assert len(subgraph.entities) == 0

    @pytest.mark.asyncio
    async def test_find_path(self, store):
        await store.initialize()
        e1 = Entity(id="e1", name="A", entity_type="CONCEPT")
        e2 = Entity(id="e2", name="B", entity_type="CONCEPT")
        await store.add_entity(e1)
        await store.add_entity(e2)

        rel = Relation(
            id="r1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="RELATED_TO",
        )
        await store.add_relation(rel)

        path = await store.find_path("e1", "e2")
        assert isinstance(path, SubGraph)

    @pytest.mark.asyncio
    async def test_find_path_nonexistent_returns_empty(self, store):
        await store.initialize()
        path = await store.find_path("nonexistent_a", "nonexistent_b")
        assert isinstance(path, SubGraph)
        assert len(path.entities) == 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, store):
        await store.initialize()
        e1 = Entity(id="e1", name="A", entity_type="CONCEPT")
        await store.add_entity(e1)

        stats = await store.get_statistics()
        assert stats["entity_count"] == 1

    @pytest.mark.asyncio
    async def test_delete_entity(self, store):
        await store.initialize()
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        await store.delete_entity("e1")
        result = await store.get_entity("e1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_entity_wrong_tenant_noop(self, store, other_store):
        """Cannot delete entity from another tenant's store."""
        await store.initialize()
        await other_store.initialize()

        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        # other_store can't delete it (not in their store)
        await other_store.delete_entity("e1")

        # Still exists in store
        result = await store.get_entity("e1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_clear(self, store):
        await store.initialize()
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        await store.clear()
        stats = await store.get_statistics()
        assert stats["entity_count"] == 0

    @pytest.mark.asyncio
    async def test_delete_tenant_data(self, store, tmp_path):
        await store.initialize()
        entity = Entity(id="e1", name="Test", entity_type="CONCEPT")
        await store.add_entity(entity)

        await store.delete_tenant_data()
        # Graph file should be deleted
        assert not store._graph_path.exists()

    @pytest.mark.asyncio
    async def test_query(self, store):
        await store.initialize()
        entity = Entity(id="e1", name="TestQuery", entity_type="CONCEPT")
        await store.add_entity(entity)

        result = await store.query("TestQuery")
        assert isinstance(result, SubGraph)


# ---------------------------------------------------------------------------
# TenantGraphManager
# ---------------------------------------------------------------------------

class TestTenantGraphManager:
    @pytest.fixture
    def graph_manager(self, tmp_path):
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
        return TenantGraphManager(
            base_store_class=NetworkXGraphStore,
            graph_dir=tmp_path / "graphs",
        )

    @pytest.mark.asyncio
    async def test_get_store(self, graph_manager):
        store = await graph_manager.get_store("t1")
        assert isinstance(store, TenantGraphStore)

    @pytest.mark.asyncio
    async def test_caches_store(self, graph_manager):
        s1 = await graph_manager.get_store("t1")
        s2 = await graph_manager.get_store("t1")
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_different_tenants_get_different_stores(self, graph_manager):
        s1 = await graph_manager.get_store("t1")
        s2 = await graph_manager.get_store("t2")
        assert s1 is not s2

    @pytest.mark.asyncio
    async def test_delete_tenant(self, graph_manager):
        await graph_manager.get_store("t1")
        await graph_manager.delete_tenant("t1")
        assert "t1" not in graph_manager._store_cache

    @pytest.mark.asyncio
    async def test_delete_nonexistent_tenant_noop(self, graph_manager):
        await graph_manager.delete_tenant("nonexistent")  # Should not error

    @pytest.mark.asyncio
    async def test_list_tenants_empty(self, graph_manager):
        tenants = await graph_manager.list_tenants()
        assert tenants == []


# ---------------------------------------------------------------------------
# get_tenant_graph_manager singleton
# ---------------------------------------------------------------------------

class TestGetTenantGraphManager:
    def test_returns_instance(self):
        import src.pdf_framework.multitenancy.tenant_graph as mod
        mod._tenant_graph_manager = None

        mgr = get_tenant_graph_manager()
        assert isinstance(mgr, TenantGraphManager)

        mod._tenant_graph_manager = None

    def test_returns_same_instance(self):
        import src.pdf_framework.multitenancy.tenant_graph as mod
        mod._tenant_graph_manager = None

        m1 = get_tenant_graph_manager()
        m2 = get_tenant_graph_manager()
        assert m1 is m2

        mod._tenant_graph_manager = None
