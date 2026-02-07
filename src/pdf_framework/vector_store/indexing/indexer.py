"""Document indexer: orchestrates embedding computation and vector storage."""

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.schemas.responses import IndexResult
from src.pdf_framework.vector_store.base import BaseVectorStore


class DocumentIndexer:
    """Orchestrate: compute embeddings → store in vector DB."""

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
    ):
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store

    async def index_chunks(
        self,
        chunks: list[DocumentChunk],
        document_id: str = "",
        source_path: str = "",
    ) -> IndexResult:
        """Embed and store a list of document chunks."""
        if not chunks:
            return IndexResult(
                document_id=document_id,
                source_path=source_path,
                chunks_stored=0,
                embeddings_computed=0,
            )

        # Phase 3.1: Use contextual_content for embedding if available
        texts = [
            c.metadata.get("contextual_content", c.content)
            for c in chunks
        ]
        embeddings = await self._embedding_engine.embed_batch(texts)

        stored_ids = await self._vector_store.add_documents(chunks, embeddings)

        return IndexResult(
            document_id=document_id or chunks[0].document_id,
            source_path=source_path,
            chunks_stored=len(stored_ids),
            embeddings_computed=len(embeddings),
        )
