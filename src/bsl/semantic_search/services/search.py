"""
BSL Search Service - Единый интерфейс поиска

Объединяет все поисковые движки системы:
1. Semantic Search (Qdrant) - векторный поиск по эмбеддингам
2. Graph Search (Neo4j) - поиск по графу зависимостей
3. Hybrid Search - комбинированный подход
4. LLM Re-ranking - финальное ранжирование через LLM

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    """Режимы поиска"""

    SEMANTIC_ONLY = "semantic"  # Только векторный поиск
    GRAPH_ONLY = "graph"  # Только поиск по графу
    HYBRID = "hybrid"  # Гибридный подход
    INTELLIGENT = "intelligent"  # Умный поиск с LLM re-ranking
    MULTI_STAGE = "multi_stage"  # Многостадийный поиск


@dataclass
class SearchResult:
    """Результат поиска"""

    file_path: str
    module_type: str
    score: float
    original_score: float
    summary: str
    functions_count: int
    variables_count: int = 0
    source: str = "unknown"  # Источник результата (semantic, graph, hybrid)
    reranked: bool = False  # Был ли применен LLM re-ranking
    reasoning: str = ""  # Объяснение от LLM (если reranked=True)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchRequest:
    """Запрос на поиск"""

    query: str
    mode: SearchMode = SearchMode.INTELLIGENT
    limit: int = 10

    # Фильтры
    module_types: list[str] | None = None
    file_path_pattern: str | None = None
    min_score: float = 0.0

    # Опции
    include_functions: bool = False
    use_llm_reranking: bool = True
    combine_sources: bool = True  # Объединять результаты из разных источников


class BSLSearchService:
    """
    Единый сервис поиска для BSL кода

    Объединяет все поисковые движки и предоставляет
    унифицированный интерфейс для поиска по кодовой базе.
    """

    def __init__(
        self,
        qdrant_service=None,  # QdrantVectorStore
        neo4j_service=None,  # Neo4jService или GraphAnalyzer
        hybrid_engine=None,  # HybridSearchEngine
        llm_service=None,  # LLMService
    ):
        """
        Инициализация BSL Search Service

        Args:
            qdrant_service: Сервис векторного поиска
            neo4j_service: Сервис графового поиска
            hybrid_engine: Гибридный поисковый движок
            llm_service: Сервис для LLM re-ranking
        """
        self.qdrant = qdrant_service
        self.neo4j = neo4j_service
        self.hybrid = hybrid_engine
        self.llm = llm_service

        # Ленивая инициализация embedding service
        self._embedding_service = None
        self._qdrant_client = None
        # Lazy-init Neo4j driver (2026-05-22: closes architecture gap —
        # mcp.py:131 hardcodes neo4j_service=None, ранее граф фактически
        # не использовался в production search).
        self._neo4j_driver = None
        # Lazy-init BM25 sparse embedder + collection layout cache (2026-05-22:
        # native Qdrant BM25 + RRF fusion. Anchor bench showed dense Hit@10
        # ~16% vs hybrid ~90% on bsl_code_v4_late. Layout detected once on
        # first query — None means "not probed yet", "dense_only"/"hybrid"
        # decides the query path.
        self._bm25_sparse = None
        self._collection_layout: str | None = None

        logger.info("BSLSearchService инициализирован")
        logger.info(f"  Qdrant: {'✓' if qdrant_service else '✗'}")
        logger.info(f"  Neo4j: {'✓' if neo4j_service else '✗'}")
        logger.info(f"  Hybrid: {'✓' if hybrid_engine else '✗'}")
        logger.info(f"  LLM: {'✓' if llm_service else '✗'}")

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """
        Выполнить поиск согласно запросу

        Args:
            request: Параметры поискового запроса

        Returns:
            Список результатов поиска, отсортированных по релевантности
        """
        logger.info(f"Начат поиск: query='{request.query}', mode={request.mode.value}")

        # Выбор стратегии поиска
        if request.mode == SearchMode.SEMANTIC_ONLY:
            results = await self._semantic_search(request)
        elif request.mode == SearchMode.GRAPH_ONLY:
            results = await self._graph_search(request)
        elif request.mode == SearchMode.HYBRID:
            results = await self._hybrid_search(request)
        elif request.mode == SearchMode.INTELLIGENT:
            results = await self._intelligent_search(request)
        elif request.mode == SearchMode.MULTI_STAGE:
            results = await self._multi_stage_search(request)
        else:
            logger.warning(f"Неизвестный режим поиска: {request.mode}")
            results = await self._semantic_search(request)

        logger.info(f"Поиск завершен: найдено {len(results)} результатов")
        return results[: request.limit]

    async def _semantic_search(self, request: SearchRequest) -> list[SearchResult]:
        """Векторный поиск через Qdrant"""
        logger.debug("Выполняется semantic search")

        try:
            raw_results = await self._call_qdrant_search(
                query=request.query,
                limit=request.limit * 2,
                filters=self._build_qdrant_filters(request),
            )

            results = []
            for r in raw_results:
                results.append(
                    SearchResult(
                        file_path=r.get("file_path", ""),
                        module_type=r.get("module_type", "Unknown"),
                        score=r.get("score", 0.0),
                        original_score=r.get("score", 0.0),
                        summary=r.get("summary", ""),
                        functions_count=r.get("functions_count", 0),
                        variables_count=r.get("variables_count", 0),
                        source="semantic",
                        metadata=r,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Ошибка semantic search: {e}")
            return []

    async def _graph_search(self, request: SearchRequest) -> list[SearchResult]:
        """Поиск по графу зависимостей через Neo4j (lazy-init driver)."""
        logger.debug("Выполняется graph search")

        try:
            raw_results = await self._call_neo4j_search(
                query=request.query, limit=request.limit * 2
            )

            results = []
            for r in raw_results:
                results.append(
                    SearchResult(
                        file_path=r.get("file_path", ""),
                        module_type=r.get("type", "Unknown"),
                        score=r.get("relevance", 0.5),
                        original_score=r.get("relevance", 0.5),
                        summary=r.get("description", ""),
                        functions_count=r.get("functions_count", 0),
                        source="graph",
                        metadata=r,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Ошибка graph search: {e}")
            return []

    async def _hybrid_search(self, request: SearchRequest) -> list[SearchResult]:
        """Гибридный поиск"""
        logger.debug("Выполняется hybrid search")

        try:
            raw_results = await self._call_hybrid_search(
                query=request.query, limit=request.limit * 2
            )

            results = []
            for r in raw_results:
                results.append(
                    SearchResult(
                        file_path=r.get("file_path", ""),
                        module_type=r.get("module_type", "Unknown"),
                        score=r.get("combined_score", 0.0),
                        original_score=r.get("combined_score", 0.0),
                        summary=r.get("summary", ""),
                        functions_count=r.get("functions_count", 0),
                        source="hybrid",
                        metadata=r,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Ошибка hybrid search: {e}")
            return []

    async def _intelligent_search(self, request: SearchRequest) -> list[SearchResult]:
        """Умный поиск с LLM re-ranking"""
        logger.debug("Выполняется intelligent search с LLM")

        # Fetch x4 кандидатов для reranker pool (vector ranking weak per
        # investigation 2026-05-22 — anisotropy 0.59 → tied scores).
        rerank_pool = max(request.limit * 4, 20) if request.use_llm_reranking else request.limit
        original_limit = request.limit
        request.limit = rerank_pool
        try:
            results = await self._hybrid_search(request)
            if not results:
                logger.warning("Hybrid search не вернул результатов, пробуем semantic")
                results = await self._semantic_search(request)
        finally:
            request.limit = original_limit

        # LLM re-ranking via local Ollama qwen2.5-coder:7b. Evidence-based
        # patch (2026-05-22): 20-query A/B test показал +5-10pp top-1
        # relevance vs vector-only. Graceful fallback на vector ordering
        # при недоступности Ollama. Latency: +1.5s per query.
        if request.use_llm_reranking and len(results) > 1:
            results = await self._llm_rerank(request.query, results, top_k=request.limit)
        else:
            results = results[: request.limit]

        return results

    async def _llm_rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """LLM re-ranking via local Ollama qwen2.5-coder:7b.

        Investigation 2026-05-22: BSL embeddings collapsed (effective rank
        6/200, anisotropy 0.59) → vector top-5 имеют tied scores (spread 2%).
        LLM reranker разрешает ambiguity через actual semantic understanding.

        Live A/B 20 queries:
          - vector-only top-1 relevance: 45-65%
          - + LLM rerank top-1 relevance: 50-75% (+5-10pp)
          - latency: ~1.5s/query
          - failures: 0/20 in test, graceful fallback на vector order

        Args:
            query: User query.
            results: Vector search results (fetched as 4× top_k pool).
            top_k: Final result count to return.

        Returns:
            Reranked top_k results, with `reranked=True` flag on returned items.
        """
        if len(results) <= 1:
            return results[:top_k]

        import re

        import httpx

        # Build numbered prompt with candidate signatures (top-20 cap для prompt length)
        cand_lines = []
        for i, r in enumerate(results[:20], 1):
            text = (r.summary or "")[:300].replace("\n", " ")
            short_path = r.file_path.replace("\\", "/").rsplit("/", 2)[-1][:60]
            cand_lines.append(f"{i}. {short_path}\n   {text}")
        cand_str = "\n".join(cand_lines)

        prompt = (
            f"You are a code search reranker for BSL (1C:Enterprise). "
            f"Given a query and {len(results[:20])} candidate BSL code snippets, "
            f"rank them by relevance to the query.\n\n"
            f"Output ONLY a comma-separated list of numbers in order of relevance "
            f'(most relevant first). Example: "3,7,1,5,2,9,4,8,6,10"\n\n'
            f"Query: {query}\n\nCandidates:\n{cand_str}\n\n"
            f"Ranking (most relevant first):"
        )

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                resp = await http.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "qwen2.5-coder:7b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 100},
                    },
                )
                text = resp.json().get("response", "")
        except Exception as e:
            logger.warning(f"[LLM-RERANK] Ollama unavailable, fallback vector order: {e}")
            return results[:top_k]

        # Parse comma-separated indices
        match = re.search(r"\d+(?:\s*,\s*\d+)+", text)
        if not match:
            logger.warning("[LLM-RERANK] No ranking in LLM response, fallback vector order")
            return results[:top_k]

        try:
            order = [int(x.strip()) - 1 for x in match.group(0).split(",")]
        except ValueError:
            return results[:top_k]

        seen: set[int] = set()
        reranked: list[SearchResult] = []
        for idx in order:
            if 0 <= idx < len(results) and idx not in seen:
                r = results[idx]
                r.reranked = True
                r.original_score = r.score  # preserve vector score
                # Decay score by LLM rank position (для downstream UI sort)
                r.score = max(0.0, 1.0 - (len(reranked) * 0.01))
                reranked.append(r)
                seen.add(idx)

        # Append any non-ranked candidates at end (vector order)
        for i, r in enumerate(results):
            if i not in seen:
                reranked.append(r)
                seen.add(i)

        return reranked[:top_k]

    async def _multi_stage_search(self, request: SearchRequest) -> list[SearchResult]:
        """Многостадийный поиск"""
        logger.debug("Выполняется multi-stage search")

        # Стадия 1: Широкий semantic search
        semantic_results = await self._semantic_search(
            SearchRequest(query=request.query, limit=request.limit * 5)
        )

        if not semantic_results:
            return []

        # Стадия 2-4: TODO

        return semantic_results[: request.limit]

    def _detect_collection_layout(self, collection_name: str) -> str:
        """Detect collection layout: 'hybrid' (named dense + sparse BM25) or 'dense_only'.

        Cached on first call. Falls back to 'dense_only' on probe error so
        a transient Qdrant hiccup doesn't break search — the dense-only path
        works on any layout (single-vector OR named-vector via `using='dense'`).
        """
        if self._collection_layout is not None:
            return self._collection_layout
        try:
            info = self._qdrant_client.get_collection(collection_name)
            vec_cfg = info.config.params.vectors
            sparse_cfg = info.config.params.sparse_vectors
            has_named_dense = isinstance(vec_cfg, dict) and "dense" in vec_cfg
            has_sparse_bm25 = bool(sparse_cfg and "bm25" in sparse_cfg)
            self._collection_layout = (
                "hybrid" if (has_named_dense and has_sparse_bm25) else "dense_only"
            )
            logger.info(
                f"[QDRANT] Collection '{collection_name}' layout: {self._collection_layout}"
            )
        except Exception as exc:
            logger.warning(
                f"[QDRANT] Layout probe failed for '{collection_name}': {exc}; "
                f"falling back to dense_only"
            )
            self._collection_layout = "dense_only"
        return self._collection_layout

    def _get_bm25_sparse(self):
        """Lazy-init FastEmbed Qdrant/bm25 sparse encoder.

        Returns None if FastEmbed is unavailable — caller falls back to
        dense-only search. First call loads the model (~2-3s); kept in memory.
        """
        if self._bm25_sparse is not None:
            return self._bm25_sparse
        try:
            from fastembed import SparseTextEmbedding

            self._bm25_sparse = SparseTextEmbedding(model_name="Qdrant/bm25")
            logger.info("[BM25] FastEmbed Qdrant/bm25 loaded for hybrid search")
            return self._bm25_sparse
        except Exception as exc:
            logger.warning(
                f"[BM25] FastEmbed unavailable, hybrid search will degrade to dense-only: {exc}"
            )
            return None

    @staticmethod
    def _normalize_camelcase_for_bm25(text: str) -> str:
        """Delegates to canonical bm25_tokenizer (single source of truth)."""
        from .bm25_tokenizer import normalize_camelcase

        return normalize_camelcase(text)

    async def _call_qdrant_search(self, query: str, limit: int, filters: Any) -> list[dict]:
        """Vector search via Qdrant.

        Auto-detects collection layout on first call:
          * `hybrid` (named dense + sparse BM25) -> **hybrid DBSF** (Prefetch
            dense + BM25 sparse -> FusionQuery DBSF, RRF fallback). 2026-06-20
            re-verified realistic eval (lexical `data/bsl_golden_set.json` +
            vocab-mismatch `data/eval/bsl/bsl_semantic_golden.json`): hybrid beats
            BM25-first on BOTH splits — lexical recall@10 0.80 vs 0.68, semantic
            0.38 vs 0.16. Phase 2 measured DBSF strictly dominates RRF (lexical
            0.80 = RRF, no regression; semantic 0.38 vs RRF 0.34) — score-distribution
            fusion z-normalizes each arm, auto-down-weighting the failing BM25 arm on
            vocab-mismatch queries (no query classifier needed). The prior "pure BM25
            dominates / dense ~18%" verdict (2026-05-22) did NOT reproduce: dense is
            healthy (0.72 lexical / 0.42 semantic) — the 18% was a harness artifact.
            Fallbacks: TEI down -> BM25-only; BM25/FastEmbed down -> dense-only.
            See memory feedback-bsl-sparse-bm25-dominance.
          * `dense_only` (single-vector OR named without sparse) -> plain
            dense `query_points`. Backwards-compat for non-migrated collections.
        """
        try:
            from qdrant_client import QdrantClient

            from ..config import get_bsl_settings

            settings = get_bsl_settings()

            if self._qdrant_client is None:
                self._qdrant_client = QdrantClient(
                    host=settings.qdrant_host, port=settings.qdrant_port
                )

            collection_name = getattr(self.qdrant, "collection_name", settings.collection_name)
            layout = self._detect_collection_layout(collection_name)

            if layout == "hybrid":
                # 2026-06-20 (Phase 0 verified): hybrid RRF default — dense + BM25
                # sparse fusion. Supersedes pure-BM25 default; hybrid beats BM25-first
                # on lexical (+10pp) AND vocab-mismatch (+18pp) recall@10. Graceful
                # degradation keeps the old BM25-only path when TEI is down.
                from qdrant_client import models as qm

                bm25 = self._get_bm25_sparse()
                # --- dense arm (TEI Qwen3; is_query=True applies the query instruct prefix) ---
                if self._embedding_service is None:
                    import atexit

                    from src.framework_search.embedder import FrameworkTEIEmbedder

                    self._embedding_service = FrameworkTEIEmbedder()
                    atexit.register(self._embedding_service.close)
                try:
                    query_embedding = (
                        await asyncio.to_thread(
                            self._embedding_service.embed_batch, [query], is_query=True
                        )
                    )[0] or None
                except Exception as exc:
                    logger.error(f"TEI embedding failed (hybrid dense arm): {exc}")
                    query_embedding = None
                # --- BM25 sparse arm (FastEmbed Qdrant/bm25 over CamelCase-normalized query) ---
                sparse_vec = None
                if bm25 is not None:
                    norm_query = self._normalize_camelcase_for_bm25(query)
                    sparse_emb = await asyncio.to_thread(
                        lambda: next(iter(bm25.embed([norm_query])))
                    )
                    sparse_vec = qm.SparseVector(
                        indices=sparse_emb.indices.tolist(),
                        values=sparse_emb.values.tolist(),
                    )

                prefetch_limit = max(limit, 50)
                if query_embedding and sparse_vec is not None:
                    # both arms healthy -> DBSF fusion. Phase 2 measured (L+S golden):
                    # DBSF strictly dominates RRF — lexical recall@10 0.80 (=RRF, no
                    # regression), semantic 0.38 vs RRF 0.34 (+4pp). DBSF z-normalizes
                    # each arm's score distribution, so the failing BM25 arm on
                    # vocab-mismatch queries (flat/low scores) auto-contributes less —
                    # score-adaptive WITHOUT a query classifier. Fallback: RRF if the
                    # Qdrant build lacks DBSF (requires Qdrant >= 1.10).
                    prefetch = [
                        qm.Prefetch(
                            query=query_embedding,
                            using="dense",
                            limit=prefetch_limit,
                            filter=filters,
                        ),
                        qm.Prefetch(
                            query=sparse_vec,
                            using="bm25",
                            limit=prefetch_limit,
                            filter=filters,
                        ),
                    ]
                    try:
                        search_results = (
                            await asyncio.to_thread(
                                self._qdrant_client.query_points,
                                collection_name=collection_name,
                                prefetch=prefetch,
                                query=qm.FusionQuery(fusion=qm.Fusion.DBSF),
                                limit=limit,
                            )
                        ).points
                    except Exception as exc:
                        logger.warning(
                            f"DBSF fusion unavailable, falling back to RRF: {exc}"
                        )
                        search_results = (
                            await asyncio.to_thread(
                                self._qdrant_client.query_points,
                                collection_name=collection_name,
                                prefetch=prefetch,
                                query=qm.FusionQuery(fusion=qm.Fusion.RRF),
                                limit=limit,
                            )
                        ).points
                elif sparse_vec is not None:
                    # TEI down -> BM25-only fallback (prev default)
                    search_results = (
                        await asyncio.to_thread(
                            self._qdrant_client.query_points,
                            collection_name=collection_name,
                            query=sparse_vec,
                            using="bm25",
                            limit=limit,
                            query_filter=filters,
                        )
                    ).points
                elif query_embedding:
                    # BM25/FastEmbed down -> dense-only fallback
                    search_results = (
                        await asyncio.to_thread(
                            self._qdrant_client.query_points,
                            collection_name=collection_name,
                            query=query_embedding,
                            using="dense",
                            limit=limit,
                            query_filter=filters,
                        )
                    ).points
                else:
                    logger.error("hybrid search: both arms unavailable (TEI + BM25 down)")
                    return []
            else:
                # Legacy single-vector path (Phase 8.12 BSL collections, others).
                # Requires TEI dense embedding.
                if self._embedding_service is None:
                    import atexit

                    from src.framework_search.embedder import FrameworkTEIEmbedder

                    self._embedding_service = FrameworkTEIEmbedder()
                    atexit.register(self._embedding_service.close)
                try:
                    query_embedding = (
                        await asyncio.to_thread(
                            self._embedding_service.embed_batch, [query], is_query=True
                        )
                    )[0]
                except Exception as exc:
                    logger.error(f"TEI embedding failed: {exc}", exc_info=True)
                    return []
                if not query_embedding:
                    logger.error("TEI вернул пустой embedding для запроса")
                    return []
                search_results = (
                    await asyncio.to_thread(
                        self._qdrant_client.query_points,
                        collection_name=collection_name,
                        query=query_embedding,
                        limit=limit,
                        query_filter=filters,
                    )
                ).points

            # Преобразование результатов
            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append(
                    {
                        "file_path": payload.get("module_path", ""),
                        "module_type": payload.get("module_type", "Unknown"),
                        "score": hit.score,
                        "summary": payload.get("content", "")[:500],
                        "functions_count": payload.get("functions_count", 0),
                        "variables_count": payload.get("variables_count", 0),
                        "functions": payload.get("functions", []),
                        "procedures": payload.get("procedures", []),
                        "file_size": payload.get("file_size", 0),
                        "indexed_at": payload.get("indexed_at", ""),
                    }
                )

            logger.info(f"Qdrant search завершен: найдено {len(results)} результатов")
            return results

        except ImportError as e:
            logger.error(f"Ошибка импорта зависимостей: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка Qdrant search: {e}", exc_info=True)
            return []

    async def _get_neo4j_driver(self):
        """Lazy-init Neo4j AsyncDriver. Returns None if unavailable.

        Default credentials match scripts/load_graph_to_neo4j.py.
        Override via env: NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD.
        """
        if self._neo4j_driver is not None:
            return self._neo4j_driver
        try:
            import os

            from neo4j import AsyncGraphDatabase

            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "")
            self._neo4j_driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            await self._neo4j_driver.verify_connectivity()
            logger.info(f"[NEO4J] AsyncDriver connected: {uri} as {user}")
            return self._neo4j_driver
        except Exception as e:
            logger.warning(f"[NEO4J] Driver init failed: {type(e).__name__}: {e}")
            self._neo4j_driver = None
            return None

    async def _call_neo4j_search(self, query: str, limit: int) -> list[dict]:
        """Вызов Neo4j search через Cypher. Schema (post-2026-05-20 reindex):
        Module/Symbol/Object nodes + BELONGS_TO/DECLARES/CALLS/CONTAINS rels.
        Properties: Module.path, Symbol.name/symbol_type/is_export.
        """
        # Backward-compat: legacy injection via constructor still works
        if self.neo4j and hasattr(self.neo4j, "execute_query"):
            return await self._call_neo4j_search_legacy(query, limit)

        # Lazy driver path (default since 2026-05-22)
        driver = await self._get_neo4j_driver()
        if driver is None:
            return []

        try:
            keywords = self._extract_keywords_from_query(query)
            if not keywords:
                logger.warning("Не удалось извлечь ключевые слова из запроса")
                return []

            # Match Symbol by name, traverse to Module via BELONGS_TO.
            # Phase 8 schema: Module.path + Symbol.name/symbol_type/is_export.
            cypher_query = """
            MATCH (s:Symbol)
            WHERE ANY(keyword IN $keywords WHERE
                toLower(s.name) CONTAINS toLower(keyword)
            )
            OPTIONAL MATCH (s)-[:BELONGS_TO]->(m:Module)
            WITH s, m,
                 count{(m)-[:DECLARES]->(:Symbol)} AS sym_count
            RETURN
                coalesce(s.name, '?') AS module_name,
                coalesce(m.path, s.module_path, '') AS file_path,
                coalesce(m.module_type, 'Unknown') AS module_type,
                s.symbol_type AS symbol_type,
                s.is_export AS is_export,
                coalesce(m.object_type, '') AS object_type,
                coalesce(m.object_name, '') AS object_name,
                sym_count AS functions_count
            LIMIT $limit
            """

            async with driver.session() as session:
                result = await session.run(cypher_query, {"keywords": keywords, "limit": limit})
                results = [dict(record) async for record in result]

            formatted_results = []
            for r in results:
                relevance = self._calculate_relevance(
                    query=query,
                    module_name=r.get("module_name", ""),
                    file_path=r.get("file_path", ""),
                )

                formatted_results.append(
                    {
                        "file_path": r.get("file_path", ""),
                        "type": r.get("module_type", "Unknown"),
                        "module_type": r.get("module_type", "Unknown"),
                        "relevance": relevance,
                        "description": f"Модуль {r.get('module_name', 'Unknown')} с {r.get('functions_count', 0)} функциями",
                        "functions_count": r.get("functions_count", 0),
                        "functions": r.get("functions", []),
                        "dependencies": r.get("dependencies", []),
                        "summary": f"Зависимости: {', '.join(r.get('dependencies', [])[:3])}"
                        if r.get("dependencies")
                        else "Нет зависимостей",
                    }
                )

            logger.info(f"Neo4j search завершен: найдено {len(formatted_results)} результатов")
            return formatted_results

        except Exception as e:
            logger.error(f"Ошибка Neo4j search: {e}", exc_info=True)
            return []

    async def _call_neo4j_search_legacy(self, query: str, limit: int) -> list[dict]:
        """Legacy path: использует injected service.execute_query() interface."""
        try:
            keywords = self._extract_keywords_from_query(query)
            if not keywords:
                return []
            cypher_query = """
            MATCH (s:Symbol)
            WHERE ANY(keyword IN $keywords WHERE toLower(s.name) CONTAINS toLower(keyword))
            OPTIONAL MATCH (s)-[:BELONGS_TO]->(m:Module)
            WITH s, m, count{(m)-[:DECLARES]->(:Symbol)} AS sym_count
            RETURN coalesce(s.name, '?') AS module_name,
                   coalesce(m.path, s.module_path, '') AS file_path,
                   coalesce(m.module_type, 'Unknown') AS module_type,
                   sym_count AS functions_count
            LIMIT $limit
            """
            return self.neo4j.execute_query(cypher_query, {"keywords": keywords, "limit": limit})
        except Exception as e:
            logger.error(f"Ошибка Neo4j legacy search: {e}")
            return []

    async def _call_hybrid_search(self, query: str, limit: int) -> list[dict]:
        """Гибридный поиск - объединение semantic + graph"""
        try:
            # Параллельный запуск semantic и graph search
            semantic_results_task = self._call_qdrant_search(
                query=query, limit=limit * 2, filters=None
            )

            graph_results_task = self._call_neo4j_search(query=query, limit=limit)

            semantic_results, graph_results = await asyncio.gather(
                semantic_results_task, graph_results_task, return_exceptions=True
            )

            if isinstance(semantic_results, Exception):
                logger.error(f"Semantic search failed: {semantic_results}")
                semantic_results = []

            if isinstance(graph_results, Exception):
                logger.error(f"Graph search failed: {graph_results}")
                graph_results = []

            # Объединение результатов
            combined_results = self._combine_search_results(
                semantic_results=semantic_results,
                graph_results=graph_results,
                semantic_weight=0.6,
                graph_weight=0.4,
            )

            logger.info(f"Hybrid search завершен: {len(combined_results)} результатов")
            return combined_results[:limit]

        except Exception as e:
            logger.error(f"Ошибка hybrid search: {e}", exc_info=True)
            return []

    def _build_qdrant_filters(self, request: SearchRequest) -> Any:
        """Построение фильтров для Qdrant"""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

            conditions = []

            if request.module_types and len(request.module_types) > 0:
                if len(request.module_types) == 1:
                    conditions.append(
                        FieldCondition(
                            key="module_type", match=MatchValue(value=request.module_types[0])
                        )
                    )
                else:
                    conditions.append(
                        FieldCondition(key="module_type", match=MatchAny(any=request.module_types))
                    )

            if conditions:
                return Filter(must=conditions)

            return None

        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Ошибка построения фильтров: {e}")
            return None

    def _extract_keywords_from_query(self, query: str) -> list[str]:
        """Извлечение ключевых слов из поискового запроса"""
        stopwords = {
            "как",
            "что",
            "где",
            "когда",
            "почему",
            "кто",
            "чем",
            "это",
            "все",
            "для",
            "из",
            "при",
            "с",
            "по",
            "на",
            "в",
            "о",
            "от",
            "до",
            "к",
            "и",
            "или",
            "не",
            "но",
            "а",
            "также",
            "еще",
            "уже",
            "только",
            "the",
            "is",
            "at",
            "which",
            "on",
            "in",
            "a",
            "an",
            "and",
            "or",
            "but",
            "for",
            "with",
            "from",
            "to",
            "of",
            "by",
            "as",
            "this",
        }

        words = query.lower().split()
        keywords = [
            w.strip(".,!?;:()[]{}\"'-") for w in words if len(w) > 2 and w.lower() not in stopwords
        ]

        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:10]

    def _calculate_relevance(self, query: str, module_name: str, file_path: str) -> float:
        """Расчет релевантности результата Neo4j поиска"""
        query_lower = query.lower()
        module_lower = module_name.lower()

        relevance = 0.5

        if query_lower in module_lower:
            relevance = 0.9

        keywords = self._extract_keywords_from_query(query)
        matches = sum(1 for kw in keywords if kw in module_lower)
        if matches > 0:
            relevance = min(0.5 + (matches * 0.1), 1.0)

        return round(relevance, 2)

    def _combine_search_results(
        self,
        semantic_results: list[dict],
        graph_results: list[dict],
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4,
    ) -> list[dict]:
        """Объединение результатов semantic и graph поиска"""
        combined = {}

        for result in semantic_results:
            file_path = result.get("file_path", "")
            if not file_path:
                continue

            combined[file_path] = {
                "file_path": file_path,
                "module_type": result.get("module_type", "Unknown"),
                "combined_score": result.get("score", 0.5) * semantic_weight,
                "semantic_score": result.get("score", 0.5),
                "graph_score": 0.0,
                "summary": result.get("summary", ""),
                "functions_count": result.get("functions_count", 0),
                "variables_count": result.get("variables_count", 0),
                "functions": result.get("functions", []),
                "source": "semantic",
            }

        for result in graph_results:
            file_path = result.get("file_path", "")
            if not file_path:
                continue

            graph_score = result.get("relevance", 0.5)

            if file_path in combined:
                combined[file_path]["combined_score"] += graph_score * graph_weight
                combined[file_path]["graph_score"] = graph_score
                combined[file_path]["source"] = "semantic+graph"
                if "dependencies" in result:
                    combined[file_path]["dependencies"] = result["dependencies"]
            else:
                combined[file_path] = {
                    "file_path": file_path,
                    "module_type": result.get("module_type", "Unknown"),
                    "combined_score": graph_score * graph_weight,
                    "semantic_score": 0.0,
                    "graph_score": graph_score,
                    "summary": result.get("summary", ""),
                    "functions_count": result.get("functions_count", 0),
                    "functions": result.get("functions", []),
                    "dependencies": result.get("dependencies", []),
                    "source": "graph",
                }

        sorted_results = sorted(combined.values(), key=lambda x: x["combined_score"], reverse=True)

        return sorted_results


# Singleton instance
_bsl_search_service: BSLSearchService | None = None


def get_bsl_search_service(
    qdrant_service=None, neo4j_service=None, hybrid_engine=None, llm_service=None
) -> BSLSearchService:
    """Получение singleton instance BSLSearchService"""
    global _bsl_search_service

    if _bsl_search_service is None:
        _bsl_search_service = BSLSearchService(
            qdrant_service=qdrant_service,
            neo4j_service=neo4j_service,
            hybrid_engine=hybrid_engine,
            llm_service=llm_service,
        )

    return _bsl_search_service
