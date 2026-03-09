"""
BSL Coding Assistant — Phase 66

Provides project-aware context for BSL code generation:
- Auto-context: object metadata, similar code, dependencies
- Code style extraction from existing codebase
"""

from .style_extractor import BSLStyleExtractor

__all__ = ["BSLStyleExtractor"]
