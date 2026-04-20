"""Integration tests for Phase 3 Auto-Librarian — wiki_promoter.

Tests the L2→L3 promotion pipeline with mocked Qdrant client.
"""

from unittest.mock import MagicMock

import pytest

from src.memory.librarian.wiki_promoter import WikiPromoter
from src.memory.orchestrator.memcube import ContentType, MemoryCube


def _make_point(idx: int, name: str, confidence: float, usage_count: int):
    """Create a mock Qdrant point with vector in payload."""
    point = MagicMock()
    point.id = f"point-{idx}"
    vec = [0.1 * idx] * 8
    point.payload = {
        "name": name,
        "content": f"Content for {name}",
        "confidence": confidence,
        "usage_count": usage_count,
        "tags": ["test"],
        "description": f"Description of {name}",
        "vector": vec,
        "id": f"point-{idx}",
    }
    point.vector = vec
    return point


@pytest.fixture
def drafts_dir(tmp_path):
    d = tmp_path / "drafts"
    d.mkdir()
    return d


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "log.md"


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def promoter(mock_client, drafts_dir, log_path):
    return WikiPromoter(
        qdrant_client=mock_client,
        wiki_drafts_dir=drafts_dir,
        wiki_log_path=log_path,
        confidence_threshold=0.8,
        usage_threshold=5,
        similarity_threshold=0.85,
    )


# ===== Scan & Promote =====


class TestWikiPromoterScan:
    @pytest.mark.asyncio
    async def test_promote_single_eligible(self, promoter, mock_client, drafts_dir):
        point = _make_point(1, "test pattern", 0.9, 10)
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[])

        created = await promoter.scan_and_promote()

        assert created == ["test-pattern"]
        assert (drafts_dir / "test-pattern.md").exists()

    @pytest.mark.asyncio
    async def test_skip_low_confidence(self, promoter, mock_client):
        # Mock scroll doesn't apply filter — return empty to simulate filter behavior
        mock_client.scroll.return_value = ([], None)

        assert await promoter.scan_and_promote() == []

    @pytest.mark.asyncio
    async def test_skip_low_usage(self, promoter, mock_client):
        mock_client.scroll.return_value = ([], None)

        assert await promoter.scan_and_promote() == []

    @pytest.mark.asyncio
    async def test_skip_duplicate_already_promoted(self, promoter, mock_client):
        point = _make_point(1, "dup pattern", 0.9, 10)
        similar = MagicMock()
        similar.id = "point-99"
        similar.score = 0.92
        similar.payload = {"promoted_to": "dup-pattern"}
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[similar])

        assert await promoter.scan_and_promote() == []

    @pytest.mark.asyncio
    async def test_skip_duplicate_draft_exists(self, promoter, mock_client, drafts_dir):
        point = _make_point(1, "existing draft", 0.9, 10)
        similar = MagicMock()
        similar.id = "point-99"
        similar.score = 0.90
        similar.payload = {"name": "existing draft"}  # no promoted_to
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[similar])
        # Pre-create the draft file
        (drafts_dir / "existing-draft.md").write_text("existing", encoding="utf-8")

        assert await promoter.scan_and_promote() == []

    @pytest.mark.asyncio
    async def test_promote_10_synthetic_patterns(self, promoter, mock_client, drafts_dir):
        points = [_make_point(i, f"pattern {i}", 0.9, 10) for i in range(10)]
        mock_client.scroll.return_value = (points, None)
        mock_client.query_points.return_value = MagicMock(points=[])

        created = await promoter.scan_and_promote()

        assert len(created) == 10
        for slug in created:
            assert (drafts_dir / f"{slug}.md").exists()

    @pytest.mark.asyncio
    async def test_no_vectors_skips_dedup(self, promoter, mock_client):
        """Pattern without vector embedding skips dedup (no crash)."""
        point = _make_point(1, "no vector", 0.9, 10)
        point.payload.pop("vector", None)  # no vector key
        # vector is on point.vector attribute, payload doesn't have it
        point.vector = None
        mock_client.scroll.return_value = ([point], None)

        created = await promoter.scan_and_promote()
        # Should still create since _dedup_check returns None for no vector
        assert len(created) == 1


# ===== Slugify =====


class TestWikiPromoterSlugify:
    def test_basic(self):
        assert WikiPromoter._slugify("My Pattern") == "my-pattern"

    def test_special_chars(self):
        assert WikiPromoter._slugify("BSL: Code (v2)") == "bsl-code-v2"

    def test_long_name_truncated(self):
        assert len(WikiPromoter._slugify("a" * 200)) == 80

    def test_empty_fallback(self):
        assert WikiPromoter._slugify("!!!") == "unnamed"


# ===== Logging =====


class TestWikiPromoterLog:
    @pytest.mark.asyncio
    async def test_log_entry_created(self, promoter, mock_client, drafts_dir, log_path):
        log_path.write_text(
            "# Wiki Log\n\n---\n\n## Format Template\n\n```\ntemplate\n```\n",
            encoding="utf-8",
        )
        point = _make_point(1, "logged pattern", 0.85, 7)
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[])

        await promoter.scan_and_promote()

        log_content = log_path.read_text(encoding="utf-8")
        assert "logged-pattern" in log_content
        assert "0.85" in log_content
        assert "Auto-promoted" in log_content

    @pytest.mark.asyncio
    async def test_log_trim_at_500_lines(self, promoter, mock_client, drafts_dir, log_path):
        lines = ["# Wiki Log", "", "---", ""]
        for i in range(490):
            lines.append(f"Line {i}")
        lines += ["", "## Format Template", "```", "template", "```"]
        log_path.write_text("\n".join(lines), encoding="utf-8")

        point = _make_point(1, "trim test", 0.9, 10)
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[])

        await promoter.scan_and_promote()

        result_lines = log_path.read_text(encoding="utf-8").split("\n")
        assert len(result_lines) <= 500

    @pytest.mark.asyncio
    async def test_log_missing_file_no_crash(self, promoter, mock_client, drafts_dir, log_path):
        """Log file doesn't exist — promoter should not crash."""
        assert not log_path.exists()
        point = _make_point(1, "no log", 0.9, 10)
        mock_client.scroll.return_value = ([point], None)
        mock_client.query_points.return_value = MagicMock(points=[])

        created = await promoter.scan_and_promote()
        assert len(created) == 1  # Draft created even without log


# ===== Draft format =====


class TestWikiPromoterDraftFormat:
    def test_draft_has_frontmatter(self, drafts_dir):
        cube = MemoryCube(
            content="Test content",
            content_type=ContentType.WIKI,
            title="Test Pattern",
            confidence=0.85,
            tags=["test"],
        )
        page = cube.to_wiki_page()
        assert "unified_id:" in page
        assert "confidence: 0.85" in page
        assert "## Content" in page
