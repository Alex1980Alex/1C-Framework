"""Entity & Relation Embedding Builder for LightRAG (Phase 38).

Builds vector embeddings for all graph entities and relations,
stored in a separate Qdrant collection for fast retrieval.

This replaces the expensive LLM map-reduce of Full GraphRAG Global
with pure vector search (~100 tokens vs ~5000, 50x cheaper).
"""

import logging
import uuid
from typing import Any

from src.pdf_framework.config import LightRAGSettings

logger = logging.getLogger(__name__)

# Namespace UUID for entity/relation embedding IDs
_ENTITY_NS = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


def _make_id(prefix: str, name: str) -> str:
    """Deterministic UUID5 from prefix+name."""
    return str(uuid.uuid5(_ENTITY_NS, f"{prefix}:{name}"))


def _entity_text(name: str, entity_type: str, properties: dict[str, Any]) -> str:
    """Build embedding text for an entity.

    Format: "EntityName (TYPE): key1=val1, key2=val2"
    """
    parts = [f"{name} ({entity_type})"]
    if properties:
        props = ", ".join(
            f"{k}={v}" for k, v in properties.items()
            if k not in ("source_document_id", "source_chunk_ids", "confidence")
            and v  # skip empty values
        )
        if props:
            parts.append(f": {props}")
    return "".join(parts)


def _relation_text(
    source_name: str,
    relation_type: str,
    target_name: str,
    properties: dict[str, Any],
) -> str:
    """Build embedding text for a relation.

    Format: "SourceName -[RELATION_TYPE]-> TargetName: key1=val1"
    """
    parts = [f"{source_name} -[{relation_type}]-> {target_name}"]
    if properties:
        props = ", ".join(
            f"{k}={v}" for k, v in properties.items()
            if k not in ("source_chunk_id", "confidence") and v
        )
        if props:
            parts.append(f": {props}")
    return "".join(parts)


class EntityEmbeddingBuilder:
    """Builds and stores entity/relation embeddings in Qdrant.

    Usage:
        builder = EntityEmbeddingBuilder(embedding_engine, settings, qdrant_url)
        stats = await builder.build(graph_store)
    """

    def __init__(
        self,
        embedding_engine: Any,
        settings: LightRAGSettings,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: str = "",
        dimensions: int = 1024,
    ):
        self._embedding_engine = embedding_engine
        self._settings = settings
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._dimensions = dimensions
        self._collection_name = settings.collection_name
        self._client = None

    async def _get_client(self):
        """Lazy-init async Qdrant client."""
        if self._client is None:
            from qdrant_client import AsyncQdrantClient

            api_key = self._qdrant_api_key or None
            self._client = AsyncQdrantClient(
                url=self._qdrant_url,
                api_key=api_key if api_key else None,
            )
        return self._client

    async def _ensure_collection(self) -> None:
        """Create graph_embeddings collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams

        client = await self._get_client()
        collections = await client.get_collections()
        names = [c.name for c in collections.collections]

        if self._collection_name not in names:
            logger.info(
                "[LIGHTRAG] Creating collection: %s (dims=%d)",
                self._collection_name, self._dimensions,
            )
            await client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._dimensions,
                    distance=Distance.COSINE,
                ),
            )
        else:
            logger.info("[LIGHTRAG] Collection %s already exists", self._collection_name)

    async def build(self, graph_store: Any) -> dict[str, int]:
        """Build entity and relation embeddings from the graph store.

        Args:
            graph_store: BaseGraphStore with _graph (NetworkX) attribute.

        Returns:
            Stats dict: entity_count, relation_count, total_points.
        """
        graph = getattr(graph_store, "_graph", None)
        if graph is None:
            raise ValueError("Graph store does not expose internal graph")

        if graph.number_of_nodes() == 0:
            raise ValueError("Graph is empty — index documents first")

        await self._ensure_collection()

        # Step 1: Collect entity texts
        entity_items = []  # (id, text, payload)
        node_names: dict[str, str] = {}  # node_id -> name

        for node_id, data in graph.nodes(data=True):
            if data.get("node_type") == "COMMUNITY":
                continue

            name = data.get("name", "")
            if not name:
                continue

            node_names[node_id] = name
            entity_type = data.get("entity_type", data.get("type", "UNKNOWN"))
            props = data.get("properties", {})
            if isinstance(props, str):
                props = {}

            text = _entity_text(name, entity_type, props)
            eid = _make_id("entity", node_id)

            payload = {
                "type": "entity",
                "graph_id": node_id,
                "name": name,
                "entity_type": entity_type,
                "text": text,
                "source_chunk_ids": data.get("source_chunk_ids", []),
                "source_document_id": data.get("source_document_id", ""),
            }
            entity_items.append((eid, text, payload))

        logger.info("[LIGHTRAG] Collected %d entities for embedding", len(entity_items))

        # Step 2: Collect relation texts
        relation_items = []  # (id, text, payload)

        for src_id, tgt_id, data in graph.edges(data=True):
            src_name = node_names.get(src_id, src_id)
            tgt_name = node_names.get(tgt_id, tgt_id)
            rel_type = data.get("relation_type", data.get("type", "RELATED_TO"))
            props = data.get("properties", {})
            if isinstance(props, str):
                props = {}

            text = _relation_text(src_name, rel_type, tgt_name, props)
            rid = _make_id("relation", f"{src_id}:{rel_type}:{tgt_id}")

            payload = {
                "type": "relation",
                "source_id": src_id,
                "target_id": tgt_id,
                "source_name": src_name,
                "target_name": tgt_name,
                "relation_type": rel_type,
                "text": text,
                "source_chunk_id": data.get("source_chunk_id", ""),
            }
            relation_items.append((rid, text, payload))

        logger.info("[LIGHTRAG] Collected %d relations for embedding", len(relation_items))

        # Step 3: Embed all texts in batches
        all_items = entity_items + relation_items
        if not all_items:
            return {"entity_count": 0, "relation_count": 0, "total_points": 0}

        all_texts = [item[1] for item in all_items]

        logger.info("[LIGHTRAG] Embedding %d texts...", len(all_texts))
        embeddings = await self._embedding_engine.embed_batch(all_texts)
        logger.info("[LIGHTRAG] Embedding complete")

        # Step 4: Upsert to Qdrant
        from qdrant_client.models import PointStruct

        client = await self._get_client()
        batch_size = 256
        total = len(all_items)

        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            points = []

            for i in range(batch_start, batch_end):
                eid, _text, payload = all_items[i]
                points.append(PointStruct(
                    id=eid,
                    vector=embeddings[i],
                    payload=payload,
                ))

            await client.upsert(
                collection_name=self._collection_name,
                points=points,
            )

            if total > batch_size:
                logger.info(
                    "[LIGHTRAG] Upserted %d/%d points...",
                    min(batch_end, total), total,
                )

        stats = {
            "entity_count": len(entity_items),
            "relation_count": len(relation_items),
            "total_points": total,
        }
        logger.info(
            "[LIGHTRAG] Build complete: %d entities + %d relations = %d points",
            stats["entity_count"], stats["relation_count"], stats["total_points"],
        )
        return stats

    async def get_stats(self) -> dict[str, Any]:
        """Get current entity embedding collection stats."""
        try:
            client = await self._get_client()
            collections = await client.get_collections()
            names = [c.name for c in collections.collections]

            if self._collection_name not in names:
                return {"exists": False, "points": 0}

            info = await client.get_collection(self._collection_name)
            return {
                "exists": True,
                "points": info.points_count or 0,
                "collection_name": self._collection_name,
            }
        except Exception as e:
            return {"exists": False, "error": str(e)}

    async def search_entities(
        self,
        query_embedding: list[float],
        k: int = 10,
        type_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search entity/relation embeddings by vector similarity.

        Args:
            query_embedding: Query vector.
            k: Number of results.
            type_filter: "entity" or "relation" to filter by type.

        Returns:
            List of dicts with payload + score.
        """
        client = await self._get_client()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        search_filter = None
        if type_filter:
            search_filter = Filter(must=[
                FieldCondition(key="type", match=MatchValue(value=type_filter)),
            ])

        result = await client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            limit=k,
            query_filter=search_filter,
            with_payload=True,
        )

        return [
            {**point.payload, "score": point.score}
            for point in result.points
        ]
