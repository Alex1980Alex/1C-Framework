"""LangChain tool for indexing PDF documents."""

import time

from langchain_core.tools import tool

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.observability.langfuse_setup import emit_observation
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
        t0 = time.monotonic()
        span_input = {"file_path": file_path}
        try:
            document = await loader.load(file_path)
            chunks = pipeline.process(document)
            result = await indexer.index_chunks(
                chunks,
                document_id=document.id,
                source_path=document.source_path,
            )
        except Exception as e:
            try:
                emit_observation(
                    name="tool.index_document",
                    input=span_input,
                    output={
                        "status": "error",
                        "error_type": type(e).__name__,
                        "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                    },
                    flush=False,
                )
            except Exception:
                pass
            raise

        try:
            emit_observation(
                name="tool.index_document",
                input=span_input,
                output={
                    "status": "ok",
                    "chunks_stored": result.chunks_stored,
                    "embeddings_computed": result.embeddings_computed,
                    "duration_ms": round((time.monotonic() - t0) * 1000, 1),
                },
                flush=False,
            )
        except Exception:
            pass

        return (
            f"Indexed '{document.metadata.title}': "
            f"{result.chunks_stored} chunks, "
            f"{result.embeddings_computed} embeddings."
        )

    return index_document
