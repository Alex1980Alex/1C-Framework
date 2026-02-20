"""Migration script: NetworkX JSON → Neo4j (Phase 51.4).

Reads the NetworkX JSON persistence file, creates entities and relations
in Neo4j using batch UNWIND operations, then verifies counts match.

Usage:
    python -m scripts.migrate_graph [--neo4j-uri bolt://localhost:7687]
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


async def migrate(neo4j_uri: str, neo4j_user: str, neo4j_password: str, json_path: Path) -> None:
    """Run the full migration pipeline."""
    from src.pdf_framework.config import GraphStoreSettings
    from src.pdf_framework.graph_store.providers.neo4j_store import Neo4jGraphStore
    from src.pdf_framework.schemas.entities import Entity, Relation

    # 1. Load NetworkX JSON
    if not json_path.exists():
        logger.error("Graph JSON not found: %s", json_path)
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    logger.info("Loaded %d nodes, %d edges from %s", len(nodes), len(edges), json_path)

    # 2. Connect to Neo4j
    settings = GraphStoreSettings(
        provider="neo4j",
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
    )
    store = Neo4jGraphStore(settings)
    await store.initialize()

    # 3. Clear existing data (optional — comment out to append)
    logger.info("Clearing existing Neo4j data...")
    await store.clear()

    # 4. Batch insert entities
    store.set_batch_mode(True)
    for node in nodes:
        node_data = node.get("data", {})
        entity = Entity(
            id=node["id"],
            name=node_data.get("name", ""),
            entity_type=node_data.get("entity_type", ""),
            properties=node_data.get("properties", {}),
            source_document_id=node_data.get("source_document_id", ""),
            source_chunk_ids=node_data.get("source_chunk_ids", []),
            confidence=node_data.get("confidence", 1.0),
        )
        await store.add_entity(entity)
    await store.flush()
    logger.info("Inserted %d entities", len(nodes))

    # 5. Batch insert relations
    for edge in edges:
        edge_data = edge.get("data", {})
        relation = Relation(
            id=edge_data.get("id", f"{edge['source']}->{edge['target']}"),
            source_entity_id=edge["source"],
            target_entity_id=edge["target"],
            relation_type=edge_data.get("relation_type", "RELATED_TO"),
            properties=edge_data.get("properties", {}),
            confidence=edge_data.get("confidence", 1.0),
            source_chunk_id=edge_data.get("source_chunk_id", ""),
        )
        await store.add_relation(relation)
    await store.flush()
    store.set_batch_mode(False)
    logger.info("Inserted %d relations", len(edges))

    # 6. Create additional indexes
    logger.info("Creating fulltext and type indexes...")
    async with store._driver.session() as session:
        await session.run(
            "CREATE INDEX entity_source_doc IF NOT EXISTS "
            "FOR (e:Entity) ON (e.source_document_id)"
        )

    # 7. Verify counts
    stats = await store.get_statistics()
    neo4j_nodes = stats["node_count"]
    neo4j_edges = stats["edge_count"]

    logger.info("=== Verification ===")
    logger.info("Source:  %d nodes, %d edges", len(nodes), len(edges))
    logger.info("Neo4j:   %d nodes, %d edges", neo4j_nodes, neo4j_edges)

    if neo4j_nodes == len(nodes) and neo4j_edges == len(edges):
        logger.info("Migration SUCCESSFUL — counts match")
    else:
        logger.warning(
            "Migration MISMATCH — expected %d/%d, got %d/%d",
            len(nodes), len(edges), neo4j_nodes, neo4j_edges,
        )

    await store.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate NetworkX graph to Neo4j")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")
    parser.add_argument(
        "--json-path",
        default=str(PROJECT_ROOT / "data" / "graph_db" / "graph.json"),
    )
    args = parser.parse_args()

    asyncio.run(migrate(args.neo4j_uri, args.neo4j_user, args.neo4j_password, Path(args.json_path)))


if __name__ == "__main__":
    main()
