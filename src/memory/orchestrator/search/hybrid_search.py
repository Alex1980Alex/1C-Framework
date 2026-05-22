"""Hybrid search service with BM25 + RRF fusion.

Combines BM25 sparse search with optional dense (embedding) search.
Supports RRF and weighted fusion methods.

Migrated from: unified-memory-mcp/src/search/hybrid_search.py (500 lines)
Simplified: removed Qdrant/Ollama/httpx deps, made dense search injectable.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import logging
import math
import re
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .config import (
    DEFAULT_SEARCH_CONFIG,
    FusionMethod,
    SearchConfig,
    SparseConfig,
    VectorType,
)

logger = logging.getLogger(__name__)

# Type for injectable dense search adapter
DenseSearchFn = Callable[[str, int], Awaitable[list[tuple[str, float]]]]


@dataclass
class SearchResult:
    """A single search result."""

    id: str
    content: str
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Result of a hybrid search operation."""

    results: list[SearchResult]
    query: str
    total_found: int
    dense_count: int
    sparse_count: int
    fusion_method: FusionMethod
    search_time_ms: float


class BM25Index:
    """
    In-memory BM25 index with BSL-aware tokenization.

    No external dependencies. Supports Russian + English tokens.
    """

    def __init__(self, config: SparseConfig | None = None):
        cfg = config or DEFAULT_SEARCH_CONFIG.sparse
        self.k1 = cfg.k1
        self.b = cfg.b
        self.stopwords = set(cfg.bsl_stopwords)

        self.documents: dict[str, str] = {}
        self.doc_lengths: dict[str, int] = {}
        self.avg_doc_length: float = 0.0
        self.term_freqs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.total_docs: int = 0

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize with BSL awareness."""
        tokens = re.findall(r"[A-Za-zА-Яа-яёЁ][A-Za-zА-Яа-яёЁ0-9_]*", text)
        tokens = [t.lower() for t in tokens]
        tokens = [t for t in tokens if t not in self.stopwords and len(t) > 1]
        return tokens

    def add_document(self, doc_id: str, content: str) -> None:
        """Add a document to the index."""
        tokens = self._tokenize(content)

        self.documents[doc_id] = content
        self.doc_lengths[doc_id] = len(tokens)
        self.total_docs += 1
        self.avg_doc_length = sum(self.doc_lengths.values()) / max(self.total_docs, 1)

        term_counts: dict[str, int] = defaultdict(int)
        for token in tokens:
            term_counts[token] += 1

        seen = set()
        for term, count in term_counts.items():
            self.term_freqs[term][doc_id] = count
            if term not in seen:
                self.doc_freqs[term] += 1
                seen.add(term)

    def add_documents_batch(self, documents: list[tuple[str, str]]) -> None:
        """Add multiple documents at once."""
        for doc_id, content in documents:
            self.add_document(doc_id, content)

    def _idf(self, term: str) -> float:
        """Inverse Document Frequency."""
        df = self.doc_freqs.get(term, 0)
        if df == 0:
            return 0.0
        return math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1)

    def _score_document(self, doc_id: str, query_tokens: list[str]) -> float:
        """Compute BM25 score for a document."""
        score = 0.0
        doc_length = self.doc_lengths.get(doc_id, 0)
        if doc_length == 0:
            return 0.0

        for token in query_tokens:
            tf = self.term_freqs.get(token, {}).get(doc_id, 0)
            if tf == 0:
                continue
            idf = self._idf(token)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        """Search the index. Returns list of (doc_id, score)."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        candidates = set()
        for token in query_tokens:
            if token in self.term_freqs:
                candidates.update(self.term_freqs[token].keys())

        scores = []
        for doc_id in candidates:
            score = self._score_document(doc_id, query_tokens)
            if score > 0:
                scores.append((doc_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if doc_id not in self.documents:
            return False

        tokens = self._tokenize(self.documents[doc_id])
        for token in set(tokens):
            if token in self.term_freqs and doc_id in self.term_freqs[token]:
                del self.term_freqs[token][doc_id]
                self.doc_freqs[token] = max(0, self.doc_freqs[token] - 1)

        del self.documents[doc_id]
        del self.doc_lengths[doc_id]
        self.total_docs -= 1
        if self.total_docs > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs
        else:
            self.avg_doc_length = 0.0
        return True

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_docs,
            "unique_terms": len(self.doc_freqs),
            "avg_doc_length": round(self.avg_doc_length, 2),
        }


class HybridSearchService:
    """
    Hybrid search: BM25 sparse + optional dense search with RRF fusion.

    Dense search is injectable via a callable -- no hard dependency on
    Qdrant, Ollama, or any embedding service.

    Usage:
        svc = HybridSearchService()
        svc.index_document("doc1", "some BSL code content")
        result = await svc.search("BSL query", top_k=10)
    """

    def __init__(
        self,
        config: SearchConfig | None = None,
        dense_search_fn: DenseSearchFn | None = None,
    ):
        self.config = config or DEFAULT_SEARCH_CONFIG
        self._dense_search_fn = dense_search_fn
        self.bm25_index = BM25Index(self.config.sparse)

    def index_document(self, doc_id: str, content: str) -> None:
        """Index a document for BM25 search."""
        self.bm25_index.add_document(doc_id, content)

    def index_documents_batch(self, documents: list[tuple[str, str]]) -> None:
        """Index multiple documents."""
        self.bm25_index.add_documents_batch(documents)

    async def _dense_search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Execute dense search via injected adapter."""
        if self._dense_search_fn is None:
            return []
        try:
            return await self._dense_search_fn(query, top_k)
        except Exception as e:
            logger.warning("Dense search error: %s", e)
            return []

    def _sparse_search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Execute BM25 sparse search."""
        return self.bm25_index.search(query, top_k)

    def _rrf_fusion(
        self,
        dense_results: list[tuple[str, float]],
        sparse_results: list[tuple[str, float]],
        k: int = 60,
    ) -> list[tuple[str, float, float, float]]:
        """Reciprocal Rank Fusion: RRF(d) = sum 1/(k + rank)."""
        scores: dict[str, dict[str, float]] = defaultdict(
            lambda: {"rrf": 0.0, "dense": 0.0, "sparse": 0.0}
        )

        for rank, (doc_id, score) in enumerate(dense_results, 1):
            scores[doc_id]["rrf"] += 1 / (k + rank)
            scores[doc_id]["dense"] = score

        for rank, (doc_id, score) in enumerate(sparse_results, 1):
            scores[doc_id]["rrf"] += 1 / (k + rank)
            scores[doc_id]["sparse"] = score

        results = [
            (doc_id, data["rrf"], data["dense"], data["sparse"]) for doc_id, data in scores.items()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _weighted_fusion(
        self,
        dense_results: list[tuple[str, float]],
        sparse_results: list[tuple[str, float]],
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> list[tuple[str, float, float, float]]:
        """Weighted sum fusion with normalization."""
        scores: dict[str, dict[str, float]] = defaultdict(
            lambda: {"weighted": 0.0, "dense": 0.0, "sparse": 0.0}
        )

        if dense_results:
            max_dense = max(r[1] for r in dense_results)
            for doc_id, score in dense_results:
                normalized = score / max_dense if max_dense > 0 else 0
                scores[doc_id]["dense"] = normalized
                scores[doc_id]["weighted"] += normalized * dense_weight

        if sparse_results:
            max_sparse = max(r[1] for r in sparse_results)
            for doc_id, score in sparse_results:
                normalized = score / max_sparse if max_sparse > 0 else 0
                scores[doc_id]["sparse"] = normalized
                scores[doc_id]["weighted"] += normalized * sparse_weight

        results = [
            (doc_id, data["weighted"], data["dense"], data["sparse"])
            for doc_id, data in scores.items()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        vector_type: VectorType | None = None,
    ) -> HybridSearchResult:
        """Execute hybrid search."""
        start_time = time.time()

        top_k = top_k or self.config.hybrid.top_k
        vector_type = vector_type or self.config.default_vector_type

        dense_results: list[tuple[str, float]] = []
        sparse_results: list[tuple[str, float]] = []

        if vector_type in (VectorType.DENSE, VectorType.HYBRID):
            dense_results = await self._dense_search(query, top_k * 2)

        if vector_type in (VectorType.SPARSE, VectorType.HYBRID):
            sparse_results = self._sparse_search(query, top_k * 2)

        # Fusion
        if vector_type == VectorType.HYBRID and dense_results and sparse_results:
            fusion_method = self.config.hybrid.fusion_method
            if fusion_method == FusionMethod.RRF:
                fused = self._rrf_fusion(dense_results, sparse_results, self.config.hybrid.rrf_k)
            else:
                fused = self._weighted_fusion(
                    dense_results,
                    sparse_results,
                    self.config.hybrid.dense_weight,
                    self.config.hybrid.sparse_weight,
                )
        elif dense_results and not sparse_results:
            fused = [(doc_id, score, score, 0.0) for doc_id, score in dense_results]
            fusion_method = FusionMethod.WEIGHTED_SUM
        else:
            fused = [(doc_id, score, 0.0, score) for doc_id, score in sparse_results]
            fusion_method = FusionMethod.WEIGHTED_SUM

        results = []
        for doc_id, score, dense_score, sparse_score in fused[:top_k]:
            content = self.bm25_index.documents.get(doc_id, "")
            results.append(
                SearchResult(
                    id=doc_id,
                    content=content,
                    score=score,
                    dense_score=dense_score if dense_score > 0 else None,
                    sparse_score=sparse_score if sparse_score > 0 else None,
                )
            )

        search_time_ms = (time.time() - start_time) * 1000

        return HybridSearchResult(
            results=results,
            query=query,
            total_found=len(fused),
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            fusion_method=fusion_method,
            search_time_ms=search_time_ms,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return search index statistics."""
        return {
            "bm25": self.bm25_index.stats,
            "dense_available": self._dense_search_fn is not None,
            "fusion_method": self.config.hybrid.fusion_method.value,
        }


__all__ = [
    "BM25Index",
    "HybridSearchResult",
    "HybridSearchService",
    "SearchResult",
]
