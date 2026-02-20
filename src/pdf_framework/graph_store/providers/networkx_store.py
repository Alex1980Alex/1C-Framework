"""NetworkX graph store with JSON persistence.

Implements BaseGraphStore using NetworkX for in-memory graph operations
with optional JSON serialization for persistence.
"""

import json
from pathlib import Path
from typing import Any

import networkx as nx

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation, SubGraph


class NetworkXGraphStore(BaseGraphStore):
    """NetworkX-backed graph store with JSON persistence."""

    def __init__(self, settings: GraphStoreSettings | None = None):
        self._settings = settings or GraphStoreSettings()
        self._graph = nx.DiGraph()
        self._persist_path = Path(self._settings.persist_dir) / "graph.json"
        self._batch_mode = False

    async def initialize(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        if self._persist_path.exists():
            self._load_from_file()

    def _load_from_file(self) -> None:
        data = json.loads(self._persist_path.read_text(encoding="utf-8"))
        self._graph = nx.DiGraph()
        for node in data.get("nodes", []):
            self._graph.add_node(node["id"], **node["data"])
        for edge in data.get("edges", []):
            self._graph.add_edge(edge["source"], edge["target"], **edge["data"])

    def _save_to_file(self) -> None:
        nodes = []
        for nid, data in self._graph.nodes(data=True):
            nodes.append({"id": nid, "data": data})
        edges = []
        for src, tgt, data in self._graph.edges(data=True):
            edges.append({"source": src, "target": tgt, "data": data})
        self._persist_path.write_text(
            json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_batch_mode(self, enabled: bool) -> None:
        """Enable/disable batch mode. In batch mode, file saves are deferred."""
        self._batch_mode = enabled

    def flush(self) -> None:
        """Persist graph to file (call after batch mode operations)."""
        self._save_to_file()

    async def add_entity(self, entity: Entity) -> str:
        self._graph.add_node(
            entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            properties=entity.properties,
            source_document_id=entity.source_document_id,
            source_chunk_ids=entity.source_chunk_ids,
            confidence=entity.confidence,
        )
        if not self._batch_mode:
            self._save_to_file()
        return entity.id

    async def add_relation(self, relation: Relation) -> str:
        self._graph.add_edge(
            relation.source_entity_id,
            relation.target_entity_id,
            id=relation.id,
            relation_type=relation.relation_type,
            properties=relation.properties,
            confidence=relation.confidence,
            source_chunk_id=relation.source_chunk_id,
        )
        if not self._batch_mode:
            self._save_to_file()
        return relation.id

    async def get_entity(self, entity_id: str) -> Entity | None:
        if entity_id not in self._graph:
            return None
        data = self._graph.nodes[entity_id]
        return Entity(
            id=entity_id,
            name=data.get("name", ""),
            entity_type=data.get("entity_type", ""),
            properties=data.get("properties", {}),
            source_document_id=data.get("source_document_id", ""),
            source_chunk_ids=data.get("source_chunk_ids", []),
            confidence=data.get("confidence", 1.0),
        )

    async def find_entities(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        results: list[Entity] = []
        for nid, data in self._graph.nodes(data=True):
            if name and name.lower() not in data.get("name", "").lower():
                continue
            if entity_type and data.get("entity_type") != entity_type:
                continue
            entity = await self.get_entity(nid)
            if entity:
                results.append(entity)
            if len(results) >= limit:
                break
        return results

    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> SubGraph:
        if entity_id not in self._graph:
            return SubGraph()

        visited: set[str] = set()
        entities: list[Entity] = []
        relations: list[Relation] = []
        queue = [(entity_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited or current_depth > depth:
                continue
            visited.add(current_id)

            entity = await self.get_entity(current_id)
            if entity:
                entities.append(entity)

            if current_depth < depth:
                for _, neighbor, edge_data in self._graph.edges(current_id, data=True):
                    if relation_type and edge_data.get("relation_type") != relation_type:
                        continue
                    relations.append(
                        Relation(
                            id=edge_data.get("id", ""),
                            source_entity_id=current_id,
                            target_entity_id=neighbor,
                            relation_type=edge_data.get("relation_type", ""),
                            properties=edge_data.get("properties", {}),
                            confidence=edge_data.get("confidence", 1.0),
                            source_chunk_id=edge_data.get("source_chunk_id", ""),
                        )
                    )
                    queue.append((neighbor, current_depth + 1))

                # Also traverse incoming edges
                for predecessor, _, edge_data in self._graph.in_edges(current_id, data=True):
                    if relation_type and edge_data.get("relation_type") != relation_type:
                        continue
                    if predecessor not in visited:
                        relations.append(
                            Relation(
                                id=edge_data.get("id", ""),
                                source_entity_id=predecessor,
                                target_entity_id=current_id,
                                relation_type=edge_data.get("relation_type", ""),
                                properties=edge_data.get("properties", {}),
                                confidence=edge_data.get("confidence", 1.0),
                                source_chunk_id=edge_data.get("source_chunk_id", ""),
                            )
                        )
                        queue.append((predecessor, current_depth + 1))

        center_entity = await self.get_entity(entity_id)
        return SubGraph(
            entities=entities,
            relations=relations,
            center_entity=center_entity,
            depth=depth,
        )

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> SubGraph:
        if source_id not in self._graph or target_id not in self._graph:
            return SubGraph()

        undirected = self._graph.to_undirected()
        try:
            path_nodes = nx.shortest_path(undirected, source_id, target_id)
        except nx.NetworkXNoPath:
            return SubGraph()

        if len(path_nodes) - 1 > max_depth:
            return SubGraph()

        entities: list[Entity] = []
        relations: list[Relation] = []

        for nid in path_nodes:
            entity = await self.get_entity(nid)
            if entity:
                entities.append(entity)

        for i in range(len(path_nodes) - 1):
            src, tgt = path_nodes[i], path_nodes[i + 1]
            if self._graph.has_edge(src, tgt):
                edge_data = self._graph.edges[src, tgt]
            elif self._graph.has_edge(tgt, src):
                edge_data = self._graph.edges[tgt, src]
                src, tgt = tgt, src
            else:
                continue
            relations.append(
                Relation(
                    id=edge_data.get("id", ""),
                    source_entity_id=src,
                    target_entity_id=tgt,
                    relation_type=edge_data.get("relation_type", ""),
                    properties=edge_data.get("properties", {}),
                    confidence=edge_data.get("confidence", 1.0),
                    source_chunk_id=edge_data.get("source_chunk_id", ""),
                )
            )

        center = await self.get_entity(source_id)
        return SubGraph(entities=entities, relations=relations, center_entity=center)

    async def query(
        self,
        query_str: str,
        params: dict[str, Any] | None = None,
    ) -> SubGraph:
        """Simple query: search entities by name substring."""
        entities = await self.find_entities(name=query_str, limit=20)
        all_relations: list[Relation] = []
        entity_ids = {e.id for e in entities}

        for src, tgt, data in self._graph.edges(data=True):
            if src in entity_ids or tgt in entity_ids:
                all_relations.append(
                    Relation(
                        id=data.get("id", ""),
                        source_entity_id=src,
                        target_entity_id=tgt,
                        relation_type=data.get("relation_type", ""),
                        properties=data.get("properties", {}),
                        confidence=data.get("confidence", 1.0),
                        source_chunk_id=data.get("source_chunk_id", ""),
                    )
                )

        return SubGraph(entities=entities, relations=all_relations)

    async def get_statistics(self) -> dict[str, Any]:
        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "connected_components": nx.number_weakly_connected_components(self._graph),
            "density": nx.density(self._graph),
        }

    async def delete_entity(self, entity_id: str) -> None:
        if entity_id in self._graph:
            self._graph.remove_node(entity_id)
            self._save_to_file()

    async def delete_by_document(self, document_id: str) -> int:
        nodes_to_remove = [
            nid
            for nid, data in self._graph.nodes(data=True)
            if data.get("source_document_id") == document_id
        ]
        for nid in nodes_to_remove:
            self._graph.remove_node(nid)  # also removes connected edges
        if nodes_to_remove:
            self._save_to_file()
        return len(nodes_to_remove)

    async def clear(self) -> None:
        self._graph.clear()
        self._save_to_file()
