"""Integration tests for Phase 0 memory layer extensions (v13).

Tests the full pipeline: UnifiedID → LinkRegistry → MemoryCube → Router → Orchestrator
with wiki and graph extensions.

Phase 0 coverage:
- 0.1: UnifiedID wiki/graph types
- 0.2: LinkRegistry new link types
- 0.3: MemoryCube wiki serialization
- 0.4: Search adapters (stubs)
- 0.5: Router wiki target
"""

import pytest

from src.memory.orchestrator.adapters.graph_adapter import GraphSearchAdapter
from src.memory.orchestrator.adapters.wiki_adapter import WikiSearchAdapter
from src.memory.orchestrator.link_registry import LinkType
from src.memory.orchestrator.memcube import ContentType, MemoryCube
from src.memory.orchestrator.memory_router import (
    CATEGORY_KEYWORDS,
    CATEGORY_TARGETS,
    INTENT_PATTERNS,
    VALID_TARGETS,
    MemoryRouter,
)
from src.memory.orchestrator.unified_id import (
    MemoryType,
    SourceServer,
    create_graph_id,
    create_wiki_id,
)


# ===== 0.1: UnifiedID extensions =====


class TestUnifiedIDExtensions:
    def test_memory_type_wiki(self):
        assert MemoryType.WIKI.value == "wiki"

    def test_memory_type_graph(self):
        assert MemoryType.GRAPH.value == "graph"

    def test_source_server_obsidian(self):
        assert SourceServer.OBSIDIAN_VAULT.value == "obsidian-vault"

    def test_source_server_lightrag(self):
        assert SourceServer.LIGHTRAG.value == "lightrag"

    def test_create_wiki_id(self):
        uid = create_wiki_id("projects/hermes.md")
        assert uid.source == SourceServer.OBSIDIAN_VAULT

    def test_create_graph_id(self):
        uid = create_graph_id("entity-42")
        assert uid.source == SourceServer.LIGHTRAG

    def test_wiki_source_maps_to_wiki_type(self):
        assert SourceServer.OBSIDIAN_VAULT.memory_type == MemoryType.WIKI

    def test_lightrag_source_maps_to_graph_type(self):
        assert SourceServer.LIGHTRAG.memory_type == MemoryType.GRAPH


# ===== 0.2: LinkRegistry new types =====


class TestLinkRegistryNewTypes:
    def test_promoted_to(self):
        assert LinkType.PROMOTED_TO.value == "promoted_to"

    def test_superseded_by(self):
        assert LinkType.SUPERSEDED_BY.value == "superseded_by"

    def test_mirrors(self):
        assert LinkType.MIRRORS.value == "mirrors"

    def test_graph_node(self):
        assert LinkType.GRAPH_NODE.value == "graph_node"


# ===== 0.3: MemoryCube wiki round-trip =====


class TestMemCubeWikiRoundTrip:
    def test_full_round_trip(self):
        cube = MemoryCube(
            cube_id="rt-001",
            content="Round trip content",
            content_type=ContentType.WIKI,
            source=SourceServer.OBSIDIAN_VAULT,
            memory_type=MemoryType.WIKI,
            confidence=0.9,
            tags=["integration"],
            what="Round trip test",
            why="Verify serialization",
            where="test file",
            learned="It works",
        )
        page = cube.to_wiki_page()
        restored = MemoryCube.from_wiki_page(page)
        assert restored.content == "Round trip content"
        assert restored.memory_type == MemoryType.WIKI
        assert restored.what == "Round trip test"


# ===== 0.4: Search adapter stubs =====


class TestSearchAdapterStubs:
    @pytest.mark.asyncio
    async def test_wiki_adapter_returns_empty(self):
        adapter = WikiSearchAdapter()
        results = await adapter.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_graph_adapter_returns_empty(self):
        adapter = GraphSearchAdapter()
        results = await adapter.search("test query")
        assert results == []

    def test_wiki_adapter_source(self):
        assert WikiSearchAdapter().source_name() == "obsidian-vault"

    def test_graph_adapter_source(self):
        assert GraphSearchAdapter().source_name() == "lightrag"


# ===== 0.5: Router wiki target =====


class TestRouterWikiTarget:
    def test_wiki_in_valid_targets(self):
        assert "wiki" in VALID_TARGETS

    def test_wiki_in_category_targets(self):
        assert CATEGORY_TARGETS.get("wiki") == "wiki"

    def test_wiki_keywords_exist(self):
        assert "wiki" in CATEGORY_KEYWORDS
        assert any("wiki" in kw for kw in CATEGORY_KEYWORDS["wiki"])

    def test_wiki_intent_patterns(self):
        wiki_intents = {k: v for k, v in INTENT_PATTERNS.items() if v == "wiki"}
        assert len(wiki_intents) >= 3

    @pytest.mark.asyncio
    async def test_router_classifies_wiki_content(self):
        router = MemoryRouter()
        decision = await router.route("сохранить в wiki статью про архитектуру")
        assert "wiki" in decision.targets
