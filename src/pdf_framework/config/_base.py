"""Root application settings and singleton accessor."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


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
    layout: LayoutSettings = Field(default_factory=LayoutSettings)  # Phase 10
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)  # Phase 11
    docling: DoclingSettings = Field(default_factory=DoclingSettings)  # Phase 15.1
    smart_router: SmartRouterSettings = Field(default_factory=SmartRouterSettings)  # Phase 15.1
    cache: CacheSettings = Field(default_factory=CacheSettings)  # Phase 11
    auth: AuthSettings = Field(default_factory=AuthSettings)  # Phase 12
    raptor: RAPTORSettings = Field(default_factory=RAPTORSettings)  # Phase 13
    summary_index: SummaryIndexSettings = Field(default_factory=SummaryIndexSettings)  # Phase 13
    mcp_server: MCPServerSettings = Field(default_factory=MCPServerSettings)
    api: APISettings = Field(default_factory=APISettings)
    ui: UISettings = Field(default_factory=UISettings)  # Phase 14
    openai_compat: OpenAICompatSettings = Field(default_factory=OpenAICompatSettings)  # Phase 14
    suggestions: SuggestionSettings = Field(default_factory=SuggestionSettings)  # Phase 14
    deep_research: DeepResearchSettings = Field(default_factory=DeepResearchSettings)  # Phase 19
    autorag: AutoRAGSettings = Field(default_factory=AutoRAGSettings)  # Phase 20
    ragas_eval: RAGASSettings = Field(default_factory=RAGASSettings)  # Phase 21
    feedback: FeedbackSettings = Field(default_factory=FeedbackSettings)  # Phase 22
    hybrid_loader: HybridLoaderSettings = Field(default_factory=HybridLoaderSettings)  # Phase 28
    hierarchical: HierarchicalSearchSettings = Field(default_factory=HierarchicalSearchSettings)  # Phase 30
    light_rag: LightRAGSettings = Field(default_factory=LightRAGSettings)  # Phase 38
    optimization: OptimizationSettings = Field(default_factory=OptimizationSettings)  # Phase 34
    external: ExternalSourcesSettings = Field(default_factory=ExternalSourcesSettings)  # Phase 37

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


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Get application settings singleton (cached)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
