"""Text splitter implementations.

Phase 7 (v0.8.0) - Parent-Child Retrieval:
- ParentChildSplitter: Two-level chunking for auto-merge retrieval

Phase 10 (v1.1.0) - Layout-Aware Parsing:
- StructureAwareSplitter: chunking based on layout elements
"""

from src.pdf_framework.processing.splitters.parent_child import ParentChildSplitter
from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter
from src.pdf_framework.processing.splitters.semantic_splitter import SemanticTextSplitter
from src.pdf_framework.processing.splitters.structure_aware import StructureAwareSplitter

__all__ = [
    "RecursiveTextSplitter",
    "SemanticTextSplitter",
    "ParentChildSplitter",  # Phase 7.1
    "StructureAwareSplitter",  # Phase 10.2
]
