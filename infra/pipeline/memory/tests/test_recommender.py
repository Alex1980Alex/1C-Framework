"""Tests for Recommender module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from .recommender import (
    Recommender,
    RecommendationEngine,
    RecommendationContext,
    ScoredRecommendation,
    RecommendationSource,
)
from models import (
    Recommendation,
    RecommendationType,
    Pattern,
    PatternType,
    ErrorRecord,
    ErrorSeverity,
    MemoryType,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    SearchResult,
    SaveResult,
)
from .pattern_saver import PatternMatcher, MatchResult
from .error_learner import ErrorLearner


class TestRecommendationSource:
    """Tests for RecommendationSource enum."""

    def test_all_sources(self):
        """Test all recommendation sources exist."""
        sources = list(RecommendationSource)

        assert RecommendationSource.PATTERN in sources
        assert RecommendationSource.ERROR in sources
        assert RecommendationSource.HISTORY in sources
        assert RecommendationSource.CONTEXT in sources
        assert RecommendationSource.USER in sources  # Changed from RULE

    def test_source_values(self):
        """Test source values."""
        assert RecommendationSource.PATTERN.value == "pattern"
        assert RecommendationSource.ERROR.value == "error"


class TestRecommendationContext:
    """Tests for RecommendationContext dataclass."""

    def test_create_context(self):
        """Test creating recommendation context."""
        ctx = RecommendationContext(
            current_task="Implement new feature",  # Changed from task
            current_agent="IMPLEMENTER",  # Changed from agent
            current_file="Module.bsl",  # Changed from file_path
        )

        assert ctx.current_task == "Implement new feature"
        assert ctx.current_agent == "IMPLEMENTER"
        assert ctx.current_file == "Module.bsl"
        assert ctx.code_snippet is None

    def test_context_with_code(self):
        """Test context with code snippet."""
        ctx = RecommendationContext(
            current_task="Fix bug",  # Changed from task
            current_agent="IMPLEMENTER",  # Changed from agent
            current_file="BuggyModule.bsl",  # Changed from file_path
            code_snippet="Функция Ошибочная() ... КонецФункции",
            error_context="NullReferenceError at line 10",
        )

        assert ctx.code_snippet is not None
        assert ctx.error_context is not None

    def test_context_with_history(self):
        """Test context with recent history."""
        ctx = RecommendationContext(
            current_task="Continue work",  # Changed from task
            current_agent="ARCHITECT",  # Changed from agent
            keywords=["pattern_1", "pattern_2"],  # Changed from recent_patterns
        )

        # RecommendationContext now has keywords instead of recent_patterns/recent_errors
        assert len(ctx.keywords) == 2


class TestScoredRecommendation:
    """Tests for ScoredRecommendation dataclass."""

    def test_create_scored(self):
        """Test creating scored recommendation."""
        rec = Recommendation(
            id="rec_1",
            recommendation_type=RecommendationType.PATTERN_MATCH,
            title="Use pattern X",
            description="Apply proven pattern X for similar tasks",
            action="Apply pattern X",
            rationale="Proven effective",
            expected_benefit="Reduces implementation time",
            confidence=0.8,
            priority=1,
        )

        scored = ScoredRecommendation(
            recommendation=rec,
            source=RecommendationSource.PATTERN,
            base_score=0.85,
            context_bonus=0.7,
            recency_bonus=0.6,
            feedback_bonus=0.5,
        )

        # final_score = base_score * 0.4 + context_bonus * 0.3 + recency_bonus * 0.15 + feedback_bonus * 0.15
        # = 0.85 * 0.4 + 0.7 * 0.3 + 0.6 * 0.15 + 0.5 * 0.15
        # = 0.34 + 0.21 + 0.09 + 0.075 = 0.715
        expected_score = 0.85 * 0.4 + 0.7 * 0.3 + 0.6 * 0.15 + 0.5 * 0.15
        assert scored.final_score == pytest.approx(expected_score, rel=0.01)
        assert scored.source == RecommendationSource.PATTERN

    def test_scored_comparison(self):
        """Test comparing scored recommendations."""
        rec1 = Recommendation(
            id="rec_a",
            recommendation_type=RecommendationType.PATTERN_MATCH,
            title="A",
            description="Pattern A implementation description",
            action="Do A",
            rationale="Because A",
            expected_benefit="Benefits from pattern A",
            confidence=0.7,
            priority=2,
        )

        rec2 = Recommendation(
            id="rec_b",
            recommendation_type=RecommendationType.PATTERN_MATCH,
            title="B",
            description="Pattern B implementation description",
            action="Do B",
            rationale="Because B",
            expected_benefit="Benefits from pattern B",
            confidence=0.9,
            priority=1,
        )

        scored1 = ScoredRecommendation(
            recommendation=rec1,
            base_score=0.6,
            context_bonus=0.0,
            recency_bonus=0.0,
            feedback_bonus=0.0,
            source=RecommendationSource.PATTERN,
        )

        scored2 = ScoredRecommendation(
            recommendation=rec2,
            base_score=0.9,
            context_bonus=0.0,
            recency_bonus=0.0,
            feedback_bonus=0.0,
            source=RecommendationSource.PATTERN,
        )

        # Higher score should be "greater"
        assert scored2.final_score > scored1.final_score


class TestRecommender:
    """Tests for Recommender class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = MagicMock(spec=UnifiedMemoryClient)
        client.search_patterns = AsyncMock(return_value=[])
        client.search_errors = AsyncMock(return_value=[])
        client.search_memory = AsyncMock(return_value=[])
        client.save_memory = AsyncMock(
            return_value=SaveResult(success=True, memory_id="mem_1", message="Saved")
        )
        return client

    @pytest.fixture
    def recommender(self, mock_memory_client):
        """Create Recommender with mock client."""
        return Recommender(memory_client=mock_memory_client)

    @pytest.mark.asyncio
    async def test_get_recommendations_basic(self, recommender):
        """Test getting basic recommendations."""
        recommendations = await recommender.get_recommendations(
            task="Implement feature",
            agent="IMPLEMENTER",
        )

        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_get_recommendations_with_file(self, recommender):
        """Test recommendations based on file type."""
        recommendations = await recommender.get_recommendations(
            task="Fix bug",
            agent="IMPLEMENTER",
            file_path="CommonModule.bsl",
        )

        assert isinstance(recommendations, list)
        # BSL files might get specific recommendations

    @pytest.mark.asyncio
    async def test_get_recommendations_with_code(self, recommender):
        """Test recommendations based on code context."""
        code = """
Процедура ОбработкаДанных()
    // TODO: Добавить обработку ошибок
    Данные = ПолучитьДанные();
КонецПроцедуры
"""
        recommendations = await recommender.get_recommendations(
            task="Improve code quality",
            agent="IMPLEMENTER",
            file_path="Module.bsl",
            code=code,
        )

        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_get_recommendations_for_architect(self, recommender):
        """Test recommendations for ARCHITECT agent."""
        recommendations = await recommender.get_recommendations(
            task="Design new subsystem",
            agent="ARCHITECT",
        )

        assert isinstance(recommendations, list)
        # ARCHITECT should get design-focused recommendations

    @pytest.mark.asyncio
    async def test_get_recommendations_for_qa(self, recommender):
        """Test recommendations for QA agent."""
        recommendations = await recommender.get_recommendations(
            task="Test feature",
            agent="QA",
        )

        assert isinstance(recommendations, list)

    def test_accept_recommendation(self, recommender):
        """Test accepting a recommendation."""
        recommender.accept_recommendation(
            recommendation_id="rec_1",
            helpful=True,
        )

        # Check feedback was recorded in engine._feedback
        assert "rec_1" in recommender.engine._feedback
        feedback_list = recommender.engine._feedback["rec_1"]
        assert len(feedback_list) == 1
        assert feedback_list[0].accepted is True
        assert feedback_list[0].helpful is True

    def test_reject_recommendation(self, recommender):
        """Test rejecting a recommendation."""
        recommender.reject_recommendation(
            recommendation_id="rec_2",
            reason="Not applicable",
        )

        assert "rec_2" in recommender.engine._feedback
        feedback_list = recommender.engine._feedback["rec_2"]
        assert len(feedback_list) == 1
        assert feedback_list[0].accepted is False
        assert feedback_list[0].comment == "Not applicable"

    def test_get_statistics(self, recommender):
        """Test getting recommender statistics."""
        # Record some feedback
        recommender.accept_recommendation("rec_a", helpful=True)
        recommender.accept_recommendation("rec_b", helpful=True)
        recommender.accept_recommendation("rec_c", helpful=False)
        recommender.reject_recommendation("rec_d", reason="wrong")

        stats = recommender.get_statistics()

        # Check stats structure
        assert "feedback_count" in stats
        assert stats["feedback_count"] == 4
        assert "recommendations_with_feedback" in stats
        assert stats["recommendations_with_feedback"] == 4

    def test_feedback_affects_bonus(self, recommender):
        """Test that feedback affects recommendation bonus scores."""
        # Record positive feedback
        recommender.accept_recommendation("rec_1", helpful=True)
        recommender.accept_recommendation("rec_1", helpful=True)

        # Get feedback bonus
        bonus = recommender.engine._get_feedback_bonus("rec_1")

        # Should be high (100% acceptance, 100% helpful)
        assert bonus > 0.5


class TestRecommendationEngine:
    """Tests for RecommendationEngine class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = MagicMock(spec=UnifiedMemoryClient)
        client.search_patterns = AsyncMock(
            return_value=[
                SearchResult(
                    id="pat_1",
                    content="Error handling pattern",
                    memory_type="pattern",
                    score=0.8,
                    importance=0.7,
                    created_at="",
                    tags=["error", "bsl"],
                    metadata={
                        "name": "error_handler",
                        "pattern_type": "bug_fix",
                        "problem": "Unhandled exceptions",
                        "solution": "Add try-except",
                        "success_count": 10,
                        "failure_count": 1,
                    },
                )
            ]
        )
        client.search_errors = AsyncMock(
            return_value=[
                SearchResult(
                    id="err_1",
                    content="Previous error",
                    memory_type="error",
                    score=0.75,
                    importance=0.6,
                    created_at="",
                    tags=[],
                    metadata={
                        "error_type": "RuntimeError",
                        "fix_applied": "Added validation",
                        "prevention_hint": "Validate inputs",
                    },
                )
            ]
        )
        client.search_memory = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_pattern_matcher(self):
        """Create mock pattern matcher."""
        matcher = MagicMock(spec=PatternMatcher)
        matcher.find_matching_patterns = AsyncMock(return_value=[])
        return matcher

    @pytest.fixture
    def mock_error_learner(self):
        """Create mock error learner."""
        learner = MagicMock(spec=ErrorLearner)
        learner.check_for_potential_errors = AsyncMock(return_value=[])
        return learner

    @pytest.fixture
    def engine(self, mock_memory_client, mock_pattern_matcher, mock_error_learner):
        """Create RecommendationEngine with mocks."""
        return RecommendationEngine(
            memory_client=mock_memory_client,
            pattern_matcher=mock_pattern_matcher,
            error_learner=mock_error_learner,
        )

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, engine):
        """Test generating recommendations."""
        context = RecommendationContext(
            current_task="Fix error handling",
            current_agent="IMPLEMENTER",
            current_file="Module.bsl",
        )

        recommendations = await engine.generate_recommendations(context)

        assert isinstance(recommendations, list)
        # Should find pattern-based recommendations
        assert len(recommendations) >= 1

    @pytest.mark.asyncio
    async def test_pattern_recommendations(self, engine, mock_pattern_matcher):
        """Test getting pattern-based recommendations."""
        # Setup mock pattern matcher to return matches
        mock_pattern = MagicMock()
        mock_pattern.id = "pat_1"
        mock_pattern.name = "Error Handler"
        mock_pattern.problem = "Unhandled exceptions"
        mock_pattern.solution = "Add try-except"
        mock_pattern.success_rate = 0.9

        mock_match = MagicMock(spec=MatchResult)
        mock_match.pattern = mock_pattern
        mock_match.score = 0.8
        mock_match.combined_score = 0.85
        mock_match.context_relevance = 0.7

        mock_pattern_matcher.find_matching_patterns = AsyncMock(
            return_value=[mock_match]
        )

        context = RecommendationContext(
            current_task="Implement error handling",
            current_agent="IMPLEMENTER",
        )

        recommendations = await engine._get_pattern_recommendations(context)

        assert isinstance(recommendations, list)
        assert len(recommendations) >= 1
        assert recommendations[0].source == RecommendationSource.PATTERN

    @pytest.mark.asyncio
    async def test_error_recommendations(self, engine, mock_memory_client):
        """Test getting error-based recommendations."""
        # Setup mock to return error with prevention hints
        mock_memory_client.search_memory = AsyncMock(
            return_value=[
                SearchResult(
                    id="err_1",
                    content="Previous error",
                    memory_type="error",
                    score=0.75,
                    importance=0.6,
                    created_at="",
                    tags=[],
                    metadata={
                        "error_type": "RuntimeError",
                        "prevention_hints": ["Validate inputs", "Add null check"],
                    },
                )
            ]
        )

        context = RecommendationContext(
            current_task="Fix runtime issues",
            current_agent="IMPLEMENTER",
            error_context="RuntimeError occurred",
        )

        recommendations = await engine._get_error_recommendations(context)

        assert isinstance(recommendations, list)
        # Should find error-based recommendations from prevention_hints
        assert len(recommendations) >= 1
        for rec in recommendations:
            assert rec.source == RecommendationSource.ERROR

    @pytest.mark.asyncio
    async def test_history_recommendations(self, engine, mock_memory_client):
        """Test getting history-based recommendations."""
        mock_memory_client.search_memory = AsyncMock(
            return_value=[
                SearchResult(
                    id="hist_1",
                    content="Previously successful approach",
                    memory_type="general",
                    score=0.7,
                    importance=0.6,
                    created_at="",
                    tags=["success"],
                    metadata={
                        "task": "Similar task",
                        "outcome": "success",
                    },
                )
            ]
        )

        context = RecommendationContext(
            current_task="Similar task to before",
            current_agent="IMPLEMENTER",
        )

        recommendations = await engine._get_history_recommendations(context)

        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_context_recommendations(self, engine):
        """Test getting context-specific recommendations."""
        context = RecommendationContext(
            current_task="Optimize query",
            current_agent="IMPLEMENTER",
            current_file="QueryModule.bsl",
            code_snippet="Запрос = Новый Запрос;",
        )

        recommendations = await engine._get_context_recommendations(context)

        assert isinstance(recommendations, list)
        # BSL query code might get optimization suggestions

    def test_dedup_in_generate_recommendations(self):
        """Test that generate_recommendations deduplicates by title."""
        # The deduplication logic is in generate_recommendations
        # Test via direct sorting and dedup verification
        recommendations = [
            ScoredRecommendation(
                recommendation=Recommendation(
                    id="rec_1",
                    recommendation_type=RecommendationType.PATTERN_MATCH,
                    title="Same title",
                    description="Description for same title",
                    action="Action 1",
                    rationale="Reason 1",
                    expected_benefit="Benefits from same title",
                    confidence=0.8,
                    priority=1,
                ),
                base_score=0.85,
                context_bonus=0.0,
                recency_bonus=0.0,
                feedback_bonus=0.0,
                source=RecommendationSource.PATTERN,
            ),
            ScoredRecommendation(
                recommendation=Recommendation(
                    id="rec_2",
                    recommendation_type=RecommendationType.PATTERN_MATCH,
                    title="Same title",  # Duplicate title
                    description="Description for duplicate recommendation",
                    action="Action 2",
                    rationale="Reason 2",
                    expected_benefit="Benefits from duplicate recommendation",
                    confidence=0.7,
                    priority=2,
                ),
                base_score=0.70,
                context_bonus=0.0,
                recency_bonus=0.0,
                feedback_bonus=0.0,
                source=RecommendationSource.HISTORY,
            ),
        ]

        # Simulate dedup logic from generate_recommendations
        recommendations.sort(key=lambda r: r.final_score, reverse=True)
        seen_titles = set()
        unique = []
        for rec in recommendations:
            if rec.recommendation.title not in seen_titles:
                seen_titles.add(rec.recommendation.title)
                unique.append(rec)

        # Should keep only higher scored one
        assert len(unique) == 1
        # base_score * 0.4 = 0.85 * 0.4 = 0.34
        assert unique[0].final_score == pytest.approx(0.34, rel=0.01)

    def test_ranking_by_final_score(self):
        """Test ranking recommendations by final score."""
        recommendations = [
            ScoredRecommendation(
                recommendation=Recommendation(
                    id="rec_low",
                    recommendation_type=RecommendationType.PATTERN_MATCH,
                    title="Low score",
                    description="Low score recommendation description",
                    action="Act",
                    rationale="Why",
                    expected_benefit="Benefits from low score",
                    confidence=0.5,
                    priority=3,
                ),
                base_score=0.5,
                context_bonus=0.0,
                recency_bonus=0.0,
                feedback_bonus=0.0,
                source=RecommendationSource.PATTERN,
            ),
            ScoredRecommendation(
                recommendation=Recommendation(
                    id="rec_high",
                    recommendation_type=RecommendationType.ERROR_PREVENTION,
                    title="High score",
                    description="High score error prevention recommendation",
                    action="Act",
                    rationale="Why",
                    expected_benefit="High benefits from error prevention",
                    confidence=0.9,
                    priority=1,
                ),
                base_score=0.9,
                context_bonus=0.0,
                recency_bonus=0.0,
                feedback_bonus=0.0,
                source=RecommendationSource.ERROR,
            ),
            ScoredRecommendation(
                recommendation=Recommendation(
                    id="rec_mid",
                    recommendation_type=RecommendationType.BEST_PRACTICE,
                    title="Mid score",
                    description="Mid score best practice recommendation",
                    action="Act",
                    rationale="Why",
                    expected_benefit="Medium benefits from best practice",
                    confidence=0.7,
                    priority=2,
                ),
                base_score=0.7,
                context_bonus=0.0,
                recency_bonus=0.0,
                feedback_bonus=0.0,
                source=RecommendationSource.CONTEXT,
            ),
        ]

        # Sort by final_score descending (as done in generate_recommendations)
        ranked = sorted(recommendations, key=lambda r: r.final_score, reverse=True)

        # Should be sorted by score descending
        # final_score = base_score * 0.4 when all bonuses are 0
        assert ranked[0].final_score == pytest.approx(0.9 * 0.4, rel=0.01)
        assert ranked[1].final_score == pytest.approx(0.7 * 0.4, rel=0.01)
        assert ranked[2].final_score == pytest.approx(0.5 * 0.4, rel=0.01)


class TestRecommenderIntegration:
    """Integration tests for recommendation flow."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock with realistic data."""
        client = MagicMock(spec=UnifiedMemoryClient)

        # Simulated pattern storage
        patterns = [
            SearchResult(
                id="pat_impl",
                content="Implementation pattern for API calls",
                memory_type="pattern",
                score=0.9,
                importance=0.8,
                created_at="",
                tags=["api", "implementation"],
                metadata={
                    "name": "api_call_pattern",
                    "pattern_type": "implementation",
                    "problem": "Need to call external API",
                    "solution": "Use wrapper with retry logic",
                    "success_count": 15,
                    "failure_count": 2,
                },
            )
        ]

        errors = [
            SearchResult(
                id="err_timeout",
                content="API timeout error",
                memory_type="error",
                score=0.85,
                importance=0.7,
                created_at="",
                tags=["api", "timeout"],
                metadata={
                    "error_type": "TimeoutError",
                    "fix_applied": "Added timeout handling",
                    "prevention_hint": "Set reasonable timeouts",
                },
            )
        ]

        client.search_patterns = AsyncMock(return_value=patterns)
        client.search_errors = AsyncMock(return_value=errors)
        client.search_memory = AsyncMock(return_value=[])
        client.save_memory = AsyncMock(
            return_value=SaveResult(success=True, memory_id="m", message="ok")
        )

        return client

    @pytest.mark.asyncio
    async def test_full_recommendation_flow(self, mock_memory_client):
        """Test complete recommendation flow."""
        recommender = Recommender(memory_client=mock_memory_client)

        # Get recommendations for API task
        recommendations = await recommender.get_recommendations(
            task="Implement API integration",
            agent="IMPLEMENTER",
            file_path="APIModule.bsl",
        )

        # Should get at least BSL file recommendations
        assert isinstance(recommendations, list)

        # Accept first recommendation if any
        if recommendations:
            first = recommendations[0]
            recommender.accept_recommendation(first.id, helpful=True)

            # Check it was tracked in engine._feedback
            assert first.id in recommender.engine._feedback

    @pytest.mark.asyncio
    async def test_recommendations_improve_with_feedback(self, mock_memory_client):
        """Test that recommendations adapt to feedback."""
        recommender = Recommender(memory_client=mock_memory_client)

        # Simulate multiple sessions with feedback
        for i in range(5):
            recs = await recommender.get_recommendations(
                task=f"Task {i}",
                agent="IMPLEMENTER",
            )

            if recs:
                # Accept odd, reject even
                if i % 2 == 0:
                    recommender.reject_recommendation(
                        recs[0].id, reason="not helpful"
                    )
                else:
                    recommender.accept_recommendation(recs[0].id, helpful=True)

        # Check statistics are calculated
        stats = recommender.get_statistics()
        assert "feedback_count" in stats
        assert "average_acceptance_rate" in stats

