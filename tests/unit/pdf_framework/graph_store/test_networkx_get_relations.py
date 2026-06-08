"""Unit tests for NetworkXGraphStore.get_relations() (added 2026-05-15).

Coverage:
    - Returns outgoing edges only as Relation objects
    - Returns empty list for unknown entity_id
    - Preserves relation_type, properties, confidence from edge data
    - Handles entity with no outgoing edges
"""

from __future__ import annotations

import pytest

from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation

pytestmark = pytest.mark.unit


@pytest.fixture
async def store(tmp_path):
    from src.pdf_framework.config import GraphStoreSettings

    settings = GraphStoreSettings(persist_dir=tmp_path / "graph")
    s = NetworkXGraphStore(settings)
    await s.initialize()
    await s.add_entity(Entity(id="a", name="A", entity_type="CONCEPT"))
    await s.add_entity(Entity(id="b", name="B", entity_type="CONCEPT"))
    await s.add_entity(Entity(id="c", name="C", entity_type="CONCEPT"))
    return s


@pytest.mark.asyncio
async def test_get_relations_returns_outgoing(store):
    """a → b should return one Relation."""
    await store.add_relation(
        Relation(
            id="r1",
            source_entity_id="a",
            target_entity_id="b",
            relation_type="uses",
            confidence=0.95,
        )
    )
    rels = await store.get_relations("a")
    assert len(rels) == 1
    assert rels[0].source_entity_id == "a"
    assert rels[0].target_entity_id == "b"
    assert rels[0].relation_type == "uses"
    assert rels[0].confidence == 0.95


@pytest.mark.asyncio
async def test_get_relations_multiple_outgoing(store):
    """a → b, a → c should return 2 relations (no specific order required)."""
    await store.add_relation(
        Relation(
            id="r1",
            source_entity_id="a",
            target_entity_id="b",
            relation_type="uses",
        )
    )
    await store.add_relation(
        Relation(
            id="r2",
            source_entity_id="a",
            target_entity_id="c",
            relation_type="extends",
        )
    )
    rels = await store.get_relations("a")
    assert len(rels) == 2
    targets = {r.target_entity_id for r in rels}
    assert targets == {"b", "c"}


@pytest.mark.asyncio
async def test_get_relations_empty_for_missing_entity(store):
    """Unknown entity_id → empty list (no exception)."""
    rels = await store.get_relations("nonexistent")
    assert rels == []


@pytest.mark.asyncio
async def test_get_relations_does_not_include_incoming(store):
    """get_relations is OUTGOING only — b's incoming edge from a is not in b's list."""
    await store.add_relation(
        Relation(
            id="r1",
            source_entity_id="a",
            target_entity_id="b",
            relation_type="uses",
        )
    )
    # b has no outgoing edges, only incoming from a
    rels = await store.get_relations("b")
    assert rels == []


@pytest.mark.asyncio
async def test_get_relations_preserves_properties(store):
    """Relation properties dict + source_chunk_id round-trip via edge data."""
    await store.add_relation(
        Relation(
            id="r1",
            source_entity_id="a",
            target_entity_id="b",
            relation_type="uses",
            properties={"weight": 1.5, "note": "primary"},
            source_chunk_id="chunk-42",
        )
    )
    rels = await store.get_relations("a")
    assert len(rels) == 1
    assert rels[0].properties == {"weight": 1.5, "note": "primary"}
    assert rels[0].source_chunk_id == "chunk-42"
