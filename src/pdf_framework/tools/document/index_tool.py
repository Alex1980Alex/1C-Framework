"""LangChain tool for indexing PDF documents."""

from langchain_core.tools import tool

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.processing.pipeline import ProcessingPipeline
from src.pdf_framework.vector_store.indexing.indexer import DocumentIndexer


def create_index_tool(
    loader: BaseLoader,
    pipeline: ProcessingPipeline,
    indexer: DocumentIndexer,
):
    """Create a LangChain tool for PDF indexing."""

    @tool
    async def index_document(file_path: str) -> str:
        """Index a PDF document: load, split, embed, and store.

        Args:
            file_path: Path to the PDF file to index.
        """
        document = await loader.load(file_path)
        chunks = pipeline.process(document)
        result = await indexer.index_chunks(
            chunks,
            document_id=document.id,
            source_path=document.source_path,
        )
        return (
            f"Indexed '{document.metadata.title}': "
            f"{result.chunks_stored} chunks, "
            f"{result.embeddings_computed} embeddings."
        )

    return index_document
