"""Agent and Self-RAG configuration."""

from typing import Literal

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """LangGraph agent configuration."""

    model: str = "claude-opus-4-6"
    temperature: float = 0.0
    max_tokens: int = 4096
    search_k: int = 5

    # Reranking configuration (Phase 1.1 / Phase 25)
    reranker_enabled: bool = True
    reranker_type: Literal["cross_encoder", "llm", "colbert"] = "llm"  # "llm" = Claude, "cross_encoder" = local, "colbert" = ColBERT
    reranker_model: str = "BAAI/bge-reranker-v2-m3"  # For cross_encoder type
    colbert_model: str = "jinaai/jina-colbert-v2"  # For colbert type (Phase 35)
    reranker_llm_model: str = "claude-sonnet-4-5-20250929"  # For llm type
    reranker_top_k: int = 20  # Retrieve more, then rerank to top_k

    checkpointer: Literal["memory", "postgres", "sqlite"] = "memory"

    # API endpoint configuration (for Z.AI or other proxies)
    base_url: str = ""  # Empty = use default Anthropic endpoint

    # Parallel entity extraction (graph building)
    graph_concurrency: int = 5  # Max concurrent LLM calls for entity extraction

    # Phase 54: Model Routing
    model_map_simple: str = "claude-haiku-3-5"
    model_map_moderate: str = "claude-sonnet-4-5-20250929"
    model_map_complex: str = "claude-opus-4-6"
    cost_budget_per_query: float = 0.10  # USD
    cost_budget_daily: float = 50.0  # USD
    model_routing_enabled: bool = False


class SelfRAGSettings(BaseSettings):
    """Phase 5: Self-RAG & Corrective RAG configuration.

    Enables:
    - Document Grading: LLM-based relevance assessment
    - Query Rewriting: Automatic query reformulation
    - Hallucination Checking: Groundedness verification
    """

    enabled: bool = True

    # Fast LLM for all Self-RAG tasks (grading, rewriting, hallucination check)
    grading_model: str = "claude-sonnet-4-5-20250929"

    # Document Grading (5.2)
    relevance_threshold: float = 0.5  # Minimum relevance ratio to proceed
    score_prefilter_threshold: float = 0.1  # Skip LLM grading for docs below this search score

    # Query Rewriting (5.3)
    max_retries: int = 2  # Maximum query rewrite attempts

    # Hallucination Checking (5.4)
    hallucination_check_enabled: bool = True
    max_generation_attempts: int = 2  # Max regenerations if hallucinated
    max_context_chars: int = 4000  # Truncate context for hallucination check

    # Strategy Escalation (5.3)
    strategy_escalation_enabled: bool = True  # vector -> hybrid -> two_stage

    # Answer Enrichment (Phase 42)
    enrichment_enabled: bool = True
    enrichment_max_rounds: int = 1  # Max enrichment iterations
    enrichment_sub_queries: int = 3  # Sub-queries per round
    enrichment_k: int = 5  # Results per sub-query


class DeepResearchSettings(BaseSettings):
    """Phase 19: Deep Research Agent configuration."""

    enabled: bool = False
    max_sub_questions: int = 4
    max_retrieval_steps: int = 5
