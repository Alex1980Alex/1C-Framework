"""Document processing pipeline with caching, versioning, and RAPTOR (Phase 11-13)."""

from src.pdf_framework.processing.cache import (
    CachedDocument,
    DocumentProcessingCache,
    get_document_cache,
)
from src.pdf_framework.processing.pipeline import ProcessingPipeline
from src.pdf_framework.processing.raptor import (
    RAPTORTree,
    RAPTORTreeBuilder,
    TreeNode,
    get_raptor_builder,
)
from src.pdf_framework.processing.summary_index import (
    DocumentSummary,
    DocumentSummaryIndex,
    get_summary_index,
)
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
    # Phase 13: RAPTOR & Summary Index
    "RAPTORTree",
    "RAPTORTreeBuilder",
    "TreeNode",
    "get_raptor_builder",
    "DocumentSummary",
    "DocumentSummaryIndex",
    "get_summary_index",
]
