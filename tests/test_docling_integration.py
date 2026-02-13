"""Tests for Docling integration (Phase 15.1).

Run tests:
    pytest tests/test_docling_integration.py -v

Or quick test:
    python tests/test_docling_integration.py
"""

from pathlib import Path

import pytest

from src.pdf_framework.loaders.providers.docling_loader import DoclingLoader
from src.pdf_framework.loaders.providers.pymupdf4llm_loader import (
    PyMuPDF4LLMLoader,
)
from src.pdf_framework.loaders.router import SmartLoaderRouter


def _is_docling_available() -> bool:
    """Check if Docling is installed."""
    try:
        import docling
        return True
    except ImportError:
        return False


def _is_pymupdf4llm_available() -> bool:
    """Check if PyMuPDF4LLM is installed."""
    try:
        import pymupdf4llm
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _is_docling_available(),
    reason="Docling not installed. Run: pip install pdf-vector-graph-framework[docling]"
)
def test_docling_loader_basic():
    """Test basic Docling loader functionality."""
    loader = DoclingLoader()
    assert loader.supported_extensions() == [".pdf", ".docx", ".pptx", ".xlsx", ".html"]


@pytest.mark.skipif(
    not _is_docling_available(),
    reason="Docling not installed"
)
@pytest.mark.asyncio
async def test_docling_loader_load():
    """Test Docling loader with a sample PDF."""
    loader = DoclingLoader()

    # Use a test PDF if available, otherwise skip
    test_pdf = Path("data/pdfs/test.pdf")
    if not test_pdf.exists():
        pytest.skip(f"Test PDF not found: {test_pdf}")

    doc = await loader.load(test_pdf)

    assert doc.id
    assert doc.raw_text
    assert doc.metadata.page_count > 0
    assert "layout_detection_method" in doc.metadata.extra
    assert doc.metadata.extra["layout_detection_method"] == "docling"


@pytest.mark.skipif(
    not _is_pymupdf4llm_available(),
    reason="PyMuPDF4LLM not installed. Run: pip install pymupdf4llm"
)
def test_pymupdf4llm_loader_basic():
    """Test basic PyMuPDF4LLM loader functionality."""
    loader = PyMuPDF4LLMLoader()
    assert loader.supported_extensions() == [".pdf"]


@pytest.mark.skipif(
    not _is_pymupdf4llm_available(),
    reason="PyMuPDF4LLM not installed"
)
@pytest.mark.asyncio
async def test_pymupdf4llm_loader_load():
    """Test PyMuPDF4LLM loader with a sample PDF."""
    loader = PyMuPDF4LLMLoader()

    test_pdf = Path("data/pdfs/test.pdf")
    if not test_pdf.exists():
        pytest.skip(f"Test PDF not found: {test_pdf}")

    doc = await loader.load(test_pdf)

    assert doc.id
    assert doc.raw_text
    assert doc.metadata.page_count > 0
    assert doc.metadata.extra["layout_detection_method"] == "pymupdf4llm"


@pytest.mark.asyncio
async def test_smart_router_classification():
    """Test SmartLoaderRouter PDF classification."""
    router = SmartLoaderRouter()

    test_pdf = Path("data/pdfs/test.pdf")
    if not test_pdf.exists():
        pytest.skip(f"Test PDF not found: {test_pdf}")

    pdf_type = router._classify_pdf(test_pdf)
    assert pdf_type in ["native_simple", "native_complex", "scanned"]


@pytest.mark.asyncio
async def test_smart_router_load():
    """Test SmartLoaderRouter full load."""
    router = SmartLoaderRouter()

    test_pdf = Path("data/pdfs/test.pdf")
    if not test_pdf.exists():
        pytest.skip(f"Test PDF not found: {test_pdf}")

    doc = await router.load(test_pdf)

    assert doc.id
    assert doc.raw_text
    method = doc.metadata.extra.get("layout_detection_method", "unknown")
    assert method in ["pymupdf4llm", "docling"]


# Quick test runner (when file is executed directly)
if __name__ == "__main__":
    print("Running Docling integration tests...\n")

    print("1. Checking dependencies...")
    if _is_docling_available():
        print("   ✓ Docling available")
    else:
        print("   ✗ Docling NOT available (run: pip install pdf-vector-graph-framework[docling])")

    if _is_pymupdf4llm_available():
        print("   ✓ PyMuPDF4LLM available")
    else:
        print("   ✗ PyMuPDF4LLM NOT available (run: pip install pymupdf4llm)")

    print("\n2. Testing loaders...")

    if _is_docling_available():
        print("   Testing DoclingLoader...")
        loader = DoclingLoader()
        print(f"   ✓ Supported: {', '.join(loader.supported_extensions())}")

    if _is_pymupdf4llm_available():
        print("   Testing PyMuPDF4LLMLoader...")
        loader = PyMuPDF4LLMLoader()
        print(f"   ✓ Supported: {', '.join(loader.supported_extensions())}")

    print("\n3. Testing SmartRouter...")
    router = SmartLoaderRouter()
    print(f"   ✓ Fast loader: {router._settings.fast_loader}")
    print(f"   ✓ Full loader: {router._settings.full_loader}")

    print("\nAll basic tests passed! Use pytest for full testing.")
