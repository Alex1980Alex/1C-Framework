"""Entity and graph schemas.

Pydantic models for knowledge graph entities, relations, and subgraphs.
"""

from typing import Any

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """A named entity extracted from a document."""

    id: str
    name: str
    entity_type: str  # PERSON, ORG, LOCATION, DATE, CONCEPT, DOCUMENT
    properties: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class Relation(BaseModel):
    """A relation between two entities."""

    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str  # WORKS_AT, LOCATED_IN, MENTIONS, RELATED_TO, etc.
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    source_chunk_id: str = ""


class SubGraph(BaseModel):
    """A subgraph of entities and relations (query result)."""

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    center_entity: Entity | None = None
    depth: int = 1


class ExtractionResult(BaseModel):
    """Result of entity/relation extraction from a chunk."""

    chunk_id: str
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
