"""ChromaDB vector store provider.

Implements BaseVectorStore using ChromaDB for persistence and similarity search.
Supports cosine, euclidean, and dot-product distance metrics plus MMR.
"""

from typing import Any

import chromadb
import numpy as np

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult
from src.pdf_framework.vector_store.base import BaseVectorStore

_DISTANCE_MAP = {
    "cosine": "cosine",
    "euclidean": "l2",
    "dot": "ip",
}


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB-backed vector store with MMR support."""

    def __init__(self, settings: VectorStoreSettings | None = None):
        self._settings = settings or VectorStoreSettings()
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("Vector store not initialized. Call initialize() first.")
        return self._collection

    async def initialize(self) -> None:
        persist_dir = str(self._settings.persist_dir)
        self._client = chromadb.PersistentClient(path=persist_dir)
        distance_fn = _DISTANCE_MAP.get(self._settings.distance_metric, "cosine")
        self._collection = self._client.get_or_create_collection(
            name=self._settings.collection_name,
            metadata={"hnsw:space": distance_fn},
        )

    async def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        ids = [c.id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number or 0,
                "section": c.section,
                **{k: str(v) for k, v in c.metadata.items()},
            }
            for c in chunks
        ]
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return ids

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where = filter if filter else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._to_search_results(results)

    async def search_mmr(
        self,
        query_embedding: list[float],
        k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where = filter if filter else None
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        candidate_embeddings = np.array(results["embeddings"][0])
        query_arr = np.array(query_embedding)

        selected_indices = self._mmr_selection(
            query_arr, candidate_embeddings, k=k, lambda_mult=lambda_mult
        )

        filtered = {
            "ids": [[results["ids"][0][i] for i in selected_indices]],
            "documents": [[results["documents"][0][i] for i in selected_indices]],
            "metadatas": [[results["metadatas"][0][i] for i in selected_indices]],
            "distances": [[results["distances"][0][i] for i in selected_indices]],
        }
        return self._to_search_results(filtered)

    @staticmethod
    def _mmr_selection(
        query: np.ndarray,
        candidates: np.ndarray,
        k: int,
        lambda_mult: float,
    ) -> list[int]:
        """Maximal Marginal Relevance selection."""
        if len(candidates) == 0:
            return []

        query_norm = query / (np.linalg.norm(query) + 1e-10)
        cand_norms = candidates / (np.linalg.norm(candidates, axis=1, keepdims=True) + 1e-10)
        query_sim = cand_norms @ query_norm

        selected: list[int] = []
        remaining = list(range(len(candidates)))

        for _ in range(min(k, len(candidates))):
            if not remaining:
                break

            if not selected:
                best = max(remaining, key=lambda i: query_sim[i])
            else:
                best_score = -float("inf")
                best = remaining[0]
                selected_embeddings = cand_norms[selected]
                for i in remaining:
                    max_sim_to_selected = float(np.max(cand_norms[i] @ selected_embeddings.T))
                    mmr_score = lambda_mult * query_sim[i] - (1 - lambda_mult) * max_sim_to_selected
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best = i
            selected.append(best)
            remaining.remove(best)

        return selected

    def _to_search_results(self, results: dict) -> list[SearchResult]:
        """Convert ChromaDB query results to SearchResult list."""
        search_results: list[SearchResult] = []

        if not results["ids"] or not results["ids"][0]:
            return search_results

        # Standard fields that go into DocumentChunk directly
        standard_fields = {"document_id", "page_number", "section", "chunk_index"}

        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            content = results["documents"][0][i] if results.get("documents") else ""
            distance = results["distances"][0][i] if results.get("distances") else 0.0

            # Convert distance to similarity score (Chroma returns distances)
            score = max(0.0, 1.0 - distance) if distance >= 0 else 1.0 + distance

            # Parse page_number (handle None string from metadata)
            page_number_str = meta.get("page_number", "0")
            if page_number_str == "None" or not page_number_str:
                page_number = None
            else:
                try:
                    page_number = int(page_number_str) or None
                except (ValueError, TypeError):
                    page_number = None

            # Parse chunk_index
            chunk_index_str = meta.get("chunk_index", "0")
            try:
                chunk_index = int(chunk_index_str)
            except (ValueError, TypeError):
                chunk_index = 0

            # Extract metadata (Phase 1.3: all non-standard fields)
            chunk_metadata = {
                k: v for k, v in meta.items()
                if k not in standard_fields
            }

            chunk = DocumentChunk(
                id=doc_id,
                content=content,
                document_id=meta.get("document_id", ""),
                page_number=page_number,
                section=meta.get("section", ""),
                chunk_index=chunk_index,
                metadata=chunk_metadata,  # Phase 1.3: restore metadata
            )
            search_results.append(SearchResult(chunk=chunk, score=score, source="vector"))

        return search_results

    async def delete(self, ids: list[str]) -> None:
        self.collection.delete(ids=ids)

    async def get_by_ids(self, ids: list[str]) -> list[DocumentChunk]:
        results = self.collection.get(ids=ids, include=["documents", "metadatas"])
        chunks: list[DocumentChunk] = []
        for i, doc_id in enumerate(results["ids"]):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            content = results["documents"][i] if results.get("documents") else ""
            chunks.append(
                DocumentChunk(
                    id=doc_id,
                    content=content,
                    document_id=meta.get("document_id", ""),
                    page_number=int(meta.get("page_number", 0)) or None,
                    section=meta.get("section", ""),
                    chunk_index=int(meta.get("chunk_index", 0)),
                )
            )
        return chunks

    async def count(self) -> int:
        return self.collection.count()

    async def clear(self) -> None:
        if self._client and self._collection:
            self._client.delete_collection(self._settings.collection_name)
            await self.initialize()
