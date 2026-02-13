"""Table of Contents parser — builds a hierarchical tree from markdown headings.

Phase 29: Parses document structure (Глава 5 → 5.1 → 5.1.1 → 5.14.3.6.2)
into a tree of ToCNode objects for section-scoped search and breadcrumb metadata.

Reuses the heading regex from RecursiveTextSplitter._parse_headings().
"""

import bisect
import re
from dataclasses import dataclass, field

# Same pattern as recursive.py
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass
class ToCNode:
    """A single section in the document hierarchy."""

    number: str  # "5.14.3.6" or "" for root/unnumbered
    title: str  # "Агрегаты"
    full_title: str  # "5.14.3.6. Агрегаты"
    level: int  # depth: 1, 2, 3, ...
    char_offset: int  # position in raw_text
    page_number: int | None = None
    children: list["ToCNode"] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)


class DocumentToC:
    """Parsed Table of Contents with tree and lookup structures."""

    def __init__(
        self,
        root: ToCNode,
        flat: list[ToCNode],
        by_number: dict[str, ToCNode],
    ):
        self.root = root
        self.flat = flat
        self.by_number = by_number

    @staticmethod
    def parse(
        raw_text: str,
        page_offsets: list[tuple[int, int]] | None = None,
    ) -> "DocumentToC":
        """Parse ToC from raw_text using markdown headings.

        Args:
            raw_text: Full document text with markdown headings.
            page_offsets: Optional [(char_offset, page_number)] for page assignment.

        Returns:
            DocumentToC with tree structure and flat index.
        """
        root = ToCNode(
            number="", title="root", full_title="root",
            level=0, char_offset=0,
        )
        flat: list[ToCNode] = []
        by_number: dict[str, ToCNode] = {}

        # Build offset arrays for page lookup
        offsets = [o[0] for o in page_offsets] if page_offsets else []
        page_nums = [o[1] for o in page_offsets] if page_offsets else []

        # Parent stack: [(level, node)]
        stack: list[tuple[int, ToCNode]] = [(0, root)]

        for match in _MD_HEADING_RE.finditer(raw_text):
            pos = match.start()
            heading_text = match.group(2).strip()

            # Normalize spaces around dots: "5 . 5 . 12" → "5.5.12"
            normalized = re.sub(r"\s*\.\s*", ".", heading_text)

            # Extract section number and title
            num_match = re.match(r"^(\d+(?:\.\d+)*)", normalized)
            title_part = normalized  # fallback
            if num_match:
                number = num_match.group(1)
                level = number.count(".") + 1
                title_part = normalized[num_match.end():].lstrip(". ")
                full_title = f"{number}. {title_part}" if title_part else number
            elif normalized.lower().startswith("глава"):
                number = ""
                level = 1
                full_title = normalized
                title_part = normalized
                # Try extracting chapter number: "Глава 5. Title"
                ch_match = re.match(r"глава\s+(\d+)", normalized, re.IGNORECASE)
                if ch_match:
                    number = ch_match.group(1)
            elif normalized.lower().startswith("рис."):
                continue  # Skip figures
            else:
                number = ""
                level = 1
                full_title = normalized

            title = title_part

            # Assign page number via binary search
            page_num = None
            if offsets:
                idx = bisect.bisect_right(offsets, pos) - 1
                if 0 <= idx < len(page_nums):
                    page_num = page_nums[idx]

            node = ToCNode(
                number=number,
                title=title,
                full_title=full_title,
                level=level,
                char_offset=pos,
                page_number=page_num,
            )

            # Find parent: pop stack until we find a node with lower level
            while len(stack) > 1 and stack[-1][0] >= level:
                stack.pop()

            parent = stack[-1][1]
            parent.children.append(node)
            stack.append((level, node))

            flat.append(node)
            if number:
                by_number[number] = node

        return DocumentToC(root=root, flat=flat, by_number=by_number)

    def find_by_prefix(self, prefix: str) -> list[ToCNode]:
        """Find all sections whose number starts with prefix.

        Example: find_by_prefix("5.14") returns 5.14, 5.14.1, 5.14.3.6.2, etc.
        """
        if not prefix:
            return list(self.flat)
        return [
            n for n in self.flat
            if n.number == prefix or n.number.startswith(prefix + ".")
        ]

    def get_breadcrumb(self, section_number: str) -> str:
        """Build breadcrumb path for a section number.

        Example: "5.14.3.6" → "5. ... > 5.14. Регистры > 5.14.3. Регистр накопления > 5.14.3.6. Агрегаты"
        """
        if not section_number:
            return ""

        parts: list[str] = []
        # Walk up the hierarchy: 5.14.3.6 → 5.14.3 → 5.14 → 5
        current = section_number
        while current:
            node = self.by_number.get(current)
            if node:
                parts.append(node.full_title)
            dot_pos = current.rfind(".")
            current = current[:dot_pos] if dot_pos > 0 else ""

        parts.reverse()
        return " > ".join(parts)

    def get_page_range(self, section_number: str) -> tuple[int | None, int | None]:
        """Get the page range for a section and its children.

        Returns (start_page, end_page) or (None, None) if not found.
        """
        nodes = self.find_by_prefix(section_number)
        if not nodes:
            return None, None

        pages = [n.page_number for n in nodes if n.page_number is not None]
        if not pages:
            return None, None

        return min(pages), max(pages)
