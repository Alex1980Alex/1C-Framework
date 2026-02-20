"""Unit tests for Graph Builder (F2.8.2).

Tests:
- F2.8.2: Test deduplication in GraphBuilder
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestGraphBuilder:
    """Test GraphBuilder construction and deduplication."""

    def test_build_from_chunks(self):
        """F2.8.2: Should build graph from document chunks."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder()

        chunks = [
            MagicMock(
                content="John Doe works at Acme Corporation.",
                metadata={"entities": []}
            ),
            MagicMock(
                content="Jane Smith is a colleague of John Doe.",
                metadata={"entities": []}
            ),
        ]

        graph = builder.build(chunks)

        assert graph is not None

    def test_deduplication_same_entity(self):
        """F2.8.2: Should deduplicate identical entities."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder()

        # Same entity mentioned twice
        chunks = [
            MagicMock(
                content="John Doe is a person.",
                metadata={"entities": [{"name": "John Doe", "type": "Person"}]}
            ),
            MagicMock(
                content="John Doe lives in New York.",
                metadata={"entities": [{"name": "John Doe", "type": "Person"}]}
            ),
        ]

        graph = builder.build(chunks, deduplicate=True)

        # Should only have one John Doe
        john_entities = [e for e in graph.get_all_entities() if e["name"] == "John Doe"]
        assert len(john_entities) == 1

    def test_deduplication_case_insensitive(self):
        """F2.8.2: Deduplication should be case-insensitive."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder(deduplication_case_sensitive=False)

        chunks = [
            MagicMock(
                content="john doe is a person",
                metadata={"entities": [{"name": "john doe", "type": "Person"}]}
            ),
            MagicMock(
                content="John Doe lives here",
                metadata={"entities": [{"name": "John Doe", "type": "Person"}]}
            ),
        ]

        graph = builder.build(chunks, deduplicate=True)

        # Should deduplicate case-insensitively
        entities = graph.get_all_entities()
        john_count = sum(1 for e in entities if e["name"].lower() == "john doe")
        assert john_count == 1

    def test_relation_extraction(self):
        """F2.8.2: Should extract relations from text."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder()

        chunk = MagicMock(
            content="John Doe works at Acme Corporation. He is managed by Jane Smith.",
            metadata={"entities": [
                {"name": "John Doe", "type": "Person"},
                {"name": "Acme Corporation", "type": "Organization"},
                {"name": "Jane Smith", "type": "Person"},
            ]}
        )

        graph = builder.build([chunk], extract_relations=True)

        # Should have relations
        relations = graph.get_all_relations()
        assert len(relations) > 0

    def test_filter_by_confidence(self):
        """F2.8.2: Should filter entities by confidence score."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder(min_confidence=0.7)

        chunk = MagicMock(
            content="Test content",
            metadata={"entities": [
                {"name": "High Confidence", "confidence": 0.9},
                {"name": "Low Confidence", "confidence": 0.5},
            ]}
        )

        graph = builder.build([chunk])

        entity_names = [e["name"] for e in graph.get_all_entities()]
        assert "High Confidence" in entity_names
        assert "Low Confidence" not in entity_names

    def test_merge_entities_same_type(self):
        """F2.8.2: Should merge entities of same type."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder()

        # Create two mentions of the same entity
        entity1 = {"name": "John Doe", "type": "Person", "age": 30}
        entity2 = {"name": "John Doe", "type": "Person", "city": "NYC"}

        merged = builder._merge_entities(entity1, entity2)

        assert merged["name"] == "John Doe"
        assert merged["age"] == 30
        assert merged["city"] == "NYC"

    def test_no_merge_different_types(self):
        """F2.8.2: Should NOT merge entities of different types."""
        from src.pdf_framework.graph_store.construction.builder import GraphBuilder

        builder = GraphBuilder()

        entity1 = {"name": "Apple", "type": "Organization"}
        entity2 = {"name": "Apple", "type": "Product"}

        merged = builder._merge_entities(entity1, entity2)

        # Should not merge - return None
        assert merged is None
