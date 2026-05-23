"""Graph Search Adapter — proxy to entity embeddings.

Returns empty results until Phase 4 (PDF → Wiki Export)
provides the actual graph store connection.
"""

import logging

from ..unified_id import SourceServer
from ..unified_search import BaseSearchAdapter, SearchResultItem

logger = logging.getLogger(__name__)


class GraphSearchAdapter(BaseSearchAdapter):
    """Search adapter for knowledge graph entities.

    Stub implementation: returns empty results.
    Real implementation in Phase 4 will query entity_embeddings.
    """

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        logger.debug(f"[GraphAdapter] Stub search: query={query!r}, limit={limit}")
        return []

    def source_name(self) -> str:
        return SourceServer.LIGHTRAG.value
