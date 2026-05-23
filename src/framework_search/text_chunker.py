"""Generic chunker for json/yaml/toml/text — sliding window, single-chunk for small files."""

from __future__ import annotations

from .chunker_base import Chunk
from .config import MAX_CHUNK_CHARS


def chunk_text(
    relative_path: str,
    content: str,
    mtime: float,
    language: str = "text",
    chunk_type: str = "config",
) -> list[Chunk]:
    """One chunk per file if it fits, else sliding window 4000-char with 800 overlap."""
    if not content.strip():
        return []

    if len(content) <= MAX_CHUNK_CHARS:
        total_lines = content.count("\n") + 1
        return [
            Chunk(
                relative_path=relative_path,
                content=content,
                language=language,
                chunk_type=chunk_type,
                symbol_name=None,
                line_start=1,
                line_end=total_lines,
                mtime=mtime,
            )
        ]

    out: list[Chunk] = []
    window = 4000
    overlap = 800
    step = window - overlap
    for offset in range(0, len(content), step):
        piece = content[offset : offset + window]
        if not piece.strip():
            continue
        ls = content.count("\n", 0, offset) + 1
        le = ls + piece.count("\n")
        out.append(
            Chunk(
                relative_path=relative_path,
                content=piece,
                language=language,
                chunk_type=chunk_type,
                symbol_name=None,
                line_start=ls,
                line_end=le,
                mtime=mtime,
            )
        )
        if offset + window >= len(content):
            break
    return out
