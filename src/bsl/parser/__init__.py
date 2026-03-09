"""
BSL AST Parser — Phase 59

Regex-based parser for 1C:Enterprise BSL (Built-in Scripting Language).
Extracts procedures, functions, variables, calls, regions.
"""

from .models import BSLSymbol, BSLModule, SymbolType, CompilationDirective
from .bsl_ast_parser import BSLASTParser
from .bsl_chunker import BSLChunker

__all__ = [
    "BSLASTParser",
    "BSLChunker",
    "BSLSymbol",
    "BSLModule",
    "SymbolType",
    "CompilationDirective",
]
