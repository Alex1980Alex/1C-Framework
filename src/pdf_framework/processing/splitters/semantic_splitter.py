"""Semantic text splitter using embedding similarity between sentences.

Phase 2.2: Splits documents at semantic boundaries where topic shifts occur,
producing more coherent chunks than fixed-size splitting.

Algorithm (breakpoint-based):
1. Split text into sentences
2. Compute embeddings for each sentence
3. Compute cosine similarity between consecutive sentences
4. Identify breakpoints where similarity drops below threshold
5. Group sentences between breakpoints into chunks
6. Enforce min/max chunk size constraints
"""

import re
import uuid

import numpy as np
from sentence_transformers import SentenceTransformer

from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex.

    Handles Russian and English text, abbreviations, and numbered lists.
    """
    # Split on sentence-ending punctuation followed by whitespace and uppercase,
    # or on double newlines (paragraph breaks).
    raw = re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])|(?:\n\s*\n)", text)
    sentences = [s.strip() for s in raw if s and s.strip()]
    return sentences


class SemanticTextSplitter:
    """Split documents at semantic boundaries using sentence embeddings.

    Produces chunks where topic shifts are detected by measuring
    cosine similarity between consecutive sentence groups.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        semantic_threshold: float = 0.75,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1500,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._semantic_threshold = semantic_threshold
        self._min_chunk_size = min_chunk_size
        self._max_chunk_size = max_chunk_size
        self._model = SentenceTransformer(embedding_model)

    def split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """Split a processed document into semantically coherent chunks.

        Args:
            document: ProcessedDocument with raw_text populated.

        Returns:
            List of DocumentChunk with sequential chunk_index.
        """
        if not document.raw_text or not document.raw_text.strip():
            return []

        sentences = _split_sentences(document.raw_text)
        if not sentences:
            return []

        # For very short documents, return as single chunk
        if len(sentences) <= 2:
            return self._make_chunks(
                [" ".join(sentences)], document,
            )

        # Compute sentence embeddings
        embeddings = self._model.encode(sentences, show_progress_bar=False)

        # Compute cosine similarity between consecutive sentences
        similarities = self._compute_consecutive_similarities(embeddings)

        # Find semantic breakpoints
        breakpoints = self._find_breakpoints(similarities)

        # Group sentences into chunks at breakpoints
        raw_chunks = self._group_sentences(sentences, breakpoints)

        # Enforce size constraints
        sized_chunks = self._enforce_size_constraints(raw_chunks)

        return self._make_chunks(sized_chunks, document)

    def _compute_consecutive_similarities(
        self, embeddings: np.ndarray,
    ) -> list[float]:
        """Compute cosine similarity between each pair of consecutive sentences."""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-10, norms)
        normalized = embeddings / norms

        similarities: list[float] = []
        for i in range(len(normalized) - 1):
            sim = float(np.dot(normalized[i], normalized[i + 1]))
            similarities.append(sim)
        return similarities

    def _find_breakpoints(self, similarities: list[float]) -> list[int]:
        """Find indices where semantic similarity drops below threshold.

        Uses adaptive threshold: if no breaks found with the configured
        threshold, falls back to percentile-based splitting.
        """
        breakpoints: list[int] = []
        for i, sim in enumerate(similarities):
            if sim < self._semantic_threshold:
                breakpoints.append(i + 1)  # Break AFTER sentence i

        # If no breakpoints found, use percentile-based approach
        if not breakpoints and len(similarities) > 3:
            arr = np.array(similarities)
            threshold = float(np.percentile(arr, 25))
            for i, sim in enumerate(similarities):
                if sim <= threshold:
                    breakpoints.append(i + 1)

        return breakpoints

    def _group_sentences(
        self, sentences: list[str], breakpoints: list[int],
    ) -> list[str]:
        """Group sentences into chunks split at breakpoints."""
        if not breakpoints:
            return [" ".join(sentences)]

        chunks: list[str] = []
        start = 0
        for bp in breakpoints:
            chunk_text = " ".join(sentences[start:bp])
            if chunk_text.strip():
                chunks.append(chunk_text)
            start = bp

        # Last segment
        if start < len(sentences):
            chunk_text = " ".join(sentences[start:])
            if chunk_text.strip():
                chunks.append(chunk_text)

        return chunks

    def _enforce_size_constraints(self, chunks: list[str]) -> list[str]:
        """Merge too-small chunks and split too-large ones."""
        result: list[str] = []

        for chunk in chunks:
            if len(chunk) < self._min_chunk_size and result:
                # Merge with previous chunk
                result[-1] = result[-1] + " " + chunk
            else:
                result.append(chunk)

        # Split chunks that are too large
        final: list[str] = []
        for chunk in result:
            if len(chunk) > self._max_chunk_size:
                final.extend(self._split_large_chunk(chunk))
            else:
                final.append(chunk)

        return final

    def _split_large_chunk(self, text: str) -> list[str]:
        """Split an oversized chunk into smaller pieces at sentence boundaries."""
        sentences = _split_sentences(text)
        pieces: list[str] = []
        current: list[str] = []
        current_len = 0

        for sent in sentences:
            if current_len + len(sent) > self._max_chunk_size and current:
                pieces.append(" ".join(current))
                current = [sent]
                current_len = len(sent)
            else:
                current.append(sent)
                current_len += len(sent) + 1  # +1 for space

        if current:
            pieces.append(" ".join(current))

        return pieces

    def _make_chunks(
        self,
        texts: list[str],
        document: ProcessedDocument,
    ) -> list[DocumentChunk]:
        """Create DocumentChunk objects from text segments."""
        chunks: list[DocumentChunk] = []
        for i, text in enumerate(texts):
            chunk_id = f"{document.id}_chunk_{uuid.uuid4().hex[:8]}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    content=text,
                    document_id=document.id,
                    chunk_index=i,
                    metadata={
                        "source": document.source_path,
                        "title": document.metadata.title,
                        "splitter": "semantic",
                    },
                )
            )
        return chunks
