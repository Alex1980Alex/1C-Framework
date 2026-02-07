"""LangGraph nodes for Self-RAG agent.

Phase 5 (v0.6.0) - Self-RAG & Corrective RAG:
- Document Grader: LLM-based relevance assessment
- Query Rewriter: Automatic query reformulation
- Hallucination Checker: Groundedness verification

Phase 9 (v1.0.0) - Conversational RAG:
- Reformulator: History-aware query reformulation

Author: Claude Code
Version: 1.0.0
"""

from .grader import grade_documents
from .hallucination_checker import check_hallucination, regenerate_answer
from .reformulator import reformulate_query_node
from .rewriter import rewrite_query

__all__ = [
    # Phase 5
    "grade_documents",
    "rewrite_query",
    "check_hallucination",
    "regenerate_answer",
    # Phase 9
    "reformulate_query_node",
]
