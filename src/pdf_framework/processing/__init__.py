"""Document processing pipeline with caching and versioning (Phase 11-12)."""

from src.pdf_framework.processing.cache import (
    CachedDocument,
    DocumentProcessingCache,
    get_document_cache,
)
from src.pdf_framework.processing.pipeline import ProcessingPipeline
from src.pdf_framework.processing.versioning import (
    DocumentVersionManager,
    VersionInfo,
    get_version_manager,
)

__all__ = [
    "ProcessingPipeline",
    "DocumentProcessingCache",
    "CachedDocument",
    "get_document_cache",
    "DocumentVersionManager",
    "VersionInfo",
    "get_version_manager",
]
