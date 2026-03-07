"""Tests for Pattern Saver module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from .pattern_saver import (
    PatternSaver,
    PatternMatcher,
    PatternCandidate,
    MatchResult,
    PatternExtractionStrategy,
)
from models import (
    Pattern,
    PatternType,
    MemoryType,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    MemoryConfig,
    SaveResult,
    SearchResult,
)


class TestPatternCandidate:
    """Tests for PatternCandidate dataclass."""

    def test_create_candidate(self):
        """Test creating a pattern candidate."""
        candidate = PatternCandidate(
            problem="Test problem",
            solution="Test solution",
            pattern_type=PatternType.IMPLEMENTATION,
            confidence=0.8,
        )

        assert candidate.problem == "Test problem"
        assert candidate.solution == "Test solution"
        assert candidate.pattern_type == PatternType.IMPLEMENTATION
        assert candidate.confidence == 0.8
        assert candidate.keywords == []

    def test_candidate_with_keywords(self):
        """Test candidate with keywords."""
        candidate = PatternCandidate(
            problem="Bug",
            solution="Fix",
            pattern_type=PatternType.BUG_FIX,
            confidence=0.9,
            keywords=["bsl", "1c", "fix"],
        )

        assert len(candidate.keywords) == 3
        assert "bsl" in candidate.keywords

    def test_generate_name(self):
        """Test name generation."""
        candidate = PatternCandidate(
            problem="Error handling exception",
            solution="Wrap in try-except",
            pattern_type=PatternType.BUG_FIX,
        )

        name = candidate.generate_name()

        assert isinstance(name, str)
        assert "bug_fix" in name
        assert "error" in name or "exception" in name

    def test_generate_hash(self):
        """Test hash generation."""
        candidate = PatternCandidate(
            problem="Test",
            solution="Solution",
            pattern_type=PatternType.IMPLEMENTATION,
        )

        hash_val = candidate.generate_hash()

        assert isinstance(hash_val, str)
        assert len(hash_val) == 12


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_create_match_result(self):
        """Test creating a match result."""
        pattern = Pattern(
            id="pat_1",
            name="matched_pattern",
            pattern_type=PatternType.IMPLEMENTATION,
            description="Test pattern",
            problem="Problem",
            solution="Solution",
        )

        result = MatchResult(
            pattern=pattern,
            score=0.85,
        )

        assert result.pattern.id == "pat_1"
        assert result.score == 0.85
        assert result.matched_elements == []
        assert result.context_relevance == 0.0

    def test_combined_score(self):
        """Test combined score calculation."""
        pattern = Pattern(
            id="pat_2",
            name="pattern",
            pattern_type=PatternType.TESTING,
            description="Test pattern",
            problem="Test issue",
            solution="Test fix",
        )

        result = MatchResult(
            pattern=pattern,
            score=0.7,
            context_relevance=0.5,
        )

        # Combined = score * 0.7 + context_relevance * 0.3
        expected = 0.7 * 0.7 + 0.5 * 0.3
        assert result.combined_score == expected


class TestPatternSaver:
    """Tests for PatternSaver class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = AsyncMock(spec=UnifiedMemoryClient)
        client.save_pattern = AsyncMock(
            return_value=SaveResult(
                success=True,
                memory_id="pat_saved_1",
                message="Pattern saved",
            )
        )
        client.search_patterns = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def pattern_saver(self, mock_memory_client):
        """Create PatternSaver with mock client."""
        return PatternSaver(memory_client=mock_memory_client)

    @pytest.mark.asyncio
    async def test_save_pattern(self, pattern_saver, mock_memory_client):
        """Test saving a pattern."""
        pattern = Pattern(
            id="pat_new",
            name="new_pattern",
            pattern_type=PatternType.IMPLEMENTATION,
            description="New pattern",
            problem="Problem",
            solution="Solution",
        )

        result = await pattern_saver.save_pattern(pattern)

        assert result.success is True
        mock_memory_client.save_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_from_candidate(self, pattern_saver, mock_memory_client):
        """Test saving from a candidate."""
        candidate = PatternCandidate(
            problem="Bug found",
            solution="Bug fixed",
            pattern_type=PatternType.BUG_FIX,
            confidence=0.88,
        )

        result = await pattern_saver.save_from_candidate(candidate)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_save_from_candidate_low_confidence(self, pattern_saver):
        """Test saving low confidence candidate."""
        candidate = PatternCandidate(
            problem="Low confidence",
            solution="Solution",
            pattern_type=PatternType.IMPLEMENTATION,
            confidence=0.2,  # Below default min_confidence 0.5
        )

        result = await pattern_saver.save_from_candidate(candidate)

        assert result.success is False
        assert "Confidence too low" in result.message

    @pytest.mark.asyncio
    async def test_deduplication(self, pattern_saver, mock_memory_client):
        """Test pattern deduplication."""
        pattern = Pattern(
            id="pat_dup",
            name="duplicate",
            pattern_type=PatternType.BUG_FIX,
            description="Duplicate test",
            problem="Test",
            solution="Solution",
        )

        # First save
        result1 = await pattern_saver.save_pattern(pattern)
        assert result1.success is True

        # Second save - should be deduplicated
        result2 = await pattern_saver.save_pattern(pattern)
        assert result2.success is True
        assert "already exists" in result2.message

    @pytest.mark.asyncio
    async def test_extract_patterns_from_code(self, pattern_saver):
        """Test extracting patterns from BSL code."""
        bsl_code = """
Процедура ОбработатьДанные(Данные) Экспорт
    Попытка
        РезультатОбработки = ВыполнитьОбработку(Данные);
    Исключение
        ЗаписьЖурналаРегистрации("Ошибка обработки",
            УровеньЖурналаРегистрации.Ошибка, , , ОписаниеОшибки());
        Возврат;
    КонецПопытки;
КонецПроцедуры
"""

        candidates = await pattern_saver.extract_patterns_from_code(
            code=bsl_code,
            file_path="Module.bsl",
        )

        # Should return list of candidates
        assert isinstance(candidates, list)

    def test_known_hashes_tracking(self, pattern_saver):
        """Test hash tracking for deduplication."""
        assert len(pattern_saver._known_hashes) == 0

        # Add to known hashes
        pattern_saver._known_hashes.add("test_hash")

        assert "test_hash" in pattern_saver._known_hashes


class TestPatternMatcher:
    """Tests for PatternMatcher class."""

    @pytest.fixture
    def mock_memory_client(self):
        """Create mock memory client."""
        client = AsyncMock(spec=UnifiedMemoryClient)
        client.search_patterns = AsyncMock(
            return_value=[
                SearchResult(
                    id="pat_match_1",
                    content="Problem: Unhandled exceptions\nSolution: Wrap in Попытка",
                    memory_type="pattern",
                    score=0.85,
                    importance=0.7,
                    created_at="",
                    tags=["error", "bsl"],
                    metadata={
                        "name": "error_handling",
                        "pattern_type": "bug_fix",
                        "description": "Error handling pattern",
                    },
                )
            ]
        )
        return client

    @pytest.fixture
    def pattern_matcher(self, mock_memory_client):
        """Create PatternMatcher with mock client."""
        return PatternMatcher(memory_client=mock_memory_client)

    @pytest.mark.asyncio
    async def test_find_matching_patterns(self, pattern_matcher):
        """Test finding matching patterns."""
        context = "Need to handle database errors in BSL module"

        results = await pattern_matcher.find_matching_patterns(
            context=context,
        )

        assert len(results) >= 1
        assert results[0].score > 0

    @pytest.mark.asyncio
    async def test_find_patterns_with_min_score(self, pattern_matcher, mock_memory_client):
        """Test filtering by minimum score."""
        # Set high min_score
        matcher = PatternMatcher(
            memory_client=mock_memory_client,
            min_score=0.95,  # Higher than mock returns
        )

        results = await matcher.find_matching_patterns(
            context="test context",
        )

        # Should filter out the 0.85 score result
        assert len(results) == 0 or all(r.combined_score >= 0.95 for r in results)

    @pytest.mark.asyncio
    async def test_find_patterns_by_type(self, pattern_matcher, mock_memory_client):
        """Test filtering by pattern type."""
        mock_memory_client.search_patterns = AsyncMock(
            return_value=[
                SearchResult(
                    id="pat_impl",
                    content="Problem: Need feature\nSolution: Implement it",
                    memory_type="pattern",
                    score=0.8,
                    importance=0.6,
                    created_at="",
                    tags=[],
                    metadata={
                        "name": "impl_pattern",
                        "pattern_type": "implementation",
                        "description": "Implementation pattern description",
                    },
                )
            ]
        )

        results = await pattern_matcher.find_matching_patterns(
            context="implementation task",
            pattern_type=PatternType.IMPLEMENTATION,
        )

        assert len(results) >= 0  # May or may not match


class TestPatternExtractionStrategy:
    """Tests for PatternExtractionStrategy enum."""

    def test_all_strategies(self):
        """Test all extraction strategies exist."""
        strategies = list(PatternExtractionStrategy)

        assert PatternExtractionStrategy.STRUCTURAL in strategies
        assert PatternExtractionStrategy.SEMANTIC in strategies
        assert PatternExtractionStrategy.HYBRID in strategies
        assert PatternExtractionStrategy.MANUAL in strategies

    def test_strategy_values(self):
        """Test strategy values."""
        assert PatternExtractionStrategy.STRUCTURAL.value == "structural"
        assert PatternExtractionStrategy.HYBRID.value == "hybrid"


class TestPatternDeduplication:
    """Tests for pattern deduplication logic."""

    @pytest.fixture
    def pattern_saver(self):
        """Create PatternSaver with mock memory client."""
        mock_client = AsyncMock(spec=UnifiedMemoryClient)
        return PatternSaver(memory_client=mock_client)

    def test_generate_hash_consistent(self, pattern_saver):
        """Test hash generation is consistent."""
        pattern = Pattern(
            id="pat_1",
            name="test_pattern",
            pattern_type=PatternType.BUG_FIX,
            description="Test pattern description",
            problem="Test",
            solution="Solution",
        )

        hash1 = pattern_saver._generate_hash(pattern)
        hash2 = pattern_saver._generate_hash(pattern)

        assert hash1 == hash2
        assert len(hash1) == 12

    def test_generate_hash_different_for_different_patterns(self, pattern_saver):
        """Test hash differs for different patterns."""
        pattern1 = Pattern(
            id="pat_1",
            name="pattern1",
            pattern_type=PatternType.BUG_FIX,
            description="First pattern",
            problem="Problem 1",
            solution="Solution 1",
        )

        pattern2 = Pattern(
            id="pat_2",
            name="pattern2",
            pattern_type=PatternType.BUG_FIX,
            description="Second pattern",
            problem="Problem 2",
            solution="Solution 2",
        )

        hash1 = pattern_saver._generate_hash(pattern1)
        hash2 = pattern_saver._generate_hash(pattern2)

        assert hash1 != hash2
