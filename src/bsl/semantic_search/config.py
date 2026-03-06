"""
BSL Semantic Search Configuration

pydantic-settings конфигурация с env_prefix BSL_

Phase 45: Миграция из 1C-Enterprise_Framework
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BSLSearchSettings(BaseSettings):
    """
    Конфигурация BSL Semantic Search

    Все переменные окружения имеют префикс BSL_
    """

    model_config = SettingsConfigDict(
        env_prefix="BSL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Qdrant ===
    qdrant_host: str = Field(default="localhost", description="Qdrant server host")
    qdrant_port: int = Field(default=6333, description="Qdrant server port")
    qdrant_url: Optional[str] = Field(default=None, description="Full Qdrant URL (overrides host/port)")
    collection_name: str = Field(default="bsl_code_v2", description="Qdrant collection name")

    # === Embeddings ===
    embedding_model: str = Field(default="nomic-embed-text", description="Ollama embedding model")
    embedding_dim: int = Field(default=768, description="Embedding dimension (768 for nomic-embed-text)")
    ollama_host: str = Field(default="http://localhost:11434", description="Ollama server URL")

    # === Neo4j Graph ===
    neo4j_uri: str = Field(default="bolt://localhost:17687", description="Neo4j Bolt URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="1c_framework_2026", description="Neo4j password")

    # === LLM Service ===
    llm_reranking_model: str = Field(default="deepseek-coder:6.7b", description="LLM for reranking")
    llm_generation_model: str = Field(default="deepseek-coder:6.7b", description="LLM for generation")
    llm_timeout: int = Field(default=180, description="LLM request timeout (seconds)")

    # === Search Defaults ===
    default_limit: int = Field(default=10, description="Default search results limit")
    min_score: float = Field(default=0.0, description="Minimum relevance score")
    use_llm_reranking: bool = Field(default=True, description="Enable LLM reranking")

    # === TimescaleDB (optional) ===
    timescale_url: Optional[str] = Field(
        default=None,
        description="TimescaleDB URL for timeline features"
    )

    @property
    def qdrant_api_url(self) -> str:
        """Get full Qdrant URL"""
        if self.qdrant_url:
            return self.qdrant_url
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


# Global settings instance
_settings: Optional[BSLSearchSettings] = None


def get_bsl_settings() -> BSLSearchSettings:
    """Get singleton BSL settings instance"""
    global _settings
    if _settings is None:
        _settings = BSLSearchSettings()
    return _settings
