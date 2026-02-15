"""Observability, caching, feedback, and evaluation configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class ObservabilitySettings(BaseSettings):
    """Phase 11: Observability configuration.

    Configures tracing backends and trace storage.
    """

    tracer: Literal["jsonfile", "langsmith", "none"] = "jsonfile"
    trace_dir: Path = _PROJECT_ROOT / "data" / "traces"
    langsmith_enabled: bool = False


class CacheSettings(BaseSettings):
    """Phase 11: Caching configuration.

    Configures embedding, LLM, and document caching.
    """

    embedding_enabled: bool = True
    embedding_ttl_days: int = 30
    embedding_db_path: Path = _PROJECT_ROOT / "data" / "cache" / "embeddings.db"

    llm_enabled: bool = True
    llm_ttl_seconds: int = 3600
    llm_db_path: Path = _PROJECT_ROOT / "data" / "cache" / "llm_responses.db"

    document_enabled: bool = True
    document_cache_dir: Path = _PROJECT_ROOT / "data" / "cache" / "documents"

    prompt_caching_enabled: bool = True

    # Phase 17: Semantic Search Cache
    semantic_enabled: bool = True
    semantic_threshold: float = 0.95
    semantic_ttl_seconds: int = 3600
    semantic_max_entries: int = 5000
    semantic_db_path: Path = _PROJECT_ROOT / "data" / "cache" / "semantic_cache.db"


class FeedbackSettings(BaseSettings):
    """Phase 22: Self-Learning Feedback configuration."""

    enabled: bool = True
    db_path: Path = _PROJECT_ROOT / "data" / "feedback.db"
    async_db_path: Path = _PROJECT_ROOT / "data" / "feedback_v2.db"
    few_shot_max_examples: int = 3
    few_shot_similarity_threshold: float = 0.7
    boost_max: float = 1.3
    boost_min_count: int = 3


class RAGASSettings(BaseSettings):
    """Phase 21: RAGAS Evaluation configuration."""

    enabled: bool = False
    eval_history_db_path: Path = _PROJECT_ROOT / "data" / "eval_history.db"
    regression_threshold: float = 0.05
    baseline_path: Path = _PROJECT_ROOT / "data" / "baseline.json"


class AutoRAGSettings(BaseSettings):
    """Phase 20: AutoRAG Optimization configuration."""

    enabled: bool = False
    max_experiments: int = 50
    output_dir: Path = _PROJECT_ROOT / "data" / "autorag_results"
