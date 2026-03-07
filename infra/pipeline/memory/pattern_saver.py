"""
Pattern Saver for Development Pipeline.

Sprint 3.3.2: Saving successful patterns

This module provides functionality for:
- Extracting patterns from successful implementations
- Matching patterns against current context
- Managing pattern lifecycle (creation, update, deprecation)
"""

import re
import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Tuple
from enum import Enum

from models import (
    Pattern,
    PatternType,
    MemoryEntry,
    MemoryType,
    LearningContext,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    SearchResult,
    SaveResult,
)


logger = logging.getLogger(__name__)


class PatternExtractionStrategy(Enum):
    """Strategy for extracting patterns from code/context."""
    STRUCTURAL = "structural"  # Based on code structure
    SEMANTIC = "semantic"  # Based on meaning/intent
    HYBRID = "hybrid"  # Combination of both
    MANUAL = "manual"  # User-defined patterns


@dataclass
class PatternCandidate:
    """A potential pattern candidate for saving."""

    problem: str
    solution: str
    pattern_type: PatternType
    source_file: Optional[str] = None
    source_lines: Optional[Tuple[int, int]] = None
    confidence: float = 0.5
    keywords: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def generate_name(self) -> str:
        """Generate a name for the pattern."""
        # Extract key terms from problem
        words = re.findall(r'\b\w+\b', self.problem.lower())
        # Filter out common words
        stop_words = {
            'в', 'и', 'на', 'для', 'при', 'из', 'по', 'с', 'к', 'о',
            'the', 'a', 'an', 'in', 'on', 'for', 'to', 'with', 'of',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
        }
        key_words = [w for w in words if w not in stop_words and len(w) > 2]

        if key_words:
            name = '_'.join(key_words[:3])
        else:
            name = f"pattern_{self.pattern_type.value}"

        return f"{self.pattern_type.value}_{name}"

    def generate_hash(self) -> str:
        """Generate unique hash for the pattern."""
        content = f"{self.problem}|{self.solution}|{self.pattern_type.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class MatchResult:
    """Result of pattern matching."""

    pattern: Pattern
    score: float
    matched_elements: List[str] = field(default_factory=list)
    context_relevance: float = 0.0

    @property
    def combined_score(self) -> float:
        """Calculate combined matching score."""
        return (self.score * 0.7 + self.context_relevance * 0.3)


class PatternMatcher:
    """
    Matches patterns against current context.

    The matcher uses multiple strategies:
    1. Keyword matching - exact/fuzzy keyword matches
    2. Semantic similarity - via memory search
    3. Context relevance - based on current task/project
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
        min_score: float = 0.3,
        max_results: int = 10,
    ):
        self.memory_client = memory_client
        self.min_score = min_score
        self.max_results = max_results

    async def find_matching_patterns(
        self,
        context: str,
        pattern_type: Optional[PatternType] = None,
        learning_context: Optional[LearningContext] = None,
    ) -> List[MatchResult]:
        """
        Find patterns matching the given context.

        Args:
            context: Current context/problem description
            pattern_type: Filter by pattern type
            learning_context: Additional learning context

        Returns:
            List of MatchResult objects sorted by relevance
        """
        # Search for similar patterns in memory
        search_results = await self.memory_client.search_patterns(
            query=context,
            limit=self.max_results * 2,  # Get more, filter later
        )

        match_results = []

        for result in search_results:
            # Parse pattern from search result
            pattern = self._parse_pattern_from_result(result)
            if not pattern:
                continue

            # Skip if type filter doesn't match
            if pattern_type and pattern.pattern_type != pattern_type:
                continue

            # Calculate match score
            keyword_score = self._calculate_keyword_score(context, pattern)
            context_relevance = self._calculate_context_relevance(
                pattern, learning_context
            )

            combined_score = result.score * 0.5 + keyword_score * 0.3 + context_relevance * 0.2

            if combined_score >= self.min_score:
                match_results.append(MatchResult(
                    pattern=pattern,
                    score=result.score,
                    matched_elements=self._extract_matched_elements(context, pattern),
                    context_relevance=context_relevance,
                ))

        # Sort by combined score
        match_results.sort(key=lambda x: x.combined_score, reverse=True)

        return match_results[:self.max_results]

    def _parse_pattern_from_result(
        self,
        result: SearchResult,
    ) -> Optional[Pattern]:
        """Parse Pattern object from search result."""
        try:
            metadata = result.metadata

            # Try to extract pattern data from content or metadata
            if "pattern_data" in metadata:
                return Pattern.from_dict(metadata["pattern_data"])

            # Parse from structured content
            content = result.content
            lines = content.split('\n')

            problem = ""
            solution = ""
            pattern_type = PatternType.IMPLEMENTATION

            for line in lines:
                if line.startswith("Проблема:") or line.startswith("Problem:"):
                    problem = line.split(":", 1)[1].strip()
                elif line.startswith("Решение:") or line.startswith("Solution:"):
                    solution = line.split(":", 1)[1].strip()
                elif line.startswith("Тип:") or line.startswith("Type:"):
                    type_str = line.split(":", 1)[1].strip().lower()
                    for pt in PatternType:
                        if pt.value == type_str:
                            pattern_type = pt
                            break

            if problem and solution:
                return Pattern(
                    id=result.id,
                    name=metadata.get("name", f"pattern_{result.id}"),
                    pattern_type=pattern_type,
                    description=metadata.get("description", f"{problem} - {solution}"),
                    problem=problem,
                    solution=solution,
                    tags=result.tags,
                    success_count=metadata.get("success_count", 1),
                    failure_count=metadata.get("failure_count", 0),
                )

            return None

        except Exception as e:
            logger.warning(f"Failed to parse pattern from result: {e}")
            return None

    def _calculate_keyword_score(
        self,
        context: str,
        pattern: Pattern,
    ) -> float:
        """Calculate keyword matching score."""
        context_words = set(re.findall(r'\b\w+\b', context.lower()))
        pattern_words = set(re.findall(
            r'\b\w+\b',
            f"{pattern.problem} {pattern.solution}".lower()
        ))

        if not pattern_words:
            return 0.0

        intersection = context_words & pattern_words
        return len(intersection) / len(pattern_words)

    def _calculate_context_relevance(
        self,
        pattern: Pattern,
        learning_context: Optional[LearningContext],
    ) -> float:
        """Calculate context relevance score."""
        if not learning_context:
            return 0.5  # Default neutral score

        relevance = 0.5

        # Check project match
        if learning_context.project_id:
            project_keywords = learning_context.project_id.lower().split('_')
            pattern_text = f"{pattern.problem} {pattern.solution}".lower()
            project_matches = sum(
                1 for kw in project_keywords if kw in pattern_text
            )
            relevance += min(0.2, project_matches * 0.05)

        # Check task match
        if learning_context.current_task:
            task_words = set(re.findall(
                r'\b\w+\b', learning_context.current_task.lower()
            ))
            pattern_words = set(re.findall(
                r'\b\w+\b', pattern.problem.lower()
            ))
            if task_words & pattern_words:
                relevance += 0.15

        # Check agent match
        if learning_context.current_agent:
            agent = learning_context.current_agent.lower()
            pattern_type = pattern.pattern_type.value.lower()

            agent_type_affinity = {
                "pm-spec": ["documentation", "architecture"],
                "architect": ["architecture", "integration"],
                "implementer": ["implementation", "refactoring", "bug_fix"],
                "qa": ["testing", "bug_fix"],
            }

            for agent_key, types in agent_type_affinity.items():
                if agent_key in agent and pattern_type in types:
                    relevance += 0.1
                    break

        return min(1.0, relevance)

    def _extract_matched_elements(
        self,
        context: str,
        pattern: Pattern,
    ) -> List[str]:
        """Extract elements that matched between context and pattern."""
        context_words = set(re.findall(r'\b\w{4,}\b', context.lower()))
        problem_words = set(re.findall(r'\b\w{4,}\b', pattern.problem.lower()))

        matched = context_words & problem_words
        return list(matched)[:10]


class PatternSaver:
    """
    Saves successful patterns to memory.

    The saver handles:
    - Pattern extraction from implementations
    - Deduplication and merging
    - Success/failure tracking
    - Pattern lifecycle management
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
        extraction_strategy: PatternExtractionStrategy = PatternExtractionStrategy.HYBRID,
        min_confidence: float = 0.5,
    ):
        self.memory_client = memory_client
        self.extraction_strategy = extraction_strategy
        self.min_confidence = min_confidence
        self._known_hashes: Set[str] = set()

    async def save_pattern(
        self,
        pattern: Pattern,
        learning_context: Optional[LearningContext] = None,
    ) -> SaveResult:
        """
        Save a pattern to memory.

        Args:
            pattern: Pattern to save
            learning_context: Optional learning context

        Returns:
            SaveResult with success status
        """
        # Check for duplicates
        pattern_hash = self._generate_hash(pattern)
        if pattern_hash in self._known_hashes:
            logger.info(f"Pattern already exists: {pattern.name}")
            return SaveResult(
                success=True,
                message="Pattern already exists (deduplicated)",
            )

        # Check for similar patterns in memory
        existing = await self._find_similar_pattern(pattern)
        if existing:
            # Merge with existing pattern
            return await self._merge_pattern(existing, pattern)

        # Save new pattern
        result = await self.memory_client.save_pattern(pattern)

        if result.success:
            self._known_hashes.add(pattern_hash)
            logger.info(f"Saved new pattern: {pattern.name}")

        return result

    async def save_from_candidate(
        self,
        candidate: PatternCandidate,
        learning_context: Optional[LearningContext] = None,
    ) -> SaveResult:
        """
        Save a pattern from a candidate.

        Args:
            candidate: Pattern candidate
            learning_context: Optional learning context

        Returns:
            SaveResult with success status
        """
        if candidate.confidence < self.min_confidence:
            return SaveResult(
                success=False,
                message=f"Confidence too low: {candidate.confidence:.2f}",
            )

        pattern = Pattern(
            id=f"pat_{candidate.generate_hash()}",
            name=candidate.generate_name(),
            pattern_type=candidate.pattern_type,
            description=f"Pattern for: {candidate.problem}",
            problem=candidate.problem,
            solution=candidate.solution,
            tags=candidate.keywords,
            success_count=1,
            failure_count=0,
        )

        return await self.save_pattern(pattern, learning_context)

    async def record_success(self, pattern_id: str) -> bool:
        """
        Record successful use of a pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            True if recorded successfully
        """
        # In a full implementation, this would update the pattern's success count
        # For now, we'll save a success event
        content = f"Pattern success: {pattern_id}"
        result = await self.memory_client.save_memory(
            content=content,
            memory_type=MemoryType.EXECUTION,
            importance=0.6,
            tags=["pattern_success", pattern_id],
            context={"pattern_id": pattern_id, "event": "success"},
        )
        return result.success

    async def record_failure(
        self,
        pattern_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Record failed use of a pattern.

        Args:
            pattern_id: ID of the pattern
            reason: Optional failure reason

        Returns:
            True if recorded successfully
        """
        content = f"Pattern failure: {pattern_id}"
        if reason:
            content += f"\nReason: {reason}"

        result = await self.memory_client.save_memory(
            content=content,
            memory_type=MemoryType.EXECUTION,
            importance=0.7,  # Failures are more important to learn from
            tags=["pattern_failure", pattern_id],
            context={
                "pattern_id": pattern_id,
                "event": "failure",
                "reason": reason,
            },
        )
        return result.success

    async def extract_patterns_from_code(
        self,
        code: str,
        file_path: Optional[str] = None,
        context_description: Optional[str] = None,
    ) -> List[PatternCandidate]:
        """
        Extract potential patterns from code.

        Args:
            code: Source code to analyze
            file_path: Optional file path for context
            context_description: Optional description of what the code does

        Returns:
            List of PatternCandidate objects
        """
        candidates = []

        if self.extraction_strategy in (
            PatternExtractionStrategy.STRUCTURAL,
            PatternExtractionStrategy.HYBRID,
        ):
            candidates.extend(
                self._extract_structural_patterns(code, file_path)
            )

        if self.extraction_strategy in (
            PatternExtractionStrategy.SEMANTIC,
            PatternExtractionStrategy.HYBRID,
        ):
            candidates.extend(
                self._extract_semantic_patterns(code, context_description)
            )

        # Deduplicate by hash
        seen_hashes = set()
        unique_candidates = []
        for candidate in candidates:
            h = candidate.generate_hash()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_candidates.append(candidate)

        return unique_candidates

    def _extract_structural_patterns(
        self,
        code: str,
        file_path: Optional[str] = None,
    ) -> List[PatternCandidate]:
        """Extract patterns based on code structure."""
        candidates = []

        # BSL-specific patterns
        if file_path and file_path.endswith('.bsl'):
            candidates.extend(self._extract_bsl_patterns(code, file_path))
        else:
            candidates.extend(self._extract_generic_patterns(code, file_path))

        return candidates

    def _extract_bsl_patterns(
        self,
        code: str,
        file_path: Optional[str] = None,
    ) -> List[PatternCandidate]:
        """Extract BSL-specific patterns."""
        candidates = []

        # Pattern: Error handling with Попытка/Исключение
        error_handling_pattern = re.compile(
            r'Попытка\s*\n(.*?)\nИсключение\s*\n(.*?)\nКонецПопытки',
            re.DOTALL | re.IGNORECASE
        )

        for match in error_handling_pattern.finditer(code):
            try_block = match.group(1).strip()
            except_block = match.group(2).strip()

            if len(try_block) > 20 and len(except_block) > 10:
                candidates.append(PatternCandidate(
                    problem="Обработка ошибок в BSL коде",
                    solution=f"Использование Попытка/Исключение:\n{match.group(0)[:500]}",
                    pattern_type=PatternType.IMPLEMENTATION,
                    source_file=file_path,
                    confidence=0.6,
                    keywords=["обработка_ошибок", "попытка", "исключение", "bsl"],
                ))

        # Pattern: Query building
        query_pattern = re.compile(
            r'Запрос\s*=\s*Новый\s+Запрос[;\s]*\n\s*Запрос\.Текст\s*=\s*["\'].*?["\'];?',
            re.DOTALL | re.IGNORECASE
        )

        for match in query_pattern.finditer(code):
            candidates.append(PatternCandidate(
                problem="Построение запросов к базе данных 1С",
                solution=f"Шаблон запроса:\n{match.group(0)[:500]}",
                pattern_type=PatternType.IMPLEMENTATION,
                source_file=file_path,
                confidence=0.5,
                keywords=["запрос", "query", "база_данных", "bsl"],
            ))

        # Pattern: Export functions
        export_pattern = re.compile(
            r'(Функция|Процедура)\s+(\w+)\s*\([^)]*\)\s*Экспорт',
            re.IGNORECASE
        )

        export_funcs = export_pattern.findall(code)
        if len(export_funcs) >= 3:
            func_names = [f[1] for f in export_funcs]
            candidates.append(PatternCandidate(
                problem="Организация экспортных функций модуля",
                solution=f"Экспортные функции: {', '.join(func_names[:10])}",
                pattern_type=PatternType.ARCHITECTURE,
                source_file=file_path,
                confidence=0.55,
                keywords=["экспорт", "api", "модуль", "bsl"],
            ))

        return candidates

    def _extract_generic_patterns(
        self,
        code: str,
        file_path: Optional[str] = None,
    ) -> List[PatternCandidate]:
        """Extract generic code patterns."""
        candidates = []

        # Pattern: Function definitions
        func_pattern = re.compile(
            r'(def|function|func)\s+(\w+)\s*\([^)]*\)',
            re.IGNORECASE
        )

        functions = func_pattern.findall(code)
        if len(functions) >= 5:
            func_names = [f[1] for f in functions]
            candidates.append(PatternCandidate(
                problem="Module organization with multiple functions",
                solution=f"Functions: {', '.join(func_names[:10])}",
                pattern_type=PatternType.ARCHITECTURE,
                source_file=file_path,
                confidence=0.4,
                keywords=["functions", "module", "organization"],
            ))

        return candidates

    def _extract_semantic_patterns(
        self,
        code: str,
        context_description: Optional[str] = None,
    ) -> List[PatternCandidate]:
        """Extract patterns based on semantic meaning."""
        candidates = []

        if context_description:
            # Create pattern from description
            candidates.append(PatternCandidate(
                problem=context_description,
                solution=f"Implementation:\n{code[:1000]}",
                pattern_type=PatternType.IMPLEMENTATION,
                confidence=0.5,
                keywords=context_description.lower().split()[:5],
            ))

        return candidates

    async def _find_similar_pattern(
        self,
        pattern: Pattern,
    ) -> Optional[Pattern]:
        """Find similar pattern in memory."""
        query = f"{pattern.problem} {pattern.solution}"

        results = await self.memory_client.search_patterns(
            query=query,
            limit=3,
        )

        for result in results:
            if result.score > 0.85:  # High similarity threshold
                parsed = PatternMatcher(
                    self.memory_client
                )._parse_pattern_from_result(result)
                if parsed:
                    return parsed

        return None

    async def _merge_pattern(
        self,
        existing: Pattern,
        new: Pattern,
    ) -> SaveResult:
        """Merge new pattern with existing one."""
        # Update success count
        existing.success_count += 1

        # Add new examples if any
        if new.examples:
            existing.examples.extend(new.examples)
            existing.examples = list(set(existing.examples))[:10]

        # Add new tags
        if new.tags:
            existing.tags = list(set(existing.tags + new.tags))[:20]

        # Save updated pattern
        result = await self.memory_client.save_pattern(existing)

        if result.success:
            logger.info(f"Merged pattern: {existing.name}")

        return result

    def _generate_hash(self, pattern: Pattern) -> str:
        """Generate hash for pattern deduplication."""
        content = f"{pattern.problem}|{pattern.solution}|{pattern.pattern_type.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
