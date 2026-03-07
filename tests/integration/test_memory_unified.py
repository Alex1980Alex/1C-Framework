"""
Integration tests for Unified Memory System (Phase 49).

Tests:
- UnifiedID creation, parsing, registry
- Link Registry CRUD, graph traversal
- Federated search engine with mock adapters
- Cross-system link enrichment
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from src.memory.orchestrator.unified_id import (
    MemoryType,
    SourceServer,
    UnifiedID,
    IDRegistry,
    create_episodic_id,
    create_semantic_id,
    create_doc_id,
)
from src.memory.orchestrator.link_registry import (
    LinkType,
    LinkRegistry,
)
from src.memory.orchestrator.unified_search import (
    SearchOptions,
    SearchResultItem,
    UnifiedSearchResult,
    BaseSearchAdapter,
    UnifiedSearchEngine,
)


# ========== UnifiedID Tests ==========


class TestUnifiedID:
    def test_create_from_source(self):
        uid = UnifiedID.generate(SourceServer.MEMORY_AI)
        assert uid.memory_type == MemoryType.EPISODIC
        assert uid.source == SourceServer.MEMORY_AI
        assert "episodic:memory-ai:" in uid.unified

    def test_parse_roundtrip(self):
        uid = UnifiedID.generate(SourceServer.VECTOR_MEMORY)
        parsed = UnifiedID.parse(uid.unified)
        assert parsed.memory_type == uid.memory_type
        assert parsed.source == uid.source
        assert parsed.identifier == uid.identifier

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError):
            UnifiedID.parse("invalid-id")

    def test_from_path_deterministic(self):
        uid1 = UnifiedID.from_path(SourceServer.PDF_DOCS, "docs/chapter5.pdf")
        uid2 = UnifiedID.from_path(SourceServer.PDF_DOCS, "docs/chapter5.pdf")
        assert uid1.identifier == uid2.identifier
        assert uid1.memory_type == MemoryType.DOCUMENTATION

    def test_equality(self):
        uid = UnifiedID.generate(SourceServer.MEMORY_AI)
        assert uid == uid.unified
        assert uid == UnifiedID.parse(uid.unified)

    def test_with_metadata(self):
        uid = UnifiedID.generate(SourceServer.MEMORY_AI)
        uid2 = uid.with_metadata(importance=0.9)
        assert uid2.metadata["importance"] == 0.9
        assert uid.metadata == {}

    def test_convenience_functions(self):
        ep = create_episodic_id(SourceServer.MEMORY_AI)
        assert ep.memory_type == MemoryType.EPISODIC
        sem = create_semantic_id()
        assert sem.memory_type == MemoryType.SEMANTIC
        doc = create_doc_id("path/to/doc.pdf")
        assert doc.memory_type == MemoryType.DOCUMENTATION


class TestIDRegistry:
    def test_register_and_resolve(self):
        reg = IDRegistry()
        uid = UnifiedID.generate(SourceServer.MEMORY_AI)
        reg.register(uid)
        assert reg.resolve(uid.unified) == uid.identifier

    def test_get_or_create_idempotent(self):
        reg = IDRegistry()
        uid1 = reg.get_or_create(SourceServer.MEMORY_AI, "test-id-1")
        uid2 = reg.get_or_create(SourceServer.MEMORY_AI, "test-id-1")
        assert uid1.unified == uid2.unified

    def test_batch_register(self):
        reg = IDRegistry()
        items = [
            (SourceServer.MEMORY_AI, "id-1", None),
            (SourceServer.VECTOR_MEMORY, "id-2", None),
            (SourceServer.PDF_DOCS, "id-3", MemoryType.DOCUMENTATION),
        ]
        results = reg.batch_register(items)
        assert len(results) == 3
        assert reg.stats()["total_ids"] == 3

    def test_export_import(self):
        reg1 = IDRegistry()
        reg1.get_or_create(SourceServer.MEMORY_AI, "test-1")
        reg1.get_or_create(SourceServer.VECTOR_MEMORY, "test-2")
        exported = reg1.export()

        reg2 = IDRegistry()
        reg2.import_state(exported)
        assert reg2.stats()["total_ids"] == 2


# ========== Link Registry Tests ==========


class TestLinkRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        return LinkRegistry(db_path=str(tmp_path / "test_links.db"))

    def test_create_and_get_link(self, registry):
        link = registry.create_link("a:b:1", "a:b:2", LinkType.BASED_ON, 0.9)
        assert link.link_id is not None
        fetched = registry.get_link(link.link_id)
        assert fetched.source_id == "a:b:1"

    def test_duplicate_link_raises(self, registry):
        registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.8)
        with pytest.raises(ValueError):
            registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.5)

    def test_update_link_strength(self, registry):
        link = registry.create_link("a:b:1", "a:b:2", LinkType.EXTENDS, 0.5)
        registry.update_link(link.link_id, strength=0.9)
        assert registry.get_link(link.link_id).strength == 0.9

    def test_delete_link(self, registry):
        link = registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.8)
        registry.delete_link(link.link_id)
        assert registry.get_link(link.link_id) is None

    def test_get_links_from_to(self, registry):
        registry.create_link("a:b:src", "a:b:t1", LinkType.SUPPORTS, 0.8)
        registry.create_link("a:b:src", "a:b:t2", LinkType.EXTENDS, 0.6)
        registry.create_link("a:b:other", "a:b:src", LinkType.BASED_ON, 0.7)
        assert len(registry.get_links_from("a:b:src")) == 2
        assert len(registry.get_links_to("a:b:src")) == 1

    def test_graph_traversal(self, registry):
        registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.9)
        registry.create_link("a:b:2", "a:b:3", LinkType.EXTENDS, 0.8)
        related = registry.get_related_entities("a:b:1", max_depth=2)
        ids = [r.entity_id for r in related]
        assert "a:b:2" in ids
        assert "a:b:3" in ids

    def test_find_path(self, registry):
        registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.9)
        registry.create_link("a:b:2", "a:b:3", LinkType.EXTENDS, 0.8)
        path = registry.find_path("a:b:1", "a:b:3")
        assert path is not None
        assert len(path) == 2

    def test_batch_create(self, registry):
        links = [
            ("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.8),
            ("a:b:2", "a:b:3", LinkType.EXTENDS, 0.7),
        ]
        created = registry.create_links_batch(links)
        assert len(created) == 2

    def test_export_import(self, registry, tmp_path):
        registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.8)
        exported = registry.export()
        reg2 = LinkRegistry(db_path=str(tmp_path / "test2.db"))
        assert reg2.import_links(exported) == 1

    def test_cleanup_expired(self, registry):
        registry.create_link(
            "a:b:1", "a:b:2", LinkType.SESSION_CONTEXT, 0.5,
            expires_at=datetime.now() - timedelta(hours=1),
        )
        assert registry.cleanup_expired() == 1

    def test_registry_stats(self, registry):
        registry.create_link("a:b:1", "a:b:2", LinkType.SUPPORTS, 0.8)
        registry.create_link("a:b:2", "a:b:3", LinkType.EXTENDS, 0.7)
        stats = registry.get_registry_stats()
        assert stats["total_links"] == 2
        assert stats["unique_entities"] == 3


# ========== Unified Search Tests ==========


class MockSearchAdapter(BaseSearchAdapter):
    def __init__(self, name: str, results: list):
        self._name = name
        self._results = results

    def source_name(self) -> str:
        return self._name

    async def search(self, query: str, limit: int = 10, **kwargs) -> list:
        return self._results[:limit]


class TestUnifiedSearch:
    @pytest.fixture
    def engine(self):
        engine = UnifiedSearchEngine()
        engine.register_adapter(MockSearchAdapter("memory-ai", [
            SearchResultItem(
                unified_id="episodic:memory-ai:id1",
                source=SourceServer.MEMORY_AI,
                memory_type=MemoryType.EPISODIC,
                content="Important pattern about error handling",
                raw_score=0.85,
            ),
        ]))
        engine.register_adapter(MockSearchAdapter("vector-memory", [
            SearchResultItem(
                unified_id="semantic:vector-memory:id2",
                source=SourceServer.VECTOR_MEMORY,
                memory_type=MemoryType.SEMANTIC,
                content="Pattern: always validate input before processing",
                raw_score=0.75,
            ),
        ]))
        return engine

    @pytest.mark.asyncio
    async def test_basic_search(self, engine):
        result = await engine.search("error handling")
        assert isinstance(result, UnifiedSearchResult)
        assert result.total_results == 2
        assert len(result.sources_searched) == 2

    @pytest.mark.asyncio
    async def test_source_filtering(self, engine):
        result = await engine.search("error", sources=[SourceServer.MEMORY_AI])
        assert result.total_results == 1
        assert result.results[0].source == SourceServer.MEMORY_AI

    @pytest.mark.asyncio
    async def test_memory_type_filtering(self, engine):
        result = await engine.search("pattern", memory_types=[MemoryType.SEMANTIC])
        assert all(r.memory_type == MemoryType.SEMANTIC for r in result.results)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        class SlowAdapter(BaseSearchAdapter):
            def source_name(self): return "slow"
            async def search(self, query, limit=10, **kw):
                await asyncio.sleep(10)
                return []

        engine = UnifiedSearchEngine()
        engine.register_adapter(SlowAdapter())
        result = await engine.search("test", options=SearchOptions(timeout_ms=100))
        assert len(result.sources_failed) == 1
        assert result.sources_failed[0].error == "timeout"
