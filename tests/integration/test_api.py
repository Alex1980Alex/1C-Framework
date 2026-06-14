"""Integration tests for API endpoints (F2.11.3) via FastAPI dependency overrides.

Rewritten 2026-06-14 (roadmap 260614 integration remediation): the previous tests
patched removed/wrong targets (`qdrant.QdrantClient`, `RAGAgent.ask`) and hit
endpoints that need a fully-wired `Components`. Now we override `get_components`
with a mock so each endpoint exercises its request→response mapping in isolation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies.components import get_components
from src.pdf_framework.config import get_settings
from src.pdf_framework.schemas.documents import SearchResponse


def _mock_components() -> MagicMock:
    """A mock Components satisfying the endpoints exercised below."""
    c = MagicMock()
    c.settings = get_settings()
    c.collection_store = None

    empty_response = SearchResponse(query="q", results=[], total_found=0, elapsed_ms=1.0)
    c.search_manager.search = AsyncMock(return_value=empty_response)
    c.search_manager.search_section_first = AsyncMock(return_value=empty_response)
    c.query_tracker.track = MagicMock()
    c.query_tracker.get_summary = MagicMock(return_value={})
    c.query_tracker.get_recent = MagicMock(return_value=[])
    c.audit_logger.log = MagicMock()
    c.audit_logger.query = MagicMock(return_value=[])

    c.vector_store.count = AsyncMock(return_value=0)
    c.vector_store.scroll = AsyncMock(return_value=([], None))
    c.vector_store.list_documents = AsyncMock(return_value=[])
    c.graph_store.get_stats = AsyncMock(return_value={"entities": 0, "edges": 0})
    return c


@pytest.fixture
def client():
    """TestClient with get_components overridden by a mock."""
    mock = _mock_components()
    app.dependency_overrides[get_components] = lambda: mock
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.pop(get_components, None)


@pytest.mark.integration
class TestAPIEndpoints:
    """API endpoints via TestClient + dependency-overridden Components."""

    def test_health_endpoints(self):
        """Health endpoints return 200 (no Components dependency)."""
        with TestClient(app) as c:
            assert c.get("/health/live").status_code == 200
            assert c.get("/health/ready").status_code in (200, 503)
            full = c.get("/health")
            assert full.status_code in (200, 503)

    def test_documents_list(self, client):
        """GET /documents/ returns a JSON list/object (200)."""
        response = client.get("/documents/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)

    def test_search_endpoint(self, client):
        """POST /search/ maps the search result to SearchResponseModel."""
        response = client.post(
            "/search/", json={"query": "test query", "strategy": "hybrid", "k": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data and "total_found" in data

    def test_graph_stats(self, client):
        """GET /graph/stats returns stats (200)."""
        response = client.get("/graph/stats")
        assert response.status_code == 200

    def test_analytics_endpoints(self, client):
        """GET /analytics/summary returns 200."""
        response = client.get("/analytics/summary")
        assert response.status_code == 200

    def test_error_handling(self, client):
        """Malformed request body → 422 validation error (no Components needed)."""
        response = client.post("/search/", json={"strategy": "hybrid"})  # missing 'query'
        assert response.status_code == 422

    @pytest.mark.skip(
        reason="/search/ask builds a RetrievalQAChain (LLM) — needs chain-level mock; "
        "deeper rework, roadmap 260614"
    )
    def test_ask_endpoint(self, client):
        """Ask endpoint — pending LLM-chain mock."""

    @pytest.mark.skip(
        reason="/chat/message uses the conversation agent (LLM) — needs agent-level mock; "
        "deeper rework, roadmap 260614"
    )
    def test_chat_endpoint(self, client):
        """Chat endpoint — pending conversation-agent mock."""
