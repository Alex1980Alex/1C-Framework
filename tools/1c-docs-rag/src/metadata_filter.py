#!/usr/bin/env python3
"""
Metadata Filter for RAG - Faceted search with metadata filtering.

Version: 1.0 (2026-01-24)

Provides:
- ChunkMetadata: Schema for document metadata
- MetadataFilter: Filter documents by metadata
- FacetedSearch: Search with facet aggregation
- Integration with 1c-docs-rag MCP

Features:
- Filter by doc_type (markdown, bsl, xml)
- Filter by tags (OR logic)
- Filter by date range
- Filter by source (path pattern)
- Facet aggregation (counts by facet)
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Set,
    Callable
)


class DocType(Enum):
    """Типы документов."""
    MARKDOWN = "markdown"
    BSL = "bsl"
    XML = "xml"
    JSON = "json"
    UNKNOWN = "unknown"


@dataclass
class ChunkMetadata:
    """
    Метаданные для чанка документа.

    Attributes:
        doc_type: Тип документа (markdown, bsl, xml)
        tags: Список тегов
        source: Путь к источнику (относительный путь проекта)
        date: Дата создания/модификации (ISO format)
        title: Опциональный заголовок
        author: Опциональный автор
        language: Код языка (ru, en, etc.)
        lines: Количество строк
        complexity: Оценка сложности (1-10)
    """

    doc_type: DocType
    source: str
    tags: List[str] = field(default_factory=list)
    date: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    language: str = "ru"
    lines: int = 0
    complexity: int = 1
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в dict."""
        return {
            "doc_type": self.doc_type.value,
            "source": self.source,
            "tags": self.tags,
            "date": self.date,
            "title": self.title,
            "author": self.author,
            "language": self.language,
            "lines": self.lines,
            "complexity": self.complexity,
            **self.extra
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        """Создать из dict."""
        doc_type = DocType(data.get("doc_type", "unknown"))

        return cls(
            doc_type=doc_type,
            source=data.get("source", ""),
            tags=data.get("tags", []),
            date=data.get("date"),
            title=data.get("title"),
            author=data.get("author"),
            language=data.get("language", "ru"),
            lines=data.get("lines", 0),
            complexity=data.get("complexity", 1),
            extra={
                k: v for k, v in data.items()
                if k not in {
                    "doc_type", "source", "tags", "date",
                    "title", "author", "language", "lines", "complexity"
                }
            }
        )

    @classmethod
    def detect_from_path(cls, file_path: str) -> "ChunkMetadata":
        """
        Определить метаданные из пути к файлу.

        Args:
            file_path: Путь к файлу

        Returns:
            ChunkMetadata с автозаполненными полями
        """
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()

        # Detect doc_type
        doc_type_map = {
            "md": DocType.MARKDOWN,
            "bsl": DocType.BSL,
            "xml": DocType.XML,
            "json": DocType.JSON,
        }
        doc_type = doc_type_map.get(ext, DocType.UNKNOWN)

        # Extract source path (relative to project root)
        source = str(path)

        # Try to get mtime for date
        date = None
        if path.exists():
            mtime = path.stat().st_mtime
            date = datetime.fromtimestamp(mtime).isoformat()

        # Count lines
        lines = 0
        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                pass

        return cls(
            doc_type=doc_type,
            source=source,
            date=date,
            lines=lines
        )


@dataclass
class FilterCondition:
    """
    Условие фильтрации.

    Supports:
    - doc_type:_eq/exact match
    - tags: any/all/none operations
    - date: before/after/between
    - source: pattern matching
    - custom: lambda functions
    """

    doc_types: Optional[List[DocType]] = None
    tags_any: Optional[List[str]] = None  # OR: имеет любой из тегов
    tags_all: Optional[List[str]] = None  # AND: имеет все теги
    tags_none: Optional[List[str]] = None  # NOT: не имеет ни одного тега
    date_after: Optional[str] = None  # ISO format
    date_before: Optional[str] = None
    source_pattern: Optional[str] = None  # Regex pattern
    source_prefix: Optional[str] = None
    custom: Optional[Callable[[ChunkMetadata], bool]] = None

    def matches(self, metadata: ChunkMetadata) -> bool:
        """Проверить соответствует ли metadata условию."""
        # Doc type filter
        if self.doc_types and metadata.doc_type not in self.doc_types:
            return False

        # Tags filters
        if self.tags_any and not any(tag in metadata.tags for tag in self.tags_any):
            return False

        if self.tags_all and not all(tag in metadata.tags for tag in self.tags_all):
            return False

        if self.tags_none and any(tag in metadata.tags for tag in self.tags_none):
            return False

        # Date filters
        if self.date_after and metadata.date:
            try:
                if metadata.date < self.date_after:
                    return False
            except ValueError:
                pass

        if self.date_before and metadata.date:
            try:
                if metadata.date > self.date_before:
                    return False
            except ValueError:
                pass

        # Source filters
        if self.source_pattern:
            if not re.search(self.source_pattern, metadata.source):
                return False

        if self.source_prefix:
            if not metadata.source.startswith(self.source_prefix):
                return False

        # Custom filter
        if self.custom and not self.custom(metadata):
            return False

        return True


class MetadataFilter:
    """
    Фильтр документов по метаданным.

    Example:
        filter = MetadataFilter()

        # Build condition
        condition = FilterCondition(
            doc_types=[DocType.BSL, DocType.MARKDOWN],
            tags_any=["important", "critical"],
            date_after="2024-01-01"
        )

        # Filter results
        filtered = filter.filter_documents(search_results, condition)
    """

    def __init__(self):
        self._conditions: List[FilterCondition] = []

    def add_condition(self, condition: FilterCondition) -> "MetadataFilter":
        """Добавить условие фильтрации."""
        self._conditions.append(condition)
        return self

    def clear_conditions(self) -> "MetadataFilter":
        """Очистить все условия."""
        self._conditions = []
        return self

    def filter_documents(
        self,
        documents: List[Dict[str, Any]],
        condition: Optional[FilterCondition] = None
    ) -> List[Dict[str, Any]]:
        """
        Отфильтровать документы по условию.

        Args:
            documents: Список документов с метаданными
            condition: Условие фильтрации (если None, использует self._conditions)

        Returns:
            Отфильтрованный список документов
        """
        if condition:
            conditions = [condition]
        else:
            conditions = self._conditions

        if not conditions:
            return documents

        result = []
        for doc in documents:
            # Extract metadata
            metadata_data = doc.get("metadata", {})
            if isinstance(metadata_data, str):
                try:
                    metadata_data = json.loads(metadata_data)
                except json.JSONDecodeError:
                    metadata_data = {}

            metadata = ChunkMetadata.from_dict(metadata_data)

            # Check all conditions (AND logic)
            if all(cond.matches(metadata) for cond in conditions):
                result.append(doc)

        return result

    def filter_by_doc_type(
        self,
        documents: List[Dict[str, Any]],
        doc_types: List[Union[DocType, str]]
    ) -> List[Dict[str, Any]]:
        """Отфильтровать по типу документа."""
        # Convert strings to DocType
        types = []
        for dt in doc_types:
            if isinstance(dt, str):
                try:
                    types.append(DocType(dt))
                except ValueError:
                    continue
            else:
                types.append(dt)

        condition = FilterCondition(doc_types=types)
        return self.filter_documents(documents, condition)

    def filter_by_tags(
        self,
        documents: List[Dict[str, Any]],
        tags: List[str],
        mode: str = "any"  # "any", "all", "none"
    ) -> List[Dict[str, Any]]:
        """Отфильтровать по тегам."""
        if mode == "any":
            condition = FilterCondition(tags_any=tags)
        elif mode == "all":
            condition = FilterCondition(tags_all=tags)
        elif mode == "none":
            condition = FilterCondition(tags_none=tags)
        else:
            raise ValueError(f"Invalid mode: {mode}")

        return self.filter_documents(documents, condition)

    def filter_by_date_range(
        self,
        documents: List[Dict[str, Any]],
        after: Optional[str] = None,
        before: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Отфильтровать по диапазону дат."""
        condition = FilterCondition(date_after=after, date_before=before)
        return self.filter_documents(documents, condition)

    def filter_by_source(
        self,
        documents: List[Dict[str, Any]],
        pattern: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Отфильтровать по пути источника."""
        condition = FilterCondition(source_pattern=pattern, source_prefix=prefix)
        return self.filter_documents(documents, condition)


@dataclass
class FacetResult:
    """Результат агрегации по фасету."""

    facet: str  # Имя фасета (doc_type, tags, etc.)
    values: Dict[str, int]  # Значение -> количество

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в dict."""
        return {
            "facet": self.facet,
            "values": self.values,
            "total": sum(self.values.values())
        }


class FacetedSearch:
    """
    Fasietный поиск с агрегацией.

    Example:
        searcher = FacetedSearch()

        results = searcher.search(
            query="обработка ошибок",
            facets=["doc_type", "tags"],
            filters={
                "doc_type": [DocType.BSL],
                "date_after": "2024-01-01"
            }
        )

        # Access results
        for doc in results["documents"]:
            print(doc)

        # Access facets
        for facet in results["facets"]:
            print(facet.facet, facet.values)
    """

    def __init__(self):
        self.metadata_filter = MetadataFilter()

    def search(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        facets: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполнить фасетный поиск.

        Args:
            query: Поисковый запрос
            documents: Документы для поиска
            facets: Список фасетов для агрегации
            filters: Фильтры

        Returns:
            {
                "documents": List[Dict],  # Отфильтрованные документы
                "facets": List[FacetResult],  # Агрегация
                "total": int,  # Всего документов
                "filtered": int  # После фильтрации
            }
        """
        # Apply filters
        if filters:
            condition = self._build_condition(filters)
            filtered_docs = self.metadata_filter.filter_documents(documents, condition)
        else:
            filtered_docs = documents

        # Compute facets
        facet_results = []
        if facets:
            for facet in facets:
                result = self._compute_facet(filtered_docs, facet)
                facet_results.append(result)

        return {
            "documents": filtered_docs,
            "facets": [f.to_dict() for f in facet_results],
            "total": len(documents),
            "filtered": len(filtered_docs),
            "query": query
        }

    def _build_condition(self, filters: Dict[str, Any]) -> FilterCondition:
        """Построить FilterCondition из dict."""
        doc_types = None
        if "doc_types" in filters:
            doc_types = [
                DocType(dt) if isinstance(dt, str) else dt
                for dt in filters["doc_types"]
            ]

        return FilterCondition(
            doc_types=doc_types,
            tags_any=filters.get("tags_any"),
            tags_all=filters.get("tags_all"),
            tags_none=filters.get("tags_none"),
            date_after=filters.get("date_after"),
            date_before=filters.get("date_before"),
            source_pattern=filters.get("source_pattern"),
            source_prefix=filters.get("source_prefix")
        )

    def _compute_facet(
        self,
        documents: List[Dict[str, Any]],
        facet: str
    ) -> FacetResult:
        """Вычислить агрегацию по фасету."""
        counts: Dict[str, int] = {}

        for doc in documents:
            # Extract metadata
            metadata_data = doc.get("metadata", {})
            if isinstance(metadata_data, str):
                try:
                    metadata_data = json.loads(metadata_data)
                except json.JSONDecodeError:
                    continue

            metadata = ChunkMetadata.from_dict(metadata_data)

            # Get facet value
            if facet == "doc_type":
                value = metadata.doc_type.value
            elif facet == "tags":
                # Count each tag separately
                for tag in metadata.tags:
                    counts[tag] = counts.get(tag, 0) + 1
                continue  # Skip default increment
            elif facet == "language":
                value = metadata.language
            elif facet == "source":
                # Use parent directory as facet value
                value = str(Path(metadata.source).parent)
            else:
                # Try to get from extra
                value = metadata.extra.get(facet, "unknown")

            counts[value] = counts.get(value, 0) + 1

        return FacetResult(facet=facet, values=counts)


# ============================================================================
# Integration with 1c-docs-rag MCP
# ============================================================================

def search_with_facets(
    query: str,
    search_type: str = "hybrid",
    top_k: int = 5,
    doc_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Выполнить поиск с фасетами (интеграция с 1c-docs-rag).

    Это функция-обёртка для использования в RAG.

    Args:
        query: Поисковый запрос
        search_type: fulltext, semantic, hybrid
        top_k: Количество результатов
        doc_type: Фильтр по типу документа
        tags: Фильтр по тегам (OR logic)
        date_after: Фильтр по дате (после)
        date_before: Фильтр по дате (до)
        source: Фильтр по источнику (path pattern)

    Returns:
        {
            "results": List[Dict],  # Результаты поиска
            "facets": Dict,  # Агрегация
            "query": str,
            "filtered": int
        }
    """
    # Import 1c-docs-rag MCP
    try:
        from mcp__1c_docs_rag import search_docs_with_facets as mcp_search
    except ImportError:
        return {
            "results": [],
            "facets": {},
            "query": query,
            "filtered": 0,
            "error": "1c-docs-rag MCP not available"
        }

    # Build facets dict for MCP call
    facets_list = ["doc_type"]
    if tags:
        facets_list.append("tags")

    # Build filters
    filters = {}
    if doc_type:
        filters["doc_type"] = doc_type
    if tags:
        filters["tags"] = tags
    if date_after:
        filters["date_after"] = date_after
    if date_before:
        filters["date_before"] = date_before
    if source:
        filters["source"] = source

    # Call MCP
    try:
        result = mcp_search(
            query=query,
            search_type=search_type,
            limit=top_k,
            doc_type=doc_type,
            tags=tags,
            date_after=date_after,
            date_before=date_before,
            source=source
        )

        return {
            "results": result.get("results", []),
            "facets": result.get("facets", {}),
            "query": query,
            "filtered": result.get("filtered", 0)
        }

    except Exception as e:
        return {
            "results": [],
            "facets": {},
            "query": query,
            "filtered": 0,
            "error": str(e)
        }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for standalone execution."""
    import asyncio

    async def demo():
        # Create sample documents
        docs = [
            {
                "content": "Пример BSL кода",
                "metadata": {
                    "doc_type": "bsl",
                    "source": "src/Modules/Example.bsl",
                    "tags": ["example", "test"],
                    "date": "2024-01-15",
                    "lines": 50
                }
            },
            {
                "content": "Документация",
                "metadata": {
                    "doc_type": "markdown",
                    "source": "docs/README.md",
                    "tags": ["docs", "important"],
                    "date": "2024-02-01",
                    "lines": 100
                }
            },
            {
                "content": "XML конфигурация",
                "metadata": {
                    "doc_type": "xml",
                    "source": "src/Config.xml",
                    "tags": ["config"],
                    "date": "2024-01-10",
                    "lines": 30
                }
            }
        ]

        # Create filter
        filter_obj = MetadataFilter()

        # Filter by doc type
        bsl_docs = filter_obj.filter_by_doc_type(docs, [DocType.BSL])
        print(f"\nBSL docs: {len(bsl_docs)}")

        # Filter by tags
        tagged = filter_obj.filter_by_tags(docs, ["important"], mode="any")
        print(f"Tagged 'important': {len(tagged)}")

        # Faceted search
        searcher = FacetedSearch()
        results = searcher.search(
            query="пример",
            documents=docs,
            facets=["doc_type", "tags"]
        )

        print(f"\nFaceted search results:")
        print(f"  Total: {results['total']}")
        print(f"  Filtered: {results['filtered']}")

        for facet in results["facets"]:
            print(f"\n  Facet: {facet['facet']}")
            for value, count in facet['values'].items():
                print(f"    {value}: {count}")

    asyncio.run(demo())


if __name__ == "__main__":
    main()
