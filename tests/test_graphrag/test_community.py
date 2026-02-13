"""Tests for CommunityDetector (Phase 6.1).

Tests Leiden community detection on real NetworkX graphs.
No LLM mocking needed — graspologic runs locally.
"""

import pytest
import networkx as nx

from src.pdf_framework.config import GraphRAGSettings
from src.pdf_framework.graph_store.community import CommunityDetector


@pytest.fixture
def settings():
    return GraphRAGSettings(leiden_resolution=1.0, community_levels=2)


@pytest.fixture
def detector(settings):
    return CommunityDetector(settings=settings)


@pytest.fixture
def empty_graph():
    return nx.DiGraph()


@pytest.fixture
def single_node_graph():
    g = nx.DiGraph()
    g.add_node("e1", name="Entity1", entity_type="CONCEPT")
    return g


@pytest.fixture
def disconnected_graph():
    """Graph with nodes but no edges."""
    g = nx.DiGraph()
    g.add_node("e1", name="Alice", entity_type="PERSON")
    g.add_node("e2", name="Bob", entity_type="PERSON")
    g.add_node("e3", name="Carol", entity_type="PERSON")
    return g


@pytest.fixture
def two_cluster_graph():
    """Graph with two clearly separated clusters."""
    g = nx.DiGraph()
    # Cluster A
    for i in range(5):
        g.add_node(f"a{i}", name=f"A{i}", entity_type="CONCEPT")
    for i in range(4):
        g.add_edge(f"a{i}", f"a{i+1}", relation_type="RELATED")
    g.add_edge("a4", "a0", relation_type="RELATED")  # Close the cycle

    # Cluster B
    for i in range(5):
        g.add_node(f"b{i}", name=f"B{i}", entity_type="CONCEPT")
    for i in range(4):
        g.add_edge(f"b{i}", f"b{i+1}", relation_type="RELATED")
    g.add_edge("b4", "b0", relation_type="RELATED")

    # Single weak bridge between clusters
    g.add_edge("a0", "b0", relation_type="MENTIONS")

    return g


@pytest.fixture
def dense_graph():
    """Densely connected graph (single community expected)."""
    g = nx.DiGraph()
    nodes = [f"n{i}" for i in range(6)]
    for n in nodes:
        g.add_node(n, name=n, entity_type="CONCEPT")
    # Fully connected
    for i, src in enumerate(nodes):
        for tgt in nodes[i + 1:]:
            g.add_edge(src, tgt, relation_type="RELATED")
    return g


class TestCommunityDetectorDetect:
    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty(self, detector, empty_graph):
        result = await detector.detect(empty_graph)
        assert result == {}

    @pytest.mark.asyncio
    async def test_no_edges_each_node_own_community(self, detector, disconnected_graph):
        result = await detector.detect(disconnected_graph)
        assert len(result) == 3
        # Each node gets a unique community
        community_ids = set(result.values())
        assert len(community_ids) == 3

    @pytest.mark.asyncio
    async def test_single_node_no_edges(self, detector, single_node_graph):
        result = await detector.detect(single_node_graph)
        assert len(result) == 1
        assert "e1" in result

    @pytest.mark.asyncio
    async def test_two_clusters_detected(self, detector, two_cluster_graph):
        result = await detector.detect(two_cluster_graph)
        assert len(result) == 10  # All 10 nodes assigned

        # Nodes within a cluster should have same community
        a_communities = {result[f"a{i}"] for i in range(5)}
        b_communities = {result[f"b{i}"] for i in range(5)}

        # Each cluster should be mostly in one community
        assert len(a_communities) <= 2  # Allow some flexibility
        assert len(b_communities) <= 2

    @pytest.mark.asyncio
    async def test_dense_graph_single_community(self, detector, dense_graph):
        result = await detector.detect(dense_graph)
        assert len(result) == 6
        # Dense graph should have very few communities
        unique_communities = set(result.values())
        assert len(unique_communities) <= 3

    @pytest.mark.asyncio
    async def test_custom_resolution(self, detector, two_cluster_graph):
        # High resolution = more communities
        high_res = await detector.detect(two_cluster_graph, resolution=10.0)
        low_res = await detector.detect(two_cluster_graph, resolution=0.1)

        high_count = len(set(high_res.values()))
        low_count = len(set(low_res.values()))

        # Higher resolution should produce >= communities as lower
        assert high_count >= low_count

    @pytest.mark.asyncio
    async def test_returns_string_keys_int_values(self, detector, two_cluster_graph):
        result = await detector.detect(two_cluster_graph)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, int)


class TestCommunityDetectorHierarchical:
    @pytest.mark.asyncio
    async def test_hierarchical_returns_correct_levels(self, detector, two_cluster_graph):
        results = await detector.detect_hierarchical(two_cluster_graph, levels=3)
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)

    @pytest.mark.asyncio
    async def test_hierarchical_default_levels(self, detector, two_cluster_graph):
        results = await detector.detect_hierarchical(two_cluster_graph)
        assert len(results) == 2  # settings.community_levels = 2

    @pytest.mark.asyncio
    async def test_hierarchical_higher_levels_more_communities(self, detector, two_cluster_graph):
        results = await detector.detect_hierarchical(two_cluster_graph, levels=3)
        # Higher resolution levels should tend to have more communities
        counts = [len(set(r.values())) for r in results]
        # At minimum, counts should be non-decreasing (not strictly, due to algorithm)
        assert counts[-1] >= counts[0]


class TestApplyToGraph:
    @pytest.mark.asyncio
    async def test_apply_sets_attributes(self, detector, two_cluster_graph):
        communities = await detector.detect(two_cluster_graph)
        result = await detector.apply_to_graph(two_cluster_graph, communities, level=0)

        assert result is two_cluster_graph  # Modifies in place

        for node_id, data in result.nodes(data=True):
            assert "community_id" in data
            assert data["community_level"] == 0

    @pytest.mark.asyncio
    async def test_apply_with_different_levels(self, detector, two_cluster_graph):
        communities = await detector.detect(two_cluster_graph)
        await detector.apply_to_graph(two_cluster_graph, communities, level=2)

        for _, data in two_cluster_graph.nodes(data=True):
            assert data["community_level"] == 2


class TestGetCommunityEntities:
    @pytest.mark.asyncio
    async def test_get_entities_for_community(self, detector, two_cluster_graph):
        communities = await detector.detect(two_cluster_graph)
        await detector.apply_to_graph(two_cluster_graph, communities, level=0)

        # Pick any community
        first_comm_id = communities["a0"]
        entities = detector.get_community_entities(two_cluster_graph, first_comm_id, level=0)

        assert len(entities) > 0
        assert all(isinstance(e, str) for e in entities)

    @pytest.mark.asyncio
    async def test_get_entities_nonexistent_community(self, detector, two_cluster_graph):
        communities = await detector.detect(two_cluster_graph)
        await detector.apply_to_graph(two_cluster_graph, communities, level=0)

        entities = detector.get_community_entities(two_cluster_graph, 999, level=0)
        assert entities == []


class TestGetCommunityStats:
    @pytest.mark.asyncio
    async def test_stats_empty(self, detector, empty_graph):
        stats = detector.get_community_stats(empty_graph, {})
        assert stats["num_communities"] == 0
        assert stats["num_entities"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_communities(self, detector, two_cluster_graph):
        communities = await detector.detect(two_cluster_graph)
        stats = detector.get_community_stats(two_cluster_graph, communities)

        assert stats["num_entities"] == 10
        assert stats["num_communities"] > 0
        assert stats["avg_community_size"] > 0
        assert stats["max_community_size"] >= stats["min_community_size"]
        assert "community_sizes" in stats
