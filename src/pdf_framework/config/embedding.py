"""Embedding provider configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class EmbeddingSettings(BaseSettings):
    """Embedding provider configuration.

    Production default Phase 8 (2026-04-30): TEI Docker + Qwen3-Embedding-8B 4096d.
    Override via EMBEDDING__PROVIDER / EMBEDDING__MODEL / EMBEDDING__DIMENSIONS env vars.
    """

    provider: Literal["openai", "voyage", "local", "giga", "jina", "tei", "bgem3"] = "tei"
    model: str = "Qwen/Qwen3-Embedding-8B"
    dimensions: int = 4096
    batch_size: int = 64

    # Phase 8.12.6: TEI HTTP backend
    tei_base_url: str = "http://localhost:8080"
    tei_client_batch: int = 32  # MAX_CLIENT_BATCH_SIZE cap on TEI server
    cache_enabled: bool = True
    cache_dir: Path = _PROJECT_ROOT / "data" / "cache" / "embeddings"
    device: str = "auto"  # "auto" | "cpu" | "cuda" | "mps"

    # Phase 43: ONNX/OpenVINO acceleration (7x speedup on CPU)
    backend: Literal["torch", "onnx", "openvino"] = "torch"

    # Phase 47: Jina Embeddings v3
    jina_api_key: str = ""  # Jina AI API key (or set EMBEDDING__JINA_API_KEY)
    jina_task: str = "retrieval.passage"  # Task type for Jina v3
    jina_truncate_dim: int | None = None  # Matryoshka dimension truncation (1024→512/256)

    # Phase 48: Late Chunking (Jina v3)
    late_chunking: bool = False  # Enable late chunking (preserves cross-chunk context)
    late_chunking_max_tokens: int = 7000  # Max tokens per late chunking window (~8192 limit)
