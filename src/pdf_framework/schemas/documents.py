"""Document schemas for the PDF framework.

Defines Pydantic models for documents, chunks, and search results.
These models are used across all modules as the standard data contract.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata extracted from a PDF document."""

    source: str = ""
    title: str = ""
    author: str = ""
    creation_date: datetime | None = None
    page_count: int = 0
    file_size_bytes: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A chunk of text from a document with metadata."""

    id: str
    content: str
    document_id: str
    page_number: int | None = None
    section: str = ""
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessedDocument(BaseModel):
    """A fully processed PDF document."""

    id: str
    source_path: str
    metadata: DocumentMetadata
    chunks: list[DocumentChunk] = Field(default_factory=list)
    raw_text: str = ""
    processed_at: datetime = Field(default_factory=datetime.now)


class SearchResult(BaseModel):
    """A single search result."""

    chunk: DocumentChunk
    score: float
    source: str = ""  # "vector", "graph", "hybrid"
    highlights: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response from a search query."""

    query: str
    results: list[SearchResult]
    total_found: int = 0
    search_type: str = ""  # "vector", "graph", "hybrid"
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
