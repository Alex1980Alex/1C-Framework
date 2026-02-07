"""Recursive text splitter wrapping LangChain's implementation.

Splits documents into overlapping chunks, producing DocumentChunk objects.
"""

import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument


class RecursiveTextSplitter:
    """Split document text into overlapping chunks."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """Split a processed document into chunks."""
        if not document.raw_text.strip():
            return []

        texts = self._splitter.split_text(document.raw_text)
        chunks: list[DocumentChunk] = []

        for i, text in enumerate(texts):
            chunk = DocumentChunk(
                id=f"{document.id}_chunk_{uuid.uuid4().hex[:8]}",
                content=text,
                document_id=document.id,
                chunk_index=i,
                metadata={
                    "source": document.source_path,
                    "title": document.metadata.title,
                },
            )
            chunks.append(chunk)

        return chunks
