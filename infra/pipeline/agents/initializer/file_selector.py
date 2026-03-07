"""
File Selector for INITIALIZER Agent.

Selects relevant files based on task description and project structure.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agents.initializer.models import (
    ObjectType,
    FileInfo,
    ModuleInfo,
    ProjectStructure,
    RelevantFile,
    InitializerConfig,
)


@dataclass
class RelevanceKeyword:
    """Keyword for relevance matching."""

    keyword: str
    weight: float = 1.0
    object_types: list[ObjectType] = field(default_factory=list)


class FileSelector:
    """
    Selects relevant files for a task.

    Features:
    - Keyword-based relevance scoring
    - Object type matching
    - Module name similarity
    - Dependency-aware selection
    """

    # Keywords mapped to 1C object types
    KEYWORD_MAPPINGS: dict[str, list[ObjectType]] = {
        # Document operations
        "документ": [ObjectType.DOCUMENT],
        "document": [ObjectType.DOCUMENT],
        "проведение": [ObjectType.DOCUMENT, ObjectType.ACCUMULATION_REGISTER],
        "posting": [ObjectType.DOCUMENT, ObjectType.ACCUMULATION_REGISTER],

        # Catalog operations
        "справочник": [ObjectType.CATALOG],
        "catalog": [ObjectType.CATALOG],
        "элемент": [ObjectType.CATALOG],
        "item": [ObjectType.CATALOG],

        # Register operations
        "регистр": [
            ObjectType.ACCUMULATION_REGISTER,
            ObjectType.INFORMATION_REGISTER,
        ],
        "register": [
            ObjectType.ACCUMULATION_REGISTER,
            ObjectType.INFORMATION_REGISTER,
        ],
        "накопления": [ObjectType.ACCUMULATION_REGISTER],
        "accumulation": [ObjectType.ACCUMULATION_REGISTER],
        "сведения": [ObjectType.INFORMATION_REGISTER],
        "information": [ObjectType.INFORMATION_REGISTER],
        "остаток": [ObjectType.ACCUMULATION_REGISTER],
        "balance": [ObjectType.ACCUMULATION_REGISTER],
        "оборот": [ObjectType.ACCUMULATION_REGISTER],
        "turnover": [ObjectType.ACCUMULATION_REGISTER],

        # Report operations
        "отчет": [ObjectType.REPORT],
        "отчёт": [ObjectType.REPORT],
        "report": [ObjectType.REPORT],

        # Data processor operations
        "обработка": [ObjectType.DATA_PROCESSOR],
        "dataprocessor": [ObjectType.DATA_PROCESSOR],
        "processing": [ObjectType.DATA_PROCESSOR],

        # Common module operations
        "общий модуль": [ObjectType.COMMON_MODULE],
        "common module": [ObjectType.COMMON_MODULE],
        "функция": [ObjectType.COMMON_MODULE],
        "function": [ObjectType.COMMON_MODULE],
        "процедура": [ObjectType.COMMON_MODULE],
        "procedure": [ObjectType.COMMON_MODULE],

        # Enum operations
        "перечисление": [ObjectType.ENUM],
        "enum": [ObjectType.ENUM],

        # Constant operations
        "константа": [ObjectType.CONSTANT],
        "constant": [ObjectType.CONSTANT],
    }

    # Additional relevance keywords
    RELEVANCE_KEYWORDS = [
        RelevanceKeyword("ошибка", 1.5),
        RelevanceKeyword("error", 1.5),
        RelevanceKeyword("bug", 1.5),
        RelevanceKeyword("исправить", 1.3),
        RelevanceKeyword("fix", 1.3),
        RelevanceKeyword("добавить", 1.2),
        RelevanceKeyword("add", 1.2),
        RelevanceKeyword("создать", 1.2),
        RelevanceKeyword("create", 1.2),
        RelevanceKeyword("изменить", 1.1),
        RelevanceKeyword("modify", 1.1),
        RelevanceKeyword("удалить", 1.0),
        RelevanceKeyword("delete", 1.0),
        RelevanceKeyword("рефакторинг", 1.0),
        RelevanceKeyword("refactor", 1.0),
    ]

    def __init__(self, config: Optional[InitializerConfig] = None) -> None:
        """Initialize selector with config."""
        self.config = config or InitializerConfig()

    def select(
        self,
        structure: ProjectStructure,
        task_description: str,
        limit: int = 20,
    ) -> list[RelevantFile]:
        """
        Select relevant files for task.

        Args:
            structure: Project structure from scanner
            task_description: Task description text
            limit: Maximum number of files to return

        Returns:
            List of RelevantFile sorted by relevance score
        """
        # Extract keywords from task
        keywords = self._extract_keywords(task_description)

        # Determine target object types
        target_types = self._determine_target_types(keywords)

        # Score all files
        scored_files: list[RelevantFile] = []

        for module in structure.modules:
            # Score module
            module_score = self._score_module(
                module=module,
                keywords=keywords,
                target_types=target_types,
                task_description=task_description,
            )

            if module_score > 0:
                # Add all BSL files from module
                for file_info in module.files:
                    if file_info.is_bsl:
                        reason = self._generate_reason(
                            module=module,
                            keywords=keywords,
                            target_types=target_types,
                        )

                        relevant = RelevantFile(
                            file_info=file_info,
                            relevance_score=module_score,
                            relevance_reason=reason,
                            module_name=module.name,
                        )
                        scored_files.append(relevant)

        # Sort by score descending
        scored_files.sort(key=lambda f: f.relevance_score, reverse=True)

        # Apply limit
        return scored_files[:limit]

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text."""
        # Convert to lowercase
        text = text.lower()

        # Remove punctuation and split
        text = re.sub(r"[^\w\s]", " ", text)
        words = text.split()

        # Filter short words and stopwords
        stopwords = {
            "в", "на", "из", "для", "по", "с", "и", "или", "не", "а", "но",
            "the", "a", "an", "in", "on", "for", "to", "of", "and", "or", "is",
        }

        keywords = [
            w for w in words
            if len(w) > 2 and w not in stopwords
        ]

        return keywords

    def _determine_target_types(
        self,
        keywords: list[str]
    ) -> set[ObjectType]:
        """Determine target object types from keywords."""
        target_types: set[ObjectType] = set()

        for keyword in keywords:
            for pattern, types in self.KEYWORD_MAPPINGS.items():
                if pattern in keyword or keyword in pattern:
                    target_types.update(types)

        return target_types

    def _score_module(
        self,
        module: ModuleInfo,
        keywords: list[str],
        target_types: set[ObjectType],
        task_description: str,
    ) -> float:
        """Score module relevance."""
        score = 0.0

        # Object type match (high weight)
        if target_types and module.object_type in target_types:
            score += 0.5

        # Module name contains keywords
        module_name_lower = module.name.lower()
        for keyword in keywords:
            if keyword in module_name_lower:
                score += 0.3

        # Keyword weight from RELEVANCE_KEYWORDS
        task_lower = task_description.lower()
        for rk in self.RELEVANCE_KEYWORDS:
            if rk.keyword in task_lower:
                score *= rk.weight

        # Exports count bonus (modules with more exports are more important)
        if module.exports_count > 10:
            score += 0.1
        elif module.exports_count > 5:
            score += 0.05

        # Normalize score to 0-1 range
        score = min(1.0, max(0.0, score))

        return score

    def _generate_reason(
        self,
        module: ModuleInfo,
        keywords: list[str],
        target_types: set[ObjectType],
    ) -> str:
        """Generate human-readable relevance reason."""
        reasons = []

        # Object type match
        if target_types and module.object_type in target_types:
            reasons.append(f"тип объекта: {module.object_type.ru_name}")

        # Name match
        module_name_lower = module.name.lower()
        matching_keywords = [k for k in keywords if k in module_name_lower]
        if matching_keywords:
            reasons.append(f"совпадение в имени: {', '.join(matching_keywords)}")

        # Exports
        if module.exports_count > 0:
            reasons.append(f"экспортов: {module.exports_count}")

        if reasons:
            return "; ".join(reasons)
        else:
            return "связанный модуль"


def rank_files_by_relevance(
    files: list[RelevantFile],
    min_score: float = 0.0,
) -> list[RelevantFile]:
    """
    Rank files by relevance score.

    Args:
        files: List of relevant files
        min_score: Minimum score threshold

    Returns:
        Filtered and sorted list
    """
    # Filter by minimum score
    filtered = [f for f in files if f.relevance_score >= min_score]

    # Sort by score descending
    filtered.sort(key=lambda f: f.relevance_score, reverse=True)

    return filtered


def select_relevant_files(
    structure: ProjectStructure,
    task_description: str,
    limit: int = 20,
    config: Optional[InitializerConfig] = None,
) -> list[RelevantFile]:
    """
    Select relevant files for task.

    Convenience function for FileSelector.

    Args:
        structure: Project structure
        task_description: Task description
        limit: Maximum files to return
        config: Optional configuration

    Returns:
        List of relevant files
    """
    selector = FileSelector(config)
    return selector.select(structure, task_description, limit)


def get_high_relevance_files(
    structure: ProjectStructure,
    task_description: str,
    threshold: float = 0.8,
    config: Optional[InitializerConfig] = None,
) -> list[RelevantFile]:
    """
    Get only high relevance files.

    Args:
        structure: Project structure
        task_description: Task description
        threshold: Minimum relevance score
        config: Optional configuration

    Returns:
        List of high relevance files
    """
    all_files = select_relevant_files(
        structure=structure,
        task_description=task_description,
        limit=100,  # Get more to filter
        config=config,
    )

    return [f for f in all_files if f.relevance_score >= threshold]


def get_files_by_type(
    structure: ProjectStructure,
    object_types: list[ObjectType],
) -> list[FileInfo]:
    """
    Get all files of specific object types.

    Args:
        structure: Project structure
        object_types: List of object types to filter

    Returns:
        List of file info objects
    """
    files = []

    for module in structure.modules:
        if module.object_type in object_types:
            files.extend([f for f in module.files if f.is_bsl])

    return files
