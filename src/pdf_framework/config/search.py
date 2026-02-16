"""Search configuration (Phase 1-3, 16)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class SearchSettings(BaseSettings):
    """Search configuration (Phase 1-3, 16)."""

    # Hybrid search weights
    hybrid_vector_weight: float = 0.5
    hybrid_graph_weight: float = 0.2
    hybrid_rrf_k: int = 60

    # Phase 16: BM25 Lexical Search
    bm25_enabled: bool = True
    bm25_weight: float = 0.3
    bm25_db_path: Path = _PROJECT_ROOT / "data" / "bm25_index.db"
    bm25_backend: Literal["qdrant", "fts5", "both"] = "qdrant"  # native sparse vs SQLite FTS5

    # Phase 27: BM25 multi-column FTS5
    bm25_two_pass: bool = False  # Two-pass title/body RRF merge

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
    """Phase 3.1 / Phase 50: Contextual Retrieval configuration.

    At index time, generates 1-2 sentence context prefix for each chunk via LLM.
    The contextual_content (context + original) is used for embedding and BM25,
    while original content is preserved for display.
    """

    enabled: bool = False
    max_context_tokens: int = 128
    model: str = "claude-haiku-4-5-20251001"  # Fast model for economy (~$0.01/page)
    batch_concurrency: int = 10  # Max parallel LLM calls
    min_chunk_tokens: int = 50  # Skip short chunks (< N words)
    cache_enabled: bool = True  # SQLite cache for generated contexts
    cache_db_path: Path = _PROJECT_ROOT / "data" / "context_cache.db"


class TwoStageSettings(BaseSettings):
    """Phase 3.3: Two-Stage Retrieval Pipeline configuration."""

    enabled: bool = False
    stage1_k: int = 50
    stage1_strategy: str = "hybrid"
    stage2_rerank_k: int = 20
    stage2_use_mmr: bool = True
    stage2_mmr_lambda: float = 0.5
    stage2_use_flashrank: bool = False
