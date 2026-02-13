"""BM25 lexical search strategy using SQLite FTS5.

Author: Claude Code
Version: 0.8.0 - Phase 27: Multi-column FTS5 + Two-Pass RRF support
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.search.bm25_store import BM25Store
from src.pdf_framework.vector_store.base import BaseVectorStore


class BM25SearchStrategy:
    """Lexical search via SQLite FTS5 BM25 ranking.

    Queries the BM25 index for matching chunk_ids, then fetches
    full DocumentChunk objects from the BM25 store or vector store.
    Supports two-pass title/body RRF search for improved section recall.
    """

    def __init__(
        self,
        bm25_store: BM25Store,
        vector_store: BaseVectorStore,
        use_two_pass: bool = False,
    ):
        self._bm25 = bm25_store
        self._vector_store = vector_store
        self._use_two_pass = use_two_pass

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        start = time.perf_counter()

        if self._use_two_pass:
            # Two-pass: title-only + body-only merged via RRF
            # Returns already-normalized scores (0-1, higher=better)
            raw_hits = await self._bm25.search_two_pass(query, k=k * 2)
            logger.info("[BM25] Two-pass query=%r, raw_hits=%d", query, len(raw_hits))

            if not raw_hits:
                elapsed = (time.perf_counter() - start) * 1000
                return SearchResponse(
                    query=query, results=[], total_found=0,
                    search_type="bm25", elapsed_ms=elapsed,
                )

            normalized = {cid: score for cid, score in raw_hits}
        else:
            # Standard search with column weights (title=10x, body=1x)
            raw_hits = await self._bm25.search(query, k=k * 2)
            logger.info("[BM25] Query=%r, raw_hits=%d", query, len(raw_hits))

            if not raw_hits:
                elapsed = (time.perf_counter() - start) * 1000
                return SearchResponse(
                    query=query, results=[], total_found=0,
                    search_type="bm25", elapsed_ms=elapsed,
                )

            # Normalize BM25 scores to 0-1 range
            # FTS5 bm25() is negative (lower = better). We negate and normalize.
            raw_scores = {cid: -score for cid, score in raw_hits}
            max_score = max(raw_scores.values()) if raw_scores else 1.0
            if max_score == 0:
                max_score = 1.0
            normalized = {cid: s / max_score for cid, s in raw_scores.items()}

        # Fetch full chunks
        chunk_ids = list(normalized.keys())
        chunks_by_id = await self._fetch_chunks(chunk_ids)

        results: list[SearchResult] = []
        for cid in chunk_ids:
            chunk = chunks_by_id.get(cid)
            if chunk is None:
                continue
            # Apply metadata filter if requested
            if filter and not self._matches_filter(chunk, filter):
                continue
            results.append(
                SearchResult(
                    chunk=chunk,
                    score=normalized[cid],
                    source="bm25",
                )
            )
            if len(results) >= k:
                break

        elapsed = (time.perf_counter() - start) * 1000
        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            search_type="bm25",
            elapsed_ms=elapsed,
        )

    async def _fetch_chunks(self, chunk_ids: list[str]) -> dict[str, DocumentChunk]:
        """Fetch DocumentChunk objects by their IDs.

        Primary source: BM25 store's chunk_meta (original_content + section_title).
        Fallback: vector store's get_by_ids() for Qdrant/ChromaDB.
        """
        chunks: dict[str, DocumentChunk] = {}

        # Try BM25 store first (has original_content, no sync issues)
        try:
            meta_rows = await self._bm25.get_chunks_by_ids(chunk_ids)
            for row in meta_rows:
                if row["original_content"]:
                    chunks[row["chunk_id"]] = DocumentChunk(
                        id=row["chunk_id"],
                        content=row["original_content"],
                        document_id=row["document_id"],
                        section=row.get("section_title", ""),
                        metadata={
                            "source": row["source"],
                            "section_title": row.get("section_title", ""),
                        },
                    )
        except Exception as e:
            logger.warning("[BM25] Failed to fetch from chunk_meta: %s", e)

        # Fallback: fetch missing chunks from vector store
        missing_ids = [cid for cid in chunk_ids if cid not in chunks]
        if missing_ids:
            try:
                vs_chunks = await self._vector_store.get_by_ids(missing_ids)
                for chunk in vs_chunks:
                    chunks[chunk.id] = chunk
            except Exception as e:
                logger.warning("[BM25] Fallback fetch from vector store failed: %s", e)

        logger.info(
            "[BM25] Fetched %d/%d chunks (bm25_meta=%d, vector_store=%d)",
            len(chunks), len(chunk_ids),
            len(chunks) - len([c for c in missing_ids if c in chunks]),
            len([c for c in missing_ids if c in chunks]),
        )
        return chunks

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        """Convert value to int, handling ChromaDB 'None' strings."""
        if val is None or val == "None" or val == "":
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _matches_filter(chunk: DocumentChunk, filter: dict[str, Any]) -> bool:
        """Check if a chunk's metadata matches the given filter."""
        for key, value in filter.items():
            meta_val = chunk.metadata.get(key)
            if meta_val != value:
                return False
        return True
