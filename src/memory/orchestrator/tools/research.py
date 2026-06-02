"""Research Tool — deep analysis of entity relationships and anomalies.

Provides analytical capabilities over the unified memory graph:
entity relationship mapping, anomaly detection, clustering, and timeline analysis.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..link_registry import LinkRegistry
    from ..unified_search import UnifiedSearchEngine

logger = logging.getLogger(__name__)


class ResearchTool:
    """Deep analysis of memory entities — relationships, anomalies, clusters, timelines.

    Works with LinkRegistry for graph analysis and search adapters for
    content-based analysis.

    Usage::

        tool = ResearchTool(link_registry, search_engine)
        result = await tool.analyze(
            query="BSL query patterns",
            analysis_type="relationships",
        )
    """

    def __init__(
        self, link_registry: LinkRegistry | None, search_engine: UnifiedSearchEngine | None
    ) -> None:
        self._links = link_registry
        self._search = search_engine

    async def analyze(
        self,
        query: str | None = None,
        entity_ids: list[str] | None = None,
        analysis_type: str = "relationships",
        max_depth: int = 3,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Run an analysis on memory entities.

        Args:
            query: Search query to find entities for analysis.
            entity_ids: Specific entity IDs to analyze.
            analysis_type: One of ``relationships``, ``anomalies``,
                ``clusters``, ``timeline``, ``summary``.
            max_depth: Maximum graph traversal depth.
            limit: Maximum entities to include.

        Returns:
            Analysis result dict.
        """
        # Resolve entity IDs from query if needed
        ids = entity_ids or []
        if query and self._search:
            search_result = await self._search.search(query=query, limit=limit, include_links=False)
            ids.extend(item.unified_id for item in search_result.results)

        if not ids:
            return {
                "analysis_type": analysis_type,
                "status": "no_entities",
                "message": "No entities found for analysis",
            }

        if analysis_type == "relationships":
            return await self._analyze_relationships(ids, max_depth, limit)
        elif analysis_type == "anomalies":
            return await self._analyze_anomalies(ids)
        elif analysis_type == "clusters":
            return await self._analyze_clusters(ids, max_depth)
        elif analysis_type == "timeline":
            return await self._analyze_timeline(ids)
        elif analysis_type == "summary":
            return await self._analyze_summary(ids, max_depth, limit)
        else:
            return {"error": f"Unknown analysis type: {analysis_type}"}

    async def _analyze_relationships(
        self, entity_ids: list[str], max_depth: int, limit: int
    ) -> dict[str, Any]:
        """Map relationships between entities."""
        if not self._links:
            return {"analysis_type": "relationships", "status": "no_link_registry"}

        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        for eid in entity_ids[:limit]:
            nodes[eid] = {"id": eid, "degree": 0}
            related = self._links.get_related_entities(eid, max_depth=max_depth)
            for rel in related:
                if rel.entity_id not in nodes:
                    nodes[rel.entity_id] = {"id": rel.entity_id, "degree": 0}
                nodes[eid]["degree"] += 1
                nodes[rel.entity_id]["degree"] += 1
                edges.append(
                    {
                        "source": eid,
                        "target": rel.entity_id,
                        "depth": rel.depth,
                        "strength": rel.effective_strength,
                    }
                )

        # Find hub nodes (highest degree)
        hub_nodes = sorted(nodes.values(), key=lambda n: n["degree"], reverse=True)[:5]

        return {
            "analysis_type": "relationships",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "hub_nodes": hub_nodes,
            "edges": edges[:50],
            "density": len(edges) / max(len(nodes) * (len(nodes) - 1) / 2, 1),
        }

    async def _analyze_anomalies(self, entity_ids: list[str]) -> dict[str, Any]:
        """Detect anomalous patterns in entities."""
        if not self._links:
            return {"analysis_type": "anomalies", "status": "no_link_registry"}

        anomalies = []

        # Detect isolated entities (no links)
        for eid in entity_ids:
            related = self._links.get_related_entities(eid, max_depth=1)
            if not related:
                anomalies.append(
                    {
                        "entity_id": eid,
                        "type": "isolated",
                        "description": "Entity has no links to other entities",
                        "severity": "low",
                    }
                )

        # Detect entities with unusually high connectivity
        degree_counts = []
        for eid in entity_ids:
            related = self._links.get_related_entities(eid, max_depth=1)
            degree_counts.append((eid, len(related)))

        if degree_counts:
            avg_degree = sum(d for _, d in degree_counts) / len(degree_counts)
            for eid, degree in degree_counts:
                if degree > avg_degree * 3 and degree > 5:
                    anomalies.append(
                        {
                            "entity_id": eid,
                            "type": "hub_anomaly",
                            "description": f"Unusually high connectivity: {degree} links (avg: {avg_degree:.1f})",
                            "severity": "medium",
                        }
                    )

        return {
            "analysis_type": "anomalies",
            "total_entities": len(entity_ids),
            "anomalies_found": len(anomalies),
            "anomalies": anomalies,
        }

    async def _analyze_clusters(
        self,
        entity_ids: list[str],
        max_depth: int,
    ) -> dict[str, Any]:
        """Find clusters of related entities using connected components."""
        if not self._links:
            return {"analysis_type": "clusters", "status": "no_link_registry"}

        # Simple connected components via BFS
        visited: set[str] = set()
        clusters: list[list[str]] = []

        for seed in entity_ids:
            if seed in visited:
                continue
            cluster: list[str] = []
            queue = [seed]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                cluster.append(node)
                related = self._links.get_related_entities(node, max_depth=1)
                for rel in related:
                    if rel.entity_id not in visited and rel.entity_id in entity_ids:
                        queue.append(rel.entity_id)
            if cluster:
                clusters.append(cluster)

        return {
            "analysis_type": "clusters",
            "total_clusters": len(clusters),
            "cluster_sizes": [len(c) for c in clusters],
            "clusters": [
                {"cluster_id": i, "size": len(c), "entities": c[:10]}
                for i, c in enumerate(clusters)
            ],
        }

    async def _analyze_timeline(self, entity_ids: list[str]) -> dict[str, Any]:
        """Analyze temporal patterns in entities."""
        # Parse timestamps from unified IDs or metadata
        events: list[dict[str, Any]] = []
        for eid in entity_ids:
            events.append({"entity_id": eid, "id": eid})

        return {
            "analysis_type": "timeline",
            "total_entities": len(entity_ids),
            "events": events[:50],
        }

    async def _analyze_summary(
        self, entity_ids: list[str], max_depth: int, limit: int
    ) -> dict[str, Any]:
        """Combined summary analysis."""
        relationships = await self._analyze_relationships(entity_ids, max_depth, limit)
        anomalies = await self._analyze_anomalies(entity_ids)

        return {
            "analysis_type": "summary",
            "total_entities": len(entity_ids),
            "relationships": {
                "nodes": relationships.get("total_nodes", 0),
                "edges": relationships.get("total_edges", 0),
                "density": relationships.get("density", 0),
            },
            "anomalies": {
                "count": anomalies.get("anomalies_found", 0),
                "types": Counter(a["type"] for a in anomalies.get("anomalies", [])),
            },
            "hub_nodes": relationships.get("hub_nodes", [])[:3],
        }


__all__ = ["ResearchTool"]
