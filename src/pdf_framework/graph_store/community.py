"""Leiden Community Detection for GraphRAG.

Implements community detection using the Leiden algorithm to identify
thematic clusters in the knowledge graph.

Author: Claude Code
Version: 0.7.0 - Phase 6.1: Community Detection
"""

import logging
from typing import Any

import networkx as nx

from src.pdf_framework.config import GraphRAGSettings

logger = logging.getLogger(__name__)

# Try to import graspologic for Leiden algorithm
try:
    from graspologic.partition import leiden
    GRASPOLOGIC_AVAILABLE = True
except ImportError:
    GRASPOLOGIC_AVAILABLE = False
    logger.warning(
        "[COMMUNITY] graspologic not available. "
        "Install with: pip install graspologic"
    )


class CommunityDetector:
    """
    Leiden community detection for knowledge graphs.

    Detects communities (clusters) of entities that are densely connected,
    enabling thematic grouping for GraphRAG operations.
    """

    def __init__(self, settings: GraphRAGSettings | None = None):
        """
        Initialize community detector.

        Args:
            settings: GraphRAG configuration
        """
        if not GRASPOLOGIC_AVAILABLE:
            raise ImportError(
                "graspologic is required for community detection. "
                "Install with: pip install graspologic"
            )

        self.settings = settings
        self.resolution = settings.leiden_resolution if settings else 1.0
        self.levels = settings.community_levels if settings else 2

    async def detect(
        self,
        graph: nx.DiGraph,
        resolution: float | None = None,
    ) -> dict[str, int]:
        """
        Detect communities using Leiden algorithm.

        Args:
            graph: NetworkX directed graph
            resolution: Resolution parameter (higher = more communities)
                       If None, uses self.resolution

        Returns:
            Dictionary mapping entity_id -> community_id
        """
        if graph.number_of_nodes() == 0:
            logger.warning("[COMMUNITY] Empty graph, no communities detected")
            return {}

        res = resolution if resolution is not None else self.resolution

        # Leiden works on undirected graphs
        undirected = graph.to_undirected(as_view=False)

        # Handle edge case: graph with no edges
        if undirected.number_of_edges() == 0:
            logger.info("[COMMUNITY] Graph has no edges, each node is its own community")
            return {node: i for i, node in enumerate(undirected.nodes())}

        try:
            # Run Leiden algorithm
            partition_dict = leiden(
                undirected,
                resolution=res,
                random_seed=42,  # For reproducibility
            )

            # partition_dict is a dict mapping node -> community_id
            communities = {str(k): int(v) for k, v in partition_dict.items()}

            num_communities = len(set(communities.values()))
            logger.info(
                f"[COMMUNITY] Detected {num_communities} communities "
                f"from {graph.number_of_nodes()} nodes (resolution={res})"
            )

            return communities

        except Exception as e:
            logger.error(f"[COMMUNITY] Leiden detection failed: {e}")
            # Fallback: each node is its own community
            return {node: i for i, node in enumerate(graph.nodes())}

    async def detect_hierarchical(
        self,
        graph: nx.DiGraph,
        levels: int | None = None,
    ) -> list[dict[str, int]]:
        """
        Detect communities at multiple hierarchy levels.

        Higher resolution values create more fine-grained communities.
        Each level doubles the resolution, creating a hierarchy.

        Args:
            graph: NetworkX directed graph
            levels: Number of hierarchy levels (default: self.levels)

        Returns:
            List of community dictionaries, one per level
        """
        lvl_count = levels if levels is not None else self.levels

        results = []
        base_resolution = self.resolution

        for level in range(lvl_count):
            # Double resolution for each level (1x, 2x, 4x, ...)
            level_resolution = base_resolution * (2 ** level)

            logger.info(f"[COMMUNITY] Detecting level {level + 1}/{lvl_count} (resolution={level_resolution})")

            communities = await self.detect(graph, resolution=level_resolution)
            results.append(communities)

        total_levels = len(results)
        logger.info(f"[COMMUNITY] Detected {total_levels} hierarchy levels")

        return results

    async def apply_to_graph(
        self,
        graph: nx.DiGraph,
        communities: dict[str, int],
        level: int = 0,
    ) -> nx.DiGraph:
        """
        Apply community assignments as node attributes in the graph.

        Args:
            graph: NetworkX graph to modify
            communities: entity_id -> community_id mapping
            level: Hierarchy level

        Returns:
            Modified graph with community attributes
        """
        for entity_id, community_id in communities.items():
            if entity_id in graph.nodes:
                graph.nodes[entity_id]["community_id"] = community_id
                graph.nodes[entity_id]["community_level"] = level

        logger.info(
            f"[COMMUNITY] Applied community attributes for level {level} "
            f"({len(communities)} entities)"
        )

        return graph

    def get_community_entities(
        self,
        graph: nx.DiGraph,
        community_id: int,
        level: int = 0,
    ) -> list[str]:
        """
        Get all entity IDs belonging to a specific community.

        Args:
            graph: NetworkX graph with community attributes
            community_id: Target community ID
            level: Hierarchy level to check

        Returns:
            List of entity IDs in the community
        """
        entities = []
        for node_id, data in graph.nodes(data=True):
            if (
                data.get("community_id") == community_id
                and data.get("community_level") == level
            ):
                entities.append(str(node_id))
        return entities

    def get_community_stats(
        self,
        graph: nx.DiGraph,
        communities: dict[str, int],
    ) -> dict[str, Any]:
        """
        Get statistics about detected communities.

        Args:
            graph: NetworkX graph
            communities: entity_id -> community_id mapping

        Returns:
            Statistics dictionary
        """
        if not communities:
            return {
                "num_communities": 0,
                "num_entities": 0,
                "avg_community_size": 0,
                "max_community_size": 0,
                "min_community_size": 0,
            }

        # Count entities per community
        community_sizes: dict[int, int] = {}
        for comm_id in communities.values():
            community_sizes[comm_id] = community_sizes.get(comm_id, 0) + 1

        sizes = list(community_sizes.values())

        return {
            "num_communities": len(community_sizes),
            "num_entities": len(communities),
            "avg_community_size": sum(sizes) / len(sizes) if sizes else 0,
            "max_community_size": max(sizes) if sizes else 0,
            "min_community_size": min(sizes) if sizes else 0,
            "community_sizes": community_sizes,
        }
