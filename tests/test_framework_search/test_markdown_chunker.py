"""Unit tests for framework_search.markdown_chunker.chunk_markdown()."""

from __future__ import annotations

import pytest

from framework_search.markdown_chunker import chunk_markdown

pytestmark = pytest.mark.unit


class TestChunkMarkdownHeadings:
    def test_single_h1(self) -> None:
        src = "# Setup\n\nSome text here.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        assert len(chunks) >= 1
        assert chunks[0].symbol_name == "Setup"

    def test_h2_inside_h1(self) -> None:
        src = "# Guide\n\n## Docker\n\nRun it.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        symbols = [c.symbol_name for c in chunks]
        assert "Guide > Docker" in symbols

    def test_h3_inside_h2(self) -> None:
        src = "# Guide\n\n## Install\n\n### Docker\n\nStep.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        symbols = [c.symbol_name for c in chunks]
        assert "Guide > Install > Docker" in symbols

    def test_multiple_h1_headings(self) -> None:
        src = "# First\n\nText.\n\n# Second\n\nMore.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        symbols = [c.symbol_name for c in chunks]
        assert "First" in symbols
        assert "Second" in symbols

    def test_h4_stays_inside_parent(self) -> None:
        src = "# Top\n\n#### Deep\n\nContent.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        # H4 is not a boundary, so "Deep" must not appear as standalone symbol
        symbols = [c.symbol_name for c in chunks]
        assert "Deep" not in symbols
        assert "Top" in symbols


class TestChunkMarkdownFences:
    def test_heading_inside_backtick_fence_ignored(self) -> None:
        src = "# Real\n\n```\n# Fake heading\n```\n\nText.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        symbols = [c.symbol_name for c in chunks]
        assert "Fake heading" not in symbols
        assert "Real" in symbols

    def test_heading_inside_tilde_fence_ignored(self) -> None:
        src = "# Outer\n\n~~~\n## Inner fake\n~~~\n\nText.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        symbols = [c.symbol_name for c in chunks]
        assert "Inner fake" not in symbols


class TestChunkMarkdownEdgeCases:
    def test_empty_string(self) -> None:
        assert chunk_markdown("docs/x.md", "", 1.0) == []

    def test_whitespace_only(self) -> None:
        assert chunk_markdown("docs/x.md", "   \n\n  \n", 1.0) == []

    def test_no_headings_single_chunk(self) -> None:
        src = "Just prose text.\nNo headings here.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        assert len(chunks) == 1
        assert chunks[0].symbol_name is None

    def test_preamble_before_first_heading(self) -> None:
        src = "Intro text.\n\n# Section\n\nBody.\n"
        chunks = chunk_markdown("docs/x.md", src, 1.0)
        # First chunk should be preamble (symbol_name empty or None)
        preamble = [c for c in chunks if not c.symbol_name]
        assert len(preamble) >= 1


class TestChunkMarkdownAttributes:
    def test_language_is_markdown(self) -> None:
        src = "# Title\n\nContent.\n"
        for c in chunk_markdown("docs/x.md", src, 1.0):
            assert c.language == "markdown"

    def test_chunk_type_is_section(self) -> None:
        src = "# Title\n\nContent.\n"
        for c in chunk_markdown("docs/x.md", src, 1.0):
            assert c.chunk_type == "section"

    def test_line_start_gte_1(self) -> None:
        src = "# Title\n\n## Sub\n\nText.\n"
        for c in chunk_markdown("docs/x.md", src, 1.0):
            assert c.line_start >= 1

    def test_mtime_preserved(self) -> None:
        src = "# Title\n\nContent.\n"
        mtime = 999.5
        for c in chunk_markdown("docs/x.md", src, mtime):
            assert c.mtime == mtime

    def test_relative_path_preserved(self) -> None:
        src = "# Title\n\nContent.\n"
        for c in chunk_markdown("docs/readme.md", src, 1.0):
            assert c.relative_path == "docs/readme.md"
