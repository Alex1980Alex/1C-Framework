"""F12 (roadmap 260611 P1.3) — vector arm failure reaches sources_failed.

Pre-fix, ``VectorMemorySearchAdapter.search`` swallowed every exception into an
empty result (``except Exception → logger.warning → []``), so a Qdrant/TEI
outage silently degraded the vector arm while ``unified_search`` reported
nothing wrong. Now the exception propagates and the engine records it in
``sources_failed`` — same honesty the ai-memory arm always had.
"""

from __future__ import annotations

import pytest

pytest.importorskip("qdrant_client")

from src.memory.orchestrator.link_registry import LinkRegistry
from src.memory.orchestrator.memory_orchestrator import VectorMemorySearchAdapter
from src.memory.orchestrator.unified_search import UnifiedSearchEngine

pytestmark = pytest.mark.unit


async def test_vector_arm_failure_lands_in_sources_failed(tmp_path, monkeypatch):
    from src.memory.vector_memory import server as vm_server

    def _down():
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(vm_server, "_get_qdrant", _down)

    engine = UnifiedSearchEngine(LinkRegistry(db_path=str(tmp_path / "links.db")))
    engine.register_adapter(VectorMemorySearchAdapter())

    result = await engine.search("any query", include_links=False)
    failed_sources = {e.source for e in result.sources_failed}
    assert "vector-memory" in failed_sources
    assert "vector-memory" not in result.sources_searched


async def test_vector_adapter_no_longer_swallows(monkeypatch):
    """Direct adapter contract: the exception escapes (engine's job to catch)."""
    from src.memory.vector_memory import server as vm_server

    def _down():
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(vm_server, "_get_qdrant", _down)

    with pytest.raises(ConnectionError):
        await VectorMemorySearchAdapter().search("q")
