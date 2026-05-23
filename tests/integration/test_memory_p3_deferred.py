"""
Integration tests for Memory System P3 — Deferred components.

Tests:
- SubscriptionManager: create, remove, heartbeat, get_events, stale cleanup (8 tests)
- DocsRagSearchAdapter: ingest, FTS search, delete, stats (6 tests)
- IDManagementTool: generate, resolve, conflict, batch, stats (6 tests)
- SurpriseTool: score novel, score known, empty, batch (5 tests)
- WarmupTool: recent, pattern, stats (4 tests)
- ResearchTool: relationships, anomalies, clusters, summary (4 tests)

Total: 33 tests.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from src.memory.ai_memory.adapters.docs_rag import DocsRagConfig, DocsRagSearchAdapter
from src.memory.infrastructure.cache import LRUCache
from src.memory.infrastructure.event_bus import Event, EventBus, EventBusConfig
from src.memory.infrastructure.event_store import EventStore, EventStoreConfig
from src.memory.infrastructure.subscription_manager import (
    SubscriptionManager,
    SubscriptionManagerConfig,
)
from src.memory.orchestrator.tools.id_management import IDManagementTool, _uuid7
from src.memory.orchestrator.tools.research import ResearchTool
from src.memory.orchestrator.tools.surprise import SurpriseTool
from src.memory.orchestrator.tools.warmup import WarmupTool
from src.memory.orchestrator.unified_id import IDRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def bus():
    eb = EventBus(EventBusConfig(max_queue_size=50, max_subscribers=20, enable_logging=False))
    await eb.start()
    yield eb
    await eb.stop()


@pytest.fixture
async def sub_manager(bus):
    mgr = SubscriptionManager(
        bus,
        SubscriptionManagerConfig(
            heartbeat_interval=1.0,
            stale_timeout=2.0,
            max_subscriptions_per_client=5,
            enable_auto_cleanup=False,
        ),
    )
    await mgr.start()
    yield mgr
    await mgr.stop()


@pytest.fixture
async def store(tmp_path):
    es = EventStore(
        EventStoreConfig(
            hot_buffer_path=str(tmp_path / "events.jsonl"),
            cold_db_path=str(tmp_path / "events.db"),
            auto_flush_threshold=500,
            flush_interval=3600.0,
        )
    )
    await es.start()
    yield es
    await es.stop()


@pytest.fixture
async def docs_adapter(tmp_path):
    adapter = DocsRagSearchAdapter(
        DocsRagConfig(
            chunks_db_path=str(tmp_path / "docs_chunks.db"),
            enable_vector_search=False,
        )
    )
    await adapter.initialize()
    yield adapter
    await adapter.close()


@pytest.fixture
def id_tool():
    registry = IDRegistry()
    return IDManagementTool(registry)


@pytest.fixture
def cache():
    return LRUCache(max_size=100, default_ttl=3600.0)


# ---------------------------------------------------------------------------
# TestSubscriptionManager — 8 tests
# ---------------------------------------------------------------------------


class TestSubscriptionManager:
    @pytest.mark.asyncio
    async def test_create_subscription(self, sub_manager):
        sub = await sub_manager.create("client-1", "memory.*")
        assert sub.client_id == "client-1"
        assert sub.pattern == "memory.*"
        assert sub.subscription_id

    @pytest.mark.asyncio
    async def test_remove_subscription(self, sub_manager):
        sub = await sub_manager.create("client-1", "memory.save")
        removed = await sub_manager.remove(sub.subscription_id)
        assert removed is True
        removed_again = await sub_manager.remove(sub.subscription_id)
        assert removed_again is False

    @pytest.mark.asyncio
    async def test_heartbeat(self, sub_manager):
        sub = await sub_manager.create("client-1", "test.*")
        ok = await sub_manager.heartbeat(sub.subscription_id)
        assert ok is True
        not_ok = await sub_manager.heartbeat("nonexistent")
        assert not_ok is False

    @pytest.mark.asyncio
    async def test_get_events(self, sub_manager, bus):
        sub = await sub_manager.create("client-1", "data.*")
        await bus.publish("data.update", {"key": "value"})
        await asyncio.sleep(0.05)
        events = await sub_manager.get_events(sub.subscription_id, max_events=5)
        assert len(events) == 1
        assert events[0]["event_type"] == "data.update"
        assert events[0]["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_events_empty(self, sub_manager):
        sub = await sub_manager.create("client-1", "empty.*")
        events = await sub_manager.get_events(sub.subscription_id)
        assert events == []

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, sub_manager):
        await sub_manager.create("client-1", "a.*")
        await sub_manager.create("client-2", "b.*")
        await sub_manager.create("client-1", "c.*")
        all_subs = await sub_manager.list_subscriptions()
        assert len(all_subs) == 3
        client1_subs = await sub_manager.list_subscriptions(client_id="client-1")
        assert len(client1_subs) == 2

    @pytest.mark.asyncio
    async def test_max_subscriptions_per_client(self, sub_manager):
        for i in range(5):
            await sub_manager.create("limit-client", f"pattern.{i}")
        with pytest.raises(RuntimeError, match="subscription limit"):
            await sub_manager.create("limit-client", "pattern.overflow")

    @pytest.mark.asyncio
    async def test_get_stats(self, sub_manager):
        await sub_manager.create("c1", "x.*")
        stats = sub_manager.get_stats()
        assert stats["active_subscriptions"] == 1
        assert stats["total_created"] == 1


# ---------------------------------------------------------------------------
# TestDocsRagSearchAdapter — 6 tests
# ---------------------------------------------------------------------------


class TestDocsRagSearchAdapter:
    @pytest.mark.asyncio
    async def test_ingest_document(self, docs_adapter):
        count = await docs_adapter.ingest_document(
            source_path="docs/guide.md",
            content="This is a test document about BSL query language and its features.",
            metadata={"section": "BSL Guide", "tags": ["bsl", "query"]},
        )
        assert count >= 1

    @pytest.mark.asyncio
    async def test_fts_search(self, docs_adapter):
        await docs_adapter.ingest_document(
            source_path="docs/bsl.md",
            content="The BSL query language supports ВЫБРАТЬ and СОЕДИНЕНИЕ operators.",
        )
        results = await docs_adapter.search("BSL query", limit=5)
        assert len(results) >= 1
        assert "BSL" in results[0].content or "query" in results[0].content

    @pytest.mark.asyncio
    async def test_search_no_results(self, docs_adapter):
        results = await docs_adapter.search("nonexistent_xyz_12345", limit=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_delete_document(self, docs_adapter):
        await docs_adapter.ingest_document("docs/temp.md", "Temporary content for deletion test.")
        deleted = await docs_adapter.delete_document("docs/temp.md")
        assert deleted >= 1

    @pytest.mark.asyncio
    async def test_get_stats(self, docs_adapter):
        await docs_adapter.ingest_document("docs/stats.md", "Stats test document content.")
        stats = await docs_adapter.get_stats()
        assert stats["total_chunks"] >= 1
        assert stats["source_documents"] >= 1

    @pytest.mark.asyncio
    async def test_chunking(self, docs_adapter):
        long_content = "word " * 500  # ~2500 chars
        count = await docs_adapter.ingest_document("docs/long.md", long_content)
        assert count > 1  # should be split into multiple chunks


# ---------------------------------------------------------------------------
# TestIDManagementTool — 6 tests
# ---------------------------------------------------------------------------


class TestIDManagementTool:
    @pytest.mark.asyncio
    async def test_uuid7_format(self):
        uid = _uuid7()
        assert len(uid) == 36  # standard UUID format
        assert uid[14] == "7"  # version 7

    @pytest.mark.asyncio
    async def test_generate(self, id_tool):
        result = await id_tool.execute(operation="generate", source="memory-ai", count=3)
        assert result["operation"] == "generate"
        assert result["count"] == 3
        assert len(result["ids"]) == 3

    @pytest.mark.asyncio
    async def test_resolve(self, id_tool):
        gen = await id_tool.execute(operation="generate", source="memory-ai")
        uid = gen["ids"][0]["unified_id"]
        result = await id_tool.execute(operation="resolve", unified_id=uid)
        assert result["found"] is True

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, id_tool):
        result = await id_tool.execute(
            operation="resolve", unified_id="episodic:memory-ai:nonexistent"
        )
        assert result["found"] is False

    @pytest.mark.asyncio
    async def test_batch_register(self, id_tool):
        items = [
            {"source": "memory-ai", "original_id": "orig-1"},
            {"source": "vector-memory", "original_id": "orig-2", "memory_type": "semantic"},
        ]
        result = await id_tool.execute(operation="batch_register", items=items)
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_stats(self, id_tool):
        await id_tool.execute(operation="generate", source="memory-ai", count=2)
        result = await id_tool.execute(operation="stats")
        assert result["total_ids"] >= 2


# ---------------------------------------------------------------------------
# TestSurpriseTool — 5 tests
# ---------------------------------------------------------------------------


class _FakeSearchEngine:
    """Minimal fake search engine for testing surprise scoring."""

    def __init__(self, results=None):
        self._results = results

    async def search(self, query, limit=10, include_links=False):
        from src.memory.orchestrator.unified_search import (
            UnifiedSearchResult,
        )

        items = self._results or []
        return UnifiedSearchResult(
            query=query,
            total_results=len(items),
            results=items,
            search_time_ms=1.0,
            sources_searched=["fake"],
        )


class TestSurpriseTool:
    @pytest.mark.asyncio
    async def test_score_novel_content(self):
        tool = SurpriseTool(search_engine=_FakeSearchEngine(results=[]))
        result = await tool.score("Completely novel content about quantum computing")
        assert result["surprise_score"] == 1.0
        assert result["novelty_level"] == "high"

    @pytest.mark.asyncio
    async def test_score_known_content(self):
        from src.memory.orchestrator.unified_id import MemoryType, SourceServer
        from src.memory.orchestrator.unified_search import SearchResultItem

        existing = [
            SearchResultItem(
                unified_id="test:1",
                source=SourceServer.MEMORY_AI,
                memory_type=MemoryType.EPISODIC,
                content="BSL query language patterns",
                raw_score=0.95,
            ),
        ]
        tool = SurpriseTool(search_engine=_FakeSearchEngine(results=existing))
        result = await tool.score("BSL query language patterns")
        assert result["surprise_score"] < 0.5
        assert result["novelty_level"] == "low"

    @pytest.mark.asyncio
    async def test_score_empty_content(self):
        tool = SurpriseTool(search_engine=None)
        result = await tool.score("")
        assert result["surprise_score"] == 0.0
        assert result["novelty_level"] == "empty"

    @pytest.mark.asyncio
    async def test_score_with_detail(self):
        from src.memory.orchestrator.unified_id import MemoryType, SourceServer
        from src.memory.orchestrator.unified_search import SearchResultItem

        existing = [
            SearchResultItem(
                unified_id="test:detail",
                source=SourceServer.MEMORY_AI,
                memory_type=MemoryType.EPISODIC,
                content="Some existing content about Python",
                raw_score=0.5,
            ),
        ]
        tool = SurpriseTool(search_engine=_FakeSearchEngine(results=existing))
        result = await tool.score("Novel content about Rust programming", detail=True)
        assert "novel_tokens" in result
        assert "metrics" in result

    @pytest.mark.asyncio
    async def test_batch_score(self):
        tool = SurpriseTool(search_engine=_FakeSearchEngine(results=[]))
        result = await tool.batch_score(["Item one", "Item two"])
        assert result["summary"]["total"] == 2
        assert len(result["items"]) == 2


# ---------------------------------------------------------------------------
# TestWarmupTool — 4 tests
# ---------------------------------------------------------------------------


class TestWarmupTool:
    @pytest.mark.asyncio
    async def test_warmup_recent(self, cache, store):
        # Add some events to the store
        event = Event(
            event_id="w1",
            event_type="memory.save",
            data={"key": "val"},
            timestamp=datetime.now(tz=UTC),
            source="test",
        )
        await store.append(event)

        tool = WarmupTool(cache, event_store=store)
        result = await tool.warmup(strategy="recent", limit=10)
        assert result["entities_loaded"] >= 1
        assert result["cache_delta"] >= 1

    @pytest.mark.asyncio
    async def test_warmup_pattern(self, cache):
        tool = WarmupTool(cache, search_engine=_FakeSearchEngine(results=[]))
        result = await tool.warmup(strategy="pattern", query="BSL", limit=5)
        assert result["entities_loaded"] == 0  # fake returns empty

    @pytest.mark.asyncio
    async def test_warmup_unknown_strategy(self, cache):
        tool = WarmupTool(cache)
        result = await tool.warmup(strategy="unknown_xyz")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_warmup_stats(self, cache):
        tool = WarmupTool(cache)
        stats = await tool.get_warmup_stats()
        assert "warmed_entries" in stats
        assert "size" in stats


# ---------------------------------------------------------------------------
# TestResearchTool — 4 tests
# ---------------------------------------------------------------------------


class _FakeLinkRegistry:
    """Minimal fake link registry for research tool tests."""

    def __init__(self, relations=None):
        self._relations = relations or {}

    def get_related_entities(self, entity_id, max_depth=2, **kwargs):
        return self._relations.get(entity_id, [])


class _FakeRelated:
    def __init__(self, entity_id, depth=1, effective_strength=0.8):
        self.entity_id = entity_id
        self.depth = depth
        self.effective_strength = effective_strength
        self.link_path = []

    def to_dict(self):
        return {"entity_id": self.entity_id, "depth": self.depth}


class TestResearchTool:
    @pytest.mark.asyncio
    async def test_relationships(self):
        links = _FakeLinkRegistry(
            {
                "e1": [_FakeRelated("e2"), _FakeRelated("e3")],
                "e2": [_FakeRelated("e1")],
            }
        )
        tool = ResearchTool(links, search_engine=None)
        result = await tool.analyze(entity_ids=["e1", "e2"], analysis_type="relationships")
        assert result["analysis_type"] == "relationships"
        assert result["total_nodes"] >= 2

    @pytest.mark.asyncio
    async def test_anomalies_isolated(self):
        links = _FakeLinkRegistry({"e1": [], "e2": []})
        tool = ResearchTool(links, search_engine=None)
        result = await tool.analyze(entity_ids=["e1", "e2"], analysis_type="anomalies")
        assert result["anomalies_found"] == 2
        assert all(a["type"] == "isolated" for a in result["anomalies"])

    @pytest.mark.asyncio
    async def test_clusters(self):
        links = _FakeLinkRegistry(
            {
                "e1": [_FakeRelated("e2")],
                "e2": [_FakeRelated("e1")],
                "e3": [],
            }
        )
        tool = ResearchTool(links, search_engine=None)
        result = await tool.analyze(entity_ids=["e1", "e2", "e3"], analysis_type="clusters")
        assert result["total_clusters"] >= 2

    @pytest.mark.asyncio
    async def test_no_entities(self):
        tool = ResearchTool(link_registry=None, search_engine=None)
        result = await tool.analyze(analysis_type="summary")
        assert result["status"] == "no_entities"
