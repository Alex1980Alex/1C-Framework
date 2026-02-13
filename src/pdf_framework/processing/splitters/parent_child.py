"""Parent-Child text splitter for two-level document chunking.

Splits documents into large parent chunks for context and small child
chunks for precise search retrieval.

Author: Claude Code
Version: 0.8.0 - Phase 7.1: Parent-Child Splitter
"""

import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument
from src.pdf_framework.utils.id_generator import generate_chunk_id

logger = logging.getLogger(__name__)


class ParentChildSplitter:
    """
    Two-level text splitter for parent-child document retrieval.

    Strategy:
    1. Split document into large parent chunks (e.g., 2000 chars)
    2. Split each parent into small child chunks (e.g., 400 chars)
    3. Link children to parents via metadata

    This enables:
    - Precise search on small child chunks
    - Broad context from merged parent chunks
    """

    def __init__(
        self,
        parent_chunk_size: int = 2000,
        parent_chunk_overlap: int = 200,
        child_chunk_size: int = 400,
        child_chunk_overlap: int = 50,
    ):
        """
        Initialize parent-child splitter.

        Args:
            parent_chunk_size: Size of parent chunks in characters
            parent_chunk_overlap: Overlap between parent chunks
            child_chunk_size: Size of child chunks in characters
            child_chunk_overlap: Overlap between child chunks
        """
        self.parent_chunk_size = parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap

        # Initialize splitters for both levels
        self._parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, document: ProcessedDocument) -> tuple[list[DocumentChunk], list[DocumentChunk]]:
        """
        Split document into parent and child chunks.

        Args:
            document: Processed document to split

        Returns:
            Tuple of (parent_chunks, child_chunks)
        """
        if not document.raw_text.strip():
            logger.warning(f"[PARENT_CHILD] Empty document: {document.id}")
            return [], []

        # Step 1: Split into parent chunks
        parent_texts = self._parent_splitter.split_text(document.raw_text)
        parent_chunks: list[DocumentChunk] = []
        all_child_chunks: list[DocumentChunk] = []

        logger.info(
            f"[PARENT_CHILD] Splitting {document.id} into "
            f"{len(parent_texts)} parent chunks"
        )

        for parent_idx, parent_text in enumerate(parent_texts):
            # Create parent chunk
            parent_id = generate_chunk_id(document.id, f"parent_{parent_idx}", parent_text)

            parent_chunk = DocumentChunk(
                id=parent_id,
                content=parent_text,
                document_id=document.id,
                chunk_index=parent_idx,
                metadata={
                    "source": document.source_path,
                    "title": document.metadata.title,
                    "chunk_type": "parent",
                    "child_ids": [],  # Will be populated
                    "char_count": len(parent_text),
                },
            )
            parent_chunks.append(parent_chunk)

            # Step 2: Split parent into child chunks
            child_texts = self._child_splitter.split_text(parent_text)
            child_ids = []

            for child_idx, child_text in enumerate(child_texts):
                child_id = generate_chunk_id(document.id, f"child_{parent_idx}_{child_idx}", child_text)

                child_chunk = DocumentChunk(
                    id=child_id,
                    content=child_text,
                    document_id=document.id,
                    chunk_index=child_idx,
                    metadata={
                        "source": document.source_path,
                        "title": document.metadata.title,
                        "chunk_type": "child",
                        "parent_id": parent_id,
                        "parent_index": parent_idx,
                        "char_count": len(child_text),
                    },
                )
                all_child_chunks.append(child_chunk)
                child_ids.append(child_id)

            # Link parent to children
            parent_chunk.metadata["child_ids"] = child_ids
            parent_chunk.metadata["child_count"] = len(child_ids)

        logger.info(
            f"[PARENT_CHILD] Created {len(parent_chunks)} parent chunks, "
            f"{len(all_child_chunks)} child chunks"
        )

        return parent_chunks, all_child_chunks

    def split_to_parents_only(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """
        Split document into parent chunks only (no children).

        Useful for baseline comparison or when parent-child is disabled.

        Args:
            document: Processed document to split

        Returns:
            List of parent chunks
        """
        parents, _ = self.split(document)
        return parents

    def split_to_children_only(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """
        Split document into child chunks only (no parent metadata).

        Useful for baseline comparison.

        Args:
            document: Processed document to split

        Returns:
            List of child chunks without parent links
        """
        _, children = self.split(document)

        # Remove parent metadata from children
        clean_children = []
        for child in children:
            clean_child = child.model_copy(
                update={
                    "metadata": {
                        k: v for k, v in child.metadata.items()
                        if k not in ("parent_id", "parent_index")
                    }
                }
            )
            clean_children.append(clean_child)

        return clean_children

    def get_stats(self, parents: list[DocumentChunk], children: list[DocumentChunk]) -> dict:
        """
        Get statistics about the split results.

        Args:
            parents: Parent chunks
            children: Child chunks

        Returns:
            Statistics dictionary
        """
        if not parents:
            return {
                "parent_count": 0,
                "child_count": 0,
                "avg_parent_size": 0,
                "avg_child_size": 0,
                "avg_children_per_parent": 0,
            }

        parent_sizes = [len(p.content) for p in parents]
        child_sizes = [len(c.content) for c in children]
        children_per_parent = [p.metadata.get("child_count", 0) for p in parents]

        return {
            "parent_count": len(parents),
            "child_count": len(children),
            "avg_parent_size": sum(parent_sizes) / len(parent_sizes) if parent_sizes else 0,
            "avg_child_size": sum(child_sizes) / len(child_sizes) if child_sizes else 0,
            "avg_children_per_parent": sum(children_per_parent) / len(children_per_parent) if children_per_parent else 0,
            "min_children_per_parent": min(children_per_parent) if children_per_parent else 0,
            "max_children_per_parent": max(children_per_parent) if children_per_parent else 0,
        }
