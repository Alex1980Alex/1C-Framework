"""Integration tests for Neo4j Graph Store (Phase 51.5).

Requires a running Neo4j instance. Run with:
    pytest tests/integration/test_neo4j.py -m slow
"""

import pytest

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.schemas.entities import Entity, Relation


@pytest.fixture
def neo4j_settings():
    return GraphStoreSettings(
        provider="neo4j",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
    )


@pytest.fixture
async def neo4j_store(neo4j_settings):
    """Create and initialize a Neo4j store, clear after test."""
    from src.pdf_framework.graph_store.providers.neo4j_store import Neo4jGraphStore

    store = Neo4jGraphStore(neo4j_settings)
    try:
        await store.initialize()
    except Exception:
        pytest.skip("Neo4j not available")

    await store.clear()
    yield store
    await store.clear()
    await store.close()


@pytest.mark.slow
@pytest.mark.integration
class TestNeo4jIntegration:
    """Integration tests requiring a real Neo4j instance."""

    @pytest.mark.asyncio
    async def test_full_crud_pipeline(self, neo4j_store):
        """Test complete CRUD cycle: add → get → find → delete."""
        store = neo4j_store

        # Add entity
        entity = Entity(
            id="test-ent-1",
            name="Документ",
            entity_type="CONCEPT",
            properties={"domain": "1C"},
            source_document_id="doc-001",
        )
        eid = await store.add_entity(entity)
        assert eid == "test-ent-1"

        # Get entity
        fetched = await store.get_entity("test-ent-1")
        assert fetched is not None
        assert fetched.name == "Документ"
        assert fetched.entity_type == "CONCEPT"

        # Find entities
        found = await store.find_entities(name="Документ")
        assert len(found) >= 1
        assert any(e.id == "test-ent-1" for e in found)

        # Delete entity
        await store.delete_entity("test-ent-1")
        deleted = await store.get_entity("test-ent-1")
        assert deleted is None

    @pytest.mark.asyncio
    async def test_relations_and_neighbors(self, neo4j_store):
        """Test adding relations and traversing neighbors."""
        store = neo4j_store

        # Add two entities
        e1 = Entity(id="e1", name="Справочник", entity_type="CONCEPT")
        e2 = Entity(id="e2", name="Реквизит", entity_type="CONCEPT")
        await store.add_entity(e1)
        await store.add_entity(e2)

        # Add relation
        rel = Relation(
            id="r1",
            source_entity_id="e1",
            target_entity_id="e2",
            relation_type="HAS_ATTRIBUTE",
        )
        rid = await store.add_relation(rel)
        assert rid == "r1"

        # Get neighbors
        subgraph = await store.get_neighbors("e1", depth=1)
        assert len(subgraph.entities) >= 1
        assert len(subgraph.relations) >= 1

    @pytest.mark.asyncio
    async def test_statistics(self, neo4j_store):
        """Test get_statistics returns correct counts."""
        store = neo4j_store

        await store.add_entity(Entity(id="s1", name="A", entity_type="T"))
        await store.add_entity(Entity(id="s2", name="B", entity_type="T"))
        await store.add_relation(Relation(
            id="sr1", source_entity_id="s1", target_entity_id="s2",
            relation_type="LINK",
        ))

        stats = await store.get_statistics()
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 1

    @pytest.mark.asyncio
    async def test_batch_insert(self, neo4j_store):
        """Test batch mode for bulk operations."""
        store = neo4j_store

        store.set_batch_mode(True)
        for i in range(100):
            await store.add_entity(Entity(
                id=f"batch-{i}", name=f"Entity {i}", entity_type="TEST",
            ))
        await store.flush()
        store.set_batch_mode(False)

        stats = await store.get_statistics()
        assert stats["node_count"] == 100

    @pytest.mark.asyncio
    async def test_find_path(self, neo4j_store):
        """Test shortest path finding."""
        store = neo4j_store

        # Create chain: A -> B -> C
        for name in ["A", "B", "C"]:
            await store.add_entity(Entity(id=name, name=name, entity_type="NODE"))
        await store.add_relation(Relation(id="ab", source_entity_id="A", target_entity_id="B", relation_type="NEXT"))
        await store.add_relation(Relation(id="bc", source_entity_id="B", target_entity_id="C", relation_type="NEXT"))

        path = await store.find_path("A", "C", max_depth=5)
        assert len(path.entities) == 3
        assert len(path.relations) == 2
