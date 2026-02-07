"""Graph builder: orchestrates entity extraction → deduplication → storage."""

from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.schemas.entities import ExtractionResult, Relation


class GraphBuilder:
    """Orchestrate: extract entities → deduplicate → store in graph."""

    def __init__(
        self,
        extractor: LLMEntityExtractor,
        graph_store: BaseGraphStore,
    ):
        self._extractor = extractor
        self._graph_store = graph_store
        # Track known entities for deduplication: (name_lower, entity_type) -> entity_id
        self._entity_index: dict[tuple[str, str], str] = {}

    async def build_from_chunks(self, chunks: list[DocumentChunk]) -> dict:
        """Extract entities from chunks and build the knowledge graph.

        Returns summary statistics.
        """
        total_entities = 0
        total_relations = 0

        for chunk in chunks:
            result = await self._extractor.extract(chunk)
            entities_added, relations_added = await self._store_extraction(result)
            total_entities += entities_added
            total_relations += relations_added

        return {
            "entities_added": total_entities,
            "relations_added": total_relations,
            "chunks_processed": len(chunks),
        }

    async def _store_extraction(self, result: ExtractionResult) -> tuple[int, int]:
        """Deduplicate and store entities and relations."""
        # Map original entity IDs to potentially deduplicated IDs
        id_remap: dict[str, str] = {}
        entities_added = 0

        for entity in result.entities:
            key = (entity.name.lower().strip(), entity.entity_type)
            existing_id = self._entity_index.get(key)

            if existing_id:
                # Entity already exists — merge source chunk IDs
                id_remap[entity.id] = existing_id
                existing = await self._graph_store.get_entity(existing_id)
                if existing and result.chunk_id not in existing.source_chunk_ids:
                    existing.source_chunk_ids.append(result.chunk_id)
                    await self._graph_store.add_entity(existing)
            else:
                await self._graph_store.add_entity(entity)
                self._entity_index[key] = entity.id
                id_remap[entity.id] = entity.id
                entities_added += 1

        relations_added = 0
        for relation in result.relations:
            remapped = Relation(
                id=relation.id,
                source_entity_id=id_remap.get(relation.source_entity_id, relation.source_entity_id),
                target_entity_id=id_remap.get(relation.target_entity_id, relation.target_entity_id),
                relation_type=relation.relation_type,
                properties=relation.properties,
                confidence=relation.confidence,
                source_chunk_id=relation.source_chunk_id,
            )
            await self._graph_store.add_relation(remapped)
            relations_added += 1

        return entities_added, relations_added
