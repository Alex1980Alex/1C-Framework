"""Markdown chunker — splits by ATX headings (#, ##, ###) preserving heading path."""

from __future__ import annotations

import re

from .chunker_base import Chunk
from .config import MAX_CHUNK_CHARS

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def chunk_markdown(
    relative_path: str,
    content: str,
    mtime: float,
) -> list[Chunk]:
    """Split markdown by H1-H3 headings; H4+ stay inside parent section.

    Each chunk's symbol_name = ' > '-joined heading path (e.g. 'Setup > Docker').
    Sections longer than MAX_CHUNK_CHARS are split by paragraph blocks.
    """
    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    n = len(lines)

    # Find heading boundaries (level <= 3), skipping anything inside ```/~~~ fences.
    boundaries: list[tuple[int, int, str]] = []  # (line_idx_0based, level, heading_text)
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line.rstrip("\n"))
        if m and len(m.group(1)) <= 3:
            boundaries.append((i, len(m.group(1)), m.group(2).strip()))

    chunks: list[Chunk] = []

    if not boundaries:
        # No headings — emit whole file as one chunk (or split if too big).
        return _emit_section(relative_path, content, "", 1, n, mtime)

    # Preamble before first heading.
    if boundaries[0][0] > 0:
        pre = "".join(lines[: boundaries[0][0]])
        if pre.strip():
            chunks.extend(
                _emit_section(
                    relative_path,
                    pre,
                    "",
                    1,
                    boundaries[0][0],
                    mtime,
                )
            )

    # Walk sections.
    heading_stack: list[tuple[int, str]] = []  # [(level, text), ...]
    for idx, (line_idx, level, text) in enumerate(boundaries):
        # Update heading path: pop deeper-or-equal levels.
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, text))
        path_str = " > ".join(t for _, t in heading_stack)

        next_line_idx = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else n
        section_text = "".join(lines[line_idx:next_line_idx])
        if not section_text.strip():
            continue
        chunks.extend(
            _emit_section(
                relative_path,
                section_text,
                path_str,
                line_idx + 1,
                next_line_idx,
                mtime,
            )
        )

    return chunks


def _emit_section(
    relative_path: str,
    text: str,
    symbol_name: str,
    line_start: int,
    line_end: int,
    mtime: float,
) -> list[Chunk]:
    """Emit one or more section chunks; split by paragraph if oversize."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [
            Chunk(
                relative_path=relative_path,
                content=text,
                language="markdown",
                chunk_type="section",
                symbol_name=symbol_name or None,
                line_start=line_start,
                line_end=line_end,
                mtime=mtime,
            )
        ]

    # Split by blank-line paragraph boundaries, accumulate up to limit.
    paragraphs = re.split(r"\n\s*\n", text)
    out: list[Chunk] = []
    buf = ""
    buf_start_line = line_start
    cur_line = line_start
    for para in paragraphs:
        para_lines = para.count("\n") + 1
        if buf and len(buf) + len(para) + 2 > MAX_CHUNK_CHARS:
            out.append(
                Chunk(
                    relative_path=relative_path,
                    content=buf,
                    language="markdown",
                    chunk_type="section",
                    symbol_name=symbol_name or None,
                    line_start=buf_start_line,
                    line_end=cur_line,
                    mtime=mtime,
                )
            )
            buf = ""
            buf_start_line = cur_line + 1
        buf = (buf + "\n\n" + para) if buf else para
        cur_line += para_lines + 1  # +1 for blank line separator
    if buf.strip():
        out.append(
            Chunk(
                relative_path=relative_path,
                content=buf,
                language="markdown",
                chunk_type="section",
                symbol_name=symbol_name or None,
                line_start=buf_start_line,
                line_end=line_end,
                mtime=mtime,
            )
        )
    return out
