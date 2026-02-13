"""Response models for indexing and pipeline operations."""

from pydantic import BaseModel, Field


class IndexResult(BaseModel):
    """Result of indexing a single document."""

    document_id: str
    source_path: str
    chunks_stored: int = 0
    embeddings_computed: int = 0
    success: bool = True
    error: str = ""


class PipelineResult(BaseModel):
    """Result of a complete pipeline run."""

    documents_processed: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    results: list[IndexResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
