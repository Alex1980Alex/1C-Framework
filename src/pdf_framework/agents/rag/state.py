"""RAG agent state definition for LangGraph.

Author: Claude Code
Version: 0.6.0 - Phase 5: Self-RAG & Corrective RAG
"""

from typing import TypedDict

from src.pdf_framework.schemas.documents import SearchResponse


class RAGState(TypedDict, total=False):
    """State for the RAG agent graph with Self-RAG support.

    Phase 5 (v0.6.0) adds fields for:
    - Document grading (relevance assessment)
    - Query rewriting with retries
    - Hallucination checking
    """

    # ========== Input ==========
    question: str

    # ========== Analysis ==========
    query_type: str  # "factual", "analytical", "comparative"
    search_strategy: str  # "vector", "graph", "hybrid", "two_stage"

    # ========== Search results ==========
    search_response: SearchResponse
    context: str

    # ========== Evaluation (legacy, kept for compatibility) ==========
    relevance_score: float
    needs_more_context: bool

    # ========== Phase 5: Self-RAG fields ==========

    # Document Grading (5.2)
    graded_documents: list[dict]  # [{chunk_id, is_relevant, reason, score}]
    relevance_ratio: float  # % of relevant documents (0.0-1.0)

    # Query Rewriting (5.3)
    retry_count: int  # Current retry attempt (0-based)
    max_retries: int  # Maximum retries allowed (default: 2)
    original_question: str  # Original user query (before rewrites)

    # Hallucination Checking (5.4)
    is_hallucinated: bool  # Whether answer contains hallucinations
    hallucination_reason: str  # Explanation of hallucination check
    generation_attempts: int  # Number of generation attempts (default: 0)

    # ========== Output ==========
    answer: str
    sources: list[str]
    error: str

    # ========== Metadata (for debugging/monitoring) ==========
    metadata: dict  # Additional info about execution path
