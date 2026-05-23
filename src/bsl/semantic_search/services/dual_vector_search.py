"""
Dual Named Vector Search Extension for BSL Hybrid Pipeline — Phase 10

Extends BSLHybridPipeline with support for two named vectors ("content" and "module_path")
using Qdrant's prefetch mechanism and RRF (Reciprocal Rank Fusion) fusion.

Usage:
    from dual_vector_search import DualVectorPipeline, create_dual_vector_collection
    create_dual_vector_collection(qdrant_client, "bsl_code_v4")
    pipeline = DualVectorPipeline(sqlite_db, qdrant_client, embedder, call_graph,
                                  qdrant_collection="bsl_code_v4")
    results = pipeline.search("модуль менеджера справочника Контрагенты", limit=10)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from .hybrid_search import BSLSearchResult

logger = logging.getLogger(__name__)


def create_dual_vector_collection(
    qdrant_client: QdrantClient,
    collection_name: str,
    vector_size: int = 768,
) -> None:
    """Create a Qdrant collection with two named vectors: content and module_path."""
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "content": VectorParams(size=vector_size, distance=Distance.COSINE),
            "module_path": VectorParams(size=vector_size, distance=Distance.COSINE),
        },
    )
    logger.info("Created dual-vector collection: %s (dim=%d)", collection_name, vector_size)


def generate_module_path_embedding(embedder: Any, module_path: str) -> list[float]:
    """Generate an embedding from a module path string.

    E.g. "Документ.РеализацияТоваров.МодульОбъекта" -> [0.12, -0.34, ...]
    """
    if not module_path or not module_path.strip():
        sample = embedder.embed_query("empty")
        return [0.0] * len(sample)
    return embedder.embed_query(module_path)


def migrate_collection(
    qdrant_client: QdrantClient,
    source_collection: str,
    target_collection: str,
    embedder: Any,
    batch_size: int = 100,
) -> dict[str, int]:
    """Migrate points from single-vector to dual-vector collection.

    Reads all points from source, generates module_path embeddings
    from payload["module_path"], and upserts to target with both vectors.

    Returns:
        {"migrated": int, "failed": int}
    """
    stats = {"migrated": 0, "failed": 0}

    info = qdrant_client.get_collection(source_collection)
    total = info.points_count
    logger.info("Migrating %d points: %s -> %s", total, source_collection, target_collection)

    offset = None
    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=source_collection,
            limit=batch_size,
            offset=offset,
            with_vectors=True,
        )
        if not points:
            break

        new_points = []
        for pt in points:
            try:
                module_path = (pt.payload or {}).get("module_path", "")
                content_vec = (
                    pt.vector if isinstance(pt.vector, list) else list(pt.vector.values())[0]
                )
                mp_vec = generate_module_path_embedding(embedder, module_path)

                new_points.append(
                    PointStruct(
                        id=pt.id,
                        vector={"content": content_vec, "module_path": mp_vec},
                        payload=pt.payload,
                    )
                )
            except Exception as e:
                logger.warning("Failed to migrate point %s: %s", pt.id, e)
                stats["failed"] += 1

        if new_points:
            qdrant_client.upsert(collection_name=target_collection, points=new_points)
            stats["migrated"] += len(new_points)
            logger.info("Migrated batch: %d/%d", stats["migrated"], total)

        if next_offset is None:
            break
        offset = next_offset

    logger.info("Migration complete: %s", stats)
    return stats


class DualVectorPipeline:
    """5-stage hybrid search: BM25 + content vector + module_path vector + RRF + call graph."""

    def __init__(
        self,
        sqlite_db: str | Path | None = None,
        qdrant_client: QdrantClient | None = None,
        embedder: Any | None = None,
        call_graph: Any | None = None,
        qdrant_collection: str = "bsl_code_v4",
        rrf_k: int = 60,
        bm25_weight: float = 0.3,
        content_weight: float = 0.5,
        module_path_weight: float = 0.2,
        cg_boost_export: float = 1.2,
        cg_boost_callers: float = 0.05,
        cg_boost_max: float = 1.5,
    ) -> None:
        total = bm25_weight + content_weight + module_path_weight
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")

        self._sqlite_db = Path(sqlite_db) if sqlite_db else None
        self._qdrant = qdrant_client
        self._embedder = embedder
        self._call_graph = call_graph
        self._collection = qdrant_collection
        self._rrf_k = rrf_k
        self._bm25_weight = bm25_weight
        self._content_weight = content_weight
        self._module_path_weight = module_path_weight
        self._cg_boost_export = cg_boost_export
        self._cg_boost_callers = cg_boost_callers
        self._cg_boost_max = cg_boost_max

    def search(self, query: str, limit: int = 10, fetch_k: int = 50) -> list[BSLSearchResult]:
        """Run the full 5-stage hybrid pipeline."""
        bm25_results = self._bm25_search(query, fetch_k)
        content_results, mp_results = self._dual_vector_search(query, fetch_k)

        if not bm25_results and not content_results and not mp_results:
            return []

        fused = self._rrf_fuse_3way(bm25_results, content_results, mp_results)

        if self._call_graph:
            fused = self._apply_call_graph_boost(fused)

        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:limit]

    def _bm25_search(self, query: str, limit: int) -> list[BSLSearchResult]:
        """Stage 1: BM25 via SQLite FTS5."""
        if self._sqlite_db is None or not self._sqlite_db.exists():
            return []
        try:
            import sqlite3

            conn = sqlite3.connect(str(self._sqlite_db))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """SELECT d.id, d.path, d.doc_type, d.content, d.content_preview
                   FROM documents d
                   WHERE d.id IN (SELECT id FROM documents_fts WHERE documents_fts MATCH ?)
                   LIMIT ?""",
                (query, limit),
            )
            rows = cur.fetchall()
            conn.close()

            return [
                BSLSearchResult(
                    chunk_id=str(row["id"]),
                    name=Path(row["path"] or "").stem,
                    module_path=row["path"] or "",
                    content=(row["content_preview"] or row["content"] or "")[:500],
                    score=0.0,
                    source="bm25",
                    metadata={"doc_type": row["doc_type"] or "", "bm25_rank": rank},
                )
                for rank, row in enumerate(rows)
            ]
        except Exception as e:
            logger.warning("BM25 search failed: %s", e)
            return []

    def _dual_vector_search(
        self, query: str, limit: int
    ) -> tuple[list[BSLSearchResult], list[BSLSearchResult]]:
        """Stage 2: Dual vector search — content + module_path via Qdrant prefetch."""
        if self._qdrant is None or self._embedder is None:
            return [], []

        try:
            query_vec = self._embedder.embed_query(query)

            # Two separate searches for proper RRF ranking
            content_resp = self._qdrant.query_points(
                collection_name=self._collection,
                query=query_vec,
                using="content",
                limit=limit,
            )
            mp_resp = self._qdrant.query_points(
                collection_name=self._collection,
                query=query_vec,
                using="module_path",
                limit=limit,
            )

            def _to_results(hits: list, source_tag: str) -> list[BSLSearchResult]:
                results = []
                for rank, hit in enumerate(hits):
                    p = hit.payload or {}
                    results.append(
                        BSLSearchResult(
                            chunk_id=p.get("chunk_id", str(hit.id)),
                            name=p.get("name", ""),
                            module_path=p.get("module_path", ""),
                            content=p.get("content", "")[:500],
                            score=0.0,
                            source=source_tag,
                            metadata={
                                "symbol_type": p.get("symbol_type", ""),
                                "object_type": p.get("object_type", ""),
                                "is_export": p.get("is_export", False),
                                "vector_score": hit.score,
                                "vector_rank": rank,
                            },
                        )
                    )
                return results

            content_hits = content_resp.points if hasattr(content_resp, "points") else []
            mp_hits = mp_resp.points if hasattr(mp_resp, "points") else []

            return _to_results(content_hits, "vector_content"), _to_results(mp_hits, "vector_path")

        except Exception as e:
            logger.warning("Dual vector search failed: %s", e)
            return [], []

    def _rrf_fuse_3way(
        self,
        bm25: list[BSLSearchResult],
        content: list[BSLSearchResult],
        module_path: list[BSLSearchResult],
    ) -> list[BSLSearchResult]:
        """Stage 3: 3-way RRF fusion with weighted contributions."""
        k = self._rrf_k
        scores: dict[str, float] = {}
        result_map: dict[str, BSLSearchResult] = {}

        for rank, r in enumerate(bm25):
            rrf = self._bm25_weight / (k + rank + 1)
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + rrf
            result_map.setdefault(r.chunk_id, r)

        for rank, r in enumerate(content):
            rrf = self._content_weight / (k + rank + 1)
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + rrf
            if r.chunk_id in result_map:
                result_map[r.chunk_id].metadata.update(r.metadata)
                result_map[r.chunk_id].source = "hybrid"
            else:
                result_map[r.chunk_id] = r

        for rank, r in enumerate(module_path):
            rrf = self._module_path_weight / (k + rank + 1)
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + rrf
            if r.chunk_id in result_map:
                result_map[r.chunk_id].metadata["module_path_rank"] = rank
                result_map[r.chunk_id].source = "hybrid"
            else:
                result_map[r.chunk_id] = r

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
            if r.metadata.get("is_export", False):
                boost *= self._cg_boost_export
            if r.name:
                try:
                    callers = store.callers_of(r.name)
                    if len(callers) > 0:
                        boost += min(
                            len(callers) * self._cg_boost_callers, self._cg_boost_max - 1.0
                        )
                        r.metadata["caller_count"] = len(callers)
                except Exception:
                    pass
            r.score *= min(boost, self._cg_boost_max)

        return results
