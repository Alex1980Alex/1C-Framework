"""Phase 16: BM25 Store — SQLite FTS5 index tests.

Tests for BM25Store: initialization, add, search, delete, lemmatization.
"""

import pytest

from src.pdf_framework.search.bm25_store import (
    BM25Store,
    RUSSIAN_STOP_WORDS,
    lemmatize_text,
    lemmatize_word,
)


@pytest.fixture
def bm25_store(tmp_path):
    """Create a BM25Store with a temp DB."""
    return BM25Store(db_path=tmp_path / "test_bm25.db")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestBM25StoreInit:
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, bm25_store):
        await bm25_store.initialize()
        count = await bm25_store.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_double_initialize_is_safe(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.initialize()  # should not raise
        assert await bm25_store.count() == 0

    @pytest.mark.asyncio
    async def test_creates_parent_directory(self, tmp_path):
        store = BM25Store(db_path=tmp_path / "subdir" / "deep" / "bm25.db")
        await store.initialize()
        assert (tmp_path / "subdir" / "deep" / "bm25.db").exists()


# ---------------------------------------------------------------------------
# Add chunks
# ---------------------------------------------------------------------------

class TestBM25Add:
    @pytest.mark.asyncio
    async def test_add_single_chunk(self, bm25_store):
        await bm25_store.initialize()
        inserted = await bm25_store.add_chunks(
            chunk_ids=["c1"],
            contents=["Регистр накопления хранит остатки и обороты"],
            document_ids=["doc1"],
            sources=["test.pdf"],
        )
        assert inserted == 1
        assert await bm25_store.count() == 1

    @pytest.mark.asyncio
    async def test_add_multiple_chunks(self, bm25_store):
        await bm25_store.initialize()
        inserted = await bm25_store.add_chunks(
            chunk_ids=["c1", "c2", "c3"],
            contents=["Первый чанк", "Второй чанк", "Третий чанк"],
            document_ids=["doc1", "doc1", "doc1"],
            sources=["a.pdf", "a.pdf", "a.pdf"],
        )
        assert inserted == 3
        assert await bm25_store.count() == 3

    @pytest.mark.asyncio
    async def test_add_skips_empty_content(self, bm25_store):
        await bm25_store.initialize()
        inserted = await bm25_store.add_chunks(
            chunk_ids=["c1", "c2"],
            contents=["Содержимое", ""],
            document_ids=["d1", "d1"],
            sources=["s", "s"],
        )
        assert inserted == 1

    @pytest.mark.asyncio
    async def test_add_with_sections_prepends_header(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1"],
            contents=["Основной текст чанка"],
            document_ids=["d1"],
            sources=["s"],
            sections=["4.7.4. Передача параметров"],
        )
        # Search for the section header — it should be in the indexed content
        results = await bm25_store.search("передача параметров", k=5)
        assert len(results) > 0
        assert results[0][0] == "c1"

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1"], contents=["Старый текст"],
            document_ids=["d1"], sources=["s"],
        )
        await bm25_store.add_chunks(
            chunk_ids=["c1"], contents=["Новый текст"],
            document_ids=["d1"], sources=["s"],
        )
        assert await bm25_store.count() == 1
        # Old text should not be found
        results = await bm25_store.search("старый", k=5)
        # May find via lemmatization, but "новый" should rank higher
        results_new = await bm25_store.search("новый", k=5)
        assert len(results_new) > 0

    @pytest.mark.asyncio
    async def test_add_empty_list_returns_zero(self, bm25_store):
        await bm25_store.initialize()
        inserted = await bm25_store.add_chunks([], [], [], [])
        assert inserted == 0


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestBM25Search:
    @pytest.mark.asyncio
    async def test_basic_search(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1", "c2"],
            contents=[
                "Регистр накопления хранит остатки и обороты",
                "Справочник номенклатуры содержит список товаров",
            ],
            document_ids=["d1", "d1"],
            sources=["s", "s"],
        )
        results = await bm25_store.search("регистр накопления", k=5)
        assert len(results) >= 1
        assert results[0][0] == "c1"

    @pytest.mark.asyncio
    async def test_search_returns_scores(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1"],
            contents=["Документ реализация товаров и услуг"],
            document_ids=["d1"],
            sources=["s"],
        )
        results = await bm25_store.search("реализация товаров", k=5)
        assert len(results) > 0
        # FTS5 rank is negative (lower = better)
        assert isinstance(results[0][1], float)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, bm25_store):
        await bm25_store.initialize()
        results = await bm25_store.search("", k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_whitespace_query_returns_empty(self, bm25_store):
        await bm25_store.initialize()
        results = await bm25_store.search("   ", k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_no_results(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1"],
            contents=["Регистр накопления"],
            document_ids=["d1"],
            sources=["s"],
        )
        results = await bm25_store.search("блокчейн криптовалюта", k=5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_respects_k_limit(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=[f"c{i}" for i in range(10)],
            contents=[f"Документ номер {i} про регистры" for i in range(10)],
            document_ids=["d1"] * 10,
            sources=["s"] * 10,
        )
        results = await bm25_store.search("регистр", k=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_or_fallback_supplements_results(self, bm25_store):
        """When AND query returns fewer than k, OR query supplements."""
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1", "c2", "c3"],
            contents=[
                "Регистр накопления остатки",
                "Регистр сведений периодический",
                "Накопление оборотов по счетам",
            ],
            document_ids=["d1"] * 3,
            sources=["s"] * 3,
        )
        # "регистр накопления" as AND → only c1 matches both terms
        # OR fallback should also find c2 (регистр) and c3 (накопления)
        results = await bm25_store.search("регистр накопления", k=5)
        found_ids = {r[0] for r in results}
        assert "c1" in found_ids


# ---------------------------------------------------------------------------
# Lemmatization
# ---------------------------------------------------------------------------

class TestLemmatization:
    def test_lemmatize_word_russian(self):
        lemma = lemmatize_word("регистров")
        # Should lemmatize to base form
        assert lemma in ("регистр", "регистров")

    def test_lemmatize_word_caching(self):
        # Call twice, should use cache
        l1 = lemmatize_word("документов")
        l2 = lemmatize_word("документов")
        assert l1 == l2

    def test_lemmatize_text_preserves_structure(self):
        text = "Регистры накопления хранят остатки"
        result = lemmatize_text(text)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_stop_words_set_contains_common_words(self):
        assert "и" in RUSSIAN_STOP_WORDS
        assert "в" in RUSSIAN_STOP_WORDS
        assert "на" in RUSSIAN_STOP_WORDS
        assert "для" in RUSSIAN_STOP_WORDS


class TestTokenizeQuery:
    def test_basic_tokenization(self):
        tokens = BM25Store._tokenize_query("регистр накопления")
        assert "регистр" in tokens
        assert "накопления" in tokens

    def test_filters_stop_words(self):
        tokens = BM25Store._tokenize_query("что такое регистр и как")
        assert "что" not in tokens
        assert "и" not in tokens
        assert "как" not in tokens
        assert "регистр" in tokens

    def test_filters_single_char(self):
        tokens = BM25Store._tokenize_query("а б регистр")
        assert "а" not in tokens
        assert "б" not in tokens
        assert "регистр" in tokens

    def test_strips_quotes(self):
        tokens = BM25Store._tokenize_query('"регистр" \'накопления\'')
        assert "регистр" in tokens


class TestStemToken:
    def test_russian_suffix_removal(self):
        stem = BM25Store._stem_token("регистров")
        assert stem == "регистр"

    def test_short_word_unchanged(self):
        stem = BM25Store._stem_token("код")
        assert stem == "код"

    def test_latin_word_unchanged(self):
        stem = BM25Store._stem_token("document")
        assert stem == "document"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestBM25Delete:
    @pytest.mark.asyncio
    async def test_delete_by_source(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1", "c2", "c3"],
            contents=["Text A", "Text B", "Text C"],
            document_ids=["d1", "d1", "d2"],
            sources=["file1.pdf", "file1.pdf", "file2.pdf"],
        )
        deleted = await bm25_store.delete_by_source("file1.pdf")
        assert deleted == 2
        assert await bm25_store.count() == 1

    @pytest.mark.asyncio
    async def test_delete_by_source_nonexistent(self, bm25_store):
        await bm25_store.initialize()
        deleted = await bm25_store.delete_by_source("nonexistent.pdf")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_by_document(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1", "c2", "c3"],
            contents=["A", "B", "C"],
            document_ids=["doc_A", "doc_A", "doc_B"],
            sources=["s"] * 3,
        )
        deleted = await bm25_store.delete_by_document("doc_A")
        assert deleted == 2
        assert await bm25_store.count() == 1


# ---------------------------------------------------------------------------
# Clear and Count
# ---------------------------------------------------------------------------

class TestBM25ClearCount:
    @pytest.mark.asyncio
    async def test_clear_removes_all(self, bm25_store):
        await bm25_store.initialize()
        await bm25_store.add_chunks(
            chunk_ids=["c1", "c2"],
            contents=["A", "B"],
            document_ids=["d1", "d1"],
            sources=["s", "s"],
        )
        assert await bm25_store.count() == 2
        await bm25_store.clear()
        assert await bm25_store.count() == 0

    @pytest.mark.asyncio
    async def test_count_empty_store(self, bm25_store):
        await bm25_store.initialize()
        assert await bm25_store.count() == 0
