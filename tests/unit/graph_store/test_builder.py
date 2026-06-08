"""Unit tests for Graph Builder (F2.8.2).

Tests:
- F2.8.2: GraphBuilder deduplication, relation storage, and build_from_chunks orchestration.

API changes vs original tests
-------------------------------
* GraphBuilder(extractor, graph_store, concurrency) — no deduplication_case_sensitive / min_confidence params.
* Main entry point: async build_from_chunks(list[DocumentChunk]) -> dict with keys
  {"entities_added", "relations_added", "chunks_processed"}.
* No graph.get_all_entities() / get_all_relations() — builder returns count dict; entity
  state is inspected via the injected graph_store mock.
* Deduplication is always on, case-insensitive (name.lower().strip() + entity_type key).
* No _merge_entities() helper (different-type non-merge, same-type chunk-id merge happen
  inside _store_extraction).  We test observable behaviour, not the private method.
* min_confidence is not a builder concern — the extractor returns entities at face value;
  that test is dropped with a note below.

Tests are ``async def`` (project ``asyncio_mode = "auto"``); pytest-asyncio manages a
fresh per-test event loop. (Do NOT use ``asyncio.run()`` here — it closes the global
loop and pollutes async tests in other files.)

Deleted / adapted tests
-----------------------
* test_build_from_chunks            → adapted: async, real DocumentChunk, count assertions.
* test_deduplication_same_entity    → adapted: async, ExtractionResult mock, count check.
* test_deduplication_case_insensitive → adapted: async, lower-vs-upper name.
* test_relation_extraction          → adapted: async, relations in ExtractionResult.
* test_filter_by_confidence         → DROPPED: confidence filtering is not a GraphBuilder
  concern in the current implementation (belongs to LLMEntityExtractor layer).
* test_merge_entities_same_type     → adapted: same-name+type entity triggers chunk-id
  merge (second add_entity call carries extra source_chunk_id).
* test_no_merge_different_types     → adapted: same name, different type → two separate
  add_entity calls (no merge/collapse).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.graph_store.construction.builder import GraphBuilder
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.schemas.entities import (
    Entity,
    ExtractionResult,
    Relation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(content: str = "text", document_id: str = "doc1") -> DocumentChunk:
    return DocumentChunk(id=uuid.uuid4().hex[:12], content=content, document_id=document_id)


def _make_entity(name: str, entity_type: str = "PERSON", chunk_id: str = "c1") -> Entity:
    return Entity(
        id=uuid.uuid4().hex[:12],
        name=name,
        entity_type=entity_type,
        source_chunk_ids=[chunk_id],
    )


def _make_extractor(results: list[ExtractionResult]) -> MagicMock:
    """Return an extractor mock that yields the given results in sequence."""
    extractor = MagicMock()
    extractor.extract = AsyncMock(side_effect=results)
    return extractor


def _make_graph_store(existing_entities: dict[str, Entity] | None = None) -> MagicMock:
    """Return a graph-store mock.

    * add_entity returns entity.id
    * get_entity returns from `existing_entities` dict (keyed by entity_id) or None
    * add_relation returns relation.id
    """
    store = MagicMock()
    _db: dict[str, Entity] = dict(existing_entities or {})

    async def _add_entity(entity: Entity) -> str:
        _db[entity.id] = entity
        return entity.id

    async def _get_entity(entity_id: str) -> Entity | None:
        return _db.get(entity_id)

    async def _add_relation(relation: Relation) -> str:
        return relation.id

    store.add_entity = AsyncMock(side_effect=_add_entity)
    store.get_entity = AsyncMock(side_effect=_get_entity)
    store.add_relation = AsyncMock(side_effect=_add_relation)
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.unit


class TestGraphBuilder:
    """Test GraphBuilder.build_from_chunks orchestration and deduplication."""

    async def test_build_from_chunks_returns_counts(self):
        """build_from_chunks returns dict with entity/relation/chunk counts."""
        chunk = _make_chunk("John Doe works at Acme.")
        entity = _make_entity("John Doe", chunk_id=chunk.id)
        result = ExtractionResult(chunk_id=chunk.id, entities=[entity], relations=[])

        extractor = _make_extractor([result])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk])

        assert counts["chunks_processed"] == 1
        assert counts["entities_added"] == 1
        assert counts["relations_added"] == 0
        store.add_entity.assert_called_once()

    async def test_deduplication_same_entity(self):
        """Identical name+type from two chunks → one add_entity, one chunk-id merge."""
        chunk1 = _make_chunk("John Doe is a person.")
        chunk2 = _make_chunk("John Doe lives in New York.")

        entity1 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk1.id)
        entity2 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk2.id)

        result1 = ExtractionResult(chunk_id=chunk1.id, entities=[entity1])
        result2 = ExtractionResult(chunk_id=chunk2.id, entities=[entity2])

        extractor = _make_extractor([result1, result2])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk1, chunk2])

        # Only 1 net-new entity (second chunk triggers a merge path, not a new add)
        assert counts["entities_added"] == 1
        # add_entity called twice: once for new entity, once to persist merged chunk_ids
        assert store.add_entity.call_count == 2

    async def test_deduplication_case_insensitive(self):
        """Names 'john doe' and 'John Doe' with same type collapse to one entity."""
        chunk1 = _make_chunk("john doe is a person")
        chunk2 = _make_chunk("John Doe lives here")

        entity_lower = _make_entity("john doe", entity_type="PERSON", chunk_id=chunk1.id)
        entity_upper = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk2.id)

        result1 = ExtractionResult(chunk_id=chunk1.id, entities=[entity_lower])
        result2 = ExtractionResult(chunk_id=chunk2.id, entities=[entity_upper])

        extractor = _make_extractor([result1, result2])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk1, chunk2])

        assert counts["entities_added"] == 1, (
            "Case-insensitive dedup: 'john doe' and 'John Doe' should merge"
        )

    async def test_relation_extraction(self):
        """Relations present in ExtractionResult are stored via add_relation."""
        chunk = _make_chunk("John works at Acme.")

        john = _make_entity("John", entity_type="PERSON", chunk_id=chunk.id)
        acme = _make_entity("Acme", entity_type="ORG", chunk_id=chunk.id)
        rel = Relation(
            id=uuid.uuid4().hex[:12],
            source_entity_id=john.id,
            target_entity_id=acme.id,
            relation_type="WORKS_AT",
            source_chunk_id=chunk.id,
        )
        result = ExtractionResult(chunk_id=chunk.id, entities=[john, acme], relations=[rel])

        extractor = _make_extractor([result])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk])

        assert counts["relations_added"] == 1
        store.add_relation.assert_called_once()
        # Verify the stored relation has the correct type
        stored_relation: Relation = store.add_relation.call_args[0][0]
        assert stored_relation.relation_type == "WORKS_AT"

    async def test_merge_entities_same_type(self):
        """Same name+type entity from a second chunk triggers a chunk-id merge, not a new entity."""
        chunk1 = _make_chunk("First mention of John Doe.")
        chunk2 = _make_chunk("Second mention of John Doe.")

        # Both produce an entity with same name+type
        entity1 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk1.id)
        entity2 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk2.id)

        result1 = ExtractionResult(chunk_id=chunk1.id, entities=[entity1])
        result2 = ExtractionResult(chunk_id=chunk2.id, entities=[entity2])

        extractor = _make_extractor([result1, result2])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk1, chunk2])

        # Only 1 brand-new entity; the second mention is a merge
        assert counts["entities_added"] == 1
        # The second add_entity call carries the extra source_chunk_id
        calls = store.add_entity.call_args_list
        assert len(calls) == 2
        merged_entity: Entity = calls[1][0][0]
        assert chunk2.id in merged_entity.source_chunk_ids

    async def test_no_merge_different_types(self):
        """Same name but different entity_type → two separate entities, no collapse."""
        chunk1 = _make_chunk("Apple the organization.")
        chunk2 = _make_chunk("Apple the product.")

        org_entity = _make_entity("Apple", entity_type="ORG", chunk_id=chunk1.id)
        product_entity = _make_entity("Apple", entity_type="PRODUCT", chunk_id=chunk2.id)

        result1 = ExtractionResult(chunk_id=chunk1.id, entities=[org_entity])
        result2 = ExtractionResult(chunk_id=chunk2.id, entities=[product_entity])

        extractor = _make_extractor([result1, result2])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk1, chunk2])

        # Both should be stored as distinct entities
        assert counts["entities_added"] == 2
        assert store.add_entity.call_count == 2

    async def test_relation_id_remapped_after_dedup(self):
        """When the source entity is deduped, the stored relation uses the canonical entity ID."""
        chunk1 = _make_chunk("John Doe works at Acme.")
        chunk2 = _make_chunk("John Doe is managed by Jane.")

        # chunk1: John Doe + Acme + WORKS_AT relation
        john1 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk1.id)
        acme = _make_entity("Acme", entity_type="ORG", chunk_id=chunk1.id)
        rel1 = Relation(
            id=uuid.uuid4().hex[:12],
            source_entity_id=john1.id,
            target_entity_id=acme.id,
            relation_type="WORKS_AT",
            source_chunk_id=chunk1.id,
        )

        # chunk2: John Doe (duplicate) + Jane + MANAGED_BY relation sourced from dedup'd John
        john2 = _make_entity("John Doe", entity_type="PERSON", chunk_id=chunk2.id)
        jane = _make_entity("Jane", entity_type="PERSON", chunk_id=chunk2.id)
        rel2 = Relation(
            id=uuid.uuid4().hex[:12],
            source_entity_id=john2.id,  # john2.id will be remapped to john1.id after dedup
            target_entity_id=jane.id,
            relation_type="MANAGED_BY",
            source_chunk_id=chunk2.id,
        )

        result1 = ExtractionResult(chunk_id=chunk1.id, entities=[john1, acme], relations=[rel1])
        result2 = ExtractionResult(chunk_id=chunk2.id, entities=[john2, jane], relations=[rel2])

        extractor = _make_extractor([result1, result2])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([chunk1, chunk2])

        # 3 unique entities: john1/acme from chunk1, jane from chunk2 (john2 deduped)
        assert counts["entities_added"] == 3
        assert counts["relations_added"] == 2

        # The second relation must reference the canonical john1.id, not john2.id
        rel_calls = store.add_relation.call_args_list
        stored_rel2: Relation = rel_calls[1][0][0]
        assert stored_rel2.source_entity_id == john1.id, (
            "After dedup, relation source_entity_id must be remapped to the canonical entity ID"
        )

    async def test_empty_chunks_returns_zero_counts(self):
        """build_from_chunks with an empty list returns zero counts without errors."""
        extractor = _make_extractor([])
        store = _make_graph_store()
        builder = GraphBuilder(extractor=extractor, graph_store=store)

        counts = await builder.build_from_chunks([])

        assert counts == {"entities_added": 0, "relations_added": 0, "chunks_processed": 0}
        store.add_entity.assert_not_called()
        store.add_relation.assert_not_called()
