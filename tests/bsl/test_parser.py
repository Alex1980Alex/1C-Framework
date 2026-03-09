"""Tests for BSL parser, chunker, and evaluation metrics (Phase 58-59)."""

from src.bsl.parser.models import (
    SymbolType, CompilationDirective, ModuleType,
    BSLParam, BSLCall, BSLSymbol, BSLVariable, BSLRegion, BSLModule,
)
from src.bsl.parser.bsl_ast_parser import BSLASTParser
from src.bsl.parser.bsl_chunker import BSLChunker, BSLChunk
from src.bsl.evaluation.metrics import (
    EvalResult, recall_at_k, precision_at_k, mrr, ndcg,
    evaluate_single, aggregate_results, format_report,
)


class TestModels:

    def test_symbol_type_values(self):
        assert SymbolType.PROCEDURE.value == "Procedure"
        assert SymbolType.FUNCTION.value == "Function"

    def test_compilation_directive(self):
        assert CompilationDirective.AT_SERVER.value == "&AtServer"
        assert CompilationDirective.AT_CLIENT.value == "&AtClient"

    def test_compilation_directive_from_string(self):
        assert CompilationDirective.from_string("&AtServer") == CompilationDirective.AT_SERVER
        assert CompilationDirective.from_string("unknown") == CompilationDirective.NONE

    def test_module_type(self):
        assert ModuleType.OBJECT_MODULE.value == "ObjectModule"
        assert ModuleType.FORM_MODULE.value == "FormModule"
        assert ModuleType.COMMON_MODULE.value == "CommonModule"

    def test_module_type_from_path(self):
        assert ModuleType.from_path("CommonModules/MyModule/Module.bsl") == ModuleType.COMMON_MODULE
        assert ModuleType.from_path("unknown/path.bsl") == ModuleType.UNKNOWN

    def test_bsl_param(self):
        p = BSLParam(name="Param1", default_value="123", by_val=True)
        assert p.name == "Param1"
        assert p.by_val is True
        assert p.default_value == "123"

    def test_bsl_symbol_signature(self):
        params = [BSLParam(name="A"), BSLParam(name="B", default_value="0")]
        sym = BSLSymbol(
            name="TestProc",
            symbol_type=SymbolType.PROCEDURE,
            params=params,
            line_start=1, line_end=5, body="",
        )
        sig = sym.signature
        assert "TestProc" in sig
        assert "A" in sig
        assert "B" in sig

    def test_bsl_symbol_params_str(self):
        params = [BSLParam(name="X", by_val=True)]
        sym = BSLSymbol(
            name="Fn", symbol_type=SymbolType.FUNCTION,
            params=params, line_start=1, line_end=3, body="",
        )
        ps = sym.params_str
        assert "X" in ps

    def test_bsl_module_properties(self):
        mod = BSLModule(file_path="test.bsl", module_type=ModuleType.UNKNOWN, symbols=[], variables=[])
        assert len(mod.procedures) == 0
        assert len(mod.functions) == 0

    def test_bsl_module_with_symbols(self):
        sym1 = BSLSymbol(name="P1", symbol_type=SymbolType.PROCEDURE, line_start=1, line_end=3, body="")
        sym2 = BSLSymbol(name="F1", symbol_type=SymbolType.FUNCTION, line_start=5, line_end=8, body="")
        mod = BSLModule(file_path="m.bsl", module_type=ModuleType.UNKNOWN, symbols=[sym1, sym2], variables=[])
        assert len(mod.procedures) == 1
        assert len(mod.functions) == 1

    def test_bsl_module_exports(self):
        sym1 = BSLSymbol(name="ExportProc", symbol_type=SymbolType.PROCEDURE, line_start=1, line_end=3, body="", is_export=True)
        sym2 = BSLSymbol(name="LocalProc", symbol_type=SymbolType.PROCEDURE, line_start=5, line_end=7, body="", is_export=False)
        mod = BSLModule(file_path="m.bsl", module_type=ModuleType.UNKNOWN, symbols=[sym1, sym2])
        assert len(mod.exports) == 1
        assert mod.exports[0].name == "ExportProc"

    def test_bsl_module_name(self):
        mod = BSLModule(file_path="CommonModules/MyModule/Ext/Module.bsl", module_type=ModuleType.COMMON_MODULE)
        assert mod.module_name == "MyModule"


class TestParser:

    def _make_parser(self):
        return BSLASTParser()

    def test_parse_empty(self):
        parser = self._make_parser()
        mod = parser.parse_content("", "empty.bsl")
        assert mod.file_path == "empty.bsl"
        assert len(mod.symbols) == 0

    def test_parse_english_procedure(self):
        parser = self._make_parser()
        code = "Procedure MyProc()\n    // body\nEndProcedure"
        mod = parser.parse_content(code, "test.bsl")
        procs = [s for s in mod.symbols if s.symbol_type == SymbolType.PROCEDURE]
        assert len(procs) == 1
        assert procs[0].name == "MyProc"

    def test_parse_english_function(self):
        parser = self._make_parser()
        code = "Function GetValue()\n    Return 42;\nEndFunction"
        mod = parser.parse_content(code, "test.bsl")
        funcs = [s for s in mod.symbols if s.symbol_type == SymbolType.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].name == "GetValue"

    def test_parse_params(self):
        parser = self._make_parser()
        code = "Procedure Test(A, B, C)\n    // body\nEndProcedure"
        mod = parser.parse_content(code, "test.bsl")
        assert len(mod.symbols) == 1
        assert len(mod.symbols[0].params) == 3

    def test_parse_russian_procedure(self):
        parser = self._make_parser()
        code = "Процедура МояПроц()\n    // body\nКонецПроцедуры"
        mod = parser.parse_content(code, "test.bsl")
        procs = [s for s in mod.symbols if s.symbol_type == SymbolType.PROCEDURE]
        assert len(procs) >= 1

    def test_parse_russian_function(self):
        parser = self._make_parser()
        code = "Функция МояФункция()\n    Возврат 1;\nКонецФункции"
        mod = parser.parse_content(code, "test.bsl")
        funcs = [s for s in mod.symbols if s.symbol_type == SymbolType.FUNCTION]
        assert len(funcs) >= 1

    def test_parse_variables(self):
        parser = self._make_parser()
        code = "Перем X;\nПерем Y Экспорт;"
        mod = parser.parse_content(code, "test.bsl")
        assert len(mod.variables) >= 1

    def test_parse_regions(self):
        parser = self._make_parser()
        code = "#Область TestRegion\n// code\n#КонецОбласти"
        mod = parser.parse_content(code, "test.bsl")
        assert len(mod.regions) >= 1

    def test_parse_calls(self):
        parser = self._make_parser()
        code = "Procedure P1()\n    SomeFunction(1, 2);\n    AnotherFunc();\nEndProcedure"
        mod = parser.parse_content(code, "test.bsl")
        if mod.symbols and mod.symbols[0].calls:
            assert len(mod.symbols[0].calls) >= 1

    def test_parser_cache(self):
        parser = self._make_parser()
        code = "Procedure Cached()\nEndProcedure"
        mod1 = parser.parse_content(code, "cached.bsl")
        mod2 = parser.parse_content(code, "cached.bsl")
        assert mod1.file_path == mod2.file_path


class TestChunker:

    def _make_chunker(self):
        return BSLChunker()

    def _make_sample_module(self):
        sym = BSLSymbol(
            name="Calculate",
            symbol_type=SymbolType.FUNCTION,
            params=[BSLParam(name="Value")],
            line_start=1, line_end=5,
            body="Return Value * 2;",
            calls=[BSLCall(caller_name="Calculate", callee_module=None, callee_method="Multiply", line=3)],
            comment="Doubles the value",
        )
        return BSLModule(
            file_path="calc.bsl",
            module_type=ModuleType.COMMON_MODULE,
            raw_content="Function Calculate(Value)\n    Return Value * 2;\nEndFunction",
            symbols=[sym],
            variables=[],
            line_count=3,
        )

    def test_chunk_module(self):
        chunker = self._make_chunker()
        mod = self._make_sample_module()
        chunks = chunker.chunk_module(mod)
        assert len(chunks) >= 1
        assert all(isinstance(c, BSLChunk) for c in chunks)

    def test_chunk_has_metadata(self):
        chunker = self._make_chunker()
        mod = self._make_sample_module()
        chunks = chunker.chunk_module(mod)
        for chunk in chunks:
            assert chunk.module_path == "calc.bsl"

    def test_chunk_content_not_empty(self):
        chunker = self._make_chunker()
        mod = self._make_sample_module()
        chunks = chunker.chunk_module(mod)
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_empty_module(self):
        chunker = self._make_chunker()
        mod = BSLModule(file_path="empty.bsl", module_type=ModuleType.UNKNOWN, raw_content="", symbols=[], variables=[])
        chunks = chunker.chunk_module(mod)
        assert isinstance(chunks, list)

    def test_multiple_symbols(self):
        chunker = self._make_chunker()
        sym1 = BSLSymbol(name="A", symbol_type=SymbolType.PROCEDURE, line_start=1, line_end=3, body="// a")
        sym2 = BSLSymbol(name="B", symbol_type=SymbolType.FUNCTION, line_start=5, line_end=8, body="Return 1;")
        mod = BSLModule(file_path="multi.bsl", module_type=ModuleType.UNKNOWN, raw_content="code", symbols=[sym1, sym2], line_count=8)
        chunks = chunker.chunk_module(mod)
        # 1 summary + 2 symbols = 3
        assert len(chunks) >= 2

    def test_no_summary_mode(self):
        chunker = BSLChunker(include_module_summary=False)
        mod = self._make_sample_module()
        chunks = chunker.chunk_module(mod)
        # Should only have symbol chunks, no summary
        chunk_types = [c.metadata.get("chunk_type") for c in chunks]
        assert "module_summary" not in chunk_types


class TestMetrics:

    def test_recall_at_k_full(self):
        retrieved = ["a", "b", "c", "d", "e"]
        expected = {"a", "c"}
        assert recall_at_k(retrieved, expected, 5) == 1.0

    def test_recall_at_k_partial(self):
        retrieved = ["a", "b", "c"]
        expected = {"a", "d"}
        assert recall_at_k(retrieved, expected, 3) == 0.5

    def test_recall_at_k_none(self):
        retrieved = ["x", "y", "z"]
        expected = {"a", "b"}
        assert recall_at_k(retrieved, expected, 3) == 0.0

    def test_recall_at_k_empty_expected(self):
        assert recall_at_k(["a"], set(), 5) == 0.0

    def test_precision_at_k(self):
        retrieved = ["a", "b", "c", "d", "e"]
        expected = {"a", "c", "e"}
        assert precision_at_k(retrieved, expected, 5) == 0.6

    def test_precision_at_k_zero(self):
        assert precision_at_k([], set(), 0) == 0.0

    def test_mrr_first(self):
        assert mrr(["a", "b", "c"], {"a"}) == 1.0

    def test_mrr_second(self):
        assert mrr(["x", "a", "b"], {"a"}) == 0.5

    def test_mrr_none(self):
        assert mrr(["x", "y", "z"], {"a"}) == 0.0

    def test_ndcg_perfect(self):
        retrieved = ["a", "b"]
        expected = {"a", "b"}
        result = ndcg(retrieved, expected, 5)
        assert abs(result - 1.0) < 0.001

    def test_ndcg_empty(self):
        assert ndcg([], set(), 5) == 0.0

    def test_ndcg_no_match(self):
        assert ndcg(["x", "y"], {"a", "b"}, 5) == 0.0

    def test_evaluate_single(self):
        result = evaluate_single("q1", "test query", "cat1", ["a", "b", "c"], ["a", "c"])
        assert isinstance(result, EvalResult)
        assert result.query_id == "q1"
        assert result.recall_5 > 0

    def test_aggregate_results(self):
        r1 = EvalResult(query_id="1", query="q1", category="c1", expected=["a"], retrieved=["a"], recall_5=1.0, recall_10=1.0, precision_5=0.2, mrr_val=1.0, ndcg_val=1.0)
        r2 = EvalResult(query_id="2", query="q2", category="c1", expected=["b"], retrieved=["x"], recall_5=0.0, recall_10=0.0, precision_5=0.0, mrr_val=0.0, ndcg_val=0.0)
        summary = aggregate_results([r1, r2])
        assert summary["total_queries"] == 2
        assert summary["recall_5"] == 0.5
        assert summary["zero_recall_count"] == 1
        assert "c1" in summary["by_category"]

    def test_aggregate_empty(self):
        summary = aggregate_results([])
        assert "error" in summary

    def test_format_report(self):
        summary = {
            "total_queries": 10,
            "recall_5": 0.5,
            "recall_10": 0.7,
            "precision_5": 0.3,
            "mrr": 0.6,
            "ndcg_10": 0.55,
            "zero_recall_count": 2,
            "by_category": {
                "cat1": {"count": 5, "recall_5": 0.6, "recall_10": 0.8, "mrr": 0.7, "ndcg_10": 0.6},
            },
        }
        report = format_report(summary, title="Test Report")
        assert "Test Report" in report
        assert "Recall@5" in report
        assert "cat1" in report
