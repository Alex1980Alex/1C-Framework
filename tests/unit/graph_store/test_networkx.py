"""Unit tests for NetworkX Graph Store (F2.8).

Tests:
- F2.8.1: Test NetworkXGraphStore add/get entity
- F2.8.3: Test JSON persistence (save/load)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestNetworkXGraphStore:
    """Test NetworkX-based graph store operations."""

    def test_add_entity(self):
        """F2.8.1: Should add entity to graph."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        entity = {
            "id": "entity1",
            "type": "Person",
            "name": "John Doe",
        }

        store.add_entity(entity)

        retrieved = store.get_entity("entity1")
        assert retrieved is not None
        assert retrieved["id"] == "entity1"

    def test_get_entity_not_exists(self):
        """F2.8.1: get_entity should return None for non-existent."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        result = store.get_entity("nonexistent")

        assert result is None

    def test_add_relation(self):
        """F2.8.1: Should add relation between entities."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        # Add entities first
        store.add_entity({"id": "e1", "type": "Entity"})
        store.add_entity({"id": "e2", "type": "Entity"})

        # Add relation
        store.add_relation("e1", "e2", "KNOWS", weight=0.8)

        # Verify relation exists
        relations = store.get_relations("e1")
        assert len(relations) == 1
        assert relations[0]["target"] == "e2"
        assert relations[0]["type"] == "KNOWS"

    def test_get_neighbors(self):
        """F2.8.1: Should get neighbors of an entity."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        store.add_entity({"id": "e1", "type": "Entity"})
        store.add_entity({"id": "e2", "type": "Entity"})
        store.add_entity({"id": "e3", "type": "Entity"})

        store.add_relation("e1", "e2", "CONNECTED")
        store.add_relation("e1", "e3", "CONNECTED")

        neighbors = store.get_neighbors("e1", depth=1)

        neighbor_ids = {n["id"] for n in neighbors}
        assert "e2" in neighbor_ids
        assert "e3" in neighbor_ids

    def test_get_neighbors_depth_2(self):
        """F2.8.1: Should get neighbors at depth 2."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        # e1 -> e2 -> e3
        store.add_entity({"id": "e1", "type": "Entity"})
        store.add_entity({"id": "e2", "type": "Entity"})
        store.add_entity({"id": "e3", "type": "Entity"})

        store.add_relation("e1", "e2", "CONNECTED")
        store.add_relation("e2", "e3", "CONNECTED")

        neighbors = store.get_neighbors("e1", depth=2)

        neighbor_ids = {n["id"] for n in neighbors}
        assert "e2" in neighbor_ids
        assert "e3" in neighbor_ids

    def test_json_persistence_save_load(self, tmp_path):
        """F2.8.3: Should save and load graph from JSON."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        # Add data
        store.add_entity({"id": "e1", "type": "Person", "name": "Alice"})
        store.add_entity({"id": "e2", "type": "Person", "name": "Bob"})
        store.add_relation("e1", "e2", "KNOWS")

        # Save to file
        file_path = tmp_path / "graph.json"
        store.save_to_json(file_path)

        assert file_path.exists()

        # Load into new store
        new_store = NetworkXGraphStore()
        new_store.load_from_json(file_path)

        # Verify data
        e1 = new_store.get_entity("e1")
        assert e1 is not None
        assert e1["name"] == "Alice"

        relations = new_store.get_relations("e1")
        assert len(relations) == 1

    def test_json_persistence_preserves_attributes(self, tmp_path):
        """F2.8.3: JSON persistence should preserve all attributes."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        entity = {
            "id": "e1",
            "type": "Person",
            "name": "Alice",
            "age": 30,
            "embedded": True,
        }

        store.add_entity(entity)

        file_path = tmp_path / "graph.json"
        store.save_to_json(file_path)

        new_store = NetworkXGraphStore()
        new_store.load_from_json(file_path)

        loaded = new_store.get_entity("e1")

        assert loaded["age"] == 30
        assert loaded["embedded"] is True

    def test_clear_graph(self):
        """F2.8.3: clear() should remove all entities and relations."""
        from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

        store = NetworkXGraphStore()

        store.add_entity({"id": "e1", "type": "Entity"})
        store.add_entity({"id": "e2", "type": "Entity"})
        store.add_relation("e1", "e2", "CONNECTED")

        assert store.count_entities() == 2
        assert store.count_relations() == 1

        store.clear()

        assert store.count_entities() == 0
        assert store.count_relations() == 0
