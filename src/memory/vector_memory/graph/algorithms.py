"""Graph algorithms for memory knowledge graph.

Pure Python implementations (no Neo4j, no networkx dependency):
- PageRank
- Shortest path (Dijkstra)
- Degree centrality
- Community detection (simplified)

- Connected components

Migrated from: unified-memory-mcp/src/graph/algorithms.py (778 lines)
Simplified for removed Neo4j, networkx dependencies.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import heapq
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .relation_types import RelationRegistry

logger = logging.getLogger(__name__)


@dataclass
class PathResult:
    """Result of a shortest path query."""

    source: str
    target: str
    path: list[str]
    total_weight: float
    hop_count: int


@dataclass
class CentralityResult:
    """Centrality score for a node."""

    node_id: str
    score: float
    rank: int


@dataclass
class PageRankResult:
    """PageRank result for a node."""

    node_id: str
    score: float
    iterations: int


@dataclass
class CommunityResult:
    """Community detection result."""

    community_id: int
    members: list[str]
    modularity: float


class GraphAlgorithms:
    """
    Graph algorithms operating on RelationRegistry.

    Builds an adjacency structure from relations and provides:
    - Shortest path (Dijkstra)
    - PageRank
    - Degree centrality
    - Connected components
    - Community detection (label propagation)
    """

    def __init__(self, registry: RelationRegistry | None = None):
        self._registry = registry or RelationRegistry()
        self._adj: dict[str, dict[str, float]] = {}  # source -> {target: weight}
        self._nodes: set[str] = set()
        self._rebuild_adjacency()

    def _rebuild_adjacency(self) -> None:
        """Rebuild adjacency structure from registry."""
        self._adj.clear()
        self._nodes.clear()

        for relation in self._registry.all_relations:
            source = relation.source_id
            target = relation.target_id
            weight = abs(relation.weight)
            self._nodes.add(source)
            self._nodes.add(target)
            self._adj.setdefault(source, {})[target] = weight
            # For bidirectional, also add reverse
            if relation.direction.value in ("bidirectional", "incoming"):
                self._adj.setdefault(target, {})[source] = weight

    def get_neighbors(self, node_id: str) -> dict[str, float]:
        """Get neighbors with edge weights."""
        return dict(self._adj.get(node_id, {}))

    def shortest_path(
        self,
        source: str,
        target: str,
        max_hops: int = 20,
    ) -> PathResult | None:
        """Find shortest path using Dijkstra's algorithm."""
        if source not in self._nodes or target not in self._nodes:
            return None
        if source == target:
            return PathResult(
                source=source, target=target, path=[source], total_weight=0.0, hop_count=0
            )

        # Dijkstra
        distances: dict[str, float] = {source: 0.0}
        previous: dict[str, str] = {}
        pq: list[tuple[float, str]] = [(0.0, source)]
        visited: set[str] = set()

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == target:
                path = []
                node = target
                while node != source:
                    path.append(node)
                    node = previous.get(node, source)
                path.append(source)
                path.reverse()
                return PathResult(
                    source=source,
                    target=target,
                    path=path,
                    total_weight=current_dist,
                    hop_count=len(path) - 1,
                )

            if len(visited) >= max_hops:
                break

            for neighbor, weight in self.get_neighbors(current).items():
                new_dist = current_dist + weight
                if neighbor not in visited and new_dist < distances.get(neighbor, float("inf")):
                    distances[neighbor] = new_dist
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        return None

    def pagerank(
        self,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> dict[str, float]:
        """
        Compute PageRank for all nodes.

        Returns dict of node_id -> pagerank_score.
        """
        nodes = list(self._nodes)
        n = len(nodes)
        if n == 0:
            return {}
        # Initialize
        rank = {node: 1.0 / n for node in nodes}
        out_degree = {node: len(self.get_neighbors(node)) for node in nodes}

        for iteration in range(max_iterations):
            new_rank = {}
            for node in nodes:
                rank_sum = 0.0
                # Find all nodes that link to this node
                for other in nodes:
                    if node in self.get_neighbors(other):
                        deg = out_degree.get(other, 0)
                        if deg > 0:
                            rank_sum += rank[other] / deg
                new_rank[node] = (1 - damping) / n + damping * rank_sum

            # Check convergence
            diff = sum(abs(new_rank[node] - rank[node]) for node in nodes)
            rank = new_rank
            if diff < tolerance:
                logger.debug("PageRank converged after %d iterations", iteration + 1)
                break

        return rank

    def degree_centrality(self) -> dict[str, int]:
        """Compute degree centrality (number of connections) for each node."""
        centrality: dict[str, int] = defaultdict(int)
        for node in self._nodes:
            centrality[node] = len(self.get_neighbors(node))
        return dict(centrality)

    def connected_components(self) -> list[set[str]]:
        """Find connected components using BFS."""
        visited: set[str] = set()
        components: list[set[str]] = []

        for node in self._nodes:
            if node in visited:
                continue

            component: set[str] = set()
            queue = [node]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in self.get_neighbors(current):
                    if neighbor not in visited:
                        queue.append(neighbor)

            components.append(component)
        return components

    def detect_communities(self, max_iterations: int = 10) -> list[CommunityResult]:
        """
        Detect communities using label propagation.

        Simplified algorithm -- assigns each node to the community
        most common among its neighbors.
        """
        nodes = list(self._nodes)
        if not nodes:
            return []

        # Initialize: each node is its own community
        labels = {node: i for i, node in enumerate(nodes)}

        for _ in range(max_iterations):
            changed = False
            for node in nodes:
                neighbors = list(self.get_neighbors(node).keys())
                if not neighbors:
                    continue

                # Count labels among neighbors
                label_counts: dict[int, int] = defaultdict(int)
                for neighbor in neighbors:
                    label_counts[labels[neighbor]] += 1

                # Pick most common label
                best_label = max(label_counts, key=lambda k: label_counts[k])
                if labels[node] != best_label:
                    labels[node] = best_label
                    changed = True

            if not changed:
                break

        # Group by label
        communities: dict[int, list[str]] = defaultdict(list)
        for node, label in labels.items():
            communities[label].append(node)

        return [
            CommunityResult(
                community_id=label,
                members=sorted(members),
                modularity=0.0,  # simplified -- exact modularity calculation omitted
            )
            for label, members in communities.items()
            if len(members) > 1
        ]

    def get_stats(self) -> dict[str, Any]:
        """Return graph statistics."""
        nodes = self._nodes
        edges = sum(len(targets) for targets in self._adj.values())
        components = self.connected_components()
        centrality = self.degree_centrality()

        top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total_nodes": len(nodes),
            "total_edges": edges,
            "connected_components": len(components),
            "largest_component_size": max(len(c) for c in components) if components else 0,
            "top_central_nodes": [(node, deg) for node, deg in top_central],
            "density": round(edges / (len(nodes) * (len(nodes) - 1)), 4) if len(nodes) > 1 else 0.0,
        }


__all__ = [
    "CentralityResult",
    "CommunityResult",
    "GraphAlgorithms",
    "PageRankResult",
    "PathResult",
]
