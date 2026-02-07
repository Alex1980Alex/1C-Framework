"""Parse template base classes (Phase 10).

Provides base template class and common parsing strategies.

Author: Claude Code
Version: 1.1.0 - Phase 10.5: Template-Based Parsing
"""

from abc import ABC, abstractmethod
from typing import Literal


class ParseTemplate(ABC):
    """
    Base class for document-specific parsing templates.

    Templates define how to prioritize and process different
    layout elements based on document type.
    """

    # Element priority (higher = more important)
    element_priorities: dict[str, int] = {
        "title": 10,
        "section_header": 9,
        "paragraph": 5,
        "list": 6,
        "table": 8,
        "image": 7,
    }

    # Elements to skip during indexing
    skip_elements: list[str] = []

    # Chunk size overrides per element type
    chunk_size_overrides: dict[str, int] = {}

    @abstractmethod
    def get_name(self) -> str:
        """Return template name."""
        pass

    def get_priority(self, element_type: str) -> int:
        """Get priority for an element type."""
        return self.element_priorities.get(element_type, 0)

    def should_skip(self, element_type: str) -> bool:
        """Check if element type should be skipped."""
        return element_type in self.skip_elements

    def get_chunk_size(self, element_type: str, default_size: int) -> int:
        """Get chunk size for element type."""
        return self.chunk_size_overrides.get(element_type, default_size)


class GenericTemplate(ParseTemplate):
    """Generic template for standard documents."""

    def get_name(self) -> str:
        return "generic"

    skip_elements: list[str] = ["header", "footer", "page_number"]


class ResearchPaperTemplate(ParseTemplate):
    """Template optimized for research/academic papers.

    Prioritizes:
    - Abstract > Methodology > Results > Conclusion
    - Skips: References, Acknowledgments
    """

    element_priorities: dict[str, int] = {
        "title": 10,
        "abstract": 10,  # If detected as special element
        "section_header": 9,
        "paragraph": 5,
        "table": 8,
        "image": 7,
        "list": 6,
        "equation": 8,
    }

    skip_elements: list[str] = [
        "header",
        "footer",
        "page_number",
        "references",
        "acknowledgments",
        "bibliography",
    ]

    # Larger chunks for methodology/results
    chunk_size_overrides: dict[str, int] = {
        "paragraph": 1200,
        "section_header": 1500,
    }

    def get_name(self) -> str:
        return "research_paper"


class UserManualTemplate(ParseTemplate):
    """Template optimized for user manuals and documentation.

    Prioritizes:
    - Instructions > Warnings > Examples
    - Preserves numbered lists as units
    """

    element_priorities: dict[str, int] = {
        "title": 10,
        "section_header": 9,
        "instruction": 10,  # If detected as special element
        "warning": 9,  # If detected as special element
        "paragraph": 5,
        "list": 8,  # High priority for lists
        "table": 7,
        "image": 8,
        "code_block": 9,
    }

    skip_elements: list[str] = [
        "header",
        "footer",
        "page_number",
    ]

    # Keep lists together as much as possible
    chunk_size_overrides: dict[str, int] = {
        "list": 2000,  # Larger chunks for lists
        "code_block": 1500,
    }

    def get_name(self) -> str:
        return "user_manual"


# Template registry
TEMPLATE_REGISTRY: dict[str, type[ParseTemplate]] = {
    "generic": GenericTemplate,
    "research_paper": ResearchPaperTemplate,
    "user_manual": UserManualTemplate,
}


def get_template(template_name: str) -> ParseTemplate:
    """
    Get template instance by name.

    Args:
        template_name: Template identifier

    Returns:
        Template instance
    """
    template_class = TEMPLATE_REGISTRY.get(template_name, GenericTemplate)
    return template_class()


def detect_document_type(
    layout_elements: list[dict],
) -> Literal["generic", "research_paper", "user_manual"]:
    """
    Auto-detect document type from layout elements.

    Args:
        layout_elements: List of layout element dicts

    Returns:
        Detected document type
    """
    if not layout_elements:
        return "generic"

    # Count element types
    element_counts: dict[str, int] = {}
    for el in layout_elements:
        el_type = el.get("type", "unknown")
        element_counts[el_type] = element_counts.get(el_type, 0) + 1

    total = len(layout_elements)

    # Check for research paper indicators
    has_abstract = any(
        "abstract" in el.get("content", "").lower()
        for el in layout_elements
    )
    has_references = any(
        "references" in el.get("content", "").lower()
        for el in layout_elements
    )
    high_table_ratio = element_counts.get("table", 0) / total > 0.1

    if has_abstract or (has_references and high_table_ratio):
        return "research_paper"

    # Check for user manual indicators
    high_list_ratio = element_counts.get("list", 0) / total > 0.15
    has_instructions = any(
        word in el.get("content", "").lower()
        for el in layout_elements
        for word in ["instruction", "step", "warning", "note"]
    )

    if high_list_ratio or has_instructions:
        return "user_manual"

    return "generic"
