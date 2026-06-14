"""D7 wiring regression (roadmap 260612 pdf-docs): DocumentIndexer registers
indexed documents in document_registry so list_documents reflects every entry
point (CLI / MCP / API / scripts), not only the REST routes.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.vector_store.indexing.indexer import DocumentIndexer

pytestmark = pytest.mark.unit


class FakeEmbeddingEngine:
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeVectorStore:
    async def add_documents(self, chunks: Any, embeddings: Any) -> list[str]:
        return [c.id for c in chunks]


class FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def register(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class ExplodingRegistry:
    async def register(self, **kwargs: Any) -> None:
        raise RuntimeError("registry down")


def _chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            id=f"c{i}",
            content=f"chunk {i}",
            document_id="doc1",
            metadata={"page_number": page, "source": "data/pdfs/x.pdf"},
        )
        for i, page in enumerate([1, 7, 3])
    ]


async def test_index_chunks_registers_document() -> None:
    registry = FakeRegistry()
    indexer = DocumentIndexer(FakeEmbeddingEngine(), FakeVectorStore(), document_registry=registry)

    result = await indexer.index_chunks(
        _chunks(), document_id="doc1", source_path="data/pdfs/x.pdf"
    )

    assert result.chunks_stored == 3
    assert len(registry.calls) == 1
    call = registry.calls[0]
    assert call["document_id"] == "doc1"
    assert call["source_path"] == "data/pdfs/x.pdf"
    assert call["chunk_count"] == 3
    assert call["page_count"] == 7  # max page across chunks


async def test_registry_failure_does_not_fail_indexing() -> None:
    indexer = DocumentIndexer(
        FakeEmbeddingEngine(), FakeVectorStore(), document_registry=ExplodingRegistry()
    )

    result = await indexer.index_chunks(
        _chunks(), document_id="doc1", source_path="data/pdfs/x.pdf"
    )

    assert result.chunks_stored == 3  # indexing survives registry outage


async def test_no_registry_is_noop() -> None:
    indexer = DocumentIndexer(FakeEmbeddingEngine(), FakeVectorStore())

    result = await indexer.index_chunks(
        _chunks(), document_id="doc1", source_path="data/pdfs/x.pdf"
    )

    assert result.chunks_stored == 3
