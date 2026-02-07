"""Application configuration.

Loads settings from environment variables and .env file.
Supports multiple profiles via config/profiles/*.env.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent.parent


class EmbeddingSettings(BaseSettings):
    """Embedding provider configuration."""

    provider: Literal["openai", "voyage", "local"] = "local"
    model: str = "all-MiniLM-L6-v2"
    dimensions: int = 384
    batch_size: int = 64
    cache_enabled: bool = True
    cache_dir: Path = PROJECT_ROOT / "data" / "cache" / "embeddings"


class VectorStoreSettings(BaseSettings):
    """Vector store configuration."""

    provider: Literal["chroma", "qdrant", "faiss"] = "chroma"
    persist_dir: Path = PROJECT_ROOT / "data" / "vector_db"
    collection_name: str = "pdf_documents"
    distance_metric: Literal["cosine", "euclidean", "dot"] = "cosine"


class SearchSettings(BaseSettings):
    """Search configuration (Phase 1–3)."""

    # Hybrid search weights
    hybrid_vector_weight: float = 0.6
    hybrid_graph_weight: float = 0.4
    hybrid_rrf_k: int = 60

    # Dynamic weighting (future enhancement)
    dynamic_weighting_enabled: bool = False

    # Phase 2.1: MMR
    mmr_diversity_lambda: float = 0.5
    mmr_fetch_k: int = 20

    # Phase 2.3: Query Expansion
    query_expansion_enabled: bool = False
    query_expansion_method: Literal["llm", "synonyms", "hyde"] = "llm"

    # Phase 3.2: FlashRank
    flashrank_enabled: bool = False
    flashrank_token_budget: int = 4096


class ContextualRetrievalSettings(BaseSettings):
    """Phase 3.1: Contextual Retrieval configuration."""

    enabled: bool = False
    max_context_tokens: int = 128


class TwoStageSettings(BaseSettings):
    """Phase 3.3: Two-Stage Retrieval Pipeline configuration."""

    enabled: bool = False
    stage1_k: int = 50
    stage1_strategy: str = "hybrid"
    stage2_rerank_k: int = 20
    stage2_use_mmr: bool = True
    stage2_mmr_lambda: float = 0.5
    stage2_use_flashrank: bool = False


class SelfRAGSettings(BaseSettings):
    """Phase 5: Self-RAG & Corrective RAG configuration.

    Enables:
    - Document Grading: LLM-based relevance assessment
    - Query Rewriting: Automatic query reformulation
    - Hallucination Checking: Groundedness verification
    """

    enabled: bool = True

    # Fast LLM for all Self-RAG tasks (grading, rewriting, hallucination check)
    grading_model: str = "claude-haiku-4-5-20251001"

    # Document Grading (5.2)
    relevance_threshold: float = 0.5  # Minimum relevance ratio to proceed

    # Query Rewriting (5.3)
    max_retries: int = 2  # Maximum query rewrite attempts

    # Hallucination Checking (5.4)
    hallucination_check_enabled: bool = True
    max_generation_attempts: int = 2  # Max regenerations if hallucinated
    max_context_chars: int = 4000  # Truncate context for hallucination check

    # Strategy Escalation (5.3)
    strategy_escalation_enabled: bool = True  # vector → hybrid → two_stage


class GraphRAGSettings(BaseSettings):
    """Phase 6: GraphRAG configuration.

    Enables community detection, local/global search, and incremental updates.
    """

    # Community Detection (6.1)
    community_detection_enabled: bool = True
    leiden_resolution: float = 1.0  # Higher = more communities
    community_levels: int = 2  # Hierarchy levels for community detection

    # Community Summaries (6.2)
    summary_model: str = "claude-haiku-4-5-20251001"  # Fast model for summaries
    summary_cache_enabled: bool = True

    # Local Search (6.3)
    local_search_depth: int = 1  # Neighbor depth for graph context
    local_search_include_summary: bool = True  # Include community summary

    # Global Search (6.4)
    global_search_max_communities: int = 20  # Max communities to process
    global_search_rank_by_similarity: bool = True  # Rank communities by embedding
    global_search_map_model: str = "claude-haiku-4-5-20251001"
    global_search_reduce_model: str = "claude-sonnet-4-5-20250929"

    # Incremental Updates (6.5)
    incremental_updates_enabled: bool = True


class ParentChildSettings(BaseSettings):
    """Phase 7: Parent-Child Retrieval configuration.

    Enables two-level chunking: small children for search, large parents for context.
    """

    enabled: bool = False

    # Parent chunks (large, for context)
    parent_chunk_size: int = 2000
    parent_chunk_overlap: int = 200

    # Child chunks (small, for search)
    child_chunk_size: int = 400
    child_chunk_overlap: int = 50

    # Auto-merge settings
    merge_threshold: int = 3  # Min children from same parent to trigger merge
    fetch_multiplier: float = 3.0  # fetch_k = k * multiplier

    # Parent store location
    parent_store_path: Path = PROJECT_ROOT / "data" / "parent_store.db"


class AdaptiveRAGSettings(BaseSettings):
    """Phase 8: Adaptive RAG configuration.

    Enables automatic query classification and strategy routing for optimal retrieval.
    """

    # Query Classification (8.1)
    classifier_model: str = "claude-haiku-4-5-20251001"
    classifier_cache_enabled: bool = True

    # Strategy Routing (8.2)
    routing_enabled: bool = True

    # Sub-Question Decomposition (8.3)
    decomposition_enabled: bool = True
    max_sub_questions: int = 4

    # Route configurations (overrides)
    route_simple_strategy: str = "vector"
    route_moderate_strategy: str = "hybrid"
    route_complex_strategy: str = "two_stage"
    route_thematic_strategy: str = "graphrag_global"


class GraphStoreSettings(BaseSettings):
    """Graph store configuration."""

    provider: Literal["neo4j", "networkx"] = "networkx"
    persist_dir: Path = PROJECT_ROOT / "data" / "graph_db"
    # Neo4j settings (optional)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""


class PDFSettings(BaseSettings):
    """PDF processing configuration."""

    loader: Literal["pymupdf", "pdfplumber", "unstructured"] = "pymupdf"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    splitter: Literal["recursive", "semantic", "by_heading", "by_page", "parent_child"] = "recursive"
    extract_tables: bool = True
    extract_images: bool = False

    # Phase 2.2: Semantic chunking
    semantic_threshold: float = 0.75
    min_chunk_size: int = 200
    max_chunk_size: int = 1500


class AgentSettings(BaseSettings):
    """LangGraph agent configuration."""

    model: str = "claude-sonnet-4-5-20250929"
    temperature: float = 0.0
    max_tokens: int = 4096
    search_k: int = 5

    # Reranking configuration (Phase 1.1)
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_k: int = 20  # Retrieve more, then rerank to top_k

    checkpointer: Literal["memory", "postgres", "sqlite"] = "memory"

    # API endpoint configuration (for Z.AI or other proxies)
    base_url: str = ""  # Empty = use default Anthropic endpoint


class MCPServerSettings(BaseSettings):
    """MCP server configuration."""

    name: str = "pdf-vector-graph"
    version: str = "0.1.0"
    transport: Literal["stdio", "sse"] = "stdio"


class ConversationSettings(BaseSettings):
    """Phase 9: Conversational RAG configuration.

    Enables multi-turn dialog support with history management and streaming.
    """

    # Memory backend
    memory_backend: Literal["memory", "sqlite"] = "sqlite"

    # History window
    max_history: int = 10  # Maximum messages to retrieve per thread

    # Auto-cleanup
    auto_cleanup_days: int = 30  # Days before cleaning old threads (0 = disabled)

    # Database path
    db_path: Path = PROJECT_ROOT / "data" / "conversations.db"

    # Reformulation
    reformulation_enabled: bool = True  # History-aware query reformulation
    reformulation_model: str = "claude-haiku-4-5-20251001"  # Fast model for reformulation


class APISettings(BaseSettings):
    """REST API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]


class Settings(BaseSettings):
    """Root application settings."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Sub-settings
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    graph_store: GraphStoreSettings = Field(default_factory=GraphStoreSettings)
    pdf: PDFSettings = Field(default_factory=PDFSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    contextual_retrieval: ContextualRetrievalSettings = Field(default_factory=ContextualRetrievalSettings)
    two_stage: TwoStageSettings = Field(default_factory=TwoStageSettings)
    self_rag: SelfRAGSettings = Field(default_factory=SelfRAGSettings)  # Phase 5
    graph_rag: GraphRAGSettings = Field(default_factory=GraphRAGSettings)  # Phase 6
    parent_child: ParentChildSettings = Field(default_factory=ParentChildSettings)  # Phase 7
    adaptive: AdaptiveRAGSettings = Field(default_factory=AdaptiveRAGSettings)  # Phase 8
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)  # Phase 9
    mcp_server: MCPServerSettings = Field(default_factory=MCPServerSettings)
    api: APISettings = Field(default_factory=APISettings)

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    voyage_api_key: str = ""

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"
    temp_dir: Path = PROJECT_ROOT / "data" / "temp"


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
