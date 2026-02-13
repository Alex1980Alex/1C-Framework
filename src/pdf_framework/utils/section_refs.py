"""Phase 41: Section reference utilities for RAG answers.

Extracts section numbers from chunk metadata and content,
and appends a navigation block to answers.
"""

import re
from typing import Any

# Pattern for section numbers like 5.9.4.3
_SECTION_RE = re.compile(r"\*{0,2}(\d+(?:\.\d+)+)\.\s*([^*\n]+)")


def extract_sections_from_chunks(chunks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Extract (section_number, section_name) pairs from chunk metadata and content.

    Looks for section numbers in:
    1. metadata.section_title (e.g. '**5.9.Документы**')
    2. Bold headers in content (e.g. '**5.9.4.3. Свойства нумератора**')

    Returns the most specific subsections found, deduplicated.
    """
    sections: dict[str, str] = {}  # number -> name

    for chunk in chunks:
        meta = chunk if isinstance(chunk, dict) else {}

        # From metadata.section_title
        sec_title = meta.get("section_title", "") or meta.get("breadcrumb", "")
        if sec_title:
            _extract_from_text(sec_title, sections)

        # From content — look for bold headers **X.Y.Z. Name**
        content = meta.get("content", "")
        if content:
            _extract_from_text(content, sections)

    # Sort by section number
    result = sorted(sections.items(), key=lambda x: _section_sort_key(x[0]))
    return result


def extract_sections_from_search_results(results: list) -> list[tuple[str, str]]:
    """Extract sections from SearchResult objects (with .chunk attribute)."""
    chunks = []
    for r in results:
        chunk_data = {
            "section_title": r.chunk.metadata.get("section_title", ""),
            "breadcrumb": r.chunk.metadata.get("breadcrumb", ""),
            "content": r.chunk.content,
        }
        chunks.append(chunk_data)
    return extract_sections_from_chunks(chunks)


def build_section_nav_block(sections: list[tuple[str, str]]) -> str:
    """Build '📚 Где найти в документации:' block from section list."""
    if not sections:
        return ""

    lines = ["\n\n**Где найти в документации:**"]
    for num, name in sections:
        lines.append(f"- §{num} — {name}")
    return "\n".join(lines)


def append_section_refs(answer: str, results: list) -> str:
    """Append section navigation block to an answer if not already present.

    Args:
        answer: The LLM-generated answer text
        results: List of SearchResult objects used to generate the answer

    Returns:
        Answer with section navigation block appended
    """
    # Don't duplicate if LLM already added it
    if "Где найти в документации" in answer:
        return answer

    sections = extract_sections_from_search_results(results)
    nav_block = build_section_nav_block(sections)
    if nav_block:
        return answer + nav_block
    return answer


def _extract_from_text(text: str, sections: dict[str, str]) -> None:
    """Extract section numbers from text into sections dict."""
    for match in _SECTION_RE.finditer(text):
        num = match.group(1)
        name = match.group(2).strip().rstrip("*")
        # Skip dates like 08.02.2026 — name starts with a 4-digit year
        if re.match(r"\d{4}", name):
            continue
        # Skip if name is empty or purely numeric
        if not name or name.isdigit():
            continue
        # Keep the longer (more descriptive) name if duplicate
        if num not in sections or len(name) > len(sections[num]):
            sections[num] = name


def _section_sort_key(num: str) -> list[int]:
    """Convert '5.9.4.3' to [5, 9, 4, 3] for sorting."""
    try:
        return [int(x) for x in num.split(".")]
    except ValueError:
        return [0]
