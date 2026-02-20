"""GraphRAG and LightRAG configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphRAGSettings(BaseSettings):
    """Phase 6: GraphRAG configuration.

    Enables community detection, local/global search, and incremental updates.
    """

    # Community Detection (6.1)
    community_detection_enabled: bool = True
    leiden_resolution: float = 1.0  # Higher = more communities
    community_levels: int = 2  # Hierarchy levels for community detection

    # Community Summaries (6.2)
    summary_model: str = "claude-sonnet-4-5-20250929"  # Fast model for summaries
    summary_cache_enabled: bool = True

    # Local Search (6.3)
    local_search_depth: int = 1  # Neighbor depth for graph context
    local_search_include_summary: bool = True  # Include community summary

    # Global Search (6.4)
    global_search_max_communities: int = 20  # Max communities to process
    global_search_rank_by_similarity: bool = True  # Rank communities by embedding
    global_search_map_model: str = "claude-sonnet-4-5-20250929"
    global_search_reduce_model: str = "claude-sonnet-4-5-20250929"

    # Incremental Updates (6.5)
    incremental_updates_enabled: bool = True
    auto_update_enabled: bool = True  # Phase 61: Auto-trigger after document re-index
    auto_update_on_reindex: bool = True  # Auto-update when document is re-indexed


class LightRAGSettings(BaseSettings):
    """Phase 38: LightRAG Mode -- Economical GraphRAG.

    Vector search over entity/relation embeddings instead of LLM map-reduce.
    ~100 tokens/query vs ~5000 for full GraphRAG Global (50x cheaper).

    Auto-selection: classifier routes simple->LightRAG, thematic->Full GraphRAG.
    """

    model_config = SettingsConfigDict(env_prefix="LIGHTRAG__")

    enabled: bool = True
    collection_name: str = "graph_embeddings"  # Qdrant collection for entity/relation vectors

    # Search parameters
    entity_top_k: int = 10  # Top entities to retrieve per query
    relation_top_k: int = 10  # Top relations to retrieve per query
    neighbor_depth: int = 1  # Depth for neighbor expansion from found entities
    max_chunks: int = 10  # Max source chunks to return

    # Auto-selection: when to use LightRAG vs Full GraphRAG
    auto_select_enabled: bool = True
    # Complexity thresholds: simple/moderate -> light, complex/thematic -> full
    light_complexities: list[str] = ["simple", "moderate"]
    full_complexities: list[str] = ["complex", "thematic"]
