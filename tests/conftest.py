"""Shared test fixtures for PDF Vector & Graph Framework."""

import pytest


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Path to a sample PDF for testing (to be created in fixtures)."""
    return tmp_path / "sample.pdf"


@pytest.fixture
def sample_chunks():
    """Sample document chunks for testing."""
    from src.pdf_framework.schemas.documents import DocumentChunk

    return [
        DocumentChunk(
            id=f"chunk_{i}",
            content=f"Sample content for chunk {i}",
            document_id="doc_1",
            page_number=i,
            chunk_index=i,
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors for testing."""
    import random

    random.seed(42)
    return [[random.random() for _ in range(384)] for _ in range(5)]
