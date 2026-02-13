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
from src.pdf_framework.processing.image_extractor import ImageExtractor
from src.pdf_framework.vector_store import get_vector_store
from src.pdf_framework.vector_store.base import BaseVectorStore
from src.pdf_framework.vector_store.indexing.indexer import DocumentIndexer
from src.pdf_framework.vector_store.parent_store import ParentDocumentStore
from src.pdf_framework.search.bm25_store import BM25Store
from src.pdf_framework.search.strategies.bm25_search import BM25SearchStrategy
from src.pdf_framework.search.semantic_cache import SemanticSearchCache


class Components:
    """Holds all initialized framework components."""

    def __init__(self) -> None:
        self.settings: Settings = get_settings()
        self.loader: BaseLoader = get_loader(self.settings.pdf)
        self.pipeline: ProcessingPipeline = ProcessingPipeline(self.settings.pdf)
        self.embedding_engine: BaseEmbeddingEngine = get_embedding_engine(self.settings.embedding)
        self.vector_store: BaseVectorStore = get_vector_store(self.settings.vector_store)
        self.graph_store: BaseGraphStore = get_graph_store(self.settings.graph_store)

        # Phase 16: BM25 Store (SQLite FTS5)
        self.bm25_store: BM25Store | None = None
        if self.settings.search.bm25_enabled:
            self.bm25_store = BM25Store(db_path=self.settings.search.bm25_db_path)

        self.indexer: DocumentIndexer = DocumentIndexer(
            self.embedding_engine, self.vector_store, bm25_store=self.bm25_store
        )

        # Phase 15: Image Extractor (Claude Vision)
        self.image_extractor: ImageExtractor = ImageExtractor(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.layout.image_description_model,
            min_size=self.settings.layout.min_image_size,
            base_url=self.settings.agent.base_url,
        )

        # Phase 17: Semantic Search Cache
        self.semantic_cache: SemanticSearchCache | None = None
        if self.settings.cache.semantic_enabled:
            from src.pdf_framework.search import semantic_cache as _sc_mod

            self.semantic_cache = SemanticSearchCache(
                db_path=self.settings.cache.semantic_db_path,
                similarity_threshold=self.settings.cache.semantic_threshold,
                ttl_seconds=self.settings.cache.semantic_ttl_seconds,
                max_entries=self.settings.cache.semantic_max_entries,
            )
            _sc_mod._semantic_cache = self.semantic_cache  # set singleton

        # Phase 1 + 2: SearchManager with reranking and query expansion support
        self.search_manager: SearchManager = SearchManager(
            agent_settings=self.settings.agent,
            search_settings=self.settings.search,
            api_key=self.settings.anthropic_api_key,
            embedding_engine=self.embedding_engine,
            semantic_cache=self.semantic_cache,
        )

        # Phase 30: Section-first pipeline (requires BM25)
        if self.bm25_store is not None:
            from src.pdf_framework.search.pipelines.section_first import SectionFirstPipeline

            self.search_manager._section_first_pipeline = SectionFirstPipeline(
                bm25_store=self.bm25_store,
                search_manager=self.search_manager,
            )

        # Register search strategies
        vector_strategy = VectorSearchStrategy(self.embedding_engine, self.vector_store)
        graph_strategy = GraphSearchStrategy(self.graph_store, self.vector_store)

        # Phase 16: BM25 strategy
        bm25_strategy = None
        if self.bm25_store is not None:
            bm25_strategy = BM25SearchStrategy(
                self.bm25_store, self.vector_store,
                use_two_pass=self.settings.search.bm25_two_pass,
            )
            self.search_manager.register_strategy("bm25", bm25_strategy)

        # Phase 1.2 + 16 + 24: Hybrid strategy with vector + graph + BM25
        # Pass vector_store + embedding_engine for Qdrant native BM25 path
        hybrid_strategy = HybridSearchStrategy(
            vector_strategy,
            graph_strategy,
            search_settings=self.settings.search,
            bm25_strategy=bm25_strategy,
            vector_store=self.vector_store,
            embedding_engine=self.embedding_engine,
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
            api_key=self.settings.anthropic_api_key,
            base_url=self.settings.agent.base_url,
        )
        self.search_manager.register_strategy("graphrag_local", graphrag_local)
        self.search_manager.register_strategy("graphrag_global", graphrag_global)

        # Phase 38: LightRAG entity embeddings + strategy
        self.entity_embeddings = None
        if self.settings.light_rag.enabled:
            from src.pdf_framework.graph_store.entity_embeddings import EntityEmbeddingBuilder

            self.entity_embeddings = EntityEmbeddingBuilder(
                embedding_engine=self.embedding_engine,
                settings=self.settings.light_rag,
                qdrant_url=self.settings.vector_store.qdrant_url,
                qdrant_api_key=self.settings.vector_store.qdrant_api_key,
                dimensions=self.settings.embedding.dimensions,
            )

            from src.pdf_framework.search.strategies.graphrag_light import LightRAGStrategy

            lightrag_strategy = LightRAGStrategy(
                embedding_engine=self.embedding_engine,
                vector_store=self.vector_store,
                graph_store=self.graph_store,
                entity_embeddings=self.entity_embeddings,
                settings=self.settings.light_rag,
            )
            self.search_manager.register_strategy("graphrag_light", lightrag_strategy)

            # Phase 38: Auto-selection (requires classifier from Phase 8)
            if self.settings.light_rag.auto_select_enabled:
                from src.pdf_framework.search.routing.classifier import QueryClassifier
                from src.pdf_framework.search.strategies.graphrag_auto import GraphRAGAutoStrategy

                auto_classifier = QueryClassifier(
                    api_key=self.settings.anthropic_api_key,
                    base_url=self.settings.agent.base_url,
                    cache_enabled=True,
                )
                graphrag_auto = GraphRAGAutoStrategy(
                    light_strategy=lightrag_strategy,
                    global_strategy=graphrag_global,
                    classifier=auto_classifier,
                    settings=self.settings.light_rag,
                )
                self.search_manager.register_strategy("graphrag_auto", graphrag_auto)

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
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.agent.base_url,
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
            reranker = self.search_manager._reranker
            if reranker is None:
                reranker = CrossEncoderReranker(
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

        # Phase 34: DSPy Optimizer
        self.dspy_optimizer = None
        if self.settings.optimization.enabled:
            from src.pdf_framework.optimization.dspy_optimizer import DSPyOptimizer

            self.dspy_optimizer = DSPyOptimizer(
                dataset_path=self.settings.optimization.dataset_path,
                optimized_dir=self.settings.optimization.optimized_dir,
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.agent.base_url,
                model=self.settings.optimization.model,
            )

        # Phase 32: Collection Store + Document Registry
        from src.pdf_framework.knowledge_base.collection_store import CollectionStore
        from src.pdf_framework.knowledge_base.document_registry import DocumentRegistry

        self.collection_store: CollectionStore = CollectionStore(
            db_path=self.settings.data_dir / "collections.db",
        )
        self.document_registry: DocumentRegistry = DocumentRegistry(
            db_path=self.settings.data_dir / "document_registry.db",
        )

        # Phase 37: Web Search + Source Fusion
        self.web_search_strategy = None
        self.source_fusion = None
        if self.settings.external.web_search_enabled:
            from src.pdf_framework.search.strategies.web_search import WebSearchStrategy
            from src.pdf_framework.search.external_sources.source_fusion import SourceFusion

            self.web_search_strategy = WebSearchStrategy(
                tavily_api_key=self.settings.external.tavily_api_key,
                serpapi_key=self.settings.external.serpapi_key,
                trust_score=self.settings.external.web_trust_score,
            )
            self.search_manager.register_strategy("web_search", self.web_search_strategy)

            self.source_fusion = SourceFusion(
                search_manager=self.search_manager,
                web_strategy=self.web_search_strategy,
                confidence_threshold=self.settings.external.confidence_threshold,
            )

        # Phase 36: Research Session Store
        self.research_session_store = None
        try:
            from src.pdf_framework.agents.research_v2.session_store import (
                ResearchSessionStore,
            )

            self.research_session_store = ResearchSessionStore(
                db_path=self.settings.data_dir / "research_sessions.db",
            )
        except ImportError:
            pass

        # Phase 40: Enterprise Analytics
        from src.pdf_framework.analytics import QueryTracker, CostTracker, AuditLogger

        self.query_tracker: QueryTracker = QueryTracker(
            db_path=self.settings.data_dir / "analytics.db",
        )
        self.cost_tracker: CostTracker = CostTracker()
        self.audit_logger: AuditLogger = AuditLogger(
            db_path=self.settings.data_dir / "audit.db",
        )

        # Phase 18: Document Version Manager
        self.version_manager = None
        try:
            from src.pdf_framework.processing.versioning import DocumentVersionManager

            self.version_manager = DocumentVersionManager(
                db_path=self.settings.data_dir / "versions.db",
            )
        except ImportError:
            pass

        # Phase 19: Deep Research Planner
        self.research_planner = None
        try:
            from src.pdf_framework.agents.deep.planner import ResearchPlanner

            self.research_planner = ResearchPlanner()
        except ImportError:
            pass

        # Phase 22: Async Feedback Store + FewShot + Boost
        self.feedback_store = None
        self.feedback_collector = None
        self.few_shot_provider = None
        self.content_booster = None
        if self.settings.feedback.enabled:
            try:
                from src.pdf_framework.feedback.store import FeedbackStore
                from src.pdf_framework.feedback.few_shot import FewShotProvider
                from src.pdf_framework.feedback.boost import ContentBooster
                from src.pdf_framework.feedback.collector import FeedbackCollector

                self.feedback_store = FeedbackStore(
                    db_path=self.settings.feedback.async_db_path,
                )
                self.feedback_collector = FeedbackCollector(
                    settings=self.settings,
                )
                self.few_shot_provider = FewShotProvider(
                    feedback_store=self.feedback_store,
                    embedding_engine=self.embedding_engine,
                    max_examples=self.settings.feedback.few_shot_max_examples,
                    similarity_threshold=self.settings.feedback.few_shot_similarity_threshold,
                )
                self.content_booster = ContentBooster(
                    feedback_store=self.feedback_store,
                    max_boost=self.settings.feedback.boost_max,
                    min_positive_count=self.settings.feedback.boost_min_count,
                )
            except ImportError:
                pass

        # Phase 30: Section Summary Service
        self.section_summary = None
        if self.settings.hierarchical.summary_enabled:
            from src.pdf_framework.processing.section_summary import SectionSummaryService

            self.section_summary = SectionSummaryService(
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.agent.base_url,
                model=self.settings.hierarchical.summary_model,
                db_path=self.settings.hierarchical.summary_db_path,
            )

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
        if self.bm25_store is not None:
            await self.bm25_store.initialize()
        if self.semantic_cache is not None:
            await self.semantic_cache.initialize()
        # Phase 18
        if self.version_manager is not None:
            await self.version_manager.initialize()
        # Phase 22
        if self.feedback_store is not None:
            await self.feedback_store.initialize()
        # Phase 30
        if self.section_summary is not None:
            await self.section_summary.initialize()
        # Phase 32
        await self.collection_store.initialize()
        await self.document_registry.initialize()
        # Phase 36
        if self.research_session_store is not None:
            await self.research_session_store.initialize()
        # Phase 40
        await self.query_tracker.initialize()
        await self.audit_logger.initialize()


_components: Components | None = None


async def get_components() -> Components:
    """Get or create the singleton components instance."""
    global _components
    if _components is None:
        _components = Components()
        await _components.initialize()
    return _components
