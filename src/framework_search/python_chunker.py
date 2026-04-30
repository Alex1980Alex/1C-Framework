"""AST-based Python chunker. Falls back to sliding window if file fails to parse."""

from __future__ import annotations

import ast
import logging

from .chunker_base import Chunk
from .config import MAX_CHUNK_CHARS

logger = logging.getLogger(__name__)


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    """Inclusive line slice. AST line numbers are 1-based."""
    return "".join(lines[start - 1 : end])


def _sliding_window(text: str, window: int = 800, overlap: int = 200) -> list[tuple[int, int, str]]:
    """Char-based fallback. Returns (start_line_approx, end_line_approx, content)."""
    out: list[tuple[int, int, str]] = []
    if not text:
        return out
    step = max(window - overlap, 1)
    for i in range(0, len(text), step):
        piece = text[i : i + window]
        if not piece.strip():
            continue
        # approximate line numbers from char offset
        ls = text.count("\n", 0, i) + 1
        le = ls + piece.count("\n")
        out.append((ls, le, piece))
        if i + window >= len(text):
            break
    return out


def chunk_python(
    relative_path: str,
    content: str,
    mtime: float,
) -> list[Chunk]:
    """Split Python source by top-level functions, classes, and module-level groups."""
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("python_chunker: %s parse failed (%s); falling back to sliding window",
                     relative_path, e)
        return _fallback_chunks(relative_path, content, mtime)

    lines = content.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[Chunk] = []
    last_emitted_line = 0  # tracks where module-level code ended last

    top_level: list[ast.stmt] = list(tree.body)
    # Sort by line number (already in source order, but be safe).
    top_level.sort(key=lambda n: getattr(n, "lineno", 0))

    for node in top_level:
        ls = getattr(node, "lineno", None)
        le = getattr(node, "end_lineno", None)
        if ls is None or le is None:
            continue

        # Emit any module-level gap between last emitted and this node.
        if ls - 1 > last_emitted_line:
            gap_text = _slice_lines(lines, last_emitted_line + 1, ls - 1)
            if gap_text.strip():
                chunks.append(_make_module_chunk(
                    relative_path, gap_text, last_emitted_line + 1, ls - 1, mtime,
                ))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            text = _slice_lines(lines, ls, le)
            chunks.append(Chunk(
                relative_path=relative_path,
                content=text[:MAX_CHUNK_CHARS],
                language="python",
                chunk_type="function",
                symbol_name=node.name,
                line_start=ls,
                line_end=le,
                mtime=mtime,
            ))
        elif isinstance(node, ast.ClassDef):
            chunks.extend(_emit_class(relative_path, node, lines, mtime))
        else:
            # imports, assignments, expressions at module level — accumulate as gap
            text = _slice_lines(lines, ls, le)
            if text.strip():
                chunks.append(_make_module_chunk(relative_path, text, ls, le, mtime))

        last_emitted_line = le

    # Trailing module-level lines after last top-level node.
    total_lines = len(lines)
    if total_lines > last_emitted_line:
        tail = _slice_lines(lines, last_emitted_line + 1, total_lines)
        if tail.strip():
            chunks.append(_make_module_chunk(
                relative_path, tail, last_emitted_line + 1, total_lines, mtime,
            ))

    return chunks


def _make_module_chunk(
    relative_path: str, text: str, ls: int, le: int, mtime: float,
) -> Chunk:
    return Chunk(
        relative_path=relative_path,
        content=text[:MAX_CHUNK_CHARS],
        language="python",
        chunk_type="module",
        symbol_name=None,
        line_start=ls,
        line_end=le,
        mtime=mtime,
    )


def _emit_class(
    relative_path: str, node: ast.ClassDef, lines: list[str], mtime: float,
) -> list[Chunk]:
    """Emit class body: one chunk for class header + each method as its own chunk.

    For small classes (<= MAX_CHUNK_CHARS) emit a single class-level chunk.
    For larger ones, split methods into individual function chunks plus a
    "class header" chunk holding the class signature, decorators, and docstring.
    """
    cls_ls = node.lineno
    cls_le = node.end_lineno or cls_ls
    full_text = _slice_lines(lines, cls_ls, cls_le)

    if len(full_text) <= MAX_CHUNK_CHARS:
        return [Chunk(
            relative_path=relative_path,
            content=full_text,
            language="python",
            chunk_type="class",
            symbol_name=node.name,
            line_start=cls_ls,
            line_end=cls_le,
            mtime=mtime,
        )]

    out: list[Chunk] = []
    # Header = class def line + decorators + docstring (up to first method/inner-class)
    body = node.body or []
    methods = [b for b in body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))]
    first_method_line = methods[0].lineno if methods else cls_le + 1
    header_le = max(cls_ls, first_method_line - 1)
    header_text = _slice_lines(lines, cls_ls, header_le)
    if header_text.strip():
        out.append(Chunk(
            relative_path=relative_path,
            content=header_text[:MAX_CHUNK_CHARS],
            language="python",
            chunk_type="class",
            symbol_name=node.name,
            line_start=cls_ls,
            line_end=header_le,
            mtime=mtime,
        ))

    for m in methods:
        m_ls = m.lineno
        m_le = m.end_lineno or m_ls
        text = _slice_lines(lines, m_ls, m_le)
        out.append(Chunk(
            relative_path=relative_path,
            content=text[:MAX_CHUNK_CHARS],
            language="python",
            chunk_type="function",
            symbol_name=f"{node.name}.{m.name}",
            line_start=m_ls,
            line_end=m_le,
            mtime=mtime,
        ))
    return out


def _fallback_chunks(relative_path: str, content: str, mtime: float) -> list[Chunk]:
    """Sliding-window fallback for unparsable files."""
    out: list[Chunk] = []
    for ls, le, piece in _sliding_window(content):
        out.append(Chunk(
            relative_path=relative_path,
            content=piece[:MAX_CHUNK_CHARS],
            language="python",
            chunk_type="text",
            symbol_name=None,
            line_start=ls,
            line_end=le,
            mtime=mtime,
        ))
    return out
