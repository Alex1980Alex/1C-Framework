"""Tests for GraphRAG Local Search (Phase 6.3).

Tests entity extraction and context formatting without LLM calls.
"""

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult


def _make_strategy():
    """Create strategy with mocked dependencies."""
    from unittest.mock import MagicMock

    from src.pdf_framework.search.strategies.graphrag_local import GraphRAGLocalStrategy

    strategy = object.__new__(GraphRAGLocalStrategy)
    strategy._embedding_engine = MagicMock()
    strategy._vector_store = MagicMock()
    strategy._graph_store = MagicMock()
    strategy._neighbor_depth = 1
    strategy._include_community_summary = True
    return strategy


def _make_result(content: str, score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk=DocumentChunk(
            id="c1",
            content=content,
            document_id="doc1",
            metadata={},
        ),
        score=score,
    )


class TestExtractEntitiesFromChunks:
    @pytest.mark.asyncio
    async def test_extracts_multi_word_capitalized(self):
        s = _make_strategy()
        results = [_make_result("The Federal Reserve Board announced new policy changes.")]
        entities = await s._extract_entities_from_chunks(results)
        # Regex captures "The Federal Reserve Board" since "The" is capitalized too
        assert any("Federal Reserve" in e for e in entities)

    @pytest.mark.asyncio
    async def test_extracts_acronyms(self):
        s = _make_strategy()
        results = [_make_result("The NASA and FBI report was released.")]
        entities = await s._extract_entities_from_chunks(results)
        assert "NASA" in entities
        assert "FBI" in entities

    @pytest.mark.asyncio
    async def test_filters_common_words(self):
        s = _make_strategy()
        results = [_make_result("The company was acquired by Google Corp.")]
        entities = await s._extract_entities_from_chunks(results)
        # "The" should be filtered out as a common word
        for entity in entities:
            assert entity.lower() not in {"the", "and", "this", "that"}

    @pytest.mark.asyncio
    async def test_empty_content(self):
        s = _make_strategy()
        results = [_make_result("")]
        entities = await s._extract_entities_from_chunks(results)
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_no_entities_in_lowercase(self):
        s = _make_strategy()
        results = [_make_result("all lowercase text without any proper nouns or entities")]
        entities = await s._extract_entities_from_chunks(results)
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_multiple_chunks(self):
        s = _make_strategy()
        results = [
            _make_result("Microsoft announced partnership."),
            _make_result("Google Cloud expanded services."),
        ]
        entities = await s._extract_entities_from_chunks(results)
        assert "Microsoft" not in entities  # Single word, not matched by multi-word pattern
        assert "Google Cloud" in entities

    @pytest.mark.asyncio
    async def test_deduplicates_entities(self):
        s = _make_strategy()
        results = [
            _make_result("United States government. United States economy."),
        ]
        entities = await s._extract_entities_from_chunks(results)
        # Should appear only once despite occurring twice
        count = sum(1 for e in entities if e == "United States")
        assert count <= 1  # set deduplication

    @pytest.mark.asyncio
    async def test_graph_aware_matching(self):
        """Test that known entity names from graph are matched in content."""
        import networkx as nx
        from unittest.mock import MagicMock

        from src.pdf_framework.search.strategies.graphrag_local import GraphRAGLocalStrategy

        strategy = object.__new__(GraphRAGLocalStrategy)
        strategy._embedding_engine = MagicMock()
        strategy._vector_store = MagicMock()

        # Create a mock graph store with a real NetworkX graph
        graph_store = MagicMock()
        g = nx.DiGraph()
        g.add_node("e1", name="Конфигуратор", entity_type="CONCEPT")
        g.add_node("e2", name="1С:Предприятие", entity_type="ORG")
        graph_store._graph = g
        strategy._graph_store = graph_store
        strategy._neighbor_depth = 1
        strategy._include_community_summary = True

        results = [_make_result("Конфигуратор — основной инструмент 1С:Предприятие")]
        entities = await strategy._extract_entities_from_chunks(results)

        assert "Конфигуратор" in entities
        assert "1С:Предприятие" in entities


class TestFormatGraphContext:
    def test_format_with_entity(self):
        from src.pdf_framework.schemas.entities import Entity

        s = _make_strategy()
        context = {
            "entity": Entity(
                id="e1", name="Microsoft", entity_type="ORG",
                source_document_id="d1",
            ),
            "neighbors": [],
            "relations": [],
        }
        result = s._format_graph_context(context)
        assert "Microsoft" in result
        assert "ORG" in result

    def test_format_with_neighbors(self):
        from src.pdf_framework.schemas.entities import Entity

        s = _make_strategy()
        context = {
            "entity": Entity(
                id="e1", name="Microsoft", entity_type="ORG",
                source_document_id="d1",
            ),
            "neighbors": [
                Entity(id="e2", name="Azure", entity_type="PRODUCT", source_document_id="d1"),
                Entity(id="e3", name="GitHub", entity_type="PRODUCT", source_document_id="d1"),
            ],
            "relations": [],
        }
        result = s._format_graph_context(context)
        assert "Azure" in result
        assert "GitHub" in result
        assert "Connected to" in result

    def test_format_with_relations(self):
        from src.pdf_framework.schemas.entities import Entity, Relation

        s = _make_strategy()
        context = {
            "entity": Entity(
                id="e1", name="Microsoft", entity_type="ORG",
                source_document_id="d1",
            ),
            "neighbors": [],
            "relations": [
                Relation(
                    id="r1", source_entity_id="e1", target_entity_id="e2",
                    relation_type="OWNS",
                ),
            ],
        }
        result = s._format_graph_context(context)
        assert "OWNS" in result
        assert "Relations" in result

    def test_format_empty_context(self):
        s = _make_strategy()
        result = s._format_graph_context({})
        assert result == ""
