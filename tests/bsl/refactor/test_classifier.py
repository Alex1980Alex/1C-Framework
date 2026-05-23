from __future__ import annotations

import pytest

from src.bsl.semantic_search.refactor.backends.multilspy_backend import (
    MultilspyBackend,
)
from src.bsl.semantic_search.refactor.classifier import (
    HeuristicClassifier,
    RouteDecision,
    RoutingMatrix,
    SymbolKind,
)


@pytest.fixture
def classifier() -> HeuristicClassifier:
    return HeuristicClassifier()


def test_form_path_classifies_as_form_handler(classifier: HeuristicClassifier) -> None:
    assert (
        classifier.classify("file:///proj/Forms/MyForm/Ext/Form/Module.bsl", 0, 0, None)
        == SymbolKind.FORM_HANDLER
    )
    assert (
        classifier.classify("file:///proj/forms/MyForm/Module.bsl", 0, 0, None)
        == SymbolKind.FORM_HANDLER
    )


def test_form_path_wins_over_content(classifier: HeuristicClassifier) -> None:
    content = "Процедура Foo() Экспорт\nКонецПроцедуры\n"
    assert (
        classifier.classify("file:///proj/Forms/X/Module.bsl", 0, 10, content)
        == SymbolKind.FORM_HANDLER
    )


def test_export_procedure(classifier: HeuristicClassifier) -> None:
    content = "Процедура ПолучитьДанные() Экспорт\nКонецПроцедуры\n"
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 10, content)
        == SymbolKind.MODULE_EXPORT_PROC
    )


def test_local_procedure(classifier: HeuristicClassifier) -> None:
    content = "Процедура ВнутренняяОбработка()\nКонецПроцедуры\n"
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 10, content)
        == SymbolKind.MODULE_LOCAL_PROC
    )


def test_export_function(classifier: HeuristicClassifier) -> None:
    content = "Функция Вычислить() Экспорт\nКонецФункции\n"
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 10, content)
        == SymbolKind.MODULE_EXPORT_FUNC
    )


def test_local_function(classifier: HeuristicClassifier) -> None:
    content = "Функция Хелпер()\nКонецФункции\n"
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 10, content)
        == SymbolKind.MODULE_LOCAL_FUNC
    )


def test_local_variable(classifier: HeuristicClassifier) -> None:
    content = "Перем МояПеременная;\nПроцедура A()\n"
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 5, content)
        == SymbolKind.LOCAL_VARIABLE
    )


def test_english_keywords(classifier: HeuristicClassifier) -> None:
    assert (
        classifier.classify("file:///x/Module.bsl", 0, 0, "Procedure Foo() Export\nEndProcedure\n")
        == SymbolKind.MODULE_EXPORT_PROC
    )
    assert (
        classifier.classify("file:///x/Module.bsl", 0, 0, "Function Bar()\nEndFunction\n")
        == SymbolKind.MODULE_LOCAL_FUNC
    )


def test_trailing_comment_with_export_not_misclassified(
    classifier: HeuristicClassifier,
) -> None:
    """`// TODO: сделать Экспорт` must NOT flip a local proc to export."""
    content = "Процедура X() // TODO: сделать Экспорт\nКонецПроцедуры\n"
    assert (
        classifier.classify("file:///x/Module.bsl", 0, 10, content) == SymbolKind.MODULE_LOCAL_PROC
    )


def test_perem_with_tab_separator(classifier: HeuristicClassifier) -> None:
    """`Перем\\tX;` must still classify as LOCAL_VARIABLE (tab, not space)."""
    content = "Перем\tТабуляцияX;\n"
    assert classifier.classify("file:///x/Module.bsl", 0, 5, content) == SymbolKind.LOCAL_VARIABLE


def test_no_content_returns_unknown(classifier: HeuristicClassifier) -> None:
    assert (
        classifier.classify("file:///proj/CommonModules/X/Module.bsl", 0, 0, None)
        == SymbolKind.UNKNOWN
    )


def test_out_of_range_line_returns_unknown(classifier: HeuristicClassifier) -> None:
    content = "Процедура A()\nКонецПроцедуры\n"
    assert classifier.classify("file:///x/Module.bsl", 99, 0, content) == SymbolKind.UNKNOWN
    assert classifier.classify("file:///x/Module.bsl", -1, 0, content) == SymbolKind.UNKNOWN


def test_routing_matrix_has_all_symbol_kinds() -> None:
    matrix_kinds = set(RoutingMatrix.all_kinds())
    enum_kinds = set(SymbolKind)
    assert matrix_kinds == enum_kinds, f"RoutingMatrix missing kinds: {enum_kinds - matrix_kinds}"


def test_route_for_export_procs_prefers_multilspy() -> None:
    decision = RoutingMatrix.route_for(SymbolKind.MODULE_EXPORT_PROC)
    assert isinstance(decision, RouteDecision)
    assert decision.primary == "multilspy"
    assert decision.fallback == "ast-grep"
    assert decision.confidence == 0.95


def test_route_for_form_handler_prefers_ast_grep() -> None:
    decision = RoutingMatrix.route_for(SymbolKind.FORM_HANDLER)
    assert decision.primary == "ast-grep"
    assert decision.fallback == "multilspy"
    assert decision.confidence == 0.60


def test_route_for_unknown_is_ast_grep_fallback() -> None:
    decision = RoutingMatrix.route_for(SymbolKind.UNKNOWN)
    assert decision.primary == "ast-grep"
    assert decision.fallback is None


def test_confidence_values_match_multilspy_backend() -> None:
    """RoutingMatrix confidence values must stay in sync with MultilspyBackend._CONFIDENCE."""
    for kind in SymbolKind:
        if kind is SymbolKind.UNKNOWN:
            continue
        mb_conf = MultilspyBackend._CONFIDENCE.get(kind.value, 0.0)
        decision = RoutingMatrix.route_for(kind)
        assert decision.confidence == mb_conf, (
            f"{kind.value}: matrix={decision.confidence} vs backend={mb_conf}"
        )
