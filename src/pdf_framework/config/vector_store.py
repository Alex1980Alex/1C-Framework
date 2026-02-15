"""Vector store configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class VectorStoreSettings(BaseSettings):
    """Vector store configuration."""

    provider: Literal["chroma", "qdrant", "faiss", "pgvector"] = "chroma"
    dimensions: int = 1024  # Must match embedding model dimensions

    # Phase 23: Qdrant settings
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Phase 23: PgVector settings
    pgvector_dsn: str = ""
    pgvector_table_name: str = "embeddings"
    persist_dir: Path = _PROJECT_ROOT / "data" / "vector_db"
    collection_name: str = "pdf_documents"
    distance_metric: Literal["cosine", "euclidean", "dot"] = "cosine"

    # Qdrant native BM25 (sparse vectors)
    qdrant_bm25_enabled: bool = True
    qdrant_bm25_language: str = "russian"
    qdrant_bm25_k: float = 1.2
    qdrant_bm25_b: float = 0.75
