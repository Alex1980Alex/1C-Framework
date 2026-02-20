"""Neo4j graph store provider (Phase 51).

Implements BaseGraphStore using Neo4j for production-grade graph operations
with ACID transactions, Cypher queries, and horizontal scalability.
"""

import logging
from typing import Any

from src.pdf_framework.config import GraphStoreSettings
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation, SubGraph

logger = logging.getLogger(__name__)


class Neo4jGraphStore(BaseGraphStore):
    """Neo4j-backed graph store with Cypher query support."""

    def __init__(self, settings: GraphStoreSettings | None = None):
        self._settings = settings or GraphStoreSettings()
        self._driver = None
        self._batch_mode = False
        self._batch_entities: list[Entity] = []
        self._batch_relations: list[Relation] = []

    async def initialize(self) -> None:
        """Initialize the Neo4j driver connection."""
        try:
            from neo4j import AsyncGraphDatabase
        except ImportError:
            raise ImportError(
                "neo4j package is required. Install with: pip install 'pdf-vector-graph-framework[neo4j]'"
            )

        self._driver = AsyncGraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )

        # Verify connection
        async with self._driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            await result.single()

        # Create indexes and constraints
        await self._ensure_indexes()
        logger.info("[NEO4J] Connected to %s", self._settings.neo4j_uri)

    async def _ensure_indexes(self) -> None:
        """Create indexes and constraints for optimal performance."""
        async with self._driver.session() as session:
            # Unique constraint on entity ID
            await session.run(
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE"
            )
            # Index on entity type for filtered queries
            await session.run(
                "CREATE INDEX entity_type_idx IF NOT EXISTS "
                "FOR (e:Entity) ON (e.entity_type)"
            )
            # Fulltext index on entity name for search
            try:
                await session.run(
                    "CREATE FULLTEXT INDEX entity_name_ft IF NOT EXISTS "
                    "FOR (e:Entity) ON EACH [e.name]"
                )
            except Exception:
                # Fulltext index might already exist with different config
                pass

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    def set_batch_mode(self, enabled: bool) -> None:
        """Enable/disable batch mode. In batch mode, writes are deferred."""
        self._batch_mode = enabled
        if not enabled:
            self._batch_entities.clear()
            self._batch_relations.clear()

    async def flush(self) -> None:
        """Flush batched entities and relations to Neo4j using UNWIND."""
        if self._batch_entities:
            await self._batch_insert_entities(self._batch_entities)
            self._batch_entities.clear()
        if self._batch_relations:
            await self._batch_insert_relations(self._batch_relations)
            self._batch_relations.clear()

    async def _batch_insert_entities(self, entities: list[Entity]) -> None:
        """Bulk insert entities using UNWIND for performance."""
        rows = [
            {
                "entity_id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "properties": e.properties,
                "source_document_id": e.source_document_id,
                "source_chunk_ids": e.source_chunk_ids,
                "confidence": e.confidence,
            }
            for e in entities
        ]
        cypher = """
        UNWIND $rows AS row
        MERGE (e:Entity {entity_id: row.entity_id})
        SET e.name = row.name,
            e.entity_type = row.entity_type,
            e.properties = row.properties,
            e.source_document_id = row.source_document_id,
            e.source_chunk_ids = row.source_chunk_ids,
            e.confidence = row.confidence
        """
        async with self._driver.session() as session:
            await session.run(cypher, rows=rows)
        logger.info("[NEO4J] Batch inserted %d entities", len(rows))

    async def _batch_insert_relations(self, relations: list[Relation]) -> None:
        """Bulk insert relations using UNWIND for performance."""
        rows = [
            {
                "relation_id": r.id,
                "source_id": r.source_entity_id,
                "target_id": r.target_entity_id,
                "relation_type": r.relation_type,
                "properties": r.properties,
                "confidence": r.confidence,
                "source_chunk_id": r.source_chunk_id,
            }
            for r in relations
        ]
        cypher = """
        UNWIND $rows AS row
        MATCH (a:Entity {entity_id: row.source_id})
        MATCH (b:Entity {entity_id: row.target_id})
        MERGE (a)-[r:RELATES_TO {relation_id: row.relation_id}]->(b)
        SET r.relation_type = row.relation_type,
            r.properties = row.properties,
            r.confidence = row.confidence,
            r.source_chunk_id = row.source_chunk_id
        """
        async with self._driver.session() as session:
            await session.run(cypher, rows=rows)
        logger.info("[NEO4J] Batch inserted %d relations", len(rows))

    async def add_entity(self, entity: Entity) -> str:
        """Add an entity node. Returns entity ID."""
        if self._batch_mode:
            self._batch_entities.append(entity)
            return entity.id

        cypher = """
        MERGE (e:Entity {entity_id: $entity_id})
        SET e.name = $name,
            e.entity_type = $entity_type,
            e.properties = $properties,
            e.source_document_id = $source_document_id,
            e.source_chunk_ids = $source_chunk_ids,
            e.confidence = $confidence
        RETURN e.entity_id AS id
        """
        async with self._driver.session() as session:
            result = await session.run(
                cypher,
                entity_id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                properties=entity.properties,
                source_document_id=entity.source_document_id,
                source_chunk_ids=entity.source_chunk_ids,
                confidence=entity.confidence,
            )
            record = await result.single()
            return record["id"]

    async def add_relation(self, relation: Relation) -> str:
        """Add a relation edge. Returns relation ID."""
        if self._batch_mode:
            self._batch_relations.append(relation)
            return relation.id

        cypher = """
        MATCH (a:Entity {entity_id: $source_id})
        MATCH (b:Entity {entity_id: $target_id})
        MERGE (a)-[r:RELATES_TO {relation_id: $relation_id}]->(b)
        SET r.relation_type = $relation_type,
            r.properties = $properties,
            r.confidence = $confidence,
            r.source_chunk_id = $source_chunk_id
        RETURN r.relation_id AS id
        """
        async with self._driver.session() as session:
            result = await session.run(
                cypher,
                relation_id=relation.id,
                source_id=relation.source_entity_id,
                target_id=relation.target_entity_id,
                relation_type=relation.relation_type,
                properties=relation.properties,
                confidence=relation.confidence,
                source_chunk_id=relation.source_chunk_id,
            )
            record = await result.single()
            return record["id"]

    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        cypher = """
        MATCH (e:Entity {entity_id: $entity_id})
        RETURN e
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, entity_id=entity_id)
            record = await result.single()
            if not record:
                return None
            return self._record_to_entity(record["e"])

    async def find_entities(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Search for entities by name or type."""
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if name:
            conditions.append("toLower(e.name) CONTAINS toLower($name)")
            params["name"] = name
        if entity_type:
            conditions.append("e.entity_type = $entity_type")
            params["entity_type"] = entity_type

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cypher = f"""
        MATCH (e:Entity)
        {where_clause}
        RETURN e
        LIMIT $limit
        """
        async with self._driver.session() as session:
            result = await session.run(cypher, **params)
            records = await result.data()
            return [self._record_to_entity(r["e"]) for r in records]

    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> SubGraph:
        """Get neighboring entities up to a given depth."""
        rel_filter = ""
        params: dict[str, Any] = {"entity_id": entity_id, "depth": depth}
        if relation_type:
            rel_filter = "{relation_type: $relation_type}"
            params["relation_type"] = relation_type

        cypher = f"""
        MATCH (start:Entity {{entity_id: $entity_id}})
        CALL apoc.path.subgraphAll(start, {{
            maxLevel: $depth,
            relationshipFilter: 'RELATES_TO'
        }})
        YIELD nodes, relationships
        RETURN nodes, relationships
        """

        # Fallback to simple variable-length path if APOC not available
        cypher_fallback = f"""
        MATCH path = (start:Entity {{entity_id: $entity_id}})-[r:RELATES_TO {rel_filter}*1..{depth}]-(neighbor:Entity)
        WITH start, collect(DISTINCT neighbor) AS neighbors,
             collect(DISTINCT r) AS rels_nested
        UNWIND rels_nested AS rel_list
        UNWIND rel_list AS rel
        WITH start, neighbors,
             collect(DISTINCT rel) AS all_rels
        RETURN start, neighbors, all_rels
        """

        async with self._driver.session() as session:
            try:
                result = await session.run(cypher, **params)
                record = await result.single()
                if not record:
                    return SubGraph()
                entities = [self._record_to_entity(n) for n in record["nodes"]]
                relations = [self._record_to_relation(r) for r in record["relationships"]]
            except Exception:
                # APOC not available, use fallback
                result = await session.run(cypher_fallback, **params)
                record = await result.single()
                if not record:
                    return SubGraph()
                entities = [self._record_to_entity(record["start"])]
                entities.extend(
                    self._record_to_entity(n) for n in record["neighbors"]
                )
                relations = [self._record_to_relation(r) for r in record["all_rels"]]

        center = await self.get_entity(entity_id)
        return SubGraph(entities=entities, relations=relations, center_entity=center, depth=depth)

    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> SubGraph:
        """Find shortest path between two entities."""
        cypher = """
        MATCH path = shortestPath(
            (a:Entity {entity_id: $source_id})-[*..%d]-(b:Entity {entity_id: $target_id})
        )
        RETURN nodes(path) AS nodes, relationships(path) AS rels
        """ % max_depth

        async with self._driver.session() as session:
            result = await session.run(cypher, source_id=source_id, target_id=target_id)
            record = await result.single()
            if not record:
                return SubGraph()

            entities = [self._record_to_entity(n) for n in record["nodes"]]
            relations = [self._record_to_relation(r) for r in record["rels"]]

        center = await self.get_entity(source_id)
        return SubGraph(entities=entities, relations=relations, center_entity=center)

    async def query(
        self,
        query_str: str,
        params: dict[str, Any] | None = None,
    ) -> SubGraph:
        """Execute a raw Cypher query."""
        async with self._driver.session() as session:
            result = await session.run(query_str, **(params or {}))
            records = await result.data()

        entities: list[Entity] = []
        relations: list[Relation] = []

        for record in records:
            for value in record.values():
                if hasattr(value, "labels") and "Entity" in value.labels:
                    entities.append(self._record_to_entity(value))
                elif hasattr(value, "type"):
                    relations.append(self._record_to_relation(value))

        return SubGraph(entities=entities, relations=relations)

    async def get_statistics(self) -> dict[str, Any]:
        """Return graph statistics: node count, edge count, etc."""
        cypher = """
        MATCH (e:Entity)
        WITH count(e) AS node_count
        MATCH ()-[r:RELATES_TO]->()
        WITH node_count, count(r) AS edge_count
        RETURN node_count, edge_count
        """
        async with self._driver.session() as session:
            result = await session.run(cypher)
            record = await result.single()
            if not record:
                return {"node_count": 0, "edge_count": 0}

            return {
                "node_count": record["node_count"],
                "edge_count": record["edge_count"],
            }

    async def delete_entity(self, entity_id: str) -> None:
        """Delete entity and all its relations."""
        cypher = """
        MATCH (e:Entity {entity_id: $entity_id})
        DETACH DELETE e
        """
        async with self._driver.session() as session:
            await session.run(cypher, entity_id=entity_id)

    async def delete_by_document(self, document_id: str) -> int:
        cypher = """
        MATCH (e:Entity {source_document_id: $doc_id})
        WITH e, count(e) AS cnt
        DETACH DELETE e
        RETURN cnt
        """
        async with self._driver.session() as session:
            # Two-step: count then delete, since DETACH DELETE doesn't return count easily
            count_result = await session.run(
                "MATCH (e:Entity {source_document_id: $doc_id}) RETURN count(e) AS cnt",
                doc_id=document_id,
            )
            record = await count_result.single()
            count = record["cnt"] if record else 0

            if count > 0:
                await session.run(
                    "MATCH (e:Entity {source_document_id: $doc_id}) DETACH DELETE e",
                    doc_id=document_id,
                )
                logger.info("[NEO4J] Deleted %d entities for document %s", count, document_id)
            return count

    async def clear(self) -> None:
        """Remove all entities and relations."""
        async with self._driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
        logger.info("[NEO4J] Cleared all entities and relations")

    # ======== Helper methods ========

    @staticmethod
    def _record_to_entity(node) -> Entity:
        """Convert a Neo4j node record to an Entity."""
        props = dict(node)
        return Entity(
            id=props.get("entity_id", ""),
            name=props.get("name", ""),
            entity_type=props.get("entity_type", ""),
            properties=props.get("properties", {}),
            source_document_id=props.get("source_document_id", ""),
            source_chunk_ids=props.get("source_chunk_ids", []),
            confidence=props.get("confidence", 1.0),
        )

    @staticmethod
    def _record_to_relation(rel) -> Relation:
        """Convert a Neo4j relationship record to a Relation."""
        props = dict(rel)
        return Relation(
            id=props.get("relation_id", ""),
            source_entity_id=str(rel.start_node.element_id) if hasattr(rel, "start_node") else "",
            target_entity_id=str(rel.end_node.element_id) if hasattr(rel, "end_node") else "",
            relation_type=props.get("relation_type", ""),
            properties=props.get("properties", {}),
            confidence=props.get("confidence", 1.0),
            source_chunk_id=props.get("source_chunk_id", ""),
        )
