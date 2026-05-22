"""Regression test for canonical BM25 tokenizer (drift guard)."""

from src.bsl.semantic_search.services.bm25_tokenizer import normalize_camelcase


def test_normalize_camelcase_bsl():
    assert normalize_camelcase("ОбработкаПроведения") == "обработка проведения"
    assert normalize_camelcase("getUserById") == "get user by id"
    assert normalize_camelcase("") == ""
    assert normalize_camelcase("ВыполнитьПроведениеДокумента") == "выполнить проведение документа"
