"""Unit tests for HybridLoader (F2.5) — behavior tests against current public API.

Rewritten 2026-06-08: old tests exercised _select_level / _calculate_page_offsets /
_verify_coverage which were deleted during Phase 28 refactor.  The cascade is now
inlined inside load(); the helper statics (_is_valid_table, _is_vision_refusal,
_merge_tables, _split_by_offsets) still exist and are tested directly.
Cascade behaviour is tested via monkeypatching _load_sync / _extract_docling_tables
/ _level4_vision_ocr on load() output so no real I/O occurs.

NOTE: test method names intentionally differ from the stale_tests.txt registry
(which holds node IDs for the pre-Phase-28 file that asserted on deleted APIs).
"""

from __future__ import annotations

import pytest

# Module-level mark so `pytest -m unit` collects every class without per-class repeat.
pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _make_fake_doc(raw_text: str = "page one", page_count: int = 1):
    """Return a minimal ProcessedDocument with the metadata shape load() expects."""
    from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument

    meta = DocumentMetadata(
        source="/tmp/x.pdf",
        title="x",
        author="",
        page_count=page_count,
        extra={
            "page_offsets": [(0, 1)],
            "tables": [],
            "loader_stats": {},
            "coverage": {},
        },
    )
    return ProcessedDocument(id="d1", source_path="/tmp/x.pdf", metadata=meta, raw_text=raw_text)


def _make_settings(*, docling=False, vision=False):
    from src.pdf_framework.config import HybridLoaderSettings

    return HybridLoaderSettings(enable_docling_tables=docling, enable_vision_ocr=vision)


# ---------------------------------------------------------------------------
# TestInit — constructor stores credentials correctly
# ---------------------------------------------------------------------------


class TestInit:
    def test_empty_api_key_stored(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(), api_key="")
        assert loader._api_key == ""

    def test_api_key_and_base_url_stored(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(
            settings=_make_settings(),
            api_key="test-key",
            base_url="http://x",
        )
        assert loader._api_key == "test-key"
        assert loader._base_url == "http://x"

    def test_vision_client_none_without_api_key(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(vision=False), api_key="")
        assert loader._vision_client is None
        assert loader._get_vision_client() is None

    def test_vision_client_lazy_not_created_at_init(self):
        """_get_vision_client is lazy — _vision_client stays None until first call."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(vision=True), api_key="fake-key")
        assert loader._vision_client is None


# ---------------------------------------------------------------------------
# TestSupportedExtensions
# ---------------------------------------------------------------------------


class TestSupportedExtensions:
    def test_pdf_is_only_supported_extension(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        assert HybridLoader(settings=_make_settings()).supported_extensions() == [".pdf"]


# ---------------------------------------------------------------------------
# TestIsVisionRefusal — static method, no I/O
# ---------------------------------------------------------------------------


class TestIsVisionRefusal:
    @pytest.fixture(autouse=True)
    def _import(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        self.fn = HybridLoader._is_vision_refusal

    def test_normal_text_not_refusal(self):
        assert self.fn("Some normal extracted text") is False

    def test_russian_refusal_phrase_ne_mogu_obrabota(self):
        assert self.fn("Извините, не могу обработать это.") is True

    def test_russian_refusal_phrase_ne_mogu_prosm(self):
        assert self.fn("Я не могу просмотреть документ") is True

    def test_english_i_cannot_is_refusal(self):
        assert self.fn("I Cannot help with this image") is True

    def test_english_cannot_transcribe_is_refusal(self):
        assert self.fn("Cannot transcribe page contents") is True

    def test_empty_string_is_not_refusal(self):
        assert self.fn("") is False


# ---------------------------------------------------------------------------
# TestIsValidTable — static method, no I/O
# ---------------------------------------------------------------------------


class TestIsValidTable:
    @pytest.fixture(autouse=True)
    def _import(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        self.fn = HybridLoader._is_valid_table

    def test_proper_md_table_is_valid(self):
        md = "| col_a | col_b |\n| --- | --- |\n| 1 | 2 |"
        assert self.fn(md) is True

    def test_text_without_pipe_is_invalid(self):
        assert self.fn("plain text without table marks ---") is False

    def test_table_without_separator_row_is_invalid(self):
        # Has pipe but no "---" separator row
        assert self.fn("| a | b |\n| 1 | 2 |") is False

    def test_string_too_short_is_invalid(self):
        assert self.fn("|abc") is False

    def test_empty_string_is_invalid(self):
        assert self.fn("") is False


# ---------------------------------------------------------------------------
# TestSplitByOffsets — static method, no I/O
# ---------------------------------------------------------------------------


class TestSplitByOffsets:
    @pytest.fixture(autouse=True)
    def _import(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        self.fn = HybridLoader._split_by_offsets

    def test_three_pages_round_trip(self):
        raw = "alpha\n\nbeta\n\ngamma"
        offsets = [(0, 1), (7, 2), (13, 3)]
        pages, nums = self.fn(raw, offsets)
        assert pages == ["alpha", "beta", "gamma"]
        assert nums == [1, 2, 3]

    def test_single_page_round_trip(self):
        pages, nums = self.fn("solo", [(0, 1)])
        assert pages == ["solo"] and nums == [1]

    def test_empty_offsets_returns_empty(self):
        pages, nums = self.fn("", [])
        assert pages == [] and nums == []


# ---------------------------------------------------------------------------
# TestMergeTables — static method, no I/O
# ---------------------------------------------------------------------------


class TestMergeTables:
    @pytest.fixture(autouse=True)
    def _import(self):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader
        from src.pdf_framework.loaders.table_extractor import TableInfo

        self.fn = HybridLoader._merge_tables
        self.TableInfo = TableInfo

    def test_table_appended_to_page_text(self):
        tables = [self.TableInfo(page_number=1, markdown="| a |\n| --- |\n| 1 |")]
        raw, offsets = self.fn(["page one"], [1], tables)
        assert "page one" in raw and "| a |" in raw
        assert offsets[0] == (0, 1)

    def test_table_for_absent_page_is_skipped(self):
        tables = [self.TableInfo(page_number=5, markdown="| x |\n| --- |\n| 9 |")]
        raw, offsets = self.fn(["only"], [1], tables)
        assert raw == "only"
        assert offsets == [(0, 1)]

    def test_two_tables_on_same_page_both_appear(self):
        t1 = self.TableInfo(page_number=2, markdown="| a |\n| --- |\n| 1 |")
        t2 = self.TableInfo(page_number=2, markdown="| b |\n| --- |\n| 2 |")
        raw, offsets = self.fn(["A", "B"], [1, 2], [t1, t2])
        page2_block = raw.split("\n\n", 1)[1]
        assert "| a |" in page2_block and "| b |" in page2_block
        assert offsets[0] == (0, 1)
        assert offsets[1][0] > 0 and offsets[1][1] == 2

    def test_empty_tables_list_leaves_raw_text_unchanged(self):
        raw, offsets = self.fn(["hello", "world"], [1, 2], [])
        assert raw == "hello\n\nworld"
        assert len(offsets) == 2


# ---------------------------------------------------------------------------
# TestCascadeFlow — load() behavior via monkeypatching heavy deps
# ---------------------------------------------------------------------------


class TestCascadeFlow:
    """Cascade behaviour tests on HybridLoader.load() with I/O mocked out."""

    @pytest.mark.asyncio
    async def test_load_calls_load_sync_with_source(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=False, vision=False), api_key="")
        captured: list = []

        def fake_load_sync(src):
            captured.append(str(src))
            return _make_fake_doc()

        monkeypatch.setattr(loader, "_load_sync", fake_load_sync)
        doc = await loader.load("/tmp/x.pdf")
        assert captured == ["/tmp/x.pdf"]
        assert doc.raw_text == "page one"

    @pytest.mark.asyncio
    async def test_docling_not_called_when_disabled(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=False, vision=False), api_key="")
        l3_called: list = []

        async def fake_l3(*_a, **_kw):
            l3_called.append(True)
            return []

        monkeypatch.setattr(loader, "_load_sync", lambda _src: _make_fake_doc())
        monkeypatch.setattr(loader, "_extract_docling_tables", fake_l3)
        await loader.load("/tmp/x.pdf")
        assert l3_called == []

    @pytest.mark.asyncio
    async def test_docling_called_when_enabled(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=True, vision=False), api_key="")
        l3_called: list = []

        async def fake_l3(pdf_path, existing):
            l3_called.append(str(pdf_path))
            return []

        monkeypatch.setattr(loader, "_load_sync", lambda _src: _make_fake_doc())
        monkeypatch.setattr(loader, "_extract_docling_tables", fake_l3)
        await loader.load("/tmp/x.pdf")
        assert len(l3_called) == 1

    @pytest.mark.asyncio
    async def test_vision_ocr_not_called_without_api_key(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=False, vision=True), api_key="")
        loader._api_key = ""  # ensure no env fallback populated it
        l4_called: list = []

        async def fake_l4(*_a, **_kw):
            l4_called.append(True)
            return []

        monkeypatch.setattr(loader, "_load_sync", lambda _src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert l4_called == []

    @pytest.mark.asyncio
    async def test_vision_ocr_called_when_enabled_and_has_key(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(
            settings=_make_settings(docling=False, vision=True), api_key="real-key"
        )
        l4_called: list = []

        async def fake_l4(pdf_path, doc):
            l4_called.append(str(pdf_path))
            return []

        monkeypatch.setattr(loader, "_load_sync", lambda _src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert len(l4_called) == 1

    @pytest.mark.asyncio
    async def test_vision_ocr_not_called_when_setting_disabled(self, monkeypatch):
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=False, vision=False), api_key="any")
        l4_called: list = []

        async def fake_l4(*_a, **_kw):
            l4_called.append(True)
            return []

        monkeypatch.setattr(loader, "_load_sync", lambda _src: _make_fake_doc())
        monkeypatch.setattr(loader, "_level4_vision_ocr", fake_l4)
        await loader.load("/tmp/x.pdf")
        assert l4_called == []

    @pytest.mark.asyncio
    async def test_load_returns_doc_with_expected_raw_text(self, monkeypatch):
        """load() passes through ProcessedDocument from _load_sync unchanged
        when no level-3/4 processing occurs."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(settings=_make_settings(docling=False, vision=False), api_key="")
        monkeypatch.setattr(
            loader, "_load_sync", lambda _src: _make_fake_doc(raw_text="hello world")
        )
        doc = await loader.load("/tmp/x.pdf")
        assert doc.raw_text == "hello world"
        assert doc.source_path == "/tmp/x.pdf"
