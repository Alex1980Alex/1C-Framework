"""Wiki Search Adapter — stub for Obsidian vault search.

Returns empty results until Phase 1 (Obsidian Vault Integration)
provides the actual MCP client connection.
"""

import logging

from ..unified_id import SourceServer
from ..unified_search import BaseSearchAdapter, SearchResultItem

logger = logging.getLogger(__name__)


class WikiSearchAdapter(BaseSearchAdapter):
    """Search adapter for Obsidian wiki pages.

    Stub implementation: returns empty results.
    Real implementation in Phase 1 will query obsidian-mcp.
    """

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        logger.debug(f"[WikiAdapter] Stub search: query={query!r}, limit={limit}")
        return []

    def source_name(self) -> str:
        return SourceServer.OBSIDIAN_VAULT.value
