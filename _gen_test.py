import os
os.makedirs("tests/bsl", exist_ok=True)

lines = []
lines.append("#!/usr/bin/env python3")
lines.append(""""Tests for BSL parser, chunker, and evaluation metrics (Phase 58-59)."""
")
lines.append("import pytest")
lines.append("import math")
lines.append("from src.bsl.parser.models import (")
lines.append("    SymbolType, CompilationDirective, ModuleType,")
lines.append("    BSLParam, BSLCall, BSLSymbol, BSLVariable, BSLRegion, BSLModule,")
lines.append(")")
lines.append("from src.bsl.parser.bsl_ast_parser import BSLASTParser")
lines.append("from src.bsl.parser.bsl_chunker import BSLChunker, BSLChunk")
lines.append("from src.bsl.evaluation.metrics import (")
lines.append("    EvalResult, recall_at_k, precision_at_k, mrr, ndcg,")
lines.append("    evaluate_single, aggregate_results, format_report,")
lines.append(")

")

# TestModels
lines.append("class TestModels:
")
lines.append("    def test_symbol_type_values(self):")
lines.append("        assert SymbolType.PROCEDURE == \"procedure\"")
lines.append("        assert SymbolType.FUNCTION == \"function\"
")
lines.append("    def test_compilation_directive(self):")
lines.append("        assert CompilationDirective.AT_SERVER == \"AtServer\"")
lines.append("        assert CompilationDirective.AT_CLIENT == \"AtClient\"
")
lines.append("    def test_module_type(self):")
lines.append("        assert ModuleType.OBJECT_MODULE == \"object_module\"")
lines.append("        assert ModuleType.FORM_MODULE == \"form_module\"")
lines.append("        assert ModuleType.COMMON_MODULE == \"common_module\"
")

with open("tests/bsl/test_parser.py", "w", encoding="utf-8") as f:
    f.write("
".join(lines))
print("Step 1 done")
