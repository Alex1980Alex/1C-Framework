"""
BSL Semantic Search - семантический поиск по BSL коду

Перенесено из D:\\1C-Enterprise_Framework\\bsl-semantic-search\\

Фаза 45: Миграция из 1C-Enterprise_Framework
"""

from .config import BSLSearchSettings, get_bsl_settings

# Lazy imports to avoid circular dependencies
__all__ = [
    "BSLSearchSettings",
    "get_bsl_settings",
    "BSLSearchService",
    "SearchRequest",
    "SearchMode",
    "SearchResult",
]

def __getattr__(name):
    """Lazy import of services to avoid circular dependencies"""
    if name == "BSLSearchService":
        from .services.search import BSLSearchService
        return BSLSearchService
    elif name == "SearchRequest":
        from .services.search import SearchRequest
        return SearchRequest
    elif name == "SearchMode":
        from .services.search import SearchMode
        return SearchMode
    elif name == "SearchResult":
        from .services.search import SearchResult
        return SearchResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
