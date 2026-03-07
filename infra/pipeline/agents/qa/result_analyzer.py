"""
Result Analyzer for QA Agent.

Parses result.md to extract code changes, functions, and test points.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from pathlib import Path


class ChangeType(Enum):
    """Types of code changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    REFACTORED = "refactored"


@dataclass
class FileChange:
    """Represents a changed file."""
    path: str
    change_type: ChangeType
    description: str = ""
    functions: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "description": self.description,
            "functions": self.functions,
            "procedures": self.procedures,
        }


@dataclass
class ImplementedFunction:
    """Represents an implemented function/procedure."""
    name: str
    description: str = ""
    parameters: List[str] = field(default_factory=list)
    returns: str = ""
    is_export: bool = False
    code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "is_export": self.is_export,
        }


@dataclass
class CodeBlock:
    """Represents a code block from result.md."""
    language: str
    content: str
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "language": self.language,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "file_path": self.file_path,
        }


@dataclass
class AnalysisResult:
    """Result of analyzing result.md."""
    file_changes: List[FileChange] = field(default_factory=list)
    functions: List[ImplementedFunction] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    requirements_covered: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def total_files(self) -> int:
        """Total number of changed files."""
        return len(self.file_changes)

    @property
    def total_functions(self) -> int:
        """Total number of implemented functions."""
        return len(self.functions)

    @property
    def bsl_files(self) -> List[FileChange]:
        """Get only BSL files."""
        return [f for f in self.file_changes if f.path.endswith('.bsl')]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_files": self.total_files,
            "total_functions": self.total_functions,
            "file_changes": [f.to_dict() for f in self.file_changes],
            "functions": [f.to_dict() for f in self.functions],
            "code_blocks_count": len(self.code_blocks),
            "requirements_covered": self.requirements_covered,
            "summary": self.summary,
        }


class ResultAnalyzer:
    """
    Analyzes result.md artifact from IMPLEMENTER agent.

    Extracts:
    - Changed files with change types
    - Implemented functions/procedures
    - Code blocks
    - Covered requirements

    Usage:
        analyzer = ResultAnalyzer()
        result = analyzer.analyze(result_md_content)
        print(f"Found {result.total_files} changed files")
    """

    # Patterns for parsing
    FILE_TABLE_PATTERN = re.compile(
        r'\|\s*([^\|]+\.bsl)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|',
        re.IGNORECASE
    )

    FUNCTION_HEADER_PATTERN = re.compile(
        r'###\s+(Функция|Процедура|Function|Procedure)\s+(\w+)',
        re.IGNORECASE
    )

    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w+)?\s*\n(.*?)```',
        re.DOTALL
    )

    REQUIREMENT_PATTERN = re.compile(
        r'(REQ-\d+|ТРБ-\d+)',
        re.IGNORECASE
    )

    BSL_FUNCTION_PATTERN = re.compile(
        r'(Функция|Function)\s+(\w+)\s*\(([^)]*)\)',
        re.IGNORECASE
    )

    BSL_PROCEDURE_PATTERN = re.compile(
        r'(Процедура|Procedure)\s+(\w+)\s*\(([^)]*)\)',
        re.IGNORECASE
    )

    EXPORT_PATTERN = re.compile(
        r'\bЭкспорт\b|\bExport\b',
        re.IGNORECASE
    )

    def __init__(self) -> None:
        """Initialize analyzer."""
        self._last_result: Optional[AnalysisResult] = None

    def analyze(self, content: str) -> AnalysisResult:
        """
        Analyze result.md content.

        Args:
            content: The markdown content of result.md

        Returns:
            AnalysisResult with extracted information
        """
        result = AnalysisResult()

        # Extract summary (first paragraph or heading)
        result.summary = self._extract_summary(content)

        # Extract file changes from tables
        result.file_changes = self._extract_file_changes(content)

        # Extract code blocks
        result.code_blocks = self._extract_code_blocks(content)

        # Extract functions from code blocks
        result.functions = self._extract_functions(result.code_blocks)

        # Also extract functions described in markdown
        result.functions.extend(self._extract_documented_functions(content))

        # Extract requirement references
        result.requirements_covered = self._extract_requirements(content)

        # Enrich file changes with function info
        self._enrich_file_changes(result)

        self._last_result = result
        return result

    def analyze_file(self, file_path: str) -> AnalysisResult:
        """
        Analyze result.md from file path.

        Args:
            file_path: Path to result.md file

        Returns:
            AnalysisResult
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(encoding='utf-8')
        return self.analyze(content)

    def _extract_summary(self, content: str) -> str:
        """Extract summary from content."""
        lines = content.split('\n')
        summary_lines = []

        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Skip main headers
                if line.startswith('# '):
                    continue
                break
            if line and not line.startswith('|') and not line.startswith('```'):
                summary_lines.append(line)
            if len(summary_lines) >= 3:
                break

        return ' '.join(summary_lines)

    def _extract_file_changes(self, content: str) -> List[FileChange]:
        """Extract file changes from markdown tables."""
        changes = []

        # Find table rows with file paths
        for match in self.FILE_TABLE_PATTERN.finditer(content):
            path = match.group(1).strip()
            change_type_str = match.group(2).strip().lower()
            description = match.group(3).strip()

            # Map change type
            change_type = ChangeType.ADDED
            if 'изменен' in change_type_str or 'modified' in change_type_str:
                change_type = ChangeType.MODIFIED
            elif 'удален' in change_type_str or 'deleted' in change_type_str:
                change_type = ChangeType.DELETED
            elif 'рефактор' in change_type_str or 'refactor' in change_type_str:
                change_type = ChangeType.REFACTORED

            changes.append(FileChange(
                path=path,
                change_type=change_type,
                description=description,
            ))

        return changes

    def _extract_code_blocks(self, content: str) -> List[CodeBlock]:
        """Extract code blocks from markdown."""
        blocks = []

        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            language = match.group(1) or 'text'
            code = match.group(2).strip()

            blocks.append(CodeBlock(
                language=language.lower(),
                content=code,
            ))

        return blocks

    def _extract_functions(self, code_blocks: List[CodeBlock]) -> List[ImplementedFunction]:
        """Extract functions from BSL code blocks."""
        functions = []

        for block in code_blocks:
            if block.language not in ('bsl', '1c', 'onec'):
                continue

            # Find functions
            for match in self.BSL_FUNCTION_PATTERN.finditer(block.content):
                name = match.group(2)
                params = match.group(3).strip()
                is_export = bool(self.EXPORT_PATTERN.search(
                    block.content[match.end():match.end() + 50]
                ))

                functions.append(ImplementedFunction(
                    name=name,
                    parameters=[p.strip() for p in params.split(',') if p.strip()],
                    is_export=is_export,
                ))

            # Find procedures
            for match in self.BSL_PROCEDURE_PATTERN.finditer(block.content):
                name = match.group(2)
                params = match.group(3).strip()
                is_export = bool(self.EXPORT_PATTERN.search(
                    block.content[match.end():match.end() + 50]
                ))

                functions.append(ImplementedFunction(
                    name=name,
                    parameters=[p.strip() for p in params.split(',') if p.strip()],
                    is_export=is_export,
                ))

        return functions

    def _extract_documented_functions(self, content: str) -> List[ImplementedFunction]:
        """Extract functions documented in markdown headers."""
        functions = []

        for match in self.FUNCTION_HEADER_PATTERN.finditer(content):
            func_type = match.group(1)
            name = match.group(2)

            # Try to extract description (next line)
            start = match.end()
            end = content.find('\n###', start)
            if end == -1:
                end = start + 500

            section = content[start:end]

            # Extract description
            desc_match = re.search(r'\*\*(?:Назначение|Description):\*\*\s*(.+)', section)
            description = desc_match.group(1).strip() if desc_match else ""

            # Extract parameters
            params_match = re.search(r'\*\*(?:Параметры|Parameters):\*\*\s*(.+)', section)
            params = []
            if params_match:
                params = [p.strip() for p in params_match.group(1).split(',')]

            # Extract return value
            returns_match = re.search(r'\*\*(?:Возвращает|Returns):\*\*\s*(.+)', section)
            returns = returns_match.group(1).strip() if returns_match else ""

            functions.append(ImplementedFunction(
                name=name,
                description=description,
                parameters=params,
                returns=returns,
            ))

        return functions

    def _extract_requirements(self, content: str) -> List[str]:
        """Extract requirement IDs mentioned in content."""
        requirements = set()

        for match in self.REQUIREMENT_PATTERN.finditer(content):
            requirements.add(match.group(1).upper())

        return sorted(list(requirements))

    def _enrich_file_changes(self, result: AnalysisResult) -> None:
        """Enrich file changes with function information."""
        # Group functions by likely file
        for func in result.functions:
            for file_change in result.file_changes:
                if file_change.path.endswith('.bsl'):
                    # Add function to first matching BSL file
                    # In real scenario, we'd match by module name
                    if func.name not in file_change.functions:
                        file_change.functions.append(func.name)
                    break

    def get_test_points(self) -> List[Dict[str, Any]]:
        """
        Get points that need testing based on last analysis.

        Returns:
            List of test points with metadata
        """
        if not self._last_result:
            return []

        test_points = []

        # Each function is a test point
        for func in self._last_result.functions:
            test_points.append({
                "type": "function",
                "name": func.name,
                "is_export": func.is_export,
                "parameters": func.parameters,
                "priority": 1 if func.is_export else 2,
            })

        # Each file change is a test point
        for file in self._last_result.file_changes:
            test_points.append({
                "type": "file",
                "path": file.path,
                "change_type": file.change_type.value,
                "priority": 1 if file.change_type == ChangeType.ADDED else 2,
            })

        return test_points

    def get_coverage_requirements(self) -> List[str]:
        """Get requirements that need test coverage."""
        if not self._last_result:
            return []
        return self._last_result.requirements_covered


# Convenience function
def analyze_result(content: str) -> AnalysisResult:
    """
    Convenience function to analyze result.md content.

    Args:
        content: The markdown content

    Returns:
        AnalysisResult
    """
    analyzer = ResultAnalyzer()
    return analyzer.analyze(content)
