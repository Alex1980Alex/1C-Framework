"""Phase 8.12.5 (A2 sliding-window split) + 8.12.2 (module_summary policy).

Goals:
- Long symbols are split into multiple overlapping chunks (no XXL bucket).
- Short symbols pass through unchanged.
- Split metadata is correct (split_part, split_total, parent_chunk_id).
- Adjacent split chunks share content (overlap > 0).
- Pathologically large module_summary is dropped (low semantic value, high
  VRAM cost — see roadmap §21.2).
"""
from __future__ import annotations

import pytest

from src.bsl.parser.bsl_chunker import BSLChunker, BSLChunk
from src.bsl.parser.models import (
    BSLModule,
    BSLSymbol,
    ModuleType,
    SymbolType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_symbol(name: str, body: str, line_start: int = 1) -> BSLSymbol:
    """Build a minimal BSLSymbol for chunking tests."""
    return BSLSymbol(
        name=name,
        symbol_type=SymbolType.FUNCTION,
        line_start=line_start,
        line_end=line_start + body.count("\n"),
        body=body,
        is_export=False,
    )


def _make_module(symbols: list[BSLSymbol], path: str = "src/CommonModules/Test/Ext/Module.bsl") -> BSLModule:
    return BSLModule(
        file_path=path,
        module_type=ModuleType.COMMON_MODULE,
        symbols=symbols,
        line_count=sum(s.body.count("\n") + 1 for s in symbols),
    )


def _huge_dictionary_body(num_lines: int = 1200) -> str:
    """Synthesize a translation-dictionary-style body (~80 chars/line,
    Cyrillic-heavy) to mirror the Slovar-en-ru chunk from roadmap §21.2."""
    lines = [
        f'    map_insert("english_word_{i:04d}", "русское_слово_{i:04d}_в_словаре");'
        for i in range(num_lines)
    ]
    header = "Функция SlovarEnRu()\n    map_init();\n"
    footer = "\n    Возврат map;\nКонецФункции"
    return header + "\n".join(lines) + footer


# ---------------------------------------------------------------------------
# A2 — sliding-window split
# ---------------------------------------------------------------------------


def test_short_symbol_unchanged():
    """A symbol below split_threshold_chars passes through as a single chunk."""
    chunker = BSLChunker(include_module_summary=False)
    body = "Функция Малая()\n    Возврат 42;\nКонецФункции"
    module = _make_module([_make_symbol("Малая", body)])
    chunks = chunker.chunk_module(module)
    assert len(chunks) == 1
    assert "split_part" not in chunks[0].metadata


def test_long_symbol_splits_into_multiple_parts():
    """Slovar-en-ru class chunk (~97k chars) must produce ≥30 chunks
    (roadmap 8.12.5 acceptance criterion).
    """
    chunker = BSLChunker(include_module_summary=False)
    body = _huge_dictionary_body(num_lines=1200)
    module = _make_module([_make_symbol("SlovarEnRu", body)])
    chunks = chunker.chunk_module(module)

    assert len(chunks) >= 30, (
        f"Expected ≥30 chunks for {len(body)}-char body with "
        f"window={chunker.window_chars}/overlap={chunker.overlap_chars}, "
        f"got {len(chunks)}"
    )

    # All must be sub-window-sized (give a small line-rounding margin).
    for c in chunks:
        assert len(c.content) <= chunker.window_chars + 200, (
            f"Chunk {c.metadata.get('split_part')}: {len(c.content)} chars > "
            f"window+200 ({chunker.window_chars + 200})"
        )


def test_split_metadata_is_correct():
    chunker = BSLChunker(include_module_summary=False)
    body = _huge_dictionary_body(num_lines=300)
    module = _make_module([_make_symbol("BigSym", body)])
    chunks = chunker.chunk_module(module)
    assert len(chunks) > 1

    parent_id = None
    for i, c in enumerate(chunks):
        assert c.metadata["split_part"] == i
        assert c.metadata["split_total"] == len(chunks)
        assert c.metadata["parent_chunk_id"], "parent_chunk_id missing"
        if parent_id is None:
            parent_id = c.metadata["parent_chunk_id"]
        else:
            assert c.metadata["parent_chunk_id"] == parent_id, (
                "All split parts must share the same parent_chunk_id"
            )
        assert c.metadata["name"] == f"BigSym_part{i}"
        assert c.chunk_id.endswith(f"__part{i}")


def test_split_overlap_present_between_adjacent_parts():
    """Overlap > 0 is the whole point of a sliding window — adjacent parts
    must share at least one full line of content."""
    chunker = BSLChunker(include_module_summary=False)
    body = _huge_dictionary_body(num_lines=300)
    module = _make_module([_make_symbol("BigSym", body)])
    chunks = chunker.chunk_module(module)
    assert len(chunks) >= 2

    for i in range(len(chunks) - 1):
        a_lines = set(chunks[i].content.splitlines())
        b_lines = set(chunks[i + 1].content.splitlines())
        common = a_lines & b_lines
        # At least 3 shared lines (overlap_chars=750 / line~80 chars ≈ 9 lines).
        assert len(common) >= 3, (
            f"Parts {i}↔{i+1}: only {len(common)} shared lines "
            f"(expected ≥3 from overlap_chars={chunker.overlap_chars})"
        )


def test_split_threshold_is_respected():
    """A chunk just under threshold stays whole; just above splits."""
    chunker = BSLChunker(include_module_summary=False)

    short_body = "x = 1;\n" * 700  # ~4900 chars
    short_mod = _make_module([_make_symbol("Short", short_body)])
    short_chunks = chunker.chunk_module(short_mod)
    assert len(short_chunks) == 1, (
        f"5K-char chunk should not split (got {len(short_chunks)})"
    )

    long_body = "y = 2;\n" * 2000  # ~14000 chars
    long_mod = _make_module([_make_symbol("Long", long_body)])
    long_chunks = chunker.chunk_module(long_mod)
    assert len(long_chunks) > 1


def test_split_handles_single_oversize_line():
    """A single line longer than window_chars must be force-emitted whole
    (no infinite loop). Embedder's max_seq_length will truncate."""
    chunker = BSLChunker(
        include_module_summary=False,
        split_threshold_chars=200,
        window_chars=100,
        overlap_chars=20,
    )
    giant_line = 'map_insert("' + "X" * 480 + '");'
    module = _make_module([_make_symbol("OneLine", giant_line)])
    chunks = chunker.chunk_module(module)
    assert len(chunks) >= 1
    assert any(giant_line in c.content for c in chunks)


def test_overlap_must_be_less_than_window():
    """Defensive ctor check — otherwise the splitter loops forever."""
    with pytest.raises(ValueError, match="overlap_chars"):
        BSLChunker(window_chars=1000, overlap_chars=1000)
    with pytest.raises(ValueError, match="overlap_chars"):
        BSLChunker(window_chars=500, overlap_chars=600)


# ---------------------------------------------------------------------------
# 8.12.2 — module_summary drop policy
# ---------------------------------------------------------------------------


def test_module_summary_kept_for_normal_module():
    chunker = BSLChunker(include_module_summary=True)
    syms = [
        _make_symbol(f"Sym{i}", f"Функция Sym{i}()\n    Возврат {i};\nКонецФункции")
        for i in range(20)
    ]
    module = _make_module(syms)
    chunks = chunker.chunk_module(module)
    summaries = [c for c in chunks if c.metadata.get("chunk_type") == "module_summary"]
    assert len(summaries) == 1, "Normal module must have exactly one summary"


def test_module_summary_dropped_for_pathological_module():
    """UpravlenieDostupom-class case: thousands of symbols → 70k+ chars summary.
    Roadmap §21.2 marks these as the worst chunks in the index."""
    chunker = BSLChunker(include_module_summary=True)
    # Each symbol contributes ~50 chars to the summary's "Symbols:" listing.
    # 5000 symbols → ~250k chars summary (well above default 30000 limit).
    syms = [
        _make_symbol(f"VeryLongSymbolName{i:05d}", f"Возврат {i};")
        for i in range(5000)
    ]
    module = _make_module(syms)
    chunks = chunker.chunk_module(module)
    summaries = [c for c in chunks if c.metadata.get("chunk_type") == "module_summary"]
    assert len(summaries) == 0, (
        "Pathological module_summary (>30k chars) must be dropped"
    )

    # Symbol chunks themselves should still be present (drop policy only
    # affects the summary).
    symbol_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "symbol"]
    assert len(symbol_chunks) == 5000


def test_module_summary_drop_threshold_configurable():
    """Tighter threshold drops sooner."""
    chunker = BSLChunker(include_module_summary=True, max_summary_chars=200)
    syms = [_make_symbol(f"S{i}", f"Возврат {i};") for i in range(50)]
    module = _make_module(syms)
    chunks = chunker.chunk_module(module)
    summaries = [c for c in chunks if c.metadata.get("chunk_type") == "module_summary"]
    assert len(summaries) == 0, "Tight threshold must drop the summary"
