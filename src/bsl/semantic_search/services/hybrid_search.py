"""
BSL Hybrid Search Pipeline — Phase 65

4-stage pipeline optimized for BSL code search:
1. BM25 top-N via SQLite FTS5 (~5ms)
2. Vector top-N via Qdrant (~50ms)
3. RRF fusion of BM25 + Vector results
4. Call Graph boost (exported symbols, caller count)

Usage:
    pipeline = BSLHybridPipeline(sqlite_db, qdrant_client, embedder, call_graph)
    results = pipeline.search("query", limit=10)
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BSLSearchResult:
    """A single search result from the hybrid pipeline."""

    chunk_id: str
    name: str
    module_path: str
    content: str
    score: float
    source: str  # "bm25", "vector", "hybrid"
    metadata: dict[str, Any] = field(default_factory=dict)


class BSLHybridPipeline:
    """4-stage hybrid search for BSL code."""

    def __init__(
        self,
        sqlite_db: str | Path | None = None,
        qdrant_client: Any | None = None,
        embedder: Any | None = None,
        call_graph: Any | None = None,
        qdrant_collection: str = "bsl_code_v3",
        rrf_k: int = 60,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        cg_boost_export: float = 1.2,
        cg_boost_callers: float = 0.05,
        cg_boost_max: float = 1.5,
    ) -> None:
        self._sqlite_db = Path(sqlite_db) if sqlite_db else None
        self._qdrant = qdrant_client
        self._embedder = embedder
        self._call_graph = call_graph
        self._collection = qdrant_collection
        self._rrf_k = rrf_k
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight
        self._cg_boost_export = cg_boost_export
        self._cg_boost_callers = cg_boost_callers
        self._cg_boost_max = cg_boost_max

    def search(
        self,
        query: str,
        limit: int = 10,
        fetch_k: int = 50,
    ) -> list[BSLSearchResult]:
        """Run the full hybrid pipeline."""
        bm25_results = self._bm25_search(query, fetch_k)
        vector_results = self._vector_search(query, fetch_k)

        if not bm25_results and not vector_results:
            return []

        # RRF fusion
        fused = self._rrf_fuse(bm25_results, vector_results)

        # Call graph boost
        if self._call_graph:
            fused = self._apply_call_graph_boost(fused)

        # Sort by score descending, take top limit
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:limit]

    def _bm25_search(self, query: str, limit: int) -> list[BSLSearchResult]:
        """Stage 1: BM25 via SQLite FTS5."""
        if self._sqlite_db is None or not self._sqlite_db.exists():
            return []

        try:
            conn = sqlite3.connect(str(self._sqlite_db))
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                cur.execute(
                    """SELECT d.id, d.path, d.doc_type, d.content, d.content_preview
                       FROM documents d
                       WHERE d.id IN (
                           SELECT id FROM documents_fts WHERE documents_fts MATCH ?
                       )
                       LIMIT ?""",
                    (query, limit),
                )
                rows = cur.fetchall()
            finally:
                conn.close()

            results = []
            for rank, row in enumerate(rows):
                results.append(BSLSearchResult(
                    chunk_id=str(row["id"]),
                    name=Path(row["path"] or "").stem if row["path"] else str(row["id"]),
                    module_path=row["path"] or "",
                    content=(row["content_preview"] or row["content"] or "")[:500],
                    score=0.0,  # filled by RRF
                    source="bm25",
                    metadata={"doc_type": row["doc_type"] or "", "bm25_rank": rank},
                ))
            return results

        except Exception as e:
            logger.warning("BM25 search failed: %s", e)
            return []

    def _vector_search(self, query: str, limit: int) -> list[BSLSearchResult]:
        """Stage 2: Vector search via Qdrant."""
        if self._qdrant is None or self._embedder is None:
            return []

        try:
            embedding = self._embedder.embed_query(query)
            if embedding is None:
                return []

            response = self._qdrant.query_points(
                collection_name=self._collection,
                query=embedding,
                limit=limit,
            )
            hits = response.points if hasattr(response, "points") else []

            results = []
            for rank, hit in enumerate(hits):
                p = hit.payload or {}
                results.append(BSLSearchResult(
                    chunk_id=p.get("chunk_id", str(hit.id)),
                    name=p.get("name", ""),
                    module_path=p.get("module_path", ""),
                    content=p.get("content", "")[:500],
                    score=0.0,  # filled by RRF
                    source="vector",
                    metadata={
                        "symbol_type": p.get("symbol_type", ""),
                        "object_type": p.get("object_type", ""),
                        "object_name": p.get("object_name", ""),
                        "is_export": p.get("is_export", False),
                        "vector_score": hit.score,
                        "vector_rank": rank,
                    },
                ))
            return results

        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []

    def _rrf_fuse(
        self,
        bm25: list[BSLSearchResult],
        vector: list[BSLSearchResult],
    ) -> list[BSLSearchResult]:
        """Stage 3: Reciprocal Rank Fusion."""
        k = self._rrf_k
        scores: dict[str, float] = {}
        result_map: dict[str, BSLSearchResult] = {}

        # BM25 contribution
        for rank, r in enumerate(bm25):
            key = r.module_path or r.chunk_id
            rrf_score = self._bm25_weight / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score
            if key not in result_map:
                result_map[key] = r

        # Vector contribution
        for rank, r in enumerate(vector):
            key = r.module_path or r.chunk_id
            rrf_score = self._vector_weight / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score
            if key not in result_map:
                result_map[key] = r
            else:
                # Merge metadata from vector into existing
                result_map[key].metadata.update(r.metadata)
                result_map[key].source = "hybrid"

        # Apply scores
        for key, result in result_map.items():
            result.score = scores.get(key, 0.0)

        return list(result_map.values())

    def _apply_call_graph_boost(self, results: list[BSLSearchResult]) -> list[BSLSearchResult]:
        """Stage 4: Boost scores based on call graph importance."""
        store = self._call_graph
        if store is None:
            return results

        for r in results:
            boost = 1.0
            name = r.name

            # Export boost
            if r.metadata.get("is_export", False):
                boost *= self._cg_boost_export

            # Caller count boost
            if name:
                try:
                    callers = store.callers_of(name)
                    caller_count = len(callers)
                    if caller_count > 0:
                        boost += min(
                            caller_count * self._cg_boost_callers,
                            self._cg_boost_max - 1.0,
                        )
                        r.metadata["caller_count"] = caller_count
                except Exception as e:
                    logger.debug("Call graph lookup failed for %s: %s", name, e)

            boost = min(boost, self._cg_boost_max)
            r.score *= boost

        return results
