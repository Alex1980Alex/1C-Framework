"""Qdrant Vector Store Provider (Phase 23.1).

Production-ready vector store using Qdrant (async client).
More stable than ChromaDB, better for production deployments.

Author: Claude Code
Version: 3.0.0 - Async client (fixes event loop blocking)
"""

import logging
import uuid
from typing import Any

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)

# Namespace UUID for deterministic string→UUID conversion
_QDRANT_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Standard fields stored directly in DocumentChunk (not in metadata)
_STANDARD_PAYLOAD_FIELDS = {"content", "document_id", "page_number", "section", "chunk_index", "original_id"}


def _to_qdrant_id(string_id: str) -> str:
    """Convert any string ID to a valid Qdrant UUID string.

    If string_id is already a valid UUID, return it as-is.
    Otherwise, generate a deterministic UUID5 from it.
    """
    try:
        uuid.UUID(string_id)
        return string_id
    except ValueError:
        return str(uuid.uuid5(_QDRANT_NS, string_id))

# Max batch size for Qdrant upsert (avoid too-large requests)
_UPSERT_BATCH_SIZE = 256


class QdrantVectorStore(BaseVectorStore):
    """Qdrant-based vector store for production (async).

    Benefits over ChromaDB:
    - No HNSW index corruption
    - Better memory management
    - Horizontal scaling
    - Non-blocking async I/O
    """

    def __init__(self, settings: VectorStoreSettings):
        self._settings = settings
        self._client = None
        self._collection_name = settings.collection_name
        self._initialized = False
        self._has_sparse = False

    async def initialize(self) -> None:
        """Initialize async Qdrant connection and create collection if needed."""
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams, SparseVectorParams, Modifier

            api_key = self._settings.qdrant_api_key or None
            self._client = AsyncQdrantClient(
                url=self._settings.qdrant_url,
                api_key=api_key if api_key else None,
            )

            # Check if collection exists, create if not
            collections = await self._client.get_collections()
            collection_names = [c.name for c in collections.collections]

            bm25_enabled = getattr(self._settings, "qdrant_bm25_enabled", False)

            if self._collection_name not in collection_names:
                logger.info(f"[QDRANT] Creating collection: {self._collection_name} (dims={self._settings.dimensions}, bm25={bm25_enabled})")

                create_kwargs = {
                    "collection_name": self._collection_name,
                    "vectors_config": {
                        "dense": VectorParams(
                            size=self._settings.dimensions,
                            distance=Distance.COSINE,
                        ),
                    },
                }
                if bm25_enabled:
                    create_kwargs["sparse_vectors_config"] = {
                        "bm25": SparseVectorParams(modifier=Modifier.IDF),
                    }

                await self._client.create_collection(**create_kwargs)
            else:
                # Verify dimensions match
                info = await self._client.get_collection(self._collection_name)
                vectors_config = info.config.params.vectors

                # Handle both named and unnamed vector configs
                if isinstance(vectors_config, dict):
                    # Named vectors: {"dense": VectorParams(...)}
                    dense_config = vectors_config.get("dense")
                    existing_size = dense_config.size if dense_config else None
                else:
                    # Single unnamed vector (legacy collection)
                    existing_size = vectors_config.size

                if existing_size and existing_size != self._settings.dimensions:
                    logger.warning(
                        f"[QDRANT] Collection dimension mismatch: "
                        f"existing={existing_size}, config={self._settings.dimensions}. "
                        f"Delete collection and re-index to fix."
                    )

                # Check for sparse vectors support
                sparse_config = info.config.params.sparse_vectors
                self._has_sparse = bool(sparse_config and "bm25" in (sparse_config if isinstance(sparse_config, dict) else {}))
                if bm25_enabled and not self._has_sparse:
                    logger.warning(
                        "[QDRANT] Collection exists without sparse BM25 vectors. "
                        "Clear and re-index to enable native BM25, or use bm25_backend='fts5'."
                    )

            self._initialized = True
            info = await self._client.get_collection(self._collection_name)
            count = info.points_count

            # Determine sparse support after init
            sparse_config = info.config.params.sparse_vectors
            self._has_sparse = bool(sparse_config and "bm25" in (sparse_config if isinstance(sparse_config, dict) else {}))

            status = f"{count} points"
            if self._has_sparse:
                status += ", BM25 sparse enabled"
            logger.info(f"[QDRANT] Initialized: {self._collection_name} ({status})")

        except ImportError:
            raise ImportError(
                "qdrant-client is not installed. "
                "Install it with: pip install qdrant-client"
            )

    async def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        """Add document chunks with embeddings in batches.

        If the collection has sparse BM25 vectors, each point includes
        both a dense embedding and a BM25 Document for server-side tokenization.
        """
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import PointStruct

        # Prepare BM25 config if sparse vectors are enabled
        bm25_doc_fn = None
        if self._has_sparse:
            from qdrant_client.models import Document as QdrantDocument, Bm25Config
            lang = getattr(self._settings, "qdrant_bm25_language", "russian")
            bm25_k = getattr(self._settings, "qdrant_bm25_k", 1.2)
            bm25_b = getattr(self._settings, "qdrant_bm25_b", 0.75)
            bm25_opts = Bm25Config(language=lang, k=bm25_k, b=bm25_b)

            def bm25_doc_fn(text: str) -> QdrantDocument:
                return QdrantDocument(text=text, model="Qdrant/bm25", options=bm25_opts)

        ids = []
        total = len(chunks)

        for batch_start in range(0, total, _UPSERT_BATCH_SIZE):
            batch_end = min(batch_start + _UPSERT_BATCH_SIZE, total)
            points = []

            for i in range(batch_start, batch_end):
                chunk = chunks[i]
                embedding = embeddings[i]
                ids.append(chunk.id)

                qdrant_id = _to_qdrant_id(chunk.id)
                payload = {
                    "original_id": chunk.id,
                    "content": chunk.content,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number or 0,
                    "section": chunk.section,
                    "chunk_index": chunk.chunk_index,
                }
                # Add extra metadata (source, version, etc.)
                for k, v in chunk.metadata.items():
                    if k not in _STANDARD_PAYLOAD_FIELDS:
                        payload[k] = v

                # Build vector dict: always include dense; add BM25 if supported
                vector: dict | list = {"dense": embedding}
                if bm25_doc_fn is not None:
                    vector["bm25"] = bm25_doc_fn(chunk.content)

                points.append(PointStruct(id=qdrant_id, vector=vector, payload=payload))

            await self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )

            if total > _UPSERT_BATCH_SIZE:
                logger.info(f"[QDRANT] Upserted batch {batch_start}-{batch_end} / {total}")

        bm25_note = " (with BM25 sparse)" if self._has_sparse else ""
        logger.info(f"[QDRANT] Added {total} points{bm25_note}")
        return ids

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform similarity search."""
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Build filter if provided
        search_filter = None
        if filter:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filter.items()
            ]
            search_filter = Filter(must=conditions)

        # Use named vector "dense" if collection has named config
        using = "dense" if self._has_sparse else None

        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            using=using,
            limit=k,
            query_filter=search_filter,
            with_payload=True,
        )
        results = result.points

        return [self._point_to_search_result(r) for r in results]

    async def search_mmr(
        self,
        query_embedding: list[float],
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Maximal Marginal Relevance search using Qdrant with_vectors."""
        if not self._initialized:
            await self.initialize()

        import numpy as np
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        search_filter = None
        if filter:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filter.items()
            ]
            search_filter = Filter(must=conditions)

        # Fetch more candidates with their vectors
        using = "dense" if self._has_sparse else None
        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            using=using,
            limit=fetch_k,
            query_filter=search_filter,
            with_payload=True,
            with_vectors=True,
        )
        results = result.points

        if len(results) <= k:
            return [self._point_to_search_result(r) for r in results]

        # MMR selection — handle named vectors (dict) and plain vectors (list)
        query_arr = np.array(query_embedding)

        def _get_dense_vec(r: Any) -> list[float]:
            v = r.vector
            if isinstance(v, dict):
                return v.get("dense", v)
            return v

        candidate_vecs = np.array([_get_dense_vec(r) for r in results])

        # Normalize
        query_norm = query_arr / (np.linalg.norm(query_arr) + 1e-10)
        cand_norms = candidate_vecs / (np.linalg.norm(candidate_vecs, axis=1, keepdims=True) + 1e-10)
        query_sim = cand_norms @ query_norm

        selected_indices: list[int] = []
        remaining = list(range(len(results)))

        for _ in range(min(k, len(results))):
            if not remaining:
                break

            if not selected_indices:
                best = max(remaining, key=lambda i: query_sim[i])
            else:
                best_score = -float("inf")
                best = remaining[0]
                selected_embeddings = cand_norms[selected_indices]
                for i in remaining:
                    max_sim_to_selected = float(np.max(cand_norms[i] @ selected_embeddings.T))
                    mmr_score = lambda_mult * query_sim[i] - (1 - lambda_mult) * max_sim_to_selected
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best = i

            selected_indices.append(best)
            remaining.remove(best)

        return [self._point_to_search_result(results[i]) for i in selected_indices]

    def _point_to_search_result(self, point: Any) -> SearchResult:
        """Convert a Qdrant ScoredPoint to SearchResult."""
        payload = point.payload or {}

        # Use original_id if available, otherwise the Qdrant UUID
        original_id = payload.get("original_id", str(point.id))

        # Parse page_number
        page_num_raw = payload.get("page_number", 0)
        page_number = int(page_num_raw) if page_num_raw and page_num_raw != 0 else None

        # Extra metadata = all payload fields minus standard ones
        metadata = {k: v for k, v in payload.items() if k not in _STANDARD_PAYLOAD_FIELDS}

        chunk = DocumentChunk(
            id=original_id,
            content=payload.get("content", ""),
            document_id=payload.get("document_id", ""),
            page_number=page_number,
            section=payload.get("section", ""),
            chunk_index=payload.get("chunk_index", 0),
            metadata=metadata,
        )

        return SearchResult(chunk=chunk, score=point.score, source="qdrant")

    async def delete(self, ids: list[str]) -> None:
        """Delete documents by IDs (converts to Qdrant UUIDs)."""
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import PointIdsList

        qdrant_ids = [_to_qdrant_id(i) for i in ids]
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=qdrant_ids),
        )
        logger.info(f"[QDRANT] Deleted {len(ids)} points")

    async def get_by_ids(self, ids: list[str]) -> list[DocumentChunk]:
        """Retrieve documents by IDs (converts to Qdrant UUIDs)."""
        if not self._initialized:
            await self.initialize()

        qdrant_ids = [_to_qdrant_id(i) for i in ids]
        results = await self._client.retrieve(
            collection_name=self._collection_name,
            ids=qdrant_ids,
            with_payload=True,
        )

        chunks = []
        for result in results:
            payload = result.payload or {}
            original_id = payload.get("original_id", str(result.id))
            page_num_raw = payload.get("page_number", 0)
            page_number = int(page_num_raw) if page_num_raw and page_num_raw != 0 else None

            metadata = {k: v for k, v in payload.items() if k not in _STANDARD_PAYLOAD_FIELDS}

            chunks.append(DocumentChunk(
                id=original_id,
                content=payload.get("content", ""),
                document_id=payload.get("document_id", ""),
                page_number=page_number,
                section=payload.get("section", ""),
                chunk_index=payload.get("chunk_index", 0),
                metadata=metadata,
            ))

        return chunks

    async def count(self) -> int:
        """Return total number of stored documents."""
        if not self._initialized:
            await self.initialize()

        info = await self._client.get_collection(self._collection_name)
        return info.points_count or 0

    async def scroll(
        self,
        filter: dict[str, Any] | None = None,
        limit: int = 10000,
        fields: list[str] | None = None,
    ) -> list[DocumentChunk]:
        """Get chunks by metadata filter using Qdrant scroll (async).

        Args:
            fields: If specified, only these payload fields are returned
                    (much faster for large collections — skips content).
        """
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import Filter, FieldCondition, MatchValue, PayloadSelectorInclude

        scroll_filter = None
        if filter:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filter.items()
            ]
            scroll_filter = Filter(must=conditions)

        # Selective payload: only load requested fields (huge perf gain)
        with_payload: Any = True
        if fields:
            with_payload = PayloadSelectorInclude(include=fields)

        all_chunks: list[DocumentChunk] = []
        offset = None

        while len(all_chunks) < limit:
            batch_size = min(256, limit - len(all_chunks))
            results, next_offset = await self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=scroll_filter,
                limit=batch_size,
                offset=offset,
                with_payload=with_payload,
                with_vectors=False,
            )

            for point in results:
                payload = point.payload or {}
                original_id = payload.get("original_id", str(point.id))
                page_num_raw = payload.get("page_number", 0)
                page_number = int(page_num_raw) if page_num_raw and page_num_raw != 0 else None
                metadata = {k: v for k, v in payload.items() if k not in _STANDARD_PAYLOAD_FIELDS}

                all_chunks.append(DocumentChunk(
                    id=original_id,
                    content=payload.get("content", ""),
                    document_id=payload.get("document_id", ""),
                    page_number=page_number,
                    section=payload.get("section", ""),
                    chunk_index=payload.get("chunk_index", 0),
                    metadata=metadata,
                ))

            if next_offset is None or not results:
                break
            offset = next_offset

        return all_chunks

    async def delete_by_filter(self, filter: dict[str, Any]) -> int:
        """Delete all chunks matching a metadata filter."""
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        if not filter:
            return 0

        # Count before delete
        conditions = [
            FieldCondition(key=key, match=MatchValue(value=value))
            for key, value in filter.items()
        ]
        qdrant_filter = Filter(must=conditions)

        count_result = await self._client.count(
            collection_name=self._collection_name,
            count_filter=qdrant_filter,
            exact=True,
        )
        count = count_result.count

        if count > 0:
            from qdrant_client.models import FilterSelector
            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=FilterSelector(filter=qdrant_filter),
            )
            logger.info(f"[QDRANT] Deleted {count} points by filter {filter}")

        return count

    async def clear(self) -> None:
        """Remove all documents and recreate collection (with sparse BM25 if enabled)."""
        if not self._initialized:
            await self.initialize()

        from qdrant_client.models import Distance, VectorParams, SparseVectorParams, Modifier

        bm25_enabled = getattr(self._settings, "qdrant_bm25_enabled", False)

        await self._client.delete_collection(self._collection_name)

        create_kwargs = {
            "collection_name": self._collection_name,
            "vectors_config": {
                "dense": VectorParams(
                    size=self._settings.dimensions,
                    distance=Distance.COSINE,
                ),
            },
        }
        if bm25_enabled:
            create_kwargs["sparse_vectors_config"] = {
                "bm25": SparseVectorParams(modifier=Modifier.IDF),
            }

        await self._client.create_collection(**create_kwargs)
        self._has_sparse = bm25_enabled
        logger.info(f"[QDRANT] Cleared and recreated collection (bm25={bm25_enabled})")

    # ------------------------------------------------------------------
    # Native BM25 hybrid search (dense + sparse with server-side RRF)
    # ------------------------------------------------------------------

    def supports_native_bm25(self) -> bool:
        """Whether this store has sparse BM25 vectors configured."""
        return getattr(self, "_has_sparse", False)

    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Hybrid dense + BM25 search with server-side RRF fusion.

        Uses Qdrant Prefetch for both dense and sparse queries, then
        merges them via Reciprocal Rank Fusion on the server side.
        """
        if not self._initialized:
            await self.initialize()

        if not self._has_sparse:
            logger.warning("[QDRANT] hybrid_search called but no sparse vectors — falling back to dense")
            return await self.search(query_embedding, k, filter)

        from qdrant_client.models import (
            Filter, FieldCondition, MatchValue,
            Prefetch, FusionQuery, Fusion,
            Document as QdrantDocument, Bm25Config,
        )

        # Build filter
        search_filter = None
        if filter:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filter.items()
            ]
            search_filter = Filter(must=conditions)

        # BM25 config
        lang = getattr(self._settings, "qdrant_bm25_language", "russian")
        bm25_k = getattr(self._settings, "qdrant_bm25_k", 1.2)
        bm25_b = getattr(self._settings, "qdrant_bm25_b", 0.75)
        bm25_opts = Bm25Config(language=lang, k=bm25_k, b=bm25_b)
        bm25_doc = QdrantDocument(text=query_text, model="Qdrant/bm25", options=bm25_opts)

        # Prefetch: dense + sparse, then RRF fusion
        prefetch_limit = k * 3

        result = await self._client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                Prefetch(query=query_embedding, using="dense", limit=prefetch_limit),
                Prefetch(query=bm25_doc, using="bm25", limit=prefetch_limit),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=k,
            query_filter=search_filter,
            with_payload=True,
        )

        return [self._point_to_search_result(r) for r in result.points]

    async def rebuild_sparse_vectors(self, batch_size: int = 256) -> int:
        """Re-upsert all points to add/update BM25 sparse vectors.

        Scrolls through all points (with dense vectors + payload), then
        re-upserts them with both dense and BM25 sparse vectors.
        Idempotent — safe to run multiple times.

        Returns:
            Number of points updated.
        """
        if not self._initialized:
            await self.initialize()

        if not self._has_sparse:
            raise RuntimeError(
                "Collection has no sparse BM25 vectors configured. "
                "Clear and re-create collection with qdrant_bm25_enabled=true first."
            )

        from qdrant_client.models import PointStruct, Document as QdrantDocument, Bm25Config

        lang = getattr(self._settings, "qdrant_bm25_language", "russian")
        bm25_k = getattr(self._settings, "qdrant_bm25_k", 1.2)
        bm25_b = getattr(self._settings, "qdrant_bm25_b", 0.75)
        bm25_opts = Bm25Config(language=lang, k=bm25_k, b=bm25_b)

        updated = 0
        offset = None

        while True:
            results, next_offset = await self._client.scroll(
                collection_name=self._collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            if not results:
                break

            points = []
            for point in results:
                payload = point.payload or {}
                content = payload.get("content", "")

                # Get dense vector (handle named dict or flat list)
                vec = point.vector
                dense_vec = vec.get("dense", vec) if isinstance(vec, dict) else vec

                bm25_doc = QdrantDocument(text=content, model="Qdrant/bm25", options=bm25_opts)

                points.append(PointStruct(
                    id=point.id,
                    vector={"dense": dense_vec, "bm25": bm25_doc},
                    payload=payload,
                ))

            await self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )
            updated += len(points)

            if next_offset is None:
                break
            offset = next_offset

            logger.info("[QDRANT] Sparse rebuild: %d points updated...", updated)

        logger.info("[QDRANT] Sparse rebuild complete: %d total points", updated)
        return updated
