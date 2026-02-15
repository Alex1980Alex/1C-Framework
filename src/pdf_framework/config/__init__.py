"""Application configuration package.

Re-exports all settings classes for backward compatibility.
``from src.pdf_framework.config import Settings, get_settings`` continues to work.
"""

from ._base import PROJECT_ROOT, Settings, get_settings
from .agent import AgentSettings, DeepResearchSettings, SelfRAGSettings
from .embedding import EmbeddingSettings
from .external import ExternalSourcesSettings, OptimizationSettings
from .features import (
    AdaptiveRAGSettings,
    ConversationSettings,
    HierarchicalSearchSettings,
    LayoutSettings,
    ParentChildSettings,
    RAPTORSettings,
    SuggestionSettings,
    SummaryIndexSettings,
)
from .graphrag import GraphRAGSettings, LightRAGSettings
from .infrastructure import (
    APISettings,
    AuthSettings,
    GraphStoreSettings,
    MCPServerSettings,
    OpenAICompatSettings,
    UISettings,
)
from .observability import (
    AutoRAGSettings,
    CacheSettings,
    FeedbackSettings,
    ObservabilitySettings,
    RAGASSettings,
)
from .pdf import DoclingSettings, HybridLoaderSettings, PDFSettings, SmartRouterSettings
from .search import ContextualRetrievalSettings, SearchSettings, TwoStageSettings
from .vector_store import VectorStoreSettings

__all__ = [
    # Root
    "PROJECT_ROOT",
    "Settings",
    "get_settings",
    # Embedding
    "EmbeddingSettings",
    # Vector Store
    "VectorStoreSettings",
    # Search
    "SearchSettings",
    "ContextualRetrievalSettings",
    "TwoStageSettings",
    # Agent
    "AgentSettings",
    "SelfRAGSettings",
    "DeepResearchSettings",
    # PDF
    "PDFSettings",
    "DoclingSettings",
    "SmartRouterSettings",
    "HybridLoaderSettings",
    # GraphRAG
    "GraphRAGSettings",
    "LightRAGSettings",
    # Infrastructure
    "GraphStoreSettings",
    "MCPServerSettings",
    "APISettings",
    "AuthSettings",
    "UISettings",
    "OpenAICompatSettings",
    # Features
    "ParentChildSettings",
    "AdaptiveRAGSettings",
    "ConversationSettings",
    "LayoutSettings",
    "RAPTORSettings",
    "SummaryIndexSettings",
    "SuggestionSettings",
    "HierarchicalSearchSettings",
    # Observability
    "ObservabilitySettings",
    "CacheSettings",
    "FeedbackSettings",
    "RAGASSettings",
    "AutoRAGSettings",
    # External
    "ExternalSourcesSettings",
    "OptimizationSettings",
]
