"""LangGraph nodes for Self-RAG agent.

Phase 5 (v0.6.0) - Self-RAG & Corrective RAG:
- Document Grader: LLM-based relevance assessment
- Query Rewriter: Automatic query reformulation
- Hallucination Checker: Groundedness verification

Author: Claude Code
Version: 0.6.0
"""

from .grader import grade_documents
from .rewriter import rewrite_query
from .hallucination_checker import check_hallucination, regenerate_answer

__all__ = [
    "grade_documents",
    "rewrite_query",
    "check_hallucination",
    "regenerate_answer",
]
