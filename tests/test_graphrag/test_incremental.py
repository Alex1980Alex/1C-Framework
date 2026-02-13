"""Tests for Incremental Graph Updates (Phase 6.5).

Tests entity merging and update logic using NetworkXGraphStore.
"""

import pytest
import networkx as nx

from src.pdf_framework.config import GraphRAGSettings, GraphStoreSettings
from src.pdf_framework.graph_store.incremental import IncrementalGraphUpdater, UpdateResult
from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation


@pytest.fixture
def settings():
    return GraphRAGSettings(incremental_updates_enabled=False)


@pytest.fixture
def graph_store(tmp_path):
    store_settings = GraphStoreSettings(persist_dir=str(tmp_path / "graph"))
    store = NetworkXGraphStore(settings=store_settings)
    import asyncio
    asyncio.get_event_loop().run_until_complete(store.initialize())
    return store


@pytest.fixture
def updater(graph_store, settings):
    return IncrementalGraphUpdater(
        graph_store=graph_store,
        settings=settings,
    )


def _entity(id: str, name: str, entity_type: str = "CONCEPT", **kwargs) -> Entity:
    return Entity(
        id=id, name=name, entity_type=entity_type,
        source_document_id="doc1",
        source_chunk_ids=kwargs.get("source_chunk_ids", ["c1"]),
        confidence=kwargs.get("confidence", 0.9),
        properties=kwargs.get("properties", {}),
    )


def _relation(id: str, src: str, tgt: str, rel_type: str = "RELATED") -> Relation:
    return Relation(
        id=id, source_entity_id=src, target_entity_id=tgt,
        relation_type=rel_type, source_chunk_id="c1",
    )


class TestUpdateResult:
    def test_default_values(self):
        r = UpdateResult()
        assert r.new_entities == []
        assert r.merged_entities == []
        assert r.new_relations == []
        assert r.affected_communities == set()
        assert r.summaries_regenerated == 0


class TestIncrementalUpdate:
    @pytest.mark.asyncio
    async def test_add_new_entities(self, updater, graph_store):
        entities = [_entity("e1", "Alpha"), _entity("e2", "Beta")]
        relations = []

        result = await updater.update(entities, relations)

        assert len(result.new_entities) == 2
        assert len(result.merged_entities) == 0

        # Verify in graph store
        e1 = await graph_store.get_entity("e1")
        assert e1 is not None
        assert e1.name == "Alpha"

    @pytest.mark.asyncio
    async def test_add_entities_with_relations(self, updater, graph_store):
        entities = [_entity("e1", "Alpha"), _entity("e2", "Beta")]
        relations = [_relation("r1", "e1", "e2", "RELATED")]

        result = await updater.update(entities, relations)

        assert len(result.new_entities) == 2
        assert len(result.new_relations) == 1

    @pytest.mark.asyncio
    async def test_relation_requires_both_entities(self, updater, graph_store):
        """Relations with missing source/target should be skipped."""
        entities = [_entity("e1", "Alpha")]
        # e3 doesn't exist
        relations = [_relation("r1", "e1", "e3", "RELATED")]

        result = await updater.update(entities, relations)

        assert len(result.new_entities) == 1
        assert len(result.new_relations) == 0  # Skipped

    @pytest.mark.asyncio
    async def test_merge_existing_entity(self, updater, graph_store):
        """Second update with same name/type should merge."""
        # First: add entity
        await graph_store.add_entity(_entity("e1", "Alpha", properties={"version": "1"}))

        # Second: try to add entity with same name and type
        new_entity = _entity("e1_new", "Alpha", source_chunk_ids=["c2"], confidence=0.95)
        result = await updater.update([new_entity], [])

        assert len(result.merged_entities) == 1
        assert len(result.new_entities) == 0

        # Verify merge result
        merged = await graph_store.get_entity("e1")
        assert merged is not None
        assert merged.confidence == 0.95  # max(0.9, 0.95)
        assert "c1" in merged.source_chunk_ids
        assert "c2" in merged.source_chunk_ids

    @pytest.mark.asyncio
    async def test_no_merge_different_type(self, updater, graph_store):
        """Entities with same name but different type should not merge."""
        await graph_store.add_entity(_entity("e1", "Alpha", entity_type="PERSON"))

        new_entity = _entity("e2", "Alpha", entity_type="ORG")
        result = await updater.update([new_entity], [])

        assert len(result.new_entities) == 1
        assert len(result.merged_entities) == 0

    @pytest.mark.asyncio
    async def test_empty_update(self, updater):
        result = await updater.update([], [])
        assert len(result.new_entities) == 0
        assert len(result.new_relations) == 0


class TestGetGraph:
    def test_get_graph_returns_networkx(self, updater, graph_store):
        graph = updater._get_graph()
        assert isinstance(graph, nx.DiGraph)

    def test_get_graph_fallback(self):
        """If graph_store has no _graph attr, returns empty DiGraph."""
        from unittest.mock import MagicMock

        store = MagicMock(spec=[])  # No _graph attribute
        updater = IncrementalGraphUpdater(graph_store=store)
        graph = updater._get_graph()
        assert isinstance(graph, nx.DiGraph)
        assert graph.number_of_nodes() == 0
