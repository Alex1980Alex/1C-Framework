"""
Integration tests for MemoryOrchestrator MCP server.

Uses mock adapters to test orchestration logic without real backends.
Tests:
- Initialization lifecycle
- Unified search with mock adapters
- Route and save
- Link operations
- Health check
- Error handling
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.memory.orchestrator.memory_orchestrator import (
    EntityNotFoundError,
    MemoryOrchestrator,
    OrchestratorConfig,
    SubsystemUnavailableError,
)
from src.memory.orchestrator.unified_id import MemoryType, SourceServer
from src.memory.orchestrator.unified_search import (
    BaseSearchAdapter,
    SearchResultItem,
)

# ===== Mock Adapters =====


class MockAiAdapter(BaseSearchAdapter):
    def source_name(self) -> str:
        return "memory-ai"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        return [
            SearchResultItem(
                unified_id="episodic:memory-ai:test-1",
                source=SourceServer.MEMORY_AI,
                memory_type=MemoryType.EPISODIC,
                content=f"Important fact about {query}",
                raw_score=0.85,
            )
        ]


class MockVectorAdapter(BaseSearchAdapter):
    def source_name(self) -> str:
        return "vector-memory"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        return [
            SearchResultItem(
                unified_id="semantic:vector-memory:test-2",
                source=SourceServer.VECTOR_MEMORY,
                memory_type=MemoryType.SEMANTIC,
                content=f"Pattern matching {query}",
                raw_score=0.75,
            )
        ]


class MockSkillAdapter(BaseSearchAdapter):
    def source_name(self) -> str:
        return "skill-learning"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        return [
            SearchResultItem(
                unified_id="learning:skill-learning:test-3",
                source=SourceServer.SKILL_LEARNING,
                memory_type=MemoryType.LEARNING,
                content=f"Confirmed skill for {query}",
                raw_score=0.65,
            )
        ]


class SlowAdapter(BaseSearchAdapter):
    def source_name(self) -> str:
        return "slow"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        await asyncio.sleep(10)
        return []


# ===== Fixtures =====


@pytest.fixture
def orchestrator_config(tmp_path):
    return OrchestratorConfig(
        link_registry_path=str(tmp_path / "test_links.db"),
        enable_auto_routing=True,
    )


@pytest.fixture
async def orchestrator(orchestrator_config):
    orch = MemoryOrchestrator(orchestrator_config)
    await orch.start()

    # Register mock adapters
    orch._search_engine.register_adapter(MockAiAdapter())
    orch._search_engine.register_adapter(MockVectorAdapter())
    orch._search_engine.register_adapter(MockSkillAdapter())

    yield orch
    await orch.stop()


# ===== Initialization Tests =====


class TestOrchestratorInit:
    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        config = OrchestratorConfig(link_registry_path=str(tmp_path / "test.db"))
        orch = MemoryOrchestrator(config)
        await orch.start()
        assert orch._link_registry is not None
        assert orch._router is not None
        assert orch._search_engine is not None
        await orch.stop()

    @pytest.mark.asyncio
    async def test_default_config(self):
        config = OrchestratorConfig()
        assert config.enable_auto_routing is True
        assert config.search_timeout == 5.0


# ===== Unified Search Tests =====


class TestUnifiedSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.unified_search("error handling")
        assert "results" in result
        assert len(result["results"]) == 3  # one from each adapter

    @pytest.mark.asyncio
    async def test_source_filtering(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.unified_search("test", include=["memory-ai"])
        sources = [r["source"] for r in result["results"]]
        assert all(s == "memory-ai" for s in sources)

    @pytest.mark.asyncio
    async def test_min_score_filter(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.unified_search("test", min_score=0.8)
        for r in result["results"]:
            assert r["final_score"] >= 0.8


# ===== Route and Save Tests =====


class TestRouteAndSave:
    @pytest.mark.asyncio
    async def test_route_fact(self, orchestrator: MemoryOrchestrator):
        # Mock _save_to_target to avoid real DB writes
        with patch.object(orchestrator, "_save_to_target", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = "test-entity-id"

            result = await orchestrator.route_and_save("Запомни: важный факт о системе")
            assert result["success"] is True
            assert len(result["saved_entities"]) > 0
            assert mock_save.called


# ===== Link Operations Tests =====


class TestLinkOperations:
    @pytest.mark.asyncio
    async def test_create_link(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.create_link(
            source_id="episodic:memory-ai:a",
            target_id="semantic:vector-memory:b",
            link_type="supports",
            strength=0.9,
        )
        assert result["success"] is True
        assert "link" in result

    @pytest.mark.asyncio
    async def test_get_related_empty(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.get_related(entity_id="episodic:memory-ai:nonexistent")
        assert result["related_count"] == 0

    @pytest.mark.asyncio
    async def test_create_link_and_get_related(self, orchestrator: MemoryOrchestrator):
        # Create link
        await orchestrator.create_link(
            source_id="episodic:memory-ai:x",
            target_id="semantic:vector-memory:y",
            link_type="supports",
            strength=0.8,
        )
        # Get related
        result = await orchestrator.get_related(entity_id="episodic:memory-ai:x")
        assert result["related_count"] == 1
        assert "semantic:vector-memory:y" in str(result["related"])


# ===== Get Full Context Tests =====


class TestGetFullContext:
    @pytest.mark.asyncio
    async def test_entity_not_found(self, orchestrator: MemoryOrchestrator):
        with pytest.raises(EntityNotFoundError):
            await orchestrator.get_full_context("invalid-id")

    @pytest.mark.asyncio
    async def test_context_with_links(self, orchestrator: MemoryOrchestrator):
        # Create link first
        await orchestrator.create_link(
            source_id="episodic:memory-ai:ctx-a",
            target_id="semantic:vector-memory:ctx-b",
            link_type="extends",
            strength=0.7,
        )
        # Mock _get_entity
        with patch.object(
            orchestrator,
            "_get_entity",
            new_callable=AsyncMock,
            return_value={"unified_id": "episodic:memory-ai:ctx-a", "content": "test"},
        ):
            result = await orchestrator.get_full_context("episodic:memory-ai:ctx-a")
            assert result["entity"]["content"] == "test"
            assert len(result["links"]) >= 1


# ===== Propagate Update Tests =====


class TestPropagateUpdate:
    @pytest.mark.asyncio
    async def test_propagation(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.propagate_update(
            entity_id="episodic:memory-ai:test",
            delta=0.1,
        )
        assert result["success"] is True
        assert "result" in result
        assert "event_id" in result["result"]


# ===== Stats Tests =====


class TestSystemStats:
    @pytest.mark.asyncio
    async def test_stats_structure(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.get_system_stats(include_subsystems=False)
        assert "orchestrator" in result
        assert "link_registry" in result

    @pytest.mark.asyncio
    async def test_request_counts(self, orchestrator: MemoryOrchestrator):
        await orchestrator.unified_search("test")
        await orchestrator.unified_search("test2")
        stats = await orchestrator.get_system_stats(include_subsystems=False)
        assert stats["orchestrator"]["request_counts"]["unified_search"] == 2


# ===== Health Check Tests =====


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_basic_health(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.health_check()
        assert "status" in result
        assert "components" in result
        assert result["components"]["link_registry"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_specific_subsystems(self, orchestrator: MemoryOrchestrator):
        result = await orchestrator.health_check(subsystems=["memory-ai"])
        assert "memory-ai" in result["components"]


# ===== Error Handling =====


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_uninitialized_search(self):
        orch = MemoryOrchestrator()
        # Don't call start()
        with pytest.raises(SubsystemUnavailableError):
            await orch.unified_search("test")

    @pytest.mark.asyncio
    async def test_uninitialized_router(self):
        orch = MemoryOrchestrator()
        with pytest.raises(SubsystemUnavailableError):
            await orch.route_and_save("test content")
