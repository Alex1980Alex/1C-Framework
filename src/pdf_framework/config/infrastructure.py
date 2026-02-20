"""Infrastructure configuration: graph store, MCP, API, auth, UI."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class GraphStoreSettings(BaseSettings):
    """Graph store configuration."""

    provider: Literal["neo4j", "networkx"] = "networkx"
    persist_dir: Path = _PROJECT_ROOT / "data" / "graph_db"
    # Neo4j settings (optional)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""


class MCPServerSettings(BaseSettings):
    """MCP server configuration."""

    name: str = "pdf-vector-graph"
    version: str = "0.1.0"
    transport: Literal["stdio", "sse"] = "stdio"


class APISettings(BaseSettings):
    """REST API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]


class AuthSettings(BaseSettings):
    """Phase 12: Authentication and authorization configuration."""

    enabled: bool = False  # Disabled by default for dev
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    token_expire_hours: int = 24
    default_tenant: str = "default"


class UISettings(BaseSettings):
    """Phase 14.1: Gradio Web UI configuration."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 7860
    share: bool = False
    theme: str = "default"
    api_backend_url: str = "http://localhost:8000"


class OpenAICompatSettings(BaseSettings):
    """Phase 14.3: OpenAI-Compatible API configuration."""

    enabled: bool = True
    model_name: str = "pdf-rag"
    model_description: str = "PDF RAG Framework with Vector and Graph Search"


class QueueSettings(BaseSettings):
    """Phase 59: Async Processing Queue (ARQ) configuration."""

    enabled: bool = False  # Disabled by default for dev
    redis_url: str = "redis://localhost:6379/0"
    max_jobs: int = 100
    job_timeout: int = 3600  # 1 hour
    retry_attempts: int = 3
    retry_delay_seconds: int = 60
    # Queue settings
    queue_name: str = "arq:queue"
    # Health check
    health_check_interval: int = 30
