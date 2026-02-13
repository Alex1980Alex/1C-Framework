"""QuickRAG High-Level API for 3-line usage (Phase 14.4).

Author: Claude Code
Version: 1.5.0 - Phase 14.4: QuickRAG
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class QuickRAG:
    """
    Maximum simplicity RAG API.

    Usage:
        rag = QuickRAG()
        rag.add("document.pdf")
        answer = rag.ask("What is this about?")
    """

    def __init__(self, **kwargs):
        """
        Initialize QuickRAG with automatic component setup.

        Args:
            **kwargs: Override default settings
                - strategy: Search strategy (default: "hybrid")
                - model: LLM model name
                - api_key: Anthropic API key
                - data_dir: Data directory path
        """
        self._kwargs = kwargs
        self._components = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization on first use."""
        if self._initialized:
            return

        from src.api.dependencies.components import Components
        from src.pdf_framework.config import get_settings

        # Get settings (with overrides from kwargs)
        settings = get_settings()

        # Apply runtime overrides
        for key, value in self._kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        # Initialize components
        self._components = Components()
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._components.initialize())

        self._initialized = True

    async def _aadd(self, path: str | Path) -> "IndexResult":
        """Internal async add implementation."""
        from src.pdf_framework.loaders.base import BaseLoader

        loader: BaseLoader = self._components.loader
        document = await loader.load(str(path))

        chunks = self._components.pipeline.process(document)

        result = await self._components.indexer.index_chunks(
            chunks,
            document_id=document.id,
            source_path=document.source_path,
        )
        return result

    def add(self, path: str | Path) -> "IndexResult":
        """
        Index a PDF document (sync wrapper).

        Args:
            path: Path to PDF file

        Returns:
            IndexResult with chunks_stored, embeddings_computed
        """
        self._ensure_initialized()
        return self._loop.run_until_complete(self._aadd(path))

    async def aadd(self, path: str | Path) -> "IndexResult":
        """Async version of add()."""
        self._ensure_initialized()
        return await self._aadd(path)

    async def _asearch(self, query: str, k: int, strategy: str) -> list[dict[str, Any]]:
        """Internal async search implementation."""
        response = await self._components.search_manager.search(
            query=query,
            strategy=strategy,
            k=k,
        )
        return [
            {
                "score": r.score,
                "content": r.chunk.content,
                "source": r.source,
                "metadata": r.chunk.metadata,
            }
            for r in response.results
        ]

    def search(self, query: str, k: int = 5, strategy: str = "hybrid") -> list[dict[str, Any]]:
        """
        Search for relevant chunks (sync wrapper).

        Args:
            query: Search query
            k: Number of results
            strategy: Search strategy

        Returns:
            List of dicts with keys: score, content, source, metadata
        """
        self._ensure_initialized()
        return self._loop.run_until_complete(self._asearch(query, k, strategy))

    async def asearch(self, query: str, k: int = 5, strategy: str = "hybrid") -> list[dict[str, Any]]:
        """Async version of search()."""
        self._ensure_initialized()
        return await self._asearch(query, k, strategy)

    async def _aask(self, question: str, strategy: str) -> str:
        """Internal async ask implementation."""
        from src.pdf_framework.agents.rag.agent import create_rag_agent

        agent = create_rag_agent(
            search_manager=self._components.search_manager,
            settings=self._components.settings.agent,
            self_rag_settings=self._components.settings.self_rag,
            api_key=self._components.settings.anthropic_api_key,
        )

        result = await agent.ainvoke({
            "question": question,
            "search_strategy": strategy,
        })

        return result.get("answer", "No answer generated.")

    def ask(self, question: str, strategy: str = "hybrid") -> str:
        """
        Ask a question and get an answer (sync wrapper).

        Args:
            question: User question
            strategy: Search strategy

        Returns:
            Answer text
        """
        self._ensure_initialized()
        return self._loop.run_until_complete(self._aask(question, strategy))

    async def aask(self, question: str, strategy: str = "hybrid") -> str:
        """Async version of ask()."""
        self._ensure_initialized()
        return await self._aask(question, strategy)

    async def _astats(self) -> dict[str, Any]:
        """Internal async stats implementation."""
        vector_count = await self._components.vector_store.count()
        graph_stats = await self._components.graph_store.get_statistics()

        return {
            "chunks": vector_count,
            "entities": graph_stats.get("entity_count", 0),
            "relations": graph_stats.get("relation_count", 0),
        }

    def stats(self) -> dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dict with document_count, chunk_count, entity_count, etc.
        """
        self._ensure_initialized()
        return self._loop.run_until_complete(self._astats())

    async def astats(self) -> dict[str, Any]:
        """Async version of stats()."""
        self._ensure_initialized()
        return await self._astats()


class IndexResult(BaseModel):
    """Result of document indexing."""

    document_id: str
    chunks_stored: int
    embeddings_computed: int
    source_path: str | None = None

    def __str__(self) -> str:
        return f"Indexed {self.chunks_stored} chunks from {self.source_path or self.document_id}"


# Global QuickRAG instance
_quick_rag: QuickRAG | None = None


def get_quick_rag(**kwargs) -> QuickRAG:
    """Get or create global QuickRAG instance."""
    global _quick_rag
    if _quick_rag is None:
        _quick_rag = QuickRAG(**kwargs)
    return _quick_rag
