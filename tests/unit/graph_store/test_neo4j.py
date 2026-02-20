"""Unit tests for Neo4j Graph Store (Phase 51.5).

Tests CRUD operations and Cypher query generation with mocked Neo4j driver.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.schemas.entities import Entity, Relation


@pytest.fixture
def settings():
    return GraphStoreSettings(
        provider="neo4j",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="testpass",
    )


@pytest.fixture
def mock_session():
    """Create a mock Neo4j async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_driver(mock_session):
    """Create a mock Neo4j async driver with proper context manager."""
    driver = MagicMock()

    # Make session() return an async context manager that yields mock_session
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    driver.session = MagicMock(return_value=ctx)
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def sample_entity():
    return Entity(
        id="ent-001",
        name="Справочник",
        entity_type="CONCEPT",
        properties={"domain": "1C"},
        source_document_id="doc-001",
        source_chunk_ids=["chunk-1", "chunk-2"],
        confidence=0.95,
    )


@pytest.fixture
def sample_relation():
    return Relation(
        id="rel-001",
        source_entity_id="ent-001",
        target_entity_id="ent-002",
        relation_type="RELATED_TO",
        properties={"weight": 0.8},
        confidence=0.9,
        source_chunk_id="chunk-1",
    )


def _make_store(settings, driver):
    """Create a Neo4jGraphStore with a pre-set mock driver."""
    from src.pdf_framework.graph_store.providers.neo4j_store import Neo4jGraphStore

    store = Neo4jGraphStore(settings)
    store._driver = driver
    return store


class TestNeo4jGraphStore:
    """Tests for Neo4jGraphStore CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_entity(self, settings, mock_driver, mock_session, sample_entity):
        """Test adding a single entity."""
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"id": "ent-001"})
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        entity_id = await store.add_entity(sample_entity)

        assert entity_id == "ent-001"
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE" in cypher
        assert mock_session.run.call_args[1]["entity_id"] == "ent-001"

    @pytest.mark.asyncio
    async def test_add_relation(self, settings, mock_driver, mock_session, sample_relation):
        """Test adding a relation between entities."""
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"id": "rel-001"})
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        rel_id = await store.add_relation(sample_relation)

        assert rel_id == "rel-001"
        cypher = mock_session.run.call_args[0][0]
        assert "MATCH (a:Entity" in cypher
        assert "MATCH (b:Entity" in cypher
        assert mock_session.run.call_args[1]["source_id"] == "ent-001"

    @pytest.mark.asyncio
    async def test_get_entity(self, settings, mock_driver, mock_session):
        """Test fetching an entity by ID."""
        # Use a dict subclass that mimics Neo4j Node (dict() works correctly)
        class FakeNode(dict):
            pass

        mock_node = FakeNode(
            entity_id="ent-001",
            name="Справочник",
            entity_type="CONCEPT",
            properties={},
            source_document_id="doc-001",
            source_chunk_ids=[],
            confidence=1.0,
        )

        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"e": mock_node})
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        entity = await store.get_entity("ent-001")

        assert entity is not None
        assert entity.id == "ent-001"
        assert entity.name == "Справочник"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, settings, mock_driver, mock_session):
        """Test fetching a non-existent entity returns None."""
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        entity = await store.get_entity("nonexistent")
        assert entity is None

    @pytest.mark.asyncio
    async def test_find_entities(self, settings, mock_driver, mock_session):
        """Test searching entities by name."""
        result_mock = AsyncMock()
        result_mock.data = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        entities = await store.find_entities(name="Справочник", limit=5)

        assert isinstance(entities, list)
        cypher = mock_session.run.call_args[0][0]
        assert "CONTAINS" in cypher

    @pytest.mark.asyncio
    async def test_delete_entity(self, settings, mock_driver, mock_session):
        """Test deleting an entity."""
        mock_session.run = AsyncMock()

        store = _make_store(settings, mock_driver)
        await store.delete_entity("ent-001")

        cypher = mock_session.run.call_args[0][0]
        assert "DETACH DELETE" in cypher

    @pytest.mark.asyncio
    async def test_clear(self, settings, mock_driver, mock_session):
        """Test clearing all entities."""
        mock_session.run = AsyncMock()

        store = _make_store(settings, mock_driver)
        await store.clear()

        cypher = mock_session.run.call_args[0][0]
        assert "DETACH DELETE" in cypher

    @pytest.mark.asyncio
    async def test_get_statistics(self, settings, mock_driver, mock_session):
        """Test getting graph statistics."""
        result_mock = AsyncMock()
        result_mock.single = AsyncMock(return_value={"node_count": 100, "edge_count": 200})
        mock_session.run = AsyncMock(return_value=result_mock)

        store = _make_store(settings, mock_driver)
        stats = await store.get_statistics()

        assert stats["node_count"] == 100
        assert stats["edge_count"] == 200

    @pytest.mark.asyncio
    async def test_batch_mode_defers_writes(self, settings, mock_driver, mock_session, sample_entity):
        """Test batch mode defers writes."""
        store = _make_store(settings, mock_driver)
        store.set_batch_mode(True)

        await store.add_entity(sample_entity)

        # In batch mode, no session.run should be called
        mock_session.run.assert_not_called()
        assert len(store._batch_entities) == 1

    @pytest.mark.asyncio
    async def test_batch_flush(self, settings, mock_driver, mock_session, sample_entity):
        """Test batch flush sends UNWIND query."""
        mock_session.run = AsyncMock()

        store = _make_store(settings, mock_driver)
        store.set_batch_mode(True)
        await store.add_entity(sample_entity)
        await store.flush()

        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "UNWIND" in cypher
        assert len(store._batch_entities) == 0
