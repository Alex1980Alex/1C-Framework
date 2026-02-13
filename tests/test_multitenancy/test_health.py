"""Tests for health check endpoints (Phase 12.6)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.health import (
    aggregate_status,
    check_disk_space,
    check_llm,
)


# ---------------------------------------------------------------------------
# aggregate_status
# ---------------------------------------------------------------------------

class TestAggregateStatus:
    def test_all_up(self):
        checks = {
            "vector": {"status": "up"},
            "graph": {"status": "up"},
        }
        assert aggregate_status(checks) == "healthy"

    def test_some_disabled(self):
        checks = {
            "vector": {"status": "up"},
            "llm": {"status": "disabled"},
        }
        assert aggregate_status(checks) == "healthy"

    def test_one_down(self):
        checks = {
            "vector": {"status": "up"},
            "graph": {"status": "down"},
        }
        assert aggregate_status(checks) == "unhealthy"

    def test_warning(self):
        checks = {
            "vector": {"status": "up"},
            "disk": {"status": "warning"},
        }
        assert aggregate_status(checks) == "degraded"

    def test_critical(self):
        checks = {
            "vector": {"status": "up"},
            "disk": {"status": "critical"},
        }
        assert aggregate_status(checks) == "degraded"

    def test_unknown_status(self):
        checks = {
            "vector": {"status": "something_else"},
        }
        assert aggregate_status(checks) == "unknown"

    def test_empty_checks(self):
        assert aggregate_status({}) == "healthy"


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------

class TestCheckDiskSpace:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await check_disk_space()
        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.asyncio
    async def test_has_free_gb(self):
        result = await check_disk_space()
        assert "free_gb" in result
        assert result["free_gb"] > 0

    @pytest.mark.asyncio
    async def test_has_total_gb(self):
        result = await check_disk_space()
        assert "total_gb" in result
        assert result["total_gb"] > 0

    @pytest.mark.asyncio
    async def test_has_used_percent(self):
        result = await check_disk_space()
        assert "used_percent" in result
        assert 0 <= result["used_percent"] <= 100


# ---------------------------------------------------------------------------
# check_llm
# ---------------------------------------------------------------------------

class TestCheckLLM:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_disabled(self):
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = ""

        with patch("src.api.routes.health.get_settings", return_value=mock_settings):
            result = await check_llm()
            assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_with_api_key_returns_up(self):
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "sk-test-key"
        mock_settings.agent.model = "claude-sonnet"

        with patch("src.api.routes.health.get_settings", return_value=mock_settings):
            with patch.dict("sys.modules", {"anthropic": MagicMock()}):
                result = await check_llm()
                assert result["status"] == "up"


# ---------------------------------------------------------------------------
# Health endpoints (via FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    @pytest.fixture
    def mock_components(self):
        components = AsyncMock()
        components.vector_store.count = AsyncMock(return_value=42)
        components.graph_store.get_statistics = AsyncMock(
            return_value={"entity_count": 10, "relation_count": 5}
        )
        return components

    @pytest.mark.asyncio
    async def test_liveness_always_ok(self):
        from src.api.routes.health import liveness_probe
        result = await liveness_probe()
        assert result["status"] == "alive"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_vector_store_check_with_mock(self, mock_components):
        from src.api.routes.health import check_vector_store

        with patch("src.api.routes.health.get_components", return_value=mock_components):
            result = await check_vector_store()
            assert result["status"] == "up"
            assert result["document_count"] == 42

    @pytest.mark.asyncio
    async def test_graph_store_check_with_mock(self, mock_components):
        from src.api.routes.health import check_graph_store

        with patch("src.api.routes.health.get_components", return_value=mock_components):
            result = await check_graph_store()
            assert result["status"] == "up"
            assert result["entity_count"] == 10

    @pytest.mark.asyncio
    async def test_vector_store_down(self):
        from src.api.routes.health import check_vector_store

        mock_comp = AsyncMock()
        mock_comp.vector_store.count = AsyncMock(side_effect=ConnectionError("fail"))

        with patch("src.api.routes.health.get_components", return_value=mock_comp):
            result = await check_vector_store()
            assert result["status"] == "down"
            assert "error" in result
