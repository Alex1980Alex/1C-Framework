"""External sources and optimization configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExternalSourcesSettings(BaseSettings):
    """External sources / web search settings (Phase 37)."""

    model_config = SettingsConfigDict(env_prefix="EXTERNAL__")
    web_search_enabled: bool = False
    tavily_api_key: str = ""
    serpapi_key: str = ""
    confidence_threshold: float = 0.5  # below this, fall back to web
    web_trust_score: float = 0.3  # web results scored lower than docs


class OptimizationSettings(BaseSettings):
    """DSPy prompt optimization settings (Phase 34)."""

    model_config = SettingsConfigDict(env_prefix="OPTIMIZATION__")
    enabled: bool = False
    dataset_path: str = "data/dspy_evaluation_dataset.json"
    optimized_dir: str = "data/dspy_optimized"
    model: str = "claude-sonnet-4-5-20250929"
    max_trials: int = 50
