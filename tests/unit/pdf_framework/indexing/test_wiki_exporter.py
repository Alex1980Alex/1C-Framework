"""Unit tests for WikiExporter and related components (Hermes Phase 4)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
from src.pdf_framework.indexing.wiki_exporter import (
    ForwardSyncService,
    GraphChangeEvent,
    GraphEventType,
    IncrementalWikiSync,
    ReverseSyncService,
    WikiExportConfig,
    WikiExporter,
    WikiPageChange,
    WikiParseError,
    WikiSearchIndexer,
)
from src.pdf_framework.schemas.entities import Entity, Relation


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def graph_store(tmp_path):
    from src.pdf_framework.config import GraphStoreSettings
    settings = GraphStoreSettings(persist_dir=tmp_path / "graph")
    store = NetworkXGraphStore(settings)
    _run(store.initialize())
    return store


@pytest.fixture
def populated_store(graph_store):
    e1 = Entity(id="e1", name="Python AsyncIO", entity_type="CONCEPT", confidence=0.95)
    e2 = Entity(id="e2", name="Event Loop", entity_type="CONCEPT", confidence=0.90)
    e3 = Entity(id="e3", name="Web Framework", entity_type="TECHNOLOGY", confidence=0.88)
    for e in [e1, e2, e3]:
        _run(graph_store.add_entity(e))
    _run(graph_store.add_relation(
        Relation(id="r1", source_entity_id="e1", target_entity_id="e2", relation_type="uses"),
    ))
    return graph_store


@pytest.fixture
def exporter(graph_store, tmp_path):
    return WikiExporter(graph_store, WikiExportConfig(output_dir=tmp_path / "wiki"))


@pytest.fixture
def pop_exp(populated_store, tmp_path):
    return WikiExporter(populated_store, WikiExportConfig(output_dir=tmp_path / "wiki"))


class TestWikiExporter:
    @pytest.mark.asyncio
    async def test_export_entity_creates_file(self, pop_exp):
        path = await pop_exp.export_entity("e1")
        assert path is not None
        assert path.exists()
        assert "Python AsyncIO" in path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_export_entity_not_found(self, exporter):
        assert await exporter.export_entity("missing") is None

    @pytest.mark.asyncio
    async def test_export_all(self, pop_exp):
        r = await pop_exp.export_all()
        assert r.exported_pages == 3
        assert r.failed_pages == 0

    @pytest.mark.asyncio
    async def test_export_all_dry_run(self, pop_exp):
        pop_exp._config.dry_run = True
        r = await pop_exp.export_all()
        assert r.exported_pages == 0

    @pytest.mark.asyncio
    async def test_frontmatter(self, pop_exp):
        path = await pop_exp.export_entity("e1")
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "CONCEPT" in content

    @pytest.mark.asyncio
    async def test_idempotent(self, pop_exp):
        await pop_exp.export_entity("e1")
        await pop_exp.export_entity("e1")
        assert len(list(pop_exp._config.output_dir.glob("*.md"))) == 1

    @pytest.mark.asyncio
    async def test_empty_graph(self, exporter):
        r = await exporter.export_all()
        assert r.total_entities == 0


class TestSanitizeFilename:
    def test_basic(self):
        assert WikiExporter._sanitize_filename("Python AsyncIO") == "python-asyncio"

    def test_special_chars(self):
        assert WikiExporter._sanitize_filename("C++ / Rust") == "c-rust"

    def test_long_name(self):
        assert len(WikiExporter._sanitize_filename("a" * 200)) <= 80

    def test_consecutive_hyphens(self):
        assert WikiExporter._sanitize_filename("foo---bar") == "foo-bar"


class TestForwardSyncService:
    @pytest.mark.asyncio
    async def test_sync_found(self, pop_exp):
        fs = ForwardSyncService(pop_exp._graph_store, pop_exp)
        assert await fs.sync_entity("e1") is not None

    @pytest.mark.asyncio
    async def test_sync_not_found(self, pop_exp):
        fs = ForwardSyncService(pop_exp._graph_store, pop_exp)
        assert await fs.sync_entity("missing") is None


class TestIncrementalWikiSync:
    @pytest.mark.asyncio
    async def test_handle_created(self, pop_exp):
        fs = ForwardSyncService(pop_exp._graph_store, pop_exp)
        inc = IncrementalWikiSync(fs, pop_exp)
        await inc.start()
        await inc.handle_event(GraphChangeEvent(
            event_type=GraphEventType.ENTITY_CREATED,
            entity_id="e1", timestamp=datetime.now(), affected_entity_ids=["e1"],
        ))
        assert len(list(pop_exp._config.output_dir.glob("*.md"))) >= 1
        await inc.stop()

    @pytest.mark.asyncio
    async def test_filters_embedding_only(self, pop_exp):
        fs = ForwardSyncService(pop_exp._graph_store, pop_exp)
        inc = IncrementalWikiSync(fs, pop_exp)
        noisy = GraphChangeEvent(
            event_type=GraphEventType.ENTITY_UPDATED, entity_id="e1",
            timestamp=datetime.now(), affected_entity_ids=["e1"],
            metadata={"change_type": "embedding_only"},
        )
        assert inc._should_sync(noisy) is False
        real = GraphChangeEvent(
            event_type=GraphEventType.ENTITY_UPDATED, entity_id="e1",
            timestamp=datetime.now(), affected_entity_ids=["e1"],
        )
        assert inc._should_sync(real) is True


class TestWikiSearchIndexer:
    def test_strips_frontmatter(self, tmp_path):
        page = tmp_path / "t.md"
        page.write_text("---\nid: x\n---\n\nContent here\n", encoding="utf-8")
        idx = WikiSearchIndexer(MagicMock(), wiki_dir=tmp_path)
        text = idx._extract_searchable_text(page)
        assert "Content here" in text
        assert "id: x" not in text

    def test_resolves_links(self, tmp_path):
        page = tmp_path / "t.md"
        page.write_text("---\n---\n\nSee [[asyncio|AsyncIO]] and [[python]]\n", encoding="utf-8")
        idx = WikiSearchIndexer(MagicMock(), wiki_dir=tmp_path)
        text = idx._extract_searchable_text(page)
        assert "AsyncIO" in text
        assert "[[" not in text
