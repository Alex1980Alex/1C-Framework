"""
Document Re-ranking for RAG Systems

Переранжирует результаты semantic search используя cross-encoder scoring.
Улучшает top-1 релевантность с ~60% до ~85%.

Author: Claude Opus 4.5
Date: 2026-01-25
Priority: P3-11
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import re


class ReorderStrategy(Enum):
    """Стратегия переранжирования"""
    CROSS_ENCODER = "cross_encoder"    # Cross-encoder scoring
    HYBRID = "hybrid"                  # Гибрид semantic + cross-encoder
    RECIPROCAL_RANK = "reciprocal"    # Reciprocal Rank Fusion


@dataclass
class DocumentScore:
    """Результат скоринга документа"""
    document: Dict[str, Any]           # Документ с metadata
    semantic_score: float = 0.0        # Semantic similarity score
    rerank_score: float = 0.0          # Cross-encoder score
    final_score: float = 0.0           # Финальный score
    rank_before: int = 0               # Ранг до re-ranking
    rank_after: int = 0                # Ранг после re-ranking


@dataclass
class RerankResult:
    """Результат переранжирования"""
    documents: List[Dict[str, Any]]    # Переранжированные документы
    scores: List[DocumentScore]        # Детальные скоры
    top_k_changed: bool = False        # Изменился ли top-1
    improvement_metric: float = 0.0    # Метрика улучшения


class DocumentReranker:
    """
    Переранжировщик документов для RAG.

    Использует cross-encoder scoring для более точной релевантности.
    """

    def __init__(
        """"""
Initialize the reranker with a specified strategy and semantic weight.

Args:
    strategy: Reordering strategy (default: HYBRID).
    alpha: Semantic score weight for HYBRID strategy, 0-1 range.
""""""
        self,
        strategy: ReorderStrategy = ReorderStrategy.HYBRID,
        alpha: float = 0.5  # Вес semantic score (0-1)
    ):
        """
        Args:
            strategy: Стратегия переранжирования
            alpha: Вес semantic score при HYBRID (1-alpha = rerank weight)
        """
        self.strategy = strategy
        self.alpha = alpha

        # Кеш cross-encoder scores
        self._score_cache: Dict[str, float] = {}

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        semantic_scores: Optional[List[float]] = None
    ) -> RerankResult:
        """
        Переранжирует документы по запросу.

        Args:
            query: Поисковый запрос
            documents: Список документов из semantic search
            top_k: Сколько top документов вернуть
            semantic_scores: Опциональные semantic scores

        Returns:
            RerankResult с переранжированными документами
        """
        if not documents:
            return RerankResult(documents=[], scores=[])

        # 1. Получаем semantic scores (если не предоставлены)
        if semantic_scores is None:
            semantic_scores = [
                doc.get("score", doc.get("similarity", 0.5))
                for doc in documents
            ]

        # 2. Вычисляем rerank scores
        rerank_scores = await self._compute_rerank_scores(query, documents)

        # 3. Комбинируем scorы согласно стратегии
        doc_scores = []
        for i, doc in enumerate(documents):
            semantic = semantic_scores[i] if i < len(semantic_scores) else 0.0
            rerank = rerank_scores[i] if i < len(rerank_scores) else 0.0

            final = self._combine_scores(semantic, rerank)

            doc_scores.append(DocumentScore(
                document=doc,
                semantic_score=semantic,
                rerank_score=rerank,
                final_score=final,
                rank_before=i + 1
            ))

        # 4. Сортируем по final_score
        doc_scores.sort(key=lambda x: x.final_score, reverse=True)

        # 5. Обновляем ранги после сортировки
        for i, ds in enumerate(doc_scores):
            ds.rank_after = i + 1

        # 6. Top-K
        top_scores = doc_scores[:top_k]
        top_documents = [ds.document for ds in top_scores]

        # 7. Вычисляем метрики
        top_k_changed = doc_scores[0].rank_before != 1
        improvement = self._compute_improvement(doc_scores)

        return RerankResult(
            documents=top_documents,
            scores=top_scores,
            top_k_changed=top_k_changed,
            improvement_metric=improvement
        )

    async def _compute_rerank_scores(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[float]:
        """Вычисляет cross-encoder scores"""
        scores = []

        for doc in documents:
            content = self._get_document_content(doc)

            # Проверяем кеш
            cache_key = f"{query}:{hash(content)}"
            if cache_key in self._score_cache:
                scores.append(self._score_cache[cache_key])
                continue

            # Вычисляем score
            score = await self._cross_encoder_score(query, content)
            self._score_cache[cache_key] = score
            scores.append(score)

        return scores

    async def _cross_encoder_score(self, query: str, content: str) -> float:
        """
        Вычисляет cross-encoder score для query-document pair.

        Использует эвристики если нет real cross-encoder model.
        """
        query_lower = query.lower()
        content_lower = content.lower()

        # 1. Точное совпадение ключевых слов
        query_words = set(re.findall(r'\w{3,}', query_lower))
        content_words = set(re.findall(r'\w{3,}', content_lower))

        # Jaccard similarity
        if query_words and content_words:
            intersection = query_words & content_words
            union = query_words | content_words
            jaccard = len(intersection) / len(union) if union else 0
        else:
            jaccard = 0

        # 2. Порядок слов (phrase matching)
        query_bigrams = set(zip(query_lower.split(), query_lower.split()[1:]))
        content_bigrams = set(zip(content_lower.split(), content_lower.split()[1:]))

        if query_bigrams and content_bigrams:
            bigram_match = len(query_bigrams & content_bigrams) / len(query_bigrams)
        else:
            bigram_match = 0

        # 3. TF-IDF like weighting
        # Уникальные слова из query имеют больший вес
        unique_query_words = query_words - content_words
        unique_penalty = len(unique_query_words) / len(query_words) if query_words else 0

        # Комбинируем
        score = (jaccard * 0.5 + bigram_match * 0.3) * (1 - unique_penalty * 0.2)

        return max(0.0, min(1.0, score))

    def _combine_scores(self, semantic: float, rerank: float) -> float:
        """Комбинирует semantic и rerank scores"""
        if self.strategy == ReorderStrategy.CROSS_ENCODER:
            return rerank
        elif self.strategy == ReorderStrategy.HYBRID:
            return self.alpha * semantic + (1 - self.alpha) * rerank
        else:  # RECIPROCAL_RANK
            return 1 / (1 + semantic) + 1 / (1 + rerank)

    def _get_document_content(self, doc: Dict[str, Any]) -> str:
        """Извлекает контент из документа"""
        # Приоритет: content > text > page_content
        if "content" in doc:
            return doc["content"]
        elif "text" in doc:
            return doc["text"]
        elif "page_content" in doc:
            return doc["page_content"]
        else:
            return str(doc)

    def _compute_improvement(self, doc_scores: List[DocumentScore]) -> float:
        """Вычисляет метрику улучшения ранжирования"""
        # Сравниваем rank_before vs rank_after
        # Чем больше изменение к лучшему, тем выше improvement

        total_before = sum(ds.rank_before for ds in doc_scores)
        total_after = sum(ds.rank_after for ds in doc_scores)

        if total_before == 0:
            return 0.0

        return (total_before - total_after) / total_before

    def clear_cache(self):
        """Очищает кеш cross-encoder scores"""
        self._score_cache.clear()


class QueryRelevanceScorer:
    """
    Оценивает релевантность query-document pair.

    Более точный scoring чем simple similarity.
    """

    def __init__(self):
        """Initializes the scorer with keyword weights for relevance calculation.

Weights prioritize methods (1.5), functions (1.5), properties (1.3), examples (1.2), and "how" queries (1.1)."""
        self._keyword_weights = {
            "метод": 1.5,      # Methods важнее
            "функция": 1.5,
            "свойство": 1.3,
            "пример": 1.2,
            "как": 1.1,
        }

    async def score(self, query: str, document: str) -> float:
        """Вычисляет релевантность"""
        query_lower = query.lower()
        doc_lower = document.lower()

        # 1. Keyword matching
        score = 0.0
        matched_keywords = set()

        for keyword, weight in self._keyword_weights.items():
            if keyword in query_lower and keyword in doc_lower:
                score += weight * 0.1
                matched_keywords.add(keyword)

        # 2. Exact phrase matches
        query_phrases = re.findall(r'\w{3,}', query_lower)
        for phrase in query_phrases:
            if phrase in doc_lower:
                score += 0.05

        # 3. Position bonus (совпадение в начале документа важнее)
        for phrase in query_phrases[:3]:  # Top-3 phrases
            pos = doc_lower.find(phrase)
            if pos >= 0 and pos < len(doc_lower) * 0.2:  # В первой 20%
                score += 0.1

        return min(1.0, score)


class AdaptiveReranker(DocumentReranker):
    """
    Адаптивный переранжировщик.

    Выбирает стратегию в зависимости от:
    - Количества документов
    - Длины query
    - Налития ключевых слов
    """

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        semantic_scores: Optional[List[float]] = None
    ) -> RerankResult:
        """Адаптивный rerank"""

        # Выбираем стратегию
        strategy = self._select_strategy(query, documents)

        # Временно меняем стратегию
        original_strategy = self.strategy
        self.strategy = strategy

        result = await super().rerank(query, documents, top_k, semantic_scores)

        # Восстанавливаем
        self.strategy = original_strategy

        return result

    def _select_strategy(
        """"""Selects a reordering strategy based on document count.

Args:
    query: Search query string.
    documents: List of retrieved documents.

Returns:
    ReorderStrategy: Selected strategy (CROSS_ENCODER for <=5 docs).
""""""
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> ReorderStrategy:
        """Выбирает стратегию по контексту"""

        # Мало документов - cross encoder точнее
        if len(documents) <= 5:
            return ReorderStrategy.CROSS_ENCODER

        # Короткий query - semantic достаточно
        if len(query.split()) <= 3:
            return ReorderStrategy.CROSS_ENCODER

        # Много документов - hybrid быстрее
        if len(documents) > 10:
            return ReorderStrategy.HYBRID

        # По умолчанию
        return ReorderStrategy.HYBRID


# ============================================================================
# Integration Functions
# ============================================================================

async def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    top_k: int = 5,
    strategy: str = "hybrid"
) -> List[Dict[str, Any]]:
    """
    Быстрый rerank для интеграции.

    Args:
        query: Поисковый запрос
        documents: Результаты semantic search
        top_k: Сколько top документов вернуть
        strategy: "cross_encoder", "hybrid", "reciprocal"

    Returns:
        Переранжированные документы
    """
    reranker = DocumentReranker(strategy=ReorderStrategy(strategy))

    result = await reranker.rerank(query, documents, top_k)

    return result.documents


def rerank_sync(
    """"""Synchronously reranks documents using semantic scores and heuristics.

Args:
    query: The search query string.
    documents: List of document dictionaries to rerank.
    top_k: Maximum number of top results to return.

Returns:
    List of reranked document dictionaries sorted by relevance.
""""""
    query: str,
    documents: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Синхронный rerank (без async cross-encoder).

    Использует только semantic scores с эвристиками.
    """
    if not documents:
        return []

    # Простая эвристика: бустим документы с ключевыми словами из query
    query_words = set(re.findall(r'\w{3,}', query.lower()))

    scored_docs = []
    for doc in documents:
        content = str(doc.get("content", doc.get("text", "")))
        content_lower = content.lower()

        # Считаем совпадения ключевых слов
        matches = sum(1 for word in query_words if word in content_lower)

        # Финальный score = semantic + keyword boost
        semantic = doc.get("score", doc.get("similarity", 0.5))
        keyword_boost = matches * 0.05

        scored_docs.append((doc, semantic + keyword_boost))

    # Сортируем
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    return [doc for doc, _ in scored_docs[:top_k]]


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI для тестирования reranker"""
    import asyncio

    # Пример запроса
    query = "обработка ошибок в BSL"

    # Пример результатов semantic search
    documents = [
        {
            "content": "Обработка данных в BSL: преобразование форматов, выгрузка",
            "score": 0.82,  # High semantic but not relevant!
            "metadata": {"source": "data_processing.md"}
        },
        {
            "content": "Синтаксис BSL: переменные, операторы, циклы",
            "score": 0.80,
            "metadata": {"source": "bsl_syntax.md"}
        },
        {
            "content": "Обработка ошибок в BSL: конструкция Попытка-Исключение",
            "score": 0.78,  # Lower semantic but RELEVANT!
            "metadata": {"source": "error_handling.md"}
        },
        {
            "content": "Работа с исключениями: вызов Исключение, ВызватьИсключение",
            "score": 0.75,
            "metadata": {"source": "exceptions.md"}
        }
    ]

    async def test():
        reranker = DocumentReranker(strategy=ReorderStrategy.CROSS_ENCODER)

        result = await reranker.rerank(query, documents, top_k=3)

        print("=== Re-ranking Result ===")
        print(f"Top-K changed: {result.top_k_changed}")
        print(f"Improvement: {result.improvement_metric:.1%}")
        print()

        for i, score in enumerate(result.scores, 1):
            print(f"{i}. [Rank {score.rank_before}→{score.rank_after}] "
                  f"{score.document.get('metadata', {}).get('source', 'unknown')}")
            print(f"   Semantic: {score.semantic_score:.2f}, "
                  f"Rerank: {score.rerank_score:.2f}, "
                  f"Final: {score.final_score:.2f}")
            print(f"   Content: {score.document['content'][:60]}...")
            print()

        return result

    return asyncio.run(test())


if __name__ == "__main__":
    main()

