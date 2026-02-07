"""FastAPI dependency injection for framework components."""

from functools import lru_cache

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.embeddings import get_embedding_engine
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.graph_store import get_graph_store
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.loaders import get_loader
from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.processing.pipeline import ProcessingPipeline
from src.pdf_framework.search.manager import SearchManager
from src.pdf_framework.search.strategies.graph_search import GraphSearchStrategy
from src.pdf_framework.search.strategies.hybrid_search import HybridSearchStrategy
from src.pdf_framework.search.pipelines.two_stage import TwoStagePipeline
from src.pdf_framework.search.reranking.cross_encoder import CrossEncoderReranker
from src.pdf_framework.search.reranking.flashrank import FlashRankReranker
from src.pdf_framework.agents.memory.conversation import ConversationMemory
from src.pdf_framework.search.strategies.adaptive import AdaptiveSearchStrategy
from src.pdf_framework.search.strategies.auto_merge import AutoMergeStrategy
from src.pdf_framework.search.strategies.graphrag_global import GraphRAGGlobalStrategy
from src.pdf_framework.search.strategies.graphrag_local import GraphRAGLocalStrategy
from src.pdf_framework.search.strategies.mmr_search import MMRSearchStrategy
from src.pdf_framework.search.strategies.raptor_search import RAPTORSearchStrategy
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy
from src.pdf_framework.vector_store import get_vector_store
from src.pdf_framework.vector_store.base import BaseVectorStore
from src.pdf_framework.vector_store.indexing.indexer import DocumentIndexer
from src.pdf_framework.vector_store.parent_store import ParentDocumentStore


class Components:
    """Holds all initialized framework components."""

    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.loader: BaseLoader = get_loader(self.settings.pdf)
        self.pipeline: ProcessingPipeline = ProcessingPipeline(self.settings.pdf)
        self.embedding_engine: BaseEmbeddingEngine = get_embedding_engine(self.settings.embedding)
        self.vector_store: BaseVectorStore = get_vector_store(self.settings.vector_store)
        self.graph_store: BaseGraphStore = get_graph_store(self.settings.graph_store)
        self.indexer: DocumentIndexer = DocumentIndexer(self.embedding_engine, self.vector_store)

        # Phase 1 + 2: SearchManager with reranking and query expansion support
        self.search_manager: SearchManager = SearchManager(
            agent_settings=self.settings.agent,
            search_settings=self.settings.search,
        )

        # Register search strategies
        vector_strategy = VectorSearchStrategy(self.embedding_engine, self.vector_store)
        graph_strategy = GraphSearchStrategy(self.graph_store, self.vector_store)

        # Phase 1.2: Hybrid strategy with configurable weights
        hybrid_strategy = HybridSearchStrategy(
            vector_strategy,
            graph_strategy,
            search_settings=self.settings.search,
        )

        # Phase 2.1: MMR strategy with configurable diversity
        mmr_strategy = MMRSearchStrategy(
            self.embedding_engine,
            self.vector_store,
            search_settings=self.settings.search,
        )

        self.search_manager.register_strategy("vector", vector_strategy)
        self.search_manager.register_strategy("graph", graph_strategy)
        self.search_manager.register_strategy("hybrid", hybrid_strategy)
        self.search_manager.register_strategy("mmr", mmr_strategy)

        # Phase 6: GraphRAG strategies
        graphrag_local = GraphRAGLocalStrategy(
            embedding_engine=self.embedding_engine,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            neighbor_depth=self.settings.graph_rag.local_search_depth,
            include_community_summary=self.settings.graph_rag.local_search_include_summary,
        )
        graphrag_global = GraphRAGGlobalStrategy(
            embedding_engine=self.embedding_engine,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            settings=self.settings.graph_rag,
        )
        self.search_manager.register_strategy("graphrag_local", graphrag_local)
        self.search_manager.register_strategy("graphrag_global", graphrag_global)

        # Phase 7: Parent-Child Auto-Merge strategy
        if self.settings.parent_child.enabled:
            self.parent_store: ParentDocumentStore = ParentDocumentStore(
                db_path=self.settings.parent_child.parent_store_path,
            )
            auto_merge = AutoMergeStrategy(
                embedding_engine=self.embedding_engine,
                vector_store=self.vector_store,
                parent_store=self.parent_store,
                merge_threshold=self.settings.parent_child.merge_threshold,
                fetch_multiplier=self.settings.parent_child.fetch_multiplier,
            )
            self.search_manager.register_strategy("auto_merge", auto_merge)
        else:
            self.parent_store = None  # type: ignore[assignment]

        # Phase 8: Adaptive RAG strategy
        if self.settings.adaptive.routing_enabled:
            adaptive_strategy = AdaptiveSearchStrategy(
                search_manager=self.search_manager,
                settings=self.settings.adaptive,
            )
            self.search_manager.register_strategy("adaptive", adaptive_strategy)

        # Phase 9: Conversation Memory
        self.conversation_memory: ConversationMemory = ConversationMemory(
            backend=self.settings.conversation.memory_backend,
            db_path=str(self.settings.conversation.db_path),
            max_history=self.settings.conversation.max_history,
            auto_cleanup_days=self.settings.conversation.auto_cleanup_days,
        )

        # Phase 3.3: Two-stage pipeline
        if self.settings.two_stage.enabled:
            reranker = self.search_manager._reranker or CrossEncoderReranker(
                model_name=self.settings.agent.reranker_model,
            )
            flashrank = None
            if self.settings.search.flashrank_enabled:
                flashrank = FlashRankReranker(
                    token_budget=self.settings.search.flashrank_token_budget,
                )
            two_stage = TwoStagePipeline(
                stage1_strategy=hybrid_strategy,
                reranker=reranker,
                flashrank=flashrank,
                settings=self.settings.two_stage,
            )
            self.search_manager.register_strategy("two_stage", two_stage)

        # Phase 13.2: RAPTOR Search Strategy
        if self.settings.raptor.enabled:
            from src.pdf_framework.search.strategies.raptor_search import (
                RAPTORSearchConfig,
            )

            raptor_config = RAPTORSearchConfig(
                search_mode=self.settings.raptor.search_mode,
                top_k_per_level=5,
                max_depth=self.settings.raptor.max_levels,
                include_leaves=True,
                include_summaries=True,
            )
            raptor_strategy = RAPTORSearchStrategy(
                vector_store=self.vector_store,
                config=raptor_config,
            )
            self.search_manager.register_strategy("raptor", raptor_strategy)

    async def initialize(self) -> None:
        """Initialize async components (stores)."""
        await self.vector_store.initialize()
        await self.graph_store.initialize()
        if self.parent_store is not None:
            await self.parent_store.initialize()


_components: Components | None = None


async def get_components() -> Components:
    """Get or create the singleton components instance."""
    global _components
    if _components is None:
        _components = Components()
        await _components.initialize()
    return _components
