"""Unit tests for HybridLoader (F2.5).

Tests:
- F2.5.1: HybridLoader level selection
- F2.5.2: page_offsets correctness
- F2.5.3: coverage verification
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.unit
class TestHybridLoader:
    """Test HybridLoader level selection and page offsets."""

    def test_level_selection_basic(self):
        """F2.5.1: HybridLoader should select appropriate loader level."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # Level 0: Basic loader
        assert loader._select_level(needs_ocr=False, has_tables=False) == 0

        # Level 1: Tables only
        assert loader._select_level(needs_ocr=False, has_tables=True) == 1

        # Level 2: OCR only
        assert loader._select_level(needs_ocr=True, has_tables=False) == 2

        # Level 3: OCR + Tables
        assert loader._select_level(needs_ocr=True, has_tables=True) == 3

    def test_page_offsets_calculation(self):
        """F2.5.2: page_offsets should be correctly calculated."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # Simulate chunks with page numbers
        chunks = [
            MagicMock(page_number=1, chunk_index=0),
            MagicMock(page_number=1, chunk_index=1),
            MagicMock(page_number=2, chunk_index=2),
            MagicMock(page_number=3, chunk_index=3),
        ]

        offsets = loader._calculate_page_offsets(chunks)

        assert offsets == {1: 0, 2: 2, 3: 3}

    def test_page_offsets_empty(self):
        """F2.5.2: Empty chunks should return empty offsets."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()
        offsets = loader._calculate_page_offsets([])

        assert offsets == {}

    def test_coverage_verification_full(self):
        """F2.5.3: Coverage should be 100% for complete document."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # 3 pages, all covered
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=2, content="page2"),
            MagicMock(page_number=3, content="page3"),
        ]

        coverage = loader._verify_coverage(chunks, total_pages=3)

        assert coverage == 1.0

    def test_coverage_verification_partial(self):
        """F2.5.3: Partial coverage should be calculated correctly."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # 3 pages, only 2 covered
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=3, content="page3"),
        ]

        coverage = loader._verify_coverage(chunks, total_pages=3)

        assert coverage == 2 / 3

    def test_coverage_threshold_warning(self):
        """F2.5.3: Coverage below threshold should warn."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(min_coverage=0.8)

        # Only 50% coverage
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=2, content="page2"),
        ]

        with pytest.warns(UserWarning, match="Coverage below threshold"):
            loader._verify_coverage(chunks, total_pages=4)


@pytest.mark.unit
class TestIsVisionRefusal:
    def test_clean_text_returns_false(self):
        assert HybridLoader._is_vision_refusal("Some normal extracted text") is False

    def test_russian_не_могу_обработать(self):
        assert HybridLoader._is_vision_refusal("Извините, не могу обработать это.") is True

    def test_russian_не_могу_просмотреть(self):
        assert HybridLoader._is_vision_refusal("Я не могу просмотреть документ") is True

    def test_english_i_cannot_case_insensitive(self):
        assert HybridLoader._is_vision_refusal("I Cannot help with this image") is True

    def test_english_cannot_transcribe(self):
        assert HybridLoader._is_vision_refusal("Cannot transcribe page contents") is True

    def test_empty_string_returns_false(self):
        assert HybridLoader._is_vision_refusal("") is False


@pytest.mark.unit
class TestIsValidTable:
    def test_valid_md_table(self):
        md = "| col_a | col_b |\n| --- | --- |\n| 1 | 2 |"
        assert HybridLoader._is_valid_table(md) is True

    def test_no_pipe_returns_false(self):
        assert HybridLoader._is_valid_table("plain text without table marks ---") is False

    def test_no_separator_returns_false(self):
        assert HybridLoader._is_valid_table("| a | b |\n| 1 | 2 |") is False

    def test_too_short_returns_false(self):
        assert HybridLoader._is_valid_table("|abc") is False

    def test_empty_string_returns_false(self):
        assert HybridLoader._is_valid_table("") is False


@pytest.mark.unit
class TestMergeTables:
    def test_single_page_single_table(self):
        tables = [TableInfo(page_number=1, markdown="| a |\n| --- |\n| 1 |")]
        raw, offsets = HybridLoader._merge_tables(["page one"], [1], tables)
        assert "page one" in raw and "| a |" in raw
        assert offsets == [(0, 1)]

    def test_table_on_missing_page_silently_skipped(self):
        tables = [TableInfo(page_number=5, markdown="| x |\n| --- |\n| 9 |")]
        raw, offsets = HybridLoader._merge_tables(["only"], [1], tables)
        assert raw == "only"
        assert offsets == [(0, 1)]

    def test_multiple_tables_on_same_page_joined(self):
        t1 = TableInfo(page_number=2, markdown="| a |\n| --- |\n| 1 |")
        t2 = TableInfo(page_number=2, markdown="| b |\n| --- |\n| 2 |")
        raw, offsets = HybridLoader._merge_tables(["A", "B"], [1, 2], [t1, t2])
        page2_block = raw.split("\n\n", 1)[1]
        assert "| a |" in page2_block and "| b |" in page2_block
        assert offsets[0] == (0, 1)
        assert offsets[1][0] > 0 and offsets[1][1] == 2


@pytest.mark.unit
class TestSplitByOffsets:
    def test_round_trip_three_pages(self):
        raw = "alpha\n\nbeta\n\ngamma"
        offsets = [(0, 1), (7, 2), (13, 3)]
        pages, nums = HybridLoader._split_by_offsets(raw, offsets)
        assert pages == ["alpha", "beta", "gamma"]
        assert nums == [1, 2, 3]

    def test_single_page(self):
        pages, nums = HybridLoader._split_by_offsets("solo", [(0, 1)])
        assert pages == ["solo"] and nums == [1]

    def test_empty_offsets(self):
        pages, nums = HybridLoader._split_by_offsets("", [])
        assert pages == [] and nums == []


@pytest.mark.unit
class TestSupportedExtensions:
    def test_returns_pdf_only(self):
        assert HybridLoader().supported_extensions() == [".pdf"]


@pytest.mark.unit
class TestInit:
    def test_default_init_no_vision_client(self):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(settings=HybridLoaderSettings(enable_vision_ocr=False), api_key="")
        assert loader._vision_client is None
        assert loader._get_vision_client() is None

    def test_custom_api_key_and_base_url_stored(self):
        loader = HybridLoader(api_key="test-key", base_url="http://x")
        assert loader._api_key == "test-key"
        assert loader._base_url == "http://x"


# Cascade flow tests — verify L3/L4 routing without invoking pymupdf4llm/fitz/Anthropic.
# We monkeypatch _load_sync (L1+L2) and the L3/L4 helpers to track calls.

def _make_fake_doc():
    from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument

    meta = DocumentMetadata(
        source="/tmp/x.pdf", title="x", author="", page_count=1,
        extra={"page_offsets": [(0, 1)], "tables": [], "loader_stats": {}},
    )
    return ProcessedDocument(id="d1", source_path="/tmp/x.pdf", metadata=meta, raw_text="page one")


@pytest.mark.unit
class TestCascadeFlow:
    @pytest.mark.asyncio
    async def test_load_invokes_load_sync(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=False, enable_vision_ocr=False),
            api_key="",
        )
        captured: list = []
        monkeypatch.setattr(loader, "_load_sync", lambda src: (captured.append(src), _make_fake_doc())[1])
        doc = await loader.load("/tmp/x.pdf")
        assert captured == ["/tmp/x.pdf"]
        assert doc.raw_text == "page one"

    @pytest.mark.asyncio
    async def test_l3_skipped_when_disabled(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=False, enable_vision_ocr=False),
            api_key="",
        )
        l3_called = []

        async def fake_l3(*a, **kw):
            l3_called.append(True)
            return []
        monkeypatch.setattr(loader, "_load_sync", lambda src: _make_fake_doc())
        monkeypatch.setattr(loader, "_extract_docling_tables", fake_l3)
        await loader.load("/tmp/x.pdf")
        assert l3_called == []

    @pytest.mark.asyncio
    async def test_l3_called_when_enabled(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=True, enable_vision_ocr=False),
            api_key="",
        )
        l3_called = []

        async def fake_l3(pdf_path, existing):
            l3_called.append(pdf_path)
            return []
        monkeypatch.setattr(loader, "_load_sync", lambda src: _make_fake_doc())
        monkeypatch.setattr(loader, "_extract_docling_tables", fake_l3)
        await loader.load("/tmp/x.pdf")
        assert len(l3_called) == 1

    @pytest.mark.asyncio
    async def test_l4_skipped_without_api_key(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=False, enable_vision_ocr=True),
            api_key="",
        )
        loader._api_key = ""  # ensure fallback didn't populate
        l4_called = []

        async def fake_l4(*a, **kw):
            l4_called.append(True)
            return []
        monkeypatch.setattr(loader, "_load_sync", lambda src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert l4_called == []

    @pytest.mark.asyncio
    async def test_l4_called_when_enabled_with_key(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=False, enable_vision_ocr=True),
            api_key="real-key",
        )
        l4_called = []

        async def fake_l4(pdf_path, doc):
            l4_called.append(pdf_path)
            return []
        monkeypatch.setattr(loader, "_load_sync", lambda src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert len(l4_called) == 1

    @pytest.mark.asyncio
    async def test_l4_skipped_when_setting_disabled(self, monkeypatch):
        from src.pdf_framework.config import HybridLoaderSettings

        loader = HybridLoader(
            settings=HybridLoaderSettings(enable_docling_tables=False, enable_vision_ocr=False),
            api_key="any-key",
        )
        l4_called = []

        async def fake_l4(*a, **kw):
            l4_called.append(True)
            return []
        monkeypatch.setattr(loader, "_load_sync", lambda src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert l4_called == []
