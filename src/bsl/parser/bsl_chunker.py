"""
BSL Symbol-Level Chunker — Phase 59

Converts parsed BSLModule into search-ready chunks with rich metadata.
Each procedure/function becomes a separate chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import BSLModule, BSLSymbol, SymbolType


@dataclass
class BSLChunk:
    """A search-ready chunk derived from a BSL symbol."""

    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.metadata.get("name", "")

    @property
    def module_path(self) -> str:
        return self.metadata.get("module_path", "")


class BSLChunker:
    """Converts BSLModule into chunks for indexing.

    Phase 8.12.5 (A2 sliding-window split): symbols whose body exceeds
    `split_threshold_chars` are split into overlapping windows. Defaults
    target the industry standard from AST-RAG / Coding-PTM literature:
    window=1024 tokens, overlap=256 (25%) — translated to chars via a
    conservative 3-char/token ratio for mixed Cyrillic+Latin BSL code.

    Phase 8.12.2 (module_summary policy): synthetic summaries for
    pathologically large modules (UpravlenieDostupom-class, 70k+ chars
    of "Symbols:" lines) are dropped instead of indexed — they have the
    lowest semantic value in the index but the highest VRAM cost.
    """

    # ~ token-to-char ratio for BSL code: Cyrillic identifiers tokenize
    # ~3-4 chars/token, Latin keywords ~4-5 chars/token. We use 3 (the
    # tighter end) so the resulting windows fit comfortably under the
    # 4096-token model.max_seq_length cap set in scripts/reindex_bsl_qwen3.
    DEFAULT_SPLIT_THRESHOLD_CHARS = 6000   # ~ 2K tokens — split anything bigger
    DEFAULT_WINDOW_CHARS = 3000             # ~ 1024 tokens
    DEFAULT_OVERLAP_CHARS = 750             # ~ 256 tokens (25%)
    DEFAULT_MAX_SUMMARY_CHARS = 30000       # ~ 10K tokens — drop above

    def __init__(
        self,
        include_module_summary: bool = True,
        max_context_lines: int = 3,
        split_threshold_chars: int | None = None,
        window_chars: int | None = None,
        overlap_chars: int | None = None,
        max_summary_chars: int | None = None,
    ) -> None:
        self.include_module_summary = include_module_summary
        self.max_context_lines = max_context_lines
        self.split_threshold_chars = (
            split_threshold_chars if split_threshold_chars is not None
            else self.DEFAULT_SPLIT_THRESHOLD_CHARS
        )
        self.window_chars = (
            window_chars if window_chars is not None
            else self.DEFAULT_WINDOW_CHARS
        )
        self.overlap_chars = (
            overlap_chars if overlap_chars is not None
            else self.DEFAULT_OVERLAP_CHARS
        )
        self.max_summary_chars = (
            max_summary_chars if max_summary_chars is not None
            else self.DEFAULT_MAX_SUMMARY_CHARS
        )
        # Defensive: overlap must leave forward progress.
        if self.overlap_chars >= self.window_chars:
            raise ValueError(
                f"overlap_chars ({self.overlap_chars}) must be < window_chars "
                f"({self.window_chars}) — otherwise splitter loops forever."
            )

    def chunk_module(self, module: BSLModule) -> list[BSLChunk]:
        """Convert a parsed BSL module into indexable chunks."""
        chunks: list[BSLChunk] = []

        # Module summary chunk (may be dropped for pathologically large modules)
        if self.include_module_summary:
            summary = self._build_module_summary(module)
            if summary:
                chunks.append(summary)

        # Symbol chunks — split anything that exceeds the threshold.
        for symbol in module.symbols:
            chunk = self._build_symbol_chunk(symbol, module)
            chunks.extend(self._split_long_chunk(chunk))

        return chunks

    def chunk_modules(self, modules: list[BSLModule]) -> list[BSLChunk]:
        """Convert multiple modules into chunks."""
        all_chunks: list[BSLChunk] = []
        for module in modules:
            all_chunks.extend(self.chunk_module(module))
        return all_chunks

    def _build_module_summary(self, module: BSLModule) -> BSLChunk | None:
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

        # Phase 8.12.2: drop pathologically large summaries (e.g. UpravlenieDostupom
        # with thousands of symbols → 70k chars). Roadmap §21.2 documents these as
        # the lowest-semantic-value chunks in the index. The summary is purely
        # synthetic (lines: 0); skipping it loses no source code.
        if len(content) > self.max_summary_chars:
            return None

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
        parts: list[str] = []

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


    def _split_long_chunk(self, chunk: BSLChunk) -> list[BSLChunk]:
        """Phase 8.12.5 (A2): split a too-long symbol chunk via line-aware
        sliding window.

        Returns `[chunk]` unchanged for content <= split_threshold_chars.
        Otherwise returns N chunks where each window is `window_chars` long
        with `overlap_chars` shared between adjacent parts. Splits on line
        boundaries so BSL syntax stays readable inside each window.

        Each split chunk inherits the parent's metadata with three additions:
            split_part:       0..N-1
            split_total:      N
            parent_chunk_id:  original chunk_id (for de-duplication / merge
                              at retrieval time if needed)
        and `name` is suffixed `_part{i}` to keep chunk names unique.
        """
        content = chunk.content
        if len(content) <= self.split_threshold_chars:
            return [chunk]

        lines = content.splitlines(keepends=True)
        line_lens = [len(line) for line in lines]
        n = len(lines)

        # Edge case: a single line > window_chars (e.g., minified BSL or a
        # giant string literal). Force-emit it whole rather than infinite-loop
        # — embedder's max_seq_length cap will truncate at forward time.
        windows: list[str] = []
        start = 0
        while start < n:
            end = start
            cur_len = 0
            while end < n and cur_len + line_lens[end] <= self.window_chars:
                cur_len += line_lens[end]
                end += 1
            if end == start:
                # Single oversize line — include it whole.
                end = start + 1
                cur_len = line_lens[start]
            windows.append("".join(lines[start:end]))
            if end >= n:
                break
            # Advance start by (window - overlap) chars worth of leading lines.
            advance_chars = max(self.window_chars - self.overlap_chars, 1)
            new_start = start
            consumed = 0
            while new_start < end and consumed < advance_chars:
                consumed += line_lens[new_start]
                new_start += 1
            # Forward-progress guarantee.
            if new_start <= start:
                new_start = start + 1
            start = new_start

        if len(windows) <= 1:
            return [chunk]

        out: list[BSLChunk] = []
        original_name = chunk.metadata.get("name", "")
        for i, body in enumerate(windows):
            new_meta = dict(chunk.metadata)
            new_meta["split_part"] = i
            new_meta["split_total"] = len(windows)
            new_meta["parent_chunk_id"] = chunk.chunk_id
            new_meta["name"] = f"{original_name}_part{i}" if original_name else f"part{i}"
            out.append(BSLChunk(
                chunk_id=f"{chunk.chunk_id}__part{i}",
                content=body,
                metadata=new_meta,
            ))
        return out


def _safe_id(s: str) -> str:
    """Convert string to a safe ID component.

    Fix #3 (2026-05-21): For strings > 80 chars, append SHA1 hash suffix to
    avoid chunk_id collisions on long similar paths (e.g. multiple
    Commands/X/CommandModule.bsl under same Catalog truncated to same prefix).
    """
    import re as _re
    import hashlib
    cleaned = _re.sub(r"[^\w]", "_", s).strip("_")
    if len(cleaned) <= 80:
        return cleaned
    # Length-stable, collision-free: 60-char prefix + 16-char SHA1 hash
    return cleaned[:60] + "_" + hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:16]
