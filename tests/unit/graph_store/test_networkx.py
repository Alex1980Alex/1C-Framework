"""Unit tests for NetworkX Graph Store (F2.8).

Tests:
- F2.8.1: add/get entity
- F2.8.1: add/get relation
- F2.8.1: get neighbors depth-1 and depth-2
- F2.8.3: JSON persistence (save/load via persist_dir)
- F2.8.3: clear removes all entities and relations

Tests are ``async def`` (project ``asyncio_mode = "auto"``); pytest-asyncio manages a
fresh per-test event loop. (Do NOT use ``asyncio.get_event_loop().run_until_complete()``
here — it manipulates the global loop and pollutes async tests in other files.)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _make_store(tmp_path):
    """Return an initialized NetworkXGraphStore writing to tmp_path."""
    from src.pdf_framework.config import GraphStoreSettings
    from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

    settings = GraphStoreSettings(persist_dir=str(tmp_path / "graph"))
    store = NetworkXGraphStore(settings)
    await store.initialize()
    return store


def _entity(eid: str, etype: str = "CONCEPT", name: str = "", **props):
    from src.pdf_framework.schemas.entities import Entity
    return Entity(
        id=eid,
        name=name or eid,
        entity_type=etype,
        properties=props,
    )


def _relation(rid: str, src: str, tgt: str, rtype: str = "RELATED_TO", **kwargs):
    from src.pdf_framework.schemas.entities import Relation
    return Relation(id=rid, source_entity_id=src, target_entity_id=tgt,
                    relation_type=rtype, **kwargs)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNetworkXGraphStore:
    """Test NetworkX-based graph store operations."""

    # -- entity CRUD ---------------------------------------------------------

    async def test_add_entity(self, tmp_path):
        """F2.8.1: Should add entity to graph and retrieve it by id."""
        store = await _make_store(tmp_path)
        await store.add_entity(_entity("entity1", "Person", name="John Doe"))

        retrieved = await store.get_entity("entity1")
        assert retrieved is not None
        assert retrieved.id == "entity1"
        assert retrieved.name == "John Doe"
        assert retrieved.entity_type == "Person"

    async def test_get_entity_not_exists(self, tmp_path):
        """F2.8.1: get_entity should return None for non-existent id."""
        store = await _make_store(tmp_path)
        result = await store.get_entity("nonexistent")
        assert result is None

    # -- relation CRUD -------------------------------------------------------

    async def test_add_relation(self, tmp_path):
        """F2.8.1: Should add relation between entities and return it via get_relations."""
        store = await _make_store(tmp_path)
        await store.add_entity(_entity("e1"))
        await store.add_entity(_entity("e2"))
        await store.add_relation(_relation("r1", "e1", "e2", "KNOWS", confidence=0.8))

        relations = await store.get_relations("e1")
        assert len(relations) == 1
        assert relations[0].target_entity_id == "e2"
        assert relations[0].relation_type == "KNOWS"
        assert relations[0].confidence == pytest.approx(0.8)

    # -- neighbor traversal --------------------------------------------------

    async def test_get_neighbors_depth_1(self, tmp_path):
        """F2.8.1: get_neighbors depth=1 should return immediate neighbors."""
        store = await _make_store(tmp_path)
        await store.add_entity(_entity("e1"))
        await store.add_entity(_entity("e2"))
        await store.add_entity(_entity("e3"))
        await store.add_relation(_relation("r1", "e1", "e2", "CONNECTED"))
        await store.add_relation(_relation("r2", "e1", "e3", "CONNECTED"))

        subgraph = await store.get_neighbors("e1", depth=1)
        neighbor_ids = {e.id for e in subgraph.entities}
        assert "e2" in neighbor_ids
        assert "e3" in neighbor_ids

    async def test_get_neighbors_depth_2(self, tmp_path):
        """F2.8.1: get_neighbors depth=2 should include transitive neighbors."""
        store = await _make_store(tmp_path)
        # e1 -> e2 -> e3
        await store.add_entity(_entity("e1"))
        await store.add_entity(_entity("e2"))
        await store.add_entity(_entity("e3"))
        await store.add_relation(_relation("r1", "e1", "e2", "CONNECTED"))
        await store.add_relation(_relation("r2", "e2", "e3", "CONNECTED"))

        subgraph = await store.get_neighbors("e1", depth=2)
        neighbor_ids = {e.id for e in subgraph.entities}
        assert "e2" in neighbor_ids
        assert "e3" in neighbor_ids

    # -- persistence ---------------------------------------------------------

    async def test_json_persistence_save_load(self, tmp_path):
        """F2.8.3: Graph persists to JSON and loads in a fresh store instance."""
        persist_dir = tmp_path / "graph"
        from src.pdf_framework.config import GraphStoreSettings
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        settings = GraphStoreSettings(persist_dir=str(persist_dir))

        # Build and populate first store
        store1 = NetworkXGraphStore(settings)
        await store1.initialize()
        await store1.add_entity(_entity("e1", "Person", name="Alice"))
        await store1.add_entity(_entity("e2", "Person", name="Bob"))
        await store1.add_relation(_relation("r1", "e1", "e2", "KNOWS"))

        # Verify persist file exists
        assert (persist_dir / "graph.json").exists()

        # Load into a second store from same directory
        store2 = NetworkXGraphStore(settings)
        await store2.initialize()

        e1 = await store2.get_entity("e1")
        assert e1 is not None
        assert e1.name == "Alice"

        relations = await store2.get_relations("e1")
        assert len(relations) == 1
        assert relations[0].target_entity_id == "e2"

    async def test_json_persistence_preserves_attributes(self, tmp_path):
        """F2.8.3: JSON persistence preserves entity properties dict."""
        persist_dir = tmp_path / "graph"
        from src.pdf_framework.config import GraphStoreSettings
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        settings = GraphStoreSettings(persist_dir=str(persist_dir))

        store1 = NetworkXGraphStore(settings)
        await store1.initialize()
        entity = _entity("e1", "Person", name="Alice", age=30, embedded=True)
        await store1.add_entity(entity)

        store2 = NetworkXGraphStore(settings)
        await store2.initialize()

        loaded = await store2.get_entity("e1")
        assert loaded is not None
        # Properties stored in the `properties` dict
        assert loaded.properties.get("age") == 30
        assert loaded.properties.get("embedded") is True

    # -- clear ---------------------------------------------------------------

    async def test_clear_graph(self, tmp_path):
        """F2.8.3: clear() should remove all entities and relations."""
        store = await _make_store(tmp_path)
        await store.add_entity(_entity("e1"))
        await store.add_entity(_entity("e2"))
        await store.add_relation(_relation("r1", "e1", "e2", "CONNECTED"))

        stats_before = await store.get_statistics()
        assert stats_before["node_count"] == 2
        assert stats_before["edge_count"] == 1

        await store.clear()

        stats_after = await store.get_statistics()
        assert stats_after["node_count"] == 0
        assert stats_after["edge_count"] == 0
