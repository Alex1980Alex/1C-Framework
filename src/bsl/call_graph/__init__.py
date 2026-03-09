"""
BSL Call Graph — Phase 61

SQLite-based call graph for 1C Enterprise BSL code analysis.
Supports: callers, callees, impact analysis, dead code detection.
"""

from .store import CallGraphStore

__all__ = ["CallGraphStore"]
