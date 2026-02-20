"""Integration tests for API endpoints (F2.11.3).

Tests API endpoints via TestClient
"""

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestAPIEndpoints:
    """Test API endpoints via TestClient."""

    def test_health_endpoints(self):
        """F2.11.3: Health endpoints should return 200."""
        from src.api.app import app

        client = TestClient(app)

        # Live endpoint
        response = client.get("/health/live")
        assert response.status_code == 200

        # Ready endpoint
        response = client.get("/health/ready")
        assert response.status_code == 200

        # Full health endpoint
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data or "checks" in data

    def test_documents_list(self):
        """F2.11.3: Should list documents."""
        from src.api.app import app

        client = TestClient(app)

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient") as mock_qdrant:
            mock_qdrant.return_value.count.return_value = 5
            mock_qdrant.return_value.scroll.return_value = ([], None)

            response = client.get("/documents/")

            assert response.status_code == 200

            data = response.json()
            assert isinstance(data, list) or "documents" in data

    def test_search_endpoint(self):
        """F2.11.3: Search endpoint should return results."""
        from src.api.app import app

        client = TestClient(app)

        with patch("src.pdf_framework.search.manager.SearchManager.search") as mock_search:
            mock_search.return_value = MagicMock(
                results=[],
                total_found=0,
                elapsed_ms=100,
            )

            response = client.post("/search/", json={
                "query": "test query",
                "strategy": "hybrid",
                "k": 5,
            })

            assert response.status_code == 200

            data = response.json()
            assert "results" in data or "total_found" in data

    def test_ask_endpoint(self):
        """F2.11.3: Ask endpoint should generate answer."""
        from src.api.app import app

        client = TestClient(app)

        with patch("src.pdf_framework.agents.rag.agent.RAGAgent.ask") as mock_ask:
            mock_ask.return_value = MagicMock(
                answer="Test answer",
                sources=[],
            )

            response = client.post("/search/ask", json={
                "question": "What is 1С?",
                "strategy": "hybrid",
            })

            assert response.status_code == 200

            data = response.json()
            assert "answer" in data

    def test_chat_endpoint(self):
        """F2.11.3: Chat endpoint should support conversation."""
        from src.api.app import app

        client = TestClient(app)

        with patch("src.pdf_framework.agents.conversation.conversation_manager.ConversationManager.message") as mock_message:
            mock_message.return_value = MagicMock(
                answer="Chat response",
                thread_id="thread_123",
            )

            response = client.post("/chat/message", json={
                "message": "Explain registers",
                "strategy": "hybrid",
            })

            assert response.status_code == 200

            data = response.json()
            assert "answer" in data

    def test_metrics_endpoint(self):
        """F2.11.3: Metrics endpoint should return metrics."""
        from src.api.app import app

        client = TestClient(app)

        response = client.get("/metrics")

        assert response.status_code == 200

        data = response.json()
        # Should have some metrics
        assert len(data) > 0

    def test_prometheus_metrics_endpoint(self):
        """F2.11.3: Prometheus metrics should be in correct format."""
        from src.api.app import app

        client = TestClient(app)

        response = client.get("/metrics/prometheus")

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    def test_graph_stats(self):
        """F2.11.3: Graph stats endpoint should return graph statistics."""
        from src.api.app import app

        client = TestClient(app)

        with patch("src.pdf_framework.graph_store.providers.networkx_store.NetworkXGraphStore") as mock_graph:
            mock_graph.return_value.get_stats.return_value = {
                "node_count": 100,
                "edge_count": 200,
            }

            response = client.get("/graph/stats")

            assert response.status_code == 200

            data = response.json()
            assert data["node_count"] == 100

    def test_collections_create_and_delete(self):
        """F2.11.3: Collections CRUD should work."""
        from src.api.app import app

        client = TestClient(app)

        # Create collection
        response = client.post("/collections/", json={
            "name": "Test Collection",
            "description": "Test",
        })

        assert response.status_code == 200

        data = response.json()
        collection_id = data.get("id") or data.get("collection_id")

        # Delete collection
        response = client.delete(f"/collections/{collection_id}")

        assert response.status_code == 200

    def test_feedback_submit(self):
        """F2.11.3: Feedback submission should work."""
        from src.api.app import app

        client = TestClient(app)

        response = client.post("/feedback/submit", json={
            "query": "test query",
            "answer": "test answer",
            "feedback": "positive",
            "score": 0.9,
        })

        assert response.status_code == 200

    def test_analytics_endpoints(self):
        """F2.11.3: Analytics endpoints should return data."""
        from src.api.app import app

        client = TestClient(app)

        endpoints = [
            "/analytics/summary",
            "/analytics/queries",
            "/analytics/costs",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)

            # Analytics may be optional - 200 or 404
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, dict)

    def test_error_handling(self):
        """F2.11.3: API should handle errors gracefully."""
        from src.api.app import app

        client = TestClient(app)

        # Invalid search strategy
        response = client.post("/search/", json={
            "query": "test",
            "strategy": "invalid_strategy",
        })

        # Should return 4xx or 200 with error
        assert response.status_code in [400, 422, 200]

        if response.status_code == 200:
            data = response.json()
            # Error should be in response
            assert "error" in data or "detail" in data
