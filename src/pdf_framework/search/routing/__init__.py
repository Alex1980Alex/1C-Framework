"""Query routing components for Adaptive RAG (Phase 8).

Provides:
- QueryClassifier: Complexity-based query classification
- StrategyRouter: Automatic strategy selection based on classification
- SubQuestionDecomposer: Complex query decomposition for multi-search
"""

from src.pdf_framework.search.routing.classifier import QueryClassifier, QueryClassification
from src.pdf_framework.search.routing.decomposer import SubQuestionDecomposer
from src.pdf_framework.search.routing.router import RoutingDecision, RouteConfig, StrategyRouter

__all__ = [
    # Core components
    "QueryClassifier",
    "QueryClassification",
    "StrategyRouter",
    "RoutingDecision",
    "RouteConfig",
    "SubQuestionDecomposer",
]
