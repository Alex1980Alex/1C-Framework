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


class TestReverseSyncService:
    """Integration tests for wiki->graph reverse sync (REQ-4)."""

    def _make_service(self, graph_store, tmp_path, debounce_s: float = 0.0):
        return ReverseSyncService(
            graph_store=graph_store,
            wiki_dir=tmp_path,
            debounce_s=debounce_s,
        )

    def test_parse_extracts_frontmatter_and_links(self, graph_store, tmp_path):
        page = tmp_path / "e1.md"
        page.write_text(
            "---\nunified_id: 019e\nstatus: active\n---\n\n"
            "Body referencing [[e2]] and [[e3|Display Three]].\n",
            encoding="utf-8",
        )
        svc = self._make_service(graph_store, tmp_path)
        change = svc._parse_wiki_page(page)
        assert change.entity_id == "e1"
        assert change.change_type == "modified"
        assert change.frontmatter == {"unified_id": "019e", "status": "active"}
        assert change.added_links == ["e2", "e3"]

    def test_parse_invalid_frontmatter_raises(self, graph_store, tmp_path):
        page = tmp_path / "bad.md"
        page.write_text("---\nkey: : : invalid yaml\n---\nbody\n", encoding="utf-8")
        svc = self._make_service(graph_store, tmp_path)
        with pytest.raises(WikiParseError):
            svc._parse_wiki_page(page)

    def test_parse_no_frontmatter_yields_empty_dict(self, graph_store, tmp_path):
        page = tmp_path / "plain.md"
        page.write_text("Just body with [[link]].\n", encoding="utf-8")
        svc = self._make_service(graph_store, tmp_path)
        change = svc._parse_wiki_page(page)
        assert change.frontmatter == {}
        assert change.added_links == ["link"]

    @pytest.mark.asyncio
    async def test_handle_page_change_adds_relations(self, populated_store, tmp_path):
        svc = self._make_service(populated_store, tmp_path)
        change = WikiPageChange(
            entity_id="e1",
            page_path=tmp_path / "e1.md",
            change_type="modified",
            frontmatter={},
            added_links=["e2", "e3"],
        )
        await svc.handle_page_change(change)
        relations = await populated_store.get_relations("e1")
        targets = {r.target_entity_id for r in relations}
        assert "e2" in targets and "e3" in targets

    @pytest.mark.asyncio
    async def test_handle_page_change_skips_deleted(self, graph_store, tmp_path):
        mock_store = AsyncMock()
        svc = ReverseSyncService(graph_store=mock_store, wiki_dir=tmp_path)
        change = WikiPageChange(
            entity_id="gone",
            page_path=tmp_path / "gone.md",
            change_type="deleted",
            frontmatter={},
            added_links=["other"],
        )
        await svc.handle_page_change(change)
        mock_store.add_relation.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_page_change_resilient_to_failed_add(self, tmp_path):
        mock_store = AsyncMock()
        mock_store.add_relation.side_effect = [RuntimeError("boom"), None]
        svc = ReverseSyncService(graph_store=mock_store, wiki_dir=tmp_path)
        change = WikiPageChange(
            entity_id="e1",
            page_path=tmp_path / "e1.md",
            change_type="modified",
            frontmatter={},
            added_links=["e2", "e3"],
        )
        await svc.handle_page_change(change)
        assert mock_store.add_relation.call_count == 2

    @pytest.mark.asyncio
    async def test_on_file_event_debounces(self, graph_store, tmp_path):
        page = tmp_path / "e1.md"
        page.write_text("---\n---\nbody [[e2]]\n", encoding="utf-8")
        mock_store = AsyncMock()
        svc = ReverseSyncService(graph_store=mock_store, wiki_dir=tmp_path, debounce_s=5.0)
        await svc._on_file_event(str(page), "modified")
        await svc._on_file_event(str(page), "modified")
        assert mock_store.add_relation.call_count == 1

    @pytest.mark.asyncio
    async def test_on_file_event_deleted_short_circuits_parse(self, graph_store, tmp_path):
        ghost = tmp_path / "ghost.md"
        mock_store = AsyncMock()
        svc = ReverseSyncService(graph_store=mock_store, wiki_dir=tmp_path)
        await svc._on_file_event(str(ghost), "deleted")
        mock_store.add_relation.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_file_event_parse_error_does_not_crash(self, graph_store, tmp_path):
        page = tmp_path / "bad.md"
        page.write_text("---\nbad: : :\n---\n", encoding="utf-8")
        mock_store = AsyncMock()
        svc = ReverseSyncService(graph_store=mock_store, wiki_dir=tmp_path)
        await svc._on_file_event(str(page), "modified")
        mock_store.add_relation.assert_not_called()


@pytest.mark.slow
class TestReverseSyncRuntimeWatchdog:
    """End-to-end watchdog runtime tests with real filesystem events.

    Uses PollingObserver (OS-agnostic) instead of native watchdog backend —
    polling is reliable across Windows/Linux/macOS/Docker volumes at the cost
    of higher latency. These tests verify the full chain:
        Path.write_text(...) → filesystem event → WikiHandler.on_*
        → loop.create_task(_on_file_event) → handle_page_change → graph_store

    Marked @pytest.mark.slow because each test waits ~2-5s for polling
    cycles. Run separately: pytest -m slow.
    """

    @pytest.mark.asyncio
    async def test_real_watchdog_picks_up_file_write(self, populated_store, tmp_path):
        pytest.importorskip("watchdog", reason="watchdog not installed; skipping runtime watchdog test")
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers.polling import PollingObserver

        svc = ReverseSyncService(
            graph_store=populated_store,
            wiki_dir=tmp_path,
            debounce_s=0.0,
        )

        events_seen: list[tuple[str, str]] = []

        class TestHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path.endswith(".md"):
                    events_seen.append(("modified", event.src_path))
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(svc._on_file_event(event.src_path, "modified"))
                    except RuntimeError:
                        pass

            def on_created(self, event):
                if event.src_path.endswith(".md"):
                    events_seen.append(("created", event.src_path))
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(svc._on_file_event(event.src_path, "created"))
                    except RuntimeError:
                        pass

        observer = PollingObserver(timeout=0.5)
        observer.schedule(TestHandler(), str(tmp_path), recursive=False)
        observer.start()

        try:
            page = tmp_path / "e1.md"
            page.write_text(
                "---\nunified_id: 019e\n---\nbody [[e2]]\n",
                encoding="utf-8",
            )

            # Wait for polling observer cycle + async task to complete.
            for _ in range(20):
                await asyncio.sleep(0.3)
                if events_seen:
                    break

            assert events_seen, "Watchdog did not fire any event within 6s"

            # Drain pending tasks
            await asyncio.sleep(0.5)

            relations = await populated_store.get_relations("e1")
            targets = {r.target_entity_id for r in relations}
            assert "e2" in targets, (
                f"Expected relation e1->e2 from wiki edit, got {targets} "
                f"(events: {events_seen})"
            )
        finally:
            observer.stop()
            observer.join(timeout=2)
