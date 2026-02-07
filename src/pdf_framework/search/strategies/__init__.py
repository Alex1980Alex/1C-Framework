"""Search strategies for PDF framework.

Phase 6 (v0.7.0) - GraphRAG:
- Local Search: vector + graph context enrichment
- Global Search: map-reduce over community summaries

Phase 7 (v0.8.0) - Parent-Child Retrieval:
- Auto-Merge: child search with parent merging

Phase 8 (v0.9.0) - Adaptive RAG:
- Adaptive Search: automatic query classification and strategy routing
"""

from src.pdf_framework.search.strategies.adaptive import AdaptiveSearchStrategy
from src.pdf_framework.search.strategies.auto_merge import AutoMergeStrategy
from src.pdf_framework.search.strategies.graph_search import GraphSearchStrategy
from src.pdf_framework.search.strategies.graphrag_global import GraphRAGGlobalStrategy
from src.pdf_framework.search.strategies.graphrag_local import GraphRAGLocalStrategy
from src.pdf_framework.search.strategies.hybrid_search import HybridSearchStrategy
from src.pdf_framework.search.strategies.mmr_search import MMRSearchStrategy
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy

__all__ = [
    "VectorSearchStrategy",
    "GraphSearchStrategy",
    "HybridSearchStrategy",
    "MMRSearchStrategy",
    "GraphRAGLocalStrategy",  # Phase 6.3
    "GraphRAGGlobalStrategy",  # Phase 6.4
    "AutoMergeStrategy",  # Phase 7.3
    "AdaptiveSearchStrategy",  # Phase 8.4
]
