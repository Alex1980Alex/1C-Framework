"""PDF Vector & Graph Framework.

Intelligent PDF document processing with Vector and Graph databases.

Architecture:
    loaders/        - PDF loading and raw content extraction
    processing/     - Text splitting, cleaning, metadata extraction
    embeddings/     - Embedding generation (OpenAI, Voyage, local)
    vector_store/   - Vector DB operations (Chroma, Qdrant, FAISS)
    graph_store/    - Graph DB operations (Neo4j, NetworkX)
    search/         - Unified search: hybrid vector+graph, reranking, routing
    agents/         - LangGraph agents: RAG, graph reasoning, hybrid, deep
    tools/          - LangChain tools for agents
    chains/         - LangChain chains: QA, summarization, extraction
    callbacks/      - Tracing, logging, metrics callbacks
    schemas/        - Pydantic models for documents, entities, responses
    utils/          - Shared utilities

Quick Start (Phase 14):
    from pdf_framework import QuickRAG
    rag = QuickRAG()
    rag.add("document.pdf")
    answer = rag.ask("What is this about?")
"""

__version__ = "1.5.0"

# Phase 14: QuickRAG High-Level API
from src.pdf_framework.quick import QuickRAG

__all__ = ["QuickRAG"]
