"""External sources integration (Phase 37).

Source fusion: combine PDF docs + web + external APIs.
Trust scoring: docs > 1C API > wiki > web.
"""

from src.pdf_framework.search.external_sources.source_fusion import SourceFusion

__all__ = ["SourceFusion"]
