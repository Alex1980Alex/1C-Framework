"""
BSL Search Service - Единый интерфейс поиска

Объединяет все поисковые движки системы:
1. Semantic Search (Qdrant) - векторный поиск по эмбеддингам
2. Graph Search (Neo4j) - поиск по графу зависимостей
3. Hybrid Search - комбинированный подход
4. LLM Re-ranking - финальное ранжирование через LLM

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

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
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchRequest:
    """Запрос на поиск"""
    query: str
    mode: SearchMode = SearchMode.INTELLIGENT
    limit: int = 10

    # Фильтры
    module_types: Optional[List[str]] = None
    file_path_pattern: Optional[str] = None
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
        neo4j_service=None,   # Neo4jService или GraphAnalyzer
        hybrid_engine=None,    # HybridSearchEngine
        llm_service=None      # LLMService
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

        logger.info("BSLSearchService инициализирован")
        logger.info(f"  Qdrant: {'✓' if qdrant_service else '✗'}")
        logger.info(f"  Neo4j: {'✓' if neo4j_service else '✗'}")
        logger.info(f"  Hybrid: {'✓' if hybrid_engine else '✗'}")
        logger.info(f"  LLM: {'✓' if llm_service else '✗'}")

    async def search(self, request: SearchRequest) -> List[SearchResult]:
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
        return results[:request.limit]

    async def _semantic_search(self, request: SearchRequest) -> List[SearchResult]:
        """Векторный поиск через Qdrant"""
        logger.debug("Выполняется semantic search")

        try:
            raw_results = await self._call_qdrant_search(
                query=request.query,
                limit=request.limit * 2,
                filters=self._build_qdrant_filters(request)
            )

            results = []
            for r in raw_results:
                results.append(SearchResult(
                    file_path=r.get("file_path", ""),
                    module_type=r.get("module_type", "Unknown"),
                    score=r.get("score", 0.0),
                    original_score=r.get("score", 0.0),
                    summary=r.get("summary", ""),
                    functions_count=r.get("functions_count", 0),
                    variables_count=r.get("variables_count", 0),
                    source="semantic",
                    metadata=r
                ))

            return results

        except Exception as e:
            logger.error(f"Ошибка semantic search: {e}")
            return []

    async def _graph_search(self, request: SearchRequest) -> List[SearchResult]:
        """Поиск по графу зависимостей через Neo4j"""
        logger.debug("Выполняется graph search")

        if not self.neo4j:
            logger.warning("Neo4j недоступен")
            return []

        try:
            raw_results = await self._call_neo4j_search(
                query=request.query,
                limit=request.limit * 2
            )

            results = []
            for r in raw_results:
                results.append(SearchResult(
                    file_path=r.get("file_path", ""),
                    module_type=r.get("type", "Unknown"),
                    score=r.get("relevance", 0.5),
                    original_score=r.get("relevance", 0.5),
                    summary=r.get("description", ""),
                    functions_count=r.get("functions_count", 0),
                    source="graph",
                    metadata=r
                ))

            return results

        except Exception as e:
            logger.error(f"Ошибка graph search: {e}")
            return []

    async def _hybrid_search(self, request: SearchRequest) -> List[SearchResult]:
        """Гибридный поиск"""
        logger.debug("Выполняется hybrid search")

        try:
            raw_results = await self._call_hybrid_search(
                query=request.query,
                limit=request.limit * 2
            )

            results = []
            for r in raw_results:
                results.append(SearchResult(
                    file_path=r.get("file_path", ""),
                    module_type=r.get("module_type", "Unknown"),
                    score=r.get("combined_score", 0.0),
                    original_score=r.get("combined_score", 0.0),
                    summary=r.get("summary", ""),
                    functions_count=r.get("functions_count", 0),
                    source="hybrid",
                    metadata=r
                ))

            return results

        except Exception as e:
            logger.error(f"Ошибка hybrid search: {e}")
            return []

    async def _intelligent_search(self, request: SearchRequest) -> List[SearchResult]:
        """Умный поиск с LLM re-ranking"""
        logger.debug("Выполняется intelligent search с LLM")

        # Hybrid search как базовая стратегия
        results = await self._hybrid_search(request)

        if not results:
            logger.warning("Hybrid search не вернул результатов, пробуем semantic")
            results = await self._semantic_search(request)

        # TODO: LLM Re-ranking

        return results

    async def _multi_stage_search(self, request: SearchRequest) -> List[SearchResult]:
        """Многостадийный поиск"""
        logger.debug("Выполняется multi-stage search")

        # Стадия 1: Широкий semantic search
        semantic_results = await self._semantic_search(
            SearchRequest(
                query=request.query,
                limit=request.limit * 5
            )
        )

        if not semantic_results:
            return []

        # Стадия 2-4: TODO

        return semantic_results[:request.limit]

    async def _call_qdrant_search(
        self,
        query: str,
        limit: int,
        filters: Any
    ) -> List[Dict]:
        """Вызов Qdrant search с генерацией embedding"""
        try:
            from qdrant_client import QdrantClient
            from ..config import get_bsl_settings

            settings = get_bsl_settings()

            if self._qdrant_client is None:
                self._qdrant_client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port
                )

            # Инициализация embedding service
            if self._embedding_service is None:
                from .embedding import EmbeddingService
                self._embedding_service = EmbeddingService(
                    ollama_host=settings.ollama_host,
                    model=settings.embedding_model
                )

            # Генерация embedding для запроса
            query_embedding = self._embedding_service.create_embedding(query)

            if not query_embedding:
                logger.error("Не удалось создать embedding для запроса")
                return []

            # Поиск в Qdrant
            collection_name = getattr(self.qdrant, 'collection_name', settings.collection_name)
            search_params = {
                "collection_name": collection_name,
                "query_vector": query_embedding,
                "limit": limit
            }

            if filters:
                search_params["query_filter"] = filters

            search_results = self._qdrant_client.search(**search_params)

            # Преобразование результатов
            results = []
            for hit in search_results:
                payload = hit.payload or {}
                results.append({
                    "file_path": payload.get("file_path", ""),
                    "module_type": payload.get("module_type", "Unknown"),
                    "score": hit.score,
                    "summary": payload.get("searchable_text", "")[:500],
                    "functions_count": payload.get("functions_count", 0),
                    "variables_count": payload.get("variables_count", 0),
                    "functions": payload.get("functions", []),
                    "procedures": payload.get("procedures", []),
                    "file_size": payload.get("file_size", 0),
                    "indexed_at": payload.get("indexed_at", "")
                })

            logger.info(f"Qdrant search завершен: найдено {len(results)} результатов")
            return results

        except ImportError as e:
            logger.error(f"Ошибка импорта зависимостей: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка Qdrant search: {e}", exc_info=True)
            return []

    async def _call_neo4j_search(
        self,
        query: str,
        limit: int
    ) -> List[Dict]:
        """Вызов Neo4j search через Cypher запрос"""
        if not self.neo4j:
            logger.warning("Neo4j service недоступен")
            return []

        try:
            keywords = self._extract_keywords_from_query(query)

            if not keywords:
                logger.warning("Не удалось извлечь ключевые слова из запроса")
                return []

            cypher_query = """
            MATCH (m:Module)
            WHERE ANY(keyword IN $keywords WHERE
                toLower(m.name) CONTAINS toLower(keyword) OR
                toLower(m.file_path) CONTAINS toLower(keyword)
            )
            OPTIONAL MATCH (m)-[:CONTAINS]->(f)
            WHERE f:Function OR f:Procedure
            OPTIONAL MATCH (m)-[:DEPENDS_ON]->(dep:Module)
            WITH m,
                 collect(DISTINCT f.name)[0..10] as functions,
                 count(DISTINCT f) as functions_count,
                 collect(DISTINCT dep.name)[0..5] as dependencies
            RETURN
                m.name as module_name,
                m.file_path as file_path,
                m.type as module_type,
                functions,
                functions_count,
                dependencies
            LIMIT $limit
            """

            results = self.neo4j.execute_query(
                cypher_query,
                {"keywords": keywords, "limit": limit}
            )

            formatted_results = []
            for r in results:
                relevance = self._calculate_relevance(
                    query=query,
                    module_name=r.get("module_name", ""),
                    file_path=r.get("file_path", "")
                )

                formatted_results.append({
                    "file_path": r.get("file_path", ""),
                    "type": r.get("module_type", "Unknown"),
                    "module_type": r.get("module_type", "Unknown"),
                    "relevance": relevance,
                    "description": f"Модуль {r.get('module_name', 'Unknown')} с {r.get('functions_count', 0)} функциями",
                    "functions_count": r.get("functions_count", 0),
                    "functions": r.get("functions", []),
                    "dependencies": r.get("dependencies", []),
                    "summary": f"Зависимости: {', '.join(r.get('dependencies', [])[:3])}" if r.get('dependencies') else "Нет зависимостей"
                })

            logger.info(f"Neo4j search завершен: найдено {len(formatted_results)} результатов")
            return formatted_results

        except Exception as e:
            logger.error(f"Ошибка Neo4j search: {e}", exc_info=True)
            return []

    async def _call_hybrid_search(
        self,
        query: str,
        limit: int
    ) -> List[Dict]:
        """Гибридный поиск - объединение semantic + graph"""
        try:
            # Параллельный запуск semantic и graph search
            semantic_results_task = self._call_qdrant_search(
                query=query,
                limit=limit * 2,
                filters=None
            )

            graph_results_task = self._call_neo4j_search(
                query=query,
                limit=limit
            )

            semantic_results, graph_results = await asyncio.gather(
                semantic_results_task,
                graph_results_task,
                return_exceptions=True
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
                graph_weight=0.4
            )

            logger.info(f"Hybrid search завершен: {len(combined_results)} результатов")
            return combined_results[:limit]

        except Exception as e:
            logger.error(f"Ошибка hybrid search: {e}", exc_info=True)
            return []

    def _build_qdrant_filters(self, request: SearchRequest) -> Any:
        """Построение фильтров для Qdrant"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

            conditions = []

            if request.module_types and len(request.module_types) > 0:
                if len(request.module_types) == 1:
                    conditions.append(
                        FieldCondition(
                            key="module_type",
                            match=MatchValue(value=request.module_types[0])
                        )
                    )
                else:
                    conditions.append(
                        FieldCondition(
                            key="module_type",
                            match=MatchAny(any=request.module_types)
                        )
                    )

            if conditions:
                return Filter(must=conditions)

            return None

        except ImportError:
            return None
        except Exception as e:
            logger.error(f"Ошибка построения фильтров: {e}")
            return None

    def _extract_keywords_from_query(self, query: str) -> List[str]:
        """Извлечение ключевых слов из поискового запроса"""
        stopwords = {
            "как", "что", "где", "когда", "почему", "кто", "чем", "это", "все",
            "для", "из", "при", "с", "по", "на", "в", "о", "от", "до", "к",
            "и", "или", "не", "но", "а", "также", "еще", "уже", "только",
            "the", "is", "at", "which", "on", "in", "a", "an", "and", "or",
            "but", "for", "with", "from", "to", "of", "by", "as", "this"
        }

        words = query.lower().split()
        keywords = [
            w.strip('.,!?;:()[]{}"\'-')
            for w in words
            if len(w) > 2 and w.lower() not in stopwords
        ]

        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords[:10]

    def _calculate_relevance(
        self,
        query: str,
        module_name: str,
        file_path: str
    ) -> float:
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
        semantic_results: List[Dict],
        graph_results: List[Dict],
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4
    ) -> List[Dict]:
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
                "source": "semantic"
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
                    "source": "graph"
                }

        sorted_results = sorted(
            combined.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )

        return sorted_results


# Singleton instance
_bsl_search_service: Optional[BSLSearchService] = None


def get_bsl_search_service(
    qdrant_service=None,
    neo4j_service=None,
    hybrid_engine=None,
    llm_service=None
) -> BSLSearchService:
    """Получение singleton instance BSLSearchService"""
    global _bsl_search_service

    if _bsl_search_service is None:
        _bsl_search_service = BSLSearchService(
            qdrant_service=qdrant_service,
            neo4j_service=neo4j_service,
            hybrid_engine=hybrid_engine,
            llm_service=llm_service
        )

    return _bsl_search_service
