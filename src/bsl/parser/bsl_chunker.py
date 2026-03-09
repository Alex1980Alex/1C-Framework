"""
BSL Symbol-Level Chunker — Phase 59

Converts parsed BSLModule into search-ready chunks with rich metadata.
Each procedure/function becomes a separate chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import BSLModule, BSLSymbol, SymbolType


@dataclass
class BSLChunk:
    """A search-ready chunk derived from a BSL symbol."""

    chunk_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.metadata.get("name", "")

    @property
    def module_path(self) -> str:
        return self.metadata.get("module_path", "")


class BSLChunker:
    """Converts BSLModule into chunks for indexing."""

    def __init__(
        self,
        include_module_summary: bool = True,
        max_context_lines: int = 3,
    ) -> None:
        self.include_module_summary = include_module_summary
        self.max_context_lines = max_context_lines

    def chunk_module(self, module: BSLModule) -> List[BSLChunk]:
        """Convert a parsed BSL module into indexable chunks."""
        chunks: List[BSLChunk] = []

        # Module summary chunk
        if self.include_module_summary:
            summary = self._build_module_summary(module)
            if summary:
                chunks.append(summary)

        # Symbol chunks
        for symbol in module.symbols:
            chunk = self._build_symbol_chunk(symbol, module)
            chunks.append(chunk)

        return chunks

    def chunk_modules(self, modules: List[BSLModule]) -> List[BSLChunk]:
        """Convert multiple modules into chunks."""
        all_chunks: List[BSLChunk] = []
        for module in modules:
            all_chunks.extend(self.chunk_module(module))
        return all_chunks

    def _build_module_summary(self, module: BSLModule) -> Optional[BSLChunk]:
        """Create a summary chunk for the entire module."""
        if not module.symbols:
            return None

        parts = [f"Module: {module.module_name}"]
        parts.append(f"Type: {module.module_type.value}")
        parts.append(f"Path: {module.file_path}")
        parts.append(f"Symbols: {len(module.symbols)}")

        if module.variables:
            var_names = ", ".join(v.name for v in module.variables[:10])
            parts.append(f"Variables: {var_names}")

        exports = module.exports
        if exports:
            export_list = ", ".join(f"{s.name}()" for s in exports[:20])
            parts.append(f"Exports: {export_list}")

        # List all symbols with types
        parts.append("\nSymbols:")
        for s in module.symbols:
            kind = "Proc" if s.symbol_type == SymbolType.PROCEDURE else "Func"
            exp = " [Export]" if s.is_export else ""
            parts.append(f"  {kind} {s.name}({s.params_str}){exp}")

        content = "\n".join(parts)
        chunk_id = f"{_safe_id(module.file_path)}__summary"

        return BSLChunk(
            chunk_id=chunk_id,
            content=content,
            metadata={
                "name": module.module_name,
                "chunk_type": "module_summary",
                "module_path": module.file_path,
                "module_type": module.module_type.value,
                "symbol_count": len(module.symbols),
                "export_count": len(exports),
                "line_count": module.line_count,
            },
        )

    def _build_symbol_chunk(self, symbol: BSLSymbol, module: BSLModule) -> BSLChunk:
        """Create a chunk for a single symbol (procedure/function)."""
        # Build enriched content: comment + signature context + body
        parts: List[str] = []

        # Module context line
        parts.append(f"// Module: {module.module_name} ({module.module_type.value})")

        # Region context
        if symbol.region:
            parts.append(f"// Region: {symbol.region}")

        # Preceding comment
        if symbol.comment:
            for line in symbol.comment.split("\n"):
                parts.append(f"// {line}")

        # The symbol body itself
        parts.append(symbol.body)

        content = "\n".join(parts)
        chunk_id = f"{_safe_id(module.file_path)}__{_safe_id(symbol.name)}"

        # Build calls list for metadata
        calls_list = [
            f"{c.callee_module}.{c.callee_method}" if c.callee_module else c.callee_method
            for c in symbol.calls
        ]

        return BSLChunk(
            chunk_id=chunk_id,
            content=content,
            metadata={
                "name": symbol.name,
                "chunk_type": "symbol",
                "symbol_type": symbol.symbol_type.value,
                "is_export": symbol.is_export,
                "params": symbol.params_str,
                "module_path": module.file_path,
                "module_name": module.module_name,
                "module_type": module.module_type.value,
                "line_start": symbol.line_start,
                "line_end": symbol.line_end,
                "compilation_directive": symbol.compilation_directive.value,
                "region": symbol.region or "",
                "comment": symbol.comment,
                "calls": calls_list,
                "signature": symbol.signature,
            },
        )


def _safe_id(s: str) -> str:
    """Convert string to a safe ID component."""
    import re as _re
    return _re.sub(r"[^\w]", "_", s).strip("_")[:80]
