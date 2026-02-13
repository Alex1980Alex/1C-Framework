"""Document loaders."""

from src.pdf_framework.config import LayoutSettings, PDFSettings, get_settings
from src.pdf_framework.loaders.base import BaseLoader


def get_loader(
    settings: PDFSettings | None = None,
    layout_settings: LayoutSettings | None = None,
) -> BaseLoader:
    """Factory: return a loader based on settings."""
    settings = settings or PDFSettings()

    # Phase 15.1: Smart Router
    if settings.loader == "smart":
        from src.pdf_framework.loaders.router import SmartLoaderRouter

        s = get_settings()
        return SmartLoaderRouter(
            settings=s.smart_router,
            docling_settings=s.docling,
        )

    # Phase 15.1: Docling loader
    if settings.loader == "docling":
        from src.pdf_framework.loaders.providers.docling_loader import DoclingLoader

        return DoclingLoader(settings=get_settings().docling)

    # Phase 15.1: PyMuPDF4LLM loader
    if settings.loader == "pymupdf4llm":
        from src.pdf_framework.loaders.providers.pymupdf4llm_loader import (
            PyMuPDF4LLMLoader,
        )

        return PyMuPDF4LLMLoader()

    # Phase 28: Hybrid loader (PyMuPDF4LLM + fitz tables + Docling tables)
    if settings.loader == "hybrid":
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        s = get_settings()
        return HybridLoader(settings=s.hybrid_loader)

    # Phase 10: Layout-aware loader
    if settings.loader == "unstructured" or (
        layout_settings and layout_settings.layout_detection_enabled
    ):
        from src.pdf_framework.loaders.providers.layout_parser import LayoutAwareLoader

        ls = layout_settings or LayoutSettings()
        return LayoutAwareLoader(
            strategy=ls.layout_strategy,
            infer_table_structure=ls.infer_table_structure,
            extract_images=ls.extract_images,
        )

    if settings.loader == "pymupdf":
        from src.pdf_framework.loaders.pdf.pymupdf_loader import PyMuPDFLoader

        return PyMuPDFLoader()

    raise ValueError(f"Unsupported loader: {settings.loader}")
