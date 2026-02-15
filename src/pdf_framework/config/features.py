"""Feature-specific configuration: Parent-Child, Adaptive RAG, Conversation, etc."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


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
    parent_store_path: Path = _PROJECT_ROOT / "data" / "parent_store.db"


class AdaptiveRAGSettings(BaseSettings):
    """Phase 8: Adaptive RAG configuration.

    Enables automatic query classification and strategy routing for optimal retrieval.
    """

    # Query Classification (8.1)
    classifier_model: str = "claude-sonnet-4-5-20250929"
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

    # Phase 26: Turbo Pipeline
    fast_classify_enabled: bool = True
    bm25_early_termination: bool = True
    bm25_early_threshold: float = 0.7
    parallel_decomposition: bool = True
    parallel_expansion: bool = True


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
    db_path: Path = _PROJECT_ROOT / "data" / "conversations.db"

    # Reformulation
    reformulation_enabled: bool = True  # History-aware query reformulation
    reformulation_model: str = "claude-sonnet-4-5-20250929"  # Fast model for reformulation


class LayoutSettings(BaseSettings):
    """Phase 10: Layout-Aware PDF Parsing configuration.

    Enables structure-aware PDF parsing with table extraction,
    image understanding, and template-based processing.
    """

    # Layout detection
    layout_detection_enabled: bool = False
    layout_provider: Literal["unstructured", "surya", "docling", "none"] = "unstructured"
    layout_strategy: Literal["hi_res", "fast"] = "hi_res"
    infer_table_structure: bool = True

    # Table extraction
    extract_tables: bool = True
    min_table_rows: int = 2
    min_table_cols: int = 2

    # Image understanding
    extract_images: bool = True
    image_description_model: str = "claude-sonnet-4-5-20250929"
    min_image_size: int = 50  # pixels

    # Template-based parsing
    parse_template: Literal["auto", "generic", "research_paper", "user_manual"] = "auto"

    # Structure-aware chunking
    structure_aware_chunk_size: int = 1000
    structure_aware_overlap: int = 200


class RAPTORSettings(BaseSettings):
    """Phase 13.1: RAPTOR Tree Builder configuration."""

    enabled: bool = False
    max_levels: int = 4
    search_mode: str = "collapsed"  # collapsed or tree_traversal
    cluster_method: str = "kmeans"  # kmeans, umap_gmm
    summarization_model: str = "claude-sonnet-4-5-20250929"


class SummaryIndexSettings(BaseSettings):
    """Phase 13.4: Document Summary Index configuration."""

    enabled: bool = False
    collection_name: str = "document_summaries"
    summarization_model: str = "claude-sonnet-4-5-20250929"
    min_chunks_for_summary: int = 10  # Only summarize docs with enough chunks


class SuggestionSettings(BaseSettings):
    """Phase 14.5: Query Suggestions configuration."""

    enabled: bool = False
    method: Literal["entity", "frequency", "llm", "related"] = "entity"
    cache_ttl: int = 3600  # seconds
    max_suggestions: int = 5
    llm_model: str = "claude-sonnet-4-5-20250929"


class HierarchicalSearchSettings(BaseSettings):
    """Phase 30: Hierarchical RAG configuration.

    Section-first search, section summaries, breadcrumb context.
    """

    model_config = SettingsConfigDict(env_prefix="HIERARCHICAL__")

    section_first_enabled: bool = True
    summary_enabled: bool = True
    summary_model: str = "claude-sonnet-4-5-20250929"
    summary_db_path: Path = _PROJECT_ROOT / "data" / "section_summaries.db"
    context_breadcrumb: bool = True
