"""Parse templates for different document types (Phase 10).

Provides templates that customize parsing based on document structure:
- ResearchPaperTemplate: for academic papers
- UserManualTemplate: for documentation and manuals
- GenericTemplate: fallback for standard documents
"""

from src.pdf_framework.loaders.templates.base import (
    ParseTemplate,
    ResearchPaperTemplate,
    UserManualTemplate,
    detect_document_type,
    get_template,
)

__all__ = [
    "ParseTemplate",
    "ResearchPaperTemplate",
    "UserManualTemplate",
    "get_template",
    "detect_document_type",
]
