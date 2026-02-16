"""Embedding provider configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class EmbeddingSettings(BaseSettings):
    """Embedding provider configuration."""

    provider: Literal["openai", "voyage", "local", "giga", "jina"] = "local"
    model: str = "intfloat/multilingual-e5-large"
    dimensions: int = 1024
    batch_size: int = 64
    cache_enabled: bool = True
    cache_dir: Path = _PROJECT_ROOT / "data" / "cache" / "embeddings"
    device: str = "auto"  # "auto" | "cpu" | "cuda" | "mps"

    # Phase 43: ONNX/OpenVINO acceleration (7x speedup on CPU)
    backend: Literal["torch", "onnx", "openvino"] = "torch"

    # Phase 47: Jina Embeddings v3
    jina_api_key: str = ""  # Jina AI API key (or set EMBEDDING__JINA_API_KEY)
    jina_task: str = "retrieval.passage"  # Task type for Jina v3
    jina_truncate_dim: int | None = None  # Matryoshka dimension truncation (1024→512/256)
