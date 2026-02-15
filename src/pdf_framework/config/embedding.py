"""Embedding provider configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class EmbeddingSettings(BaseSettings):
    """Embedding provider configuration."""

    provider: Literal["openai", "voyage", "local", "giga"] = "local"
    model: str = "intfloat/multilingual-e5-large"
    dimensions: int = 1024
    batch_size: int = 64
    cache_enabled: bool = True
    cache_dir: Path = _PROJECT_ROOT / "data" / "cache" / "embeddings"
    device: str = "auto"  # "auto" | "cpu" | "cuda" | "mps"

    # Phase 43: ONNX/OpenVINO acceleration (7x speedup on CPU)
    backend: Literal["torch", "onnx", "openvino"] = "torch"
