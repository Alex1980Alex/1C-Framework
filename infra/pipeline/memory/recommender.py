"""
Recommender for Development Pipeline.

Sprint 3.3.4: History-based recommendations

This module provides functionality for:
- Generating recommendations based on history
- Prioritizing suggestions by relevance
- Tracking recommendation effectiveness
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Set
from enum import Enum
from collections import defaultdict

from models import (
    Recommendation,
    RecommendationType,
    Pattern,
    PatternType,
    ErrorRecord,
    MemoryType,
    LearningContext,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    SearchResult,
    SaveResult,
    SearchMode,
)
from .pattern_saver import PatternMatcher, MatchResult
from .error_learner import ErrorLearner, ErrorCategory


logger = logging.getLogger(__name__)


class RecommendationSource(Enum):
    """Source of a recommendation."""
    PATTERN = "pattern"  # From successful patterns
    ERROR = "error"  # From error prevention
    HISTORY = "history"  # From execution history
    CONTEXT = "context"  # From current context
    USER = "user"  # User-provided preferences


@dataclass
class RecommendationContext:
    """Context for generating recommendations."""

    current_task: Optional[str] = None
    current_agent: Optional[str] = None
    current_file: Optional[str] = None
    code_snippet: Optional[str] = None
    error_context: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def to_query(self) -> str:
        """Convert context to search query."""
        parts = []

        if self.current_task:
            parts.append(self.current_task)
        if self.current_agent:
            parts.append(f"agent:{self.current_agent}")
        if self.keywords:
            parts.extend(self.keywords[:5])
        if self.error_context:
            parts.append(self.error_context[:100])

        return " ".join(parts) if parts else "general development"


@dataclass
class ScoredRecommendation:
    """Recommendation with calculated score."""

    recommendation: Recommendation
    source: RecommendationSource
    base_score: float
    context_bonus: float
    recency_bonus: float
    feedback_bonus: float

    @property
    def final_score(self) -> float:
        """Calculate final recommendation score."""
        return (
            self.base_score * 0.4 +
            self.context_bonus * 0.3 +
            self.recency_bonus * 0.15 +
            self.feedback_bonus * 0.15
        )


@dataclass
class FeedbackRecord:
    """Record of user feedback on a recommendation."""

    recommendation_id: str
    accepted: bool
    helpful: Optional[bool] = None
    timestamp: datetime = field(default_factory=datetime.now)
    comment: Optional[str] = None


class RecommendationEngine:
    """
    Engine for generating and ranking recommendations.

    The engine combines multiple sources:
    1. Pattern-based recommendations
    2. Error prevention recommendations
    3. History-based recommendations
    4. Context-aware recommendations
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
        pattern_matcher: Optional[PatternMatcher] = None,
        error_learner: Optional[ErrorLearner] = None,
        max_recommendations: int = 10,
    ):
        self.memory_client = memory_client
        self.pattern_matcher = pattern_matcher or PatternMatcher(memory_client)
        self.error_learner = error_learner or ErrorLearner(memory_client)
        self.max_recommendations = max_recommendations

        # Feedback tracking
        self._feedback: Dict[str, List[FeedbackRecord]] = defaultdict(list)
        self._acceptance_rates: Dict[str, float] = {}

    async def generate_recommendations(
        self,
        context: RecommendationContext,
        learning_context: Optional[LearningContext] = None,
        recommendation_types: Optional[List[RecommendationType]] = None,
    ) -> List[ScoredRecommendation]:
        """
        Generate recommendations based on context.

        Args:
            context: Recommendation context
            learning_context: Optional learning context
            recommendation_types: Filter by types

        Returns:
            List of scored recommendations
        """
        all_recommendations: List[ScoredRecommendation] = []

        # Gather recommendations from all sources
        if not recommendation_types or RecommendationType.PATTERN_MATCH in recommendation_types:
            pattern_recs = await self._get_pattern_recommendations(
                context, learning_context
            )
            all_recommendations.extend(pattern_recs)

        if not recommendation_types or RecommendationType.ERROR_PREVENTION in recommendation_types:
            error_recs = await self._get_error_recommendations(
                context, learning_context
            )
            all_recommendations.extend(error_recs)

        if not recommendation_types or RecommendationType.BEST_PRACTICE in recommendation_types:
            history_recs = await self._get_history_recommendations(
                context, learning_context
            )
            all_recommendations.extend(history_recs)

        if not recommendation_types or RecommendationType.OPTIMIZATION in recommendation_types:
            context_recs = await self._get_context_recommendations(
                context, learning_context
            )
            all_recommendations.extend(context_recs)

        # Sort by final score
        all_recommendations.sort(key=lambda r: r.final_score, reverse=True)

        # Deduplicate and limit
        seen_titles: Set[str] = set()
        unique_recommendations = []

        for rec in all_recommendations:
            if rec.recommendation.title not in seen_titles:
                seen_titles.add(rec.recommendation.title)
                unique_recommendations.append(rec)

                if len(unique_recommendations) >= self.max_recommendations:
                    break

        return unique_recommendations

    async def _get_pattern_recommendations(
        self,
        context: RecommendationContext,
        learning_context: Optional[LearningContext] = None,
    ) -> List[ScoredRecommendation]:
        """Get recommendations from successful patterns."""
        recommendations = []

        # Search for matching patterns
        matches = await self.pattern_matcher.find_matching_patterns(
            context=context.to_query(),
            learning_context=learning_context,
        )

        for match in matches[:5]:
            pattern = match.pattern

            recommendation = Recommendation(
                id=f"rec_pat_{pattern.id}",
                recommendation_type=RecommendationType.PATTERN_MATCH,
                title=f"Apply pattern: {pattern.name}",
                description=f"Apply proven pattern for: {pattern.problem}",
                action=pattern.solution,
                rationale=(
                    f"This pattern solved similar problem: {pattern.problem}. "
                    f"Success rate: {pattern.success_rate:.0%}"
                ),
                expected_benefit=f"Based on {pattern.success_rate:.0%} success rate in similar cases",
                confidence=match.combined_score,
                priority=self._calculate_priority(match.combined_score),
                source_pattern_id=pattern.id,
            )

            scored = ScoredRecommendation(
                recommendation=recommendation,
                source=RecommendationSource.PATTERN,
                base_score=match.score,
                context_bonus=match.context_relevance,
                recency_bonus=0.5,  # Patterns don't have recency
                feedback_bonus=self._get_feedback_bonus(recommendation.id),
            )

            recommendations.append(scored)

        return recommendations

    async def _get_error_recommendations(
        self,
        context: RecommendationContext,
        learning_context: Optional[LearningContext] = None,
    ) -> List[ScoredRecommendation]:
        """Get recommendations from error prevention."""
        recommendations = []

        # Check for potential errors in code
        if context.code_snippet:
            preventive_recs = await self.error_learner.check_for_potential_errors(
                code=context.code_snippet,
                file_path=context.current_file,
            )

            for rec in preventive_recs[:3]:
                scored = ScoredRecommendation(
                    recommendation=rec,
                    source=RecommendationSource.ERROR,
                    base_score=rec.confidence,
                    context_bonus=0.7,  # High relevance for current code
                    recency_bonus=0.5,
                    feedback_bonus=self._get_feedback_bonus(rec.id),
                )
                recommendations.append(scored)

        # Search for error-related recommendations
        if context.error_context:
            search_results = await self.memory_client.search_memory(
                query=f"prevent {context.error_context}",
                memory_type=MemoryType.ERROR,
                limit=5,
            )

            for result in search_results:
                if result.metadata.get("prevention_hints"):
                    hints = result.metadata["prevention_hints"]
                    for i, hint in enumerate(hints[:2]):
                        rec = Recommendation(
                            id=f"rec_err_{result.id}_{i}",
                            recommendation_type=RecommendationType.ERROR_PREVENTION,
                            title="Error prevention",
                            description="Prevent potential error based on historical data",
                            action=hint,
                            rationale="Based on similar errors in history",
                            expected_benefit="Avoid runtime errors and improve stability",
                            confidence=result.score,
                            priority=2,
                        )

                        scored = ScoredRecommendation(
                            recommendation=rec,
                            source=RecommendationSource.ERROR,
                            base_score=result.score,
                            context_bonus=0.6,
                            recency_bonus=self._calculate_recency_bonus(
                                result.created_at
                            ),
                            feedback_bonus=self._get_feedback_bonus(rec.id),
                        )
                        recommendations.append(scored)

        return recommendations

    async def _get_history_recommendations(
        self,
        context: RecommendationContext,
        learning_context: Optional[LearningContext] = None,
    ) -> List[ScoredRecommendation]:
        """Get recommendations from execution history."""
        recommendations = []

        # Search for successful executions
        query = context.to_query()
        search_results = await self.memory_client.search_memory(
            query=query,
            memory_type=MemoryType.EXECUTION,
            limit=10,
        )

        for result in search_results:
            if result.score < 0.5:
                continue

            # Extract recommendation from execution
            metadata = result.metadata
            if metadata.get("success"):
                action = metadata.get("approach", result.content[:200])
                rationale = f"Previously successful execution (score: {result.score:.2f})"

                rec = Recommendation(
                    id=f"rec_hist_{result.id}",
                    recommendation_type=RecommendationType.BEST_PRACTICE,
                    title="Repeat successful approach",
                    description="Reuse approach that worked in similar context",
                    action=action,
                    rationale=rationale,
                    expected_benefit="High probability of success based on history",
                    confidence=result.score,
                    priority=self._calculate_priority(result.score),
                )

                scored = ScoredRecommendation(
                    recommendation=rec,
                    source=RecommendationSource.HISTORY,
                    base_score=result.score,
                    context_bonus=0.5,
                    recency_bonus=self._calculate_recency_bonus(result.created_at),
                    feedback_bonus=self._get_feedback_bonus(rec.id),
                )
                recommendations.append(scored)

        return recommendations[:3]

    async def _get_context_recommendations(
        self,
        context: RecommendationContext,
        learning_context: Optional[LearningContext] = None,
    ) -> List[ScoredRecommendation]:
        """Get context-aware recommendations."""
        recommendations = []

        # Agent-specific recommendations
        if context.current_agent:
            agent_recs = self._get_agent_recommendations(context.current_agent)
            for rec in agent_recs:
                scored = ScoredRecommendation(
                    recommendation=rec,
                    source=RecommendationSource.CONTEXT,
                    base_score=0.6,
                    context_bonus=0.8,
                    recency_bonus=0.5,
                    feedback_bonus=self._get_feedback_bonus(rec.id),
                )
                recommendations.append(scored)

        # File-type specific recommendations
        if context.current_file:
            file_recs = self._get_file_recommendations(context.current_file)
            for rec in file_recs:
                scored = ScoredRecommendation(
                    recommendation=rec,
                    source=RecommendationSource.CONTEXT,
                    base_score=0.5,
                    context_bonus=0.7,
                    recency_bonus=0.5,
                    feedback_bonus=self._get_feedback_bonus(rec.id),
                )
                recommendations.append(scored)

        return recommendations

    def _get_agent_recommendations(
        self,
        agent: str,
    ) -> List[Recommendation]:
        """Get recommendations specific to an agent."""
        agent_lower = agent.lower()

        agent_tips = {
            "pm-spec": [
                Recommendation(
                    id="rec_ctx_pm_1",
                    recommendation_type=RecommendationType.BEST_PRACTICE,
                    title="Документирование требований",
                    description="Проверка полноты документации требований в spec.md",
                    action="Убедитесь, что все требования задокументированы в spec.md",
                    rationale="PM-SPEC отвечает за полноту требований",
                    expected_benefit="Уменьшение недопонимания и переделок",
                    confidence=0.7,
                    priority=2,
                ),
            ],
            "architect": [
                Recommendation(
                    id="rec_ctx_arch_1",
                    recommendation_type=RecommendationType.BEST_PRACTICE,
                    title="Проверка архитектуры",
                    description="Верификация архитектурного дизайна на соответствие стандартам",
                    action="Проверьте соответствие design.md стандартам проекта",
                    rationale="ARCHITECT отвечает за архитектурные решения",
                    expected_benefit="Согласованность архитектуры проекта",
                    confidence=0.7,
                    priority=2,
                ),
            ],
            "implementer": [
                Recommendation(
                    id="rec_ctx_impl_1",
                    recommendation_type=RecommendationType.OPTIMIZATION,
                    title="Проверка производительности",
                    description="Анализ производительности критических участков кода",
                    action="Проверьте производительность критических путей",
                    rationale="IMPLEMENTER должен учитывать производительность",
                    expected_benefit="Оптимальная производительность решения",
                    confidence=0.6,
                    priority=3,
                ),
            ],
            "qa": [
                Recommendation(
                    id="rec_ctx_qa_1",
                    recommendation_type=RecommendationType.BEST_PRACTICE,
                    title="Покрытие тестами",
                    description="Проверка полноты тестового покрытия включая edge cases",
                    action="Проверьте покрытие edge cases в тестах",
                    rationale="QA отвечает за качество тестирования",
                    expected_benefit="Высокое качество и надежность кода",
                    confidence=0.7,
                    priority=2,
                ),
            ],
        }

        for key, recs in agent_tips.items():
            if key in agent_lower:
                return recs

        return []

    def _get_file_recommendations(
        self,
        file_path: str,
    ) -> List[Recommendation]:
        """Get recommendations based on file type."""
        recommendations = []

        if file_path.endswith('.bsl'):
            recommendations.append(Recommendation(
                id="rec_ctx_bsl_1",
                recommendation_type=RecommendationType.BEST_PRACTICE,
                title="BSL Best Practices",
                description="Рекомендации по обработке ошибок в BSL коде",
                action="Используйте Попытка/Исключение для обработки ошибок",
                rationale="Стандартная практика для BSL кода",
                expected_benefit="Надежная обработка исключительных ситуаций",
                confidence=0.6,
                priority=3,
            ))

        if 'Module.bsl' in file_path:
            recommendations.append(Recommendation(
                id="rec_ctx_module_1",
                recommendation_type=RecommendationType.BEST_PRACTICE,
                title="Модульная структура",
                description="Организация кода модуля с использованием регионов",
                action="Группируйте связанные процедуры в регионы",
                rationale="Улучшает читаемость модуля",
                expected_benefit="Повышенная читаемость и поддерживаемость",
                confidence=0.5,
                priority=4,
            ))

        return recommendations

    def _calculate_priority(self, score: float) -> int:
        """Calculate recommendation priority from score."""
        if score >= 0.8:
            return 1
        elif score >= 0.6:
            return 2
        elif score >= 0.4:
            return 3
        else:
            return 4

    def _calculate_recency_bonus(
        self,
        created_at: Optional[str],
    ) -> float:
        """Calculate recency bonus for a recommendation."""
        if not created_at:
            return 0.5

        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age = datetime.now(created.tzinfo) - created

            if age < timedelta(days=1):
                return 1.0
            elif age < timedelta(days=7):
                return 0.8
            elif age < timedelta(days=30):
                return 0.6
            else:
                return 0.3
        except Exception:
            return 0.5

    def _get_feedback_bonus(self, recommendation_id: str) -> float:
        """Get feedback bonus for a recommendation."""
        if recommendation_id in self._acceptance_rates:
            return self._acceptance_rates[recommendation_id]

        # Check feedback history
        feedback_list = self._feedback.get(recommendation_id, [])
        if not feedback_list:
            return 0.5  # Neutral

        accepted = sum(1 for f in feedback_list if f.accepted)
        helpful = sum(1 for f in feedback_list if f.helpful)

        acceptance_rate = accepted / len(feedback_list)
        helpfulness_rate = helpful / len(feedback_list) if any(
            f.helpful is not None for f in feedback_list
        ) else 0.5

        bonus = acceptance_rate * 0.6 + helpfulness_rate * 0.4
        self._acceptance_rates[recommendation_id] = bonus

        return bonus

    def record_feedback(
        self,
        recommendation_id: str,
        accepted: bool,
        helpful: Optional[bool] = None,
        comment: Optional[str] = None,
    ) -> None:
        """
        Record user feedback on a recommendation.

        Args:
            recommendation_id: ID of the recommendation
            accepted: Whether user accepted the recommendation
            helpful: Whether the recommendation was helpful
            comment: Optional feedback comment
        """
        feedback = FeedbackRecord(
            recommendation_id=recommendation_id,
            accepted=accepted,
            helpful=helpful,
            comment=comment,
        )

        self._feedback[recommendation_id].append(feedback)

        # Invalidate cached acceptance rate
        self._acceptance_rates.pop(recommendation_id, None)

        logger.info(
            f"Recorded feedback for {recommendation_id}: "
            f"accepted={accepted}, helpful={helpful}"
        )


class Recommender:
    """
    Main recommender class for the development pipeline.

    Provides a high-level interface for:
    - Getting recommendations for current context
    - Recording feedback
    - Tracking recommendation effectiveness
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
        engine: Optional[RecommendationEngine] = None,
    ):
        self.memory_client = memory_client
        self.engine = engine or RecommendationEngine(memory_client)

    async def get_recommendations(
        self,
        task: Optional[str] = None,
        agent: Optional[str] = None,
        file_path: Optional[str] = None,
        code: Optional[str] = None,
        error: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        learning_context: Optional[LearningContext] = None,
        limit: int = 5,
    ) -> List[Recommendation]:
        """
        Get recommendations for current context.

        Args:
            task: Current task description
            agent: Current agent name
            file_path: Current file path
            code: Current code snippet
            error: Error context if any
            keywords: Relevant keywords
            learning_context: Optional learning context
            limit: Maximum recommendations

        Returns:
            List of recommendations sorted by priority
        """
        context = RecommendationContext(
            current_task=task,
            current_agent=agent,
            current_file=file_path,
            code_snippet=code,
            error_context=error,
            keywords=keywords or [],
        )

        scored_recs = await self.engine.generate_recommendations(
            context=context,
            learning_context=learning_context,
        )

        # Return just the recommendations, sorted by priority
        recommendations = [sr.recommendation for sr in scored_recs[:limit]]
        recommendations.sort(key=lambda r: r.priority)

        return recommendations

    def accept_recommendation(
        self,
        recommendation_id: str,
        helpful: Optional[bool] = None,
    ) -> None:
        """Record that a recommendation was accepted."""
        self.engine.record_feedback(
            recommendation_id=recommendation_id,
            accepted=True,
            helpful=helpful,
        )

    def reject_recommendation(
        self,
        recommendation_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Record that a recommendation was rejected."""
        self.engine.record_feedback(
            recommendation_id=recommendation_id,
            accepted=False,
            helpful=False,
            comment=reason,
        )

    async def save_recommendation(
        self,
        recommendation: Recommendation,
    ) -> SaveResult:
        """Save a recommendation to memory."""
        return await self.memory_client.save_recommendation(recommendation)

    def get_statistics(self) -> Dict[str, Any]:
        """Get recommender statistics."""
        return {
            "feedback_count": sum(
                len(f) for f in self.engine._feedback.values()
            ),
            "recommendations_with_feedback": len(self.engine._feedback),
            "average_acceptance_rate": (
                sum(self.engine._acceptance_rates.values()) /
                len(self.engine._acceptance_rates)
                if self.engine._acceptance_rates else 0.5
            ),
        }
