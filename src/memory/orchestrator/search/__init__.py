"""Search subsystem for memory orchestrator.

Provides BM25 sparse search, BSL-aware scoring, and hybrid RRF fusion.
No external dependencies -- pure Python.
"""

from .bsl_scorer import BSLAnalysisResult, BSLObjectType, BSLScorer, BSLScoreResult
from .config import (
    DEFAULT_SEARCH_CONFIG,
    BSLScorerConfig,
    FusionMethod,
    HybridSearchConfig,
    SearchConfig,
    SparseConfig,
    VectorType,
)
from .hybrid_search import BM25Index, HybridSearchResult, HybridSearchService, SearchResult

__all__ = [
    # Config
    "BSLScorerConfig",
    "DEFAULT_SEARCH_CONFIG",
    "FusionMethod",
    "HybridSearchConfig",
    "SearchConfig",
    "SparseConfig",
    "VectorType",
    # Hybrid search
    "BM25Index",
    "HybridSearchResult",
    "HybridSearchService",
    "SearchResult",
    # BSL scorer
    "BSLScorer",
    "BSLScoreResult",
    "BSLAnalysisResult",
    "BSLObjectType",
]
