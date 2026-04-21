"""Integration tests for IncrementalGraphUpdater → EventBus → IncrementalWikiSync."""

from __future__ import annotations

import asyncio

import pytest

from src.memory.infrastructure.event_bus import EventBus
from src.pdf_framework.graph_store.incremental import IncrementalGraphUpdater
from src.pdf_framework.indexing.wiki_exporter import (
    ForwardSyncService,
    IncrementalWikiSync,
    WikiExportConfig,
    WikiExporter,
)
from src.pdf_framework.schemas.entities import Entity


def _make_updater(graph_store, event_bus=None):
    """Create IncrementalGraphUpdater without graspologic dependency."""
    from unittest.mock import MagicMock
    return IncrementalGraphUpdater(
        graph_store=graph_store,
        community_detector=MagicMock(),
        community_summarizer=MagicMock(),
        event_bus=event_bus,
    )


@pytest.fixture
def event_bus():
    bus = EventBus()
    return bus


@pytest.fixture
def graph_store():
    import tempfile

    from src.pdf_framework.config import GraphStoreSettings
    from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
    with tempfile.TemporaryDirectory() as tmp:
        settings = GraphStoreSettings(persist_dir=tmp)
        store = NetworkXGraphStore(settings)
        asyncio.get_event_loop().run_until_complete(store.initialize())
        yield store


@pytest.fixture
def exporter(graph_store, tmp_path):
    return WikiExporter(graph_store, WikiExportConfig(output_dir=tmp_path / "wiki"))


@pytest.fixture
def forward_sync(graph_store, exporter):
    return ForwardSyncService(graph_store, exporter)


class TestEventBusIntegration:
    @pytest.mark.asyncio
    async def test_single_entity_update_triggers_single_reexport(
        self, graph_store, exporter, forward_sync, event_bus
    ):
        """Adding 1 entity via IncrementalGraphUpdater should trigger exactly 1 wiki page export."""
        await event_bus.start()

        inc_sync = IncrementalWikiSync(forward_sync, exporter, event_bus=event_bus)
        await inc_sync.start()

        updater = _make_updater(graph_store, event_bus=event_bus)

        entity = Entity(
            id="test-e1",
            name="TestEntity",
            entity_type="CONCEPT",
            confidence=0.9,
        )

        result = await updater.update([entity], [])

        # Wait for async event dispatch and handling
        await asyncio.sleep(0.5)

        assert len(result.new_entities) == 1

        wiki_files = list(exporter._config.output_dir.glob("*.md"))
        assert len(wiki_files) == 1
        assert "testentity" in wiki_files[0].stem.lower()

        await inc_sync.stop()
        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_merged_entity_publishes_updated_event(
        self, graph_store, event_bus
    ):
        """Merging an existing entity should publish entity_updated, not entity_created."""
        await event_bus.start()

        entity = Entity(id="e1", name="Existing", entity_type="CONCEPT", confidence=0.8)
        await graph_store.add_entity(entity)

        sub = await event_bus.subscribe("graph.*")

        updater = _make_updater(graph_store, event_bus=event_bus)

        duplicate = Entity(id="e1-dup", name="Existing", entity_type="CONCEPT", confidence=0.9)
        result = await updater.update([duplicate], [])

        # Give event bus time to dispatch
        await asyncio.sleep(0.3)

        # The merged entity should have been detected
        assert len(result.merged_entities) == 1

        # Read published event from subscription
        try:
            event = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
            assert event.event_type == "graph.entity_updated"
            assert event.data["entity_name"] == "Existing"
        except TimeoutError:
            pytest.fail("EventBus did not dispatch entity_updated event")

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_no_event_bus_means_no_publishing(self, graph_store):
        """Without EventBus, update() should work but publish nothing."""
        updater = _make_updater(graph_store, event_bus=None)

        entity = Entity(id="e2", name="NoBus", entity_type="CONCEPT", confidence=0.8)
        result = await updater.update([entity], [])

        assert len(result.new_entities) == 1
        # No exceptions — graceful no-op

    @pytest.mark.asyncio
    async def test_backoff_delays_exponential(self, forward_sync, exporter):
        """Verify backoff uses [1s, 5s, 30s] not linear."""
        inc = IncrementalWikiSync(forward_sync, exporter)
        assert inc._BACKOFF_DELAYS == [1.0, 5.0, 30.0]

    @pytest.mark.asyncio
    async def test_metrics_incremented_on_event(
        self, graph_store, exporter, forward_sync, event_bus
    ):
        """handle_event should increment wiki_sync_events_total."""
        await event_bus.start()

        inc_sync = IncrementalWikiSync(forward_sync, exporter, event_bus=event_bus)
        await inc_sync.start()

        updater = _make_updater(graph_store, event_bus=event_bus)

        entity = Entity(id="metrics-e1", name="MetricsEntity", entity_type="CONCEPT", confidence=0.9)
        await updater.update([entity], [])

        await asyncio.sleep(0.5)

        from src.memory.infrastructure.metrics import get_metrics_collector
        metrics = get_metrics_collector()
        counters = metrics._counters
        assert counters.get("wiki_sync_events_total", 0) >= 1

        await inc_sync.stop()
        await event_bus.stop()
