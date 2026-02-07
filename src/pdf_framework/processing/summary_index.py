"""Document Summary Index for pre-routing (Phase 13.4).

Indexes document-level summaries to accelerate search in large collections.

Author: Claude Code
Version: 1.4.0 - Phase 13.4: Document Summary Index
"""

import logging
from datetime import timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentSummary(BaseModel):
    """Summary of a document."""

    document_id: str
    summary: str
    title: str
    chunk_count: int
    embedding: list[float] | None = None
    created_at: str
    metadata: dict[str, Any] = {}


class DocumentSummaryIndex:
    """
    Index of document summaries for pre-routing.

    Workflow:
    1. Index: Generate LLM summary per document
    2. Search: Find top-K relevant documents by summary
    3. Filter: Search chunks only within those documents
    """

    def __init__(
        self,
        collection_name: str = "document_summaries",
        persist_dir: str | Path = "data/vector_db",
        summarization_model: str = "claude-haiku-4-5-20251001",
        api_key: str = "",
    ):
        """
        Initialize document summary index.

        Args:
            collection_name: ChromaDB collection name for summaries
            persist_dir: Vector store persist directory
            summarization_model: LLM for summarization
            api_key: Anthropic API key
        """
        self._collection_name = collection_name
        self._persist_dir = Path(persist_dir)
        self._summarization_model = summarization_model
        _api_key = api_key

        # Lazy initialization
        self._vector_store = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Initialize vector store for summaries."""
        if self._initialized:
            return

        from src.pdf_framework.vector_store.providers.chroma import ChromaVectorStore
        from src.pdf_framework.config import VectorStoreSettings

        settings = VectorStoreSettings(
            provider="chroma",
            collection_name=self._collection_name,
            persist_dir=self._persist_dir,
            distance_metric="cosine",
        )

        self._vector_store = ChromaVectorStore(settings)
        await self._vector_store.initialize()

        self._initialized = True

    async def add_document(
        self,
        document_id: str,
        chunks: list[dict],
        title: str = "",
        metadata: dict | None = None,
    ) -> DocumentSummary:
        """
        Generate and index document summary.

        Args:
            document_id: Document identifier
            chunks: Document chunks
            title: Document title
            metadata: Additional metadata

        Returns:
            DocumentSummary
        """
        await self._ensure_initialized()

        # Generate summary
        summary = await self._generate_summary(chunks, document_id)

        # Generate embedding
        embedding = await self._embed_text(summary)

        # Create DocumentSummary
        doc_summary = DocumentSummary(
            document_id=document_id,
            summary=summary,
            title=title or document_id,
            chunk_count=len(chunks),
            embedding=embedding,
            created_at=timezone.utc.now().isoformat(),
            metadata=metadata or {},
        )

        # Store in vector store
        from src.pdf_framework.schemas.search import DocumentChunk

        chunk = DocumentChunk(
            id=f"summary_{document_id}",
            content=summary,
            metadata={
                "summary_id": document_id,
                "title": title,
                "chunk_type": "document_summary",
                "document_id": document_id,
                **(metadata or {}),
            },
        )

        await self._vector_store.add_documents([chunk], [embedding])

        logger.info(
            f"[SUMMARY_IDX] Indexed summary for '{document_id}' "
            f"({len(summary)} chars, {len(chunks)} chunks)"
        )

        return doc_summary

    async def search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        k: int = 3,
    ) -> list[DocumentSummary]:
        """
        Search for relevant documents by summary.

        Args:
            query: Search query
            query_embedding: Pre-computed query embedding
            k: Number of documents to return

        Returns:
            List of relevant DocumentSummary
        """
        await self._ensure_initialized()

        # Search in summary collection
        from src.pdf_framework.schemas.search import SearchRequest

        request = SearchRequest(
            query=query,
            query_embedding=query_embedding,
            k=k,
        )

        response = await self._vector_store.search(request)

        # Convert to DocumentSummary
        summaries = []
        for result in response.results:
            metadata = result.chunk.metadata
            summaries.append(DocumentSummary(
                document_id=metadata.get("summary_id", ""),
                summary=result.chunk.content,
                title=metadata.get("title", ""),
                chunk_count=metadata.get("chunk_count", 0),
                embedding=result.embedding,
                created_at=metadata.get("created_at", ""),
                metadata=metadata,
            ))

        return summaries

    async def rebuild(self, documents: list[tuple[str, list[dict]]]) -> None:
        """
        Rebuild entire summary index.

        Args:
            documents: List of (document_id, chunks) tuples
        """
        await self._ensure_initialized()

        # Clear existing
        await self._vector_store.clear()

        # Re-index all documents
        for document_id, chunks in documents:
            try:
                await self.add_document(document_id, chunks)
            except Exception as e:
                logger.error(f"[SUMMARY_IDX] Failed to index {document_id}: {e}")

        logger.info(f"[SUMMARY_IDX] Rebuilt index with {len(documents)} documents")

    async def _generate_summary(
        self,
        chunks: list[dict],
        document_id: str,
    ) -> str:
        """Generate LLM summary for document chunks."""
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm = ChatAnthropic(
                model=self._summarization_model,
                temperature=0.3,
                max_tokens=500,
                api_key=_api_key or None,
            )

            # Combine chunk contents
            passages = []
            for chunk in chunks[:20]:  # Limit context
                content = chunk.get("content", "").strip()
                if content:
                    passages.append(f"- {content[:200]}...")

            context = "\n\n".join(passages)

            prompt = f"""Generate a concise summary (200-500 tokens) of this document.

Focus on:
- Main topics and themes covered
- Key entities, technologies, or concepts
- Overall purpose and audience

Document content (excerpts):
{context}

Summary:"""

            response = await llm.ainvoke([HumanMessage(content=prompt)])

            summary = response.content.strip()
            logger.info(f"[SUMMARY_IDX] Generated summary for {document_id} ({len(summary)} chars)")

            return summary

        except Exception as e:
            logger.error(f"[SUMMARY_IDX] Summarization failed for {document_id}: {e}")
            return f"Summary not available for {document_id}"

    async def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        # TODO: Use actual embedding engine from components
        import hashlib
        import numpy as np

        hash_val = hashlib.md5(text.encode()).hexdigest()
        embedding = np.array([float(int(h, 16)) / 255.0 for h in hash_val])[:384]
        return embedding.tolist()


# Global document summary index instance
_summary_index: DocumentSummaryIndex | None = None


def get_summary_index(**kwargs) -> DocumentSummaryIndex:
    """Get or create global document summary index instance."""
    global _summary_index
    if _summary_index is None:
        _summary_index = DocumentSummaryIndex(**kwargs)
    return _summary_index
