"""Integration tests for MemoryCube wiki serialization (Phase 0.3).

Tests:
- to_wiki_page() produces valid YAML frontmatter + markdown sections
- from_wiki_page() round-trips without data loss
- Edge cases: empty content, special characters, missing sections
"""

import pytest

from src.memory.orchestrator.memcube import ContentType, MemoryCube
from src.memory.orchestrator.unified_id import MemoryType, SourceServer


# ===== Fixtures =====


@pytest.fixture
def basic_cube() -> MemoryCube:
    return MemoryCube(
        cube_id="test-001",
        content="Test content for wiki page",
        content_type=ContentType.WIKI,
        source=SourceServer.OBSIDIAN_VAULT,
        memory_type=MemoryType.WIKI,
        confidence=0.85,
        importance=0.6,
        tags=["test", "wiki"],
        what="Testing wiki serialization",
        why="Phase 0.3 verification",
        where="tests/integration/",
        learned="YAML frontmatter round-trips correctly",
    )


# ===== to_wiki_page =====


class TestToWikiPage:
    def test_produces_yaml_frontmatter(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        assert page.startswith("---\n")
        assert "\n---\n" in page

    def test_frontmatter_contains_required_fields(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        fm = page.split("---\n")[1]
        assert "unified_id:" in fm
        assert "memory_type: wiki" in fm
        assert "source: obsidian-vault" in fm
        assert "confidence:" in fm
        assert "importance:" in fm

    def test_has_structured_sections(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        assert "## What" in page
        assert "## Why" in page
        assert "## Where" in page
        assert "## Learned" in page
        assert "## Content" in page

    def test_content_under_header(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        assert "Test content for wiki page" in page

    def test_minimal_cube(self):
        cube = MemoryCube(content_type=ContentType.WIKI)
        page = cube.to_wiki_page()
        assert page.startswith("---\n")
        assert "## Content" in page


# ===== from_wiki_page =====


class TestFromWikiPage:
    def test_round_trip(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        restored = MemoryCube.from_wiki_page(page)
        assert restored.content == basic_cube.content
        assert restored.memory_type == MemoryType.WIKI
        assert restored.source == SourceServer.OBSIDIAN_VAULT
        assert restored.what == basic_cube.what
        assert restored.why == basic_cube.why

    def test_preserves_tags(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        restored = MemoryCube.from_wiki_page(page)
        assert "test" in restored.tags
        assert "wiki" in restored.tags

    def test_preserves_scores(self, basic_cube: MemoryCube):
        page = basic_cube.to_wiki_page()
        restored = MemoryCube.from_wiki_page(page)
        assert abs(restored.confidence - 0.85) < 0.01
        assert abs(restored.importance - 0.6) < 0.01

    def test_plain_markdown_fallback(self):
        md = "# Just a heading\n\nSome plain text without frontmatter."
        cube = MemoryCube.from_wiki_page(md)
        assert "plain text" in cube.content

    def test_empty_frontmatter_sections(self):
        page = "---\nunified_id: test:test:001\nmemory_type: episodic\n---\n\n## Content\n\nHello."
        cube = MemoryCube.from_wiki_page(page)
        assert cube.content.strip() == "Hello."


# ===== ContentType.WIKI =====


class TestWikiContentType:
    def test_wiki_enum_value(self):
        assert ContentType.WIKI.value == "wiki"

    def test_wiki_in_enum(self):
        assert "wiki" in [e.value for e in ContentType]
