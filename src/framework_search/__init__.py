"""
Framework Self-Search — semantic code search over the framework's own codebase.

Indexes Python sources, hooks, skills, configs, and project docs into a
dedicated Qdrant collection (`framework_code_v1`) using Qwen3-Embedding-8B
via the existing TEI HTTP backend (Phase 8.12.6+ infrastructure reuse).

Stages:
  Stage 1: manual indexer + chunkers (this module)
  Stage 2: MCP server with lazy mtime check (tools/framework-search-mcp/)
  Stage 3: file watcher daemon (scripts/watch_framework.py)
"""

from .chunker_base import Chunk

__all__ = ["Chunk"]
