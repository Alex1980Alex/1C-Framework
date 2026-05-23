"""Tests for Phase 4: Semantic Skill Retrieval — indexer and shared search utilities."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".claude", "hooks"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "hooks", "learning"))


# ── parse_frontmatter tests ──────────────────────────────────────────


class TestParseFrontmatter:
    def setup_method(self):
        import importlib

        spec = importlib.util.spec_from_file_location(
            "index_skills", os.path.join(PROJECT_ROOT, "scripts", "index-skills-to-qdrant.py")
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_valid_frontmatter(self):
        content = '---\nname: test-skill\ndescription: "A test skill"\n---\n\n# Body'
        result = self.mod.parse_frontmatter(content)
        assert result["name"] == "test-skill"
        assert "A test skill" in result["description"]

    def test_missing_frontmatter(self):
        result = self.mod.parse_frontmatter("No frontmatter here")
        assert result == {}

    def test_empty_content(self):
        result = self.mod.parse_frontmatter("")
        assert result == {}

    def test_triggers_extracted(self):
        content = "---\nname: x\ndescription: \"Скилл. Триггеры: 'a', 'b', 'c'\"\n---\nBody"
        result = self.mod.parse_frontmatter(content)
        assert "a" in result["triggers"]

    def test_content_preview_limited(self):
        body = "x" * 3000
        content = f"---\nname: x\n---\n{body}"
        result = self.mod.parse_frontmatter(content)
        assert len(result["content_preview"]) <= 2000


# ── semantic_search shared module tests ──────────────────────────────


class TestSemanticSearchModule:
    def test_disabled_via_env(self):
        from shared.semantic_search import search_skills_semantic

        with patch.dict(os.environ, {"SKILL_ROUTER_SEMANTIC_DISABLED": "1"}):
            assert search_skills_semantic("test") == []

    def test_embed_query_disabled(self):
        from shared.semantic_search import embed_query_ollama

        with patch.dict(os.environ, {"SKILL_ROUTER_SEMANTIC_DISABLED": "1"}):
            assert embed_query_ollama("test") is None

    def test_embed_query_success(self):
        from shared.semantic_search import embed_query_ollama

        fake_resp = json.dumps({"embedding": [0.1] * 768}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("shared.semantic_search.urllib.request.urlopen", return_value=mock_resp):
            result = embed_query_ollama("test query", timeout=1.0)
            assert result is not None
            assert len(result) == 768

    def test_embed_query_timeout(self):
        from shared.semantic_search import embed_query_ollama

        with patch("shared.semantic_search.urllib.request.urlopen", side_effect=TimeoutError):
            assert embed_query_ollama("test", timeout=0.1) is None

    def test_search_qdrant_connection_error(self):
        from shared.semantic_search import search_qdrant_semantic

        with patch("qdrant_client.QdrantClient", side_effect=ConnectionError("down")):
            assert search_qdrant_semantic("col", [0.1] * 768) == []

    def test_search_qdrant_formats_results(self):
        from shared.semantic_search import search_qdrant_semantic

        mock_point = MagicMock()
        mock_point.id = "abc-123"
        mock_point.score = 0.85
        mock_point.payload = {"skill_name": "test-skill"}
        mock_response = MagicMock()
        mock_response.points = [mock_point]

        mock_client = MagicMock()
        mock_client.query_points.return_value = mock_response

        with patch("qdrant_client.QdrantClient", return_value=mock_client):
            results = search_qdrant_semantic("skill_library", [0.1] * 768, limit=3)
            assert len(results) == 1
            assert results[0]["score"] == 0.85
            assert results[0]["payload"]["skill_name"] == "test-skill"

    def test_search_skills_formats_output(self):
        from shared.semantic_search import search_skills_semantic

        with patch("shared.semantic_search.embed_query_ollama", return_value=[0.1] * 768):
            with patch(
                "shared.semantic_search.search_qdrant_semantic",
                return_value=[
                    {
                        "id": "1",
                        "score": 0.9,
                        "payload": {"skill_name": "bsl-dev", "description": "BSL"},
                    }
                ],
            ):
                results = search_skills_semantic("test")
                assert len(results) == 1
                assert results[0]["skill_name"] == "bsl-dev"
                assert results[0]["matched_by"] == "semantic"
                assert results[0]["score"] == 0.9

    def test_search_experiences_formats_output(self):
        from shared.semantic_search import search_experiences_semantic

        with patch("shared.semantic_search.embed_query_ollama", return_value=[0.1] * 768):
            with patch(
                "shared.semantic_search.search_qdrant_semantic",
                return_value=[
                    {
                        "id": "exp1",
                        "score": 0.8,
                        "payload": {"experience_id": "exp-001", "insight": "use ast-grep"},
                    }
                ],
            ):
                results = search_experiences_semantic("test")
                assert len(results) == 1
                assert results[0]["experience_id"] == "exp-001"
                assert results[0]["matched_by"] == "semantic"

    def test_search_skills_embed_fails_returns_empty(self):
        from shared.semantic_search import search_skills_semantic

        with patch("shared.semantic_search.embed_query_ollama", return_value=None):
            assert search_skills_semantic("test") == []

    def test_search_experiences_disabled(self):
        from shared.semantic_search import search_experiences_semantic

        with patch.dict(os.environ, {"SKILL_ROUTER_SEMANTIC_DISABLED": "1"}):
            assert search_experiences_semantic("test") == []


# ── experience-embedder tests ────────────────────────────────────────


class TestExperienceEmbedder:
    def setup_method(self):
        import importlib

        spec = importlib.util.spec_from_file_location(
            "experience_embedder",
            os.path.join(PROJECT_ROOT, "scripts", "hooks", "learning", "experience-embedder.py"),
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_index_experience_missing_id(self):
        result = self.mod.index_experience({"insight": {"reason": "test"}})
        assert result is None

    def test_index_experience_empty_embed_input(self):
        record = {"experience_id": "exp-1", "insight": {}, "trigger": {}}
        with patch.object(self.mod, "embed_text", return_value=None):
            result = self.mod.index_experience(record)
            assert result is None
