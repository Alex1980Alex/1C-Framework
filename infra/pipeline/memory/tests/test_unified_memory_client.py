"""Tests for Unified Memory Client."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from .unified_memory_client import (
    UnifiedMemoryClient,
    MemoryConfig,
    SearchResult,
    SaveResult,
    MemoryCache,
    SearchMode,
)
from models import (
    MemoryType,
    Pattern,
    PatternType,
    ErrorRecord,
    ErrorSeverity,
    Recommendation,
    RecommendationType,
)


class TestMemoryConfig:
    """Tests for MemoryConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MemoryConfig()

        assert config.server_name == "unified-memory"
        assert config.timeout_seconds == 30
        assert config.default_importance == 0.5
        assert config.enable_cache is True
        assert config.max_retries == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = MemoryConfig(
            server_name="custom-memory",
            timeout_seconds=60,
            default_importance=0.7,
            enable_cache=False,
            project_id="my_project",
        )

        assert config.server_name == "custom-memory"
        assert config.timeout_seconds == 60
        assert config.default_importance == 0.7
        assert config.enable_cache is False
        assert config.project_id == "my_project"


class TestMemoryCache:
    """Tests for MemoryCache."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = MemoryCache(ttl_seconds=300)

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        cache = MemoryCache()

        result = cache.get("nonexistent")

        assert result is None

    def test_invalidate(self):
        """Test cache invalidation."""
        cache = MemoryCache()

        cache.set("key2", "value2")
        cache.invalidate("key2")
        result = cache.get("key2")

        assert result is None

    def test_clear(self):
        """Test clearing all cache."""
        cache = MemoryCache()

        cache.set("key3", "value3")
        cache.set("key4", "value4")
        cache.clear()

        assert cache.get("key3") is None
        assert cache.get("key4") is None

    def test_max_size_eviction(self):
        """Test eviction when max size is reached."""
        cache = MemoryCache(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict oldest

        # One of the first keys should be evicted
        values = [
            cache.get("key1"),
            cache.get("key2"),
            cache.get("key3"),
            cache.get("key4"),
        ]
        assert values.count(None) == 1


class TestSearchResult:
    """Tests for SearchResult."""

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "id": "result_1",
            "content": "Test content",
            "memory_type": "pattern",
            "score": 0.85,
            "importance": 0.7,
            "created_at": "2025-01-01T10:00:00",
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }

        result = SearchResult.from_dict(data)

        assert result.id == "result_1"
        assert result.content == "Test content"
        assert result.score == 0.85
        assert len(result.tags) == 2

    def test_from_dict_defaults(self):
        """Test default values when fields missing."""
        data = {"id": "result_2"}

        result = SearchResult.from_dict(data)

        assert result.id == "result_2"
        assert result.content == ""
        assert result.score == 0.0
        assert result.importance == 0.5


class TestUnifiedMemoryClient:
    """Tests for UnifiedMemoryClient."""

    @pytest.fixture
    def mock_mcp_caller(self):
        """Create mock MCP caller."""
        async def caller(tool_name, params):
            if "save_memory" in tool_name:
                return {
                    "success": True,
                    "id": "mem_123",
                    "message": "Saved",
                }
            elif "search_memory" in tool_name:
                return {
                    "results": [
                        {
                            "id": "res_1",
                            "content": "Found content",
                            "memory_type": "general",
                            "score": 0.8,
                            "importance": 0.6,
                            "created_at": "",
                        }
                    ],
                    "total": 1,
                }
            elif "health_check" in tool_name:
                return {"status": "healthy"}
            return {}

        return caller

    @pytest.fixture
    def client(self, mock_mcp_caller):
        """Create client with mock caller."""
        config = MemoryConfig(enable_cache=True)
        return UnifiedMemoryClient(config=config, mcp_caller=mock_mcp_caller)

    @pytest.mark.asyncio
    async def test_save_memory(self, client):
        """Test saving memory."""
        result = await client.save_memory(
            content="Test content",
            memory_type=MemoryType.GENERAL,
            importance=0.7,
            tags=["test"],
        )

        assert result.success is True
        assert result.memory_id == "mem_123"

    @pytest.mark.asyncio
    async def test_search_memory(self, client):
        """Test searching memory."""
        results = await client.search_memory(
            query="test query",
            mode=SearchMode.HYBRID,
            limit=10,
        )

        assert len(results) == 1
        assert results[0].content == "Found content"
        assert results[0].score == 0.8

    @pytest.mark.asyncio
    async def test_search_with_cache(self, client):
        """Test that search results are cached."""
        # First search
        results1 = await client.search_memory(query="cached query")

        # Second search should use cache
        results2 = await client.search_memory(query="cached query")

        assert results1 == results2

    @pytest.mark.asyncio
    async def test_save_pattern(self, client):
        """Test saving a pattern."""
        pattern = Pattern(
            id="pat_1",
            name="test_pattern",
            pattern_type=PatternType.IMPLEMENTATION,
            description="Test pattern description",
            problem="Test problem",
            solution="Test solution",
        )

        result = await client.save_pattern(pattern)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_save_error(self, client):
        """Test saving an error record."""
        error = ErrorRecord(
            id="err_1",
            error_type="TestError",
            error_message="Test message",
            severity=ErrorSeverity.MEDIUM,
            context="Test context",
        )

        result = await client.save_error(error)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_save_recommendation(self, client):
        """Test saving a recommendation."""
        rec = Recommendation(
            id="rec_1",
            recommendation_type=RecommendationType.BEST_PRACTICE,
            title="Test recommendation",
            description="Test recommendation description",
            action="Do something",
            rationale="Because",
            expected_benefit="Better code quality",
            confidence=0.8,
            priority=2,
        )

        result = await client.save_recommendation(rec)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check."""
        result = await client.health_check()

        assert result["status"] == "healthy"

    def test_set_project_context(self, client):
        """Test setting project context."""
        client.set_project_context("new_project", "new_session")

        assert client.project_id == "new_project"
        assert client.session_id == "new_session"

    def test_get_learning_context(self, client):
        """Test getting learning context."""
        client.set_project_context("proj_1")

        ctx = client.get_learning_context()

        assert ctx.project_id == "proj_1"
        assert ctx.session_id is not None

    @pytest.mark.asyncio
    async def test_search_patterns(self, client):
        """Test searching for patterns specifically."""
        results = await client.search_patterns(query="test", limit=5)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_errors(self, client):
        """Test searching for errors specifically."""
        results = await client.search_errors(query="error", limit=5)

        assert isinstance(results, list)


class TestUnifiedMemoryClientWithoutCaller:
    """Tests for client without MCP caller (mock mode)."""

    def test_client_without_caller(self):
        """Test client creation without caller."""
        client = UnifiedMemoryClient()

        assert client._mcp_caller is None

    @pytest.mark.asyncio
    async def test_mock_save(self):
        """Test mock save response."""
        client = UnifiedMemoryClient()

        result = await client.save_memory(
            content="Test",
            memory_type=MemoryType.GENERAL,
        )

        assert result.success is True
        assert result.memory_id is not None

    @pytest.mark.asyncio
    async def test_mock_search(self):
        """Test mock search response."""
        client = UnifiedMemoryClient()

        results = await client.search_memory(query="test")

        assert results == []  # Mock returns empty results

    @pytest.mark.asyncio
    async def test_mock_health_check(self):
        """Test mock health check."""
        client = UnifiedMemoryClient()

        result = await client.health_check()

        assert result["status"] == "healthy"
