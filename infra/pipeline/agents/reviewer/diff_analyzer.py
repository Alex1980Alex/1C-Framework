"""
Diff Analyzer for REVIEWER Agent.

Parses and analyzes code changes (diffs).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import re
from pathlib import Path

from agents.reviewer.models import (
    FileChange,
    DiffHunk,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
)


@dataclass
class DiffStats:
    """Statistics about a diff."""
    total_files: int = 0
    bsl_files: int = 0
    additions: int = 0
    deletions: int = 0
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0

    @property
    def total_changes(self) -> int:
        """Total lines changed."""
        return self.additions + self.deletions

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_files": self.total_files,
            "bsl_files": self.bsl_files,
            "additions": self.additions,
            "deletions": self.deletions,
            "total_changes": self.total_changes,
        }


@dataclass
class AnalysisResult:
    """Result of diff analysis."""
    files: List[FileChange] = field(default_factory=list)
    stats: DiffStats = field(default_factory=DiffStats)
    issues: List[ReviewIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "files_count": len(self.files),
            "stats": self.stats.to_dict(),
            "issues_count": len(self.issues),
        }


class DiffAnalyzer:
    """
    Analyzes code diffs for review.

    Parses unified diff format and extracts:
    - Changed files
    - Added/removed lines
    - Change patterns
    - Potential issues

    Usage:
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(diff_text)
        for file in result.files:
            print(f"{file.file_path}: +{file.additions}/-{file.deletions}")
    """

    # Patterns for detecting issues in diffs
    SECURITY_PATTERNS = [
        # SQL injection - concatenation in queries
        (r'"\s*\+\s*[А-Яа-яA-Za-z_]+\s*\+\s*"', "SQL-инъекция: конкатенация строк в запросе"),
        (r"'\s*\+\s*[А-Яа-яA-Za-z_]+\s*\+\s*'", "SQL-инъекция: конкатенация строк"),
        # Hardcoded passwords
        (r'(?i)(пароль|password)\s*=\s*["\'][^"\']+["\']', "Захардкоженный пароль"),
        # Eval-like execution
        (r'Выполнить\s*\(', "Использование Выполнить() - потенциальная уязвимость"),
    ]

    PERFORMANCE_PATTERNS = [
        # Query in loop
        (r'(?:Для|Пока).*Цикл[\s\S]*?Запрос\.Выполнить', "Запрос внутри цикла"),
        # Select all
        (r'ВЫБРАТЬ\s+\*\s+ИЗ', "SELECT * - выбор всех полей"),
    ]

    STYLE_PATTERNS = [
        # Short variable names
        (r'\bПерем\s+[а-яa-z]{1,2}\s*[,;]', "Неинформативное имя переменной"),
        # Magic numbers
        (r'(?<!\.)\b\d{4,}\b(?!\.)', "Магическое число в коде"),
        # Empty exception handler
        (r'Исключение\s*[\r\n]+\s*КонецПопытки', "Пустой обработчик исключения"),
    ]

    def __init__(self) -> None:
        """Initialize analyzer."""
        self._issue_counters = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.WARNING: 0,
            IssueSeverity.RECOMMENDATION: 0,
        }

    def analyze(self, diff_text: str) -> AnalysisResult:
        """
        Analyze diff text.

        Args:
            diff_text: Unified diff format text

        Returns:
            AnalysisResult with files and issues
        """
        result = AnalysisResult()

        # Parse diff
        files = self.parse_diff(diff_text)
        result.files = files

        # Calculate stats
        result.stats = self._calculate_stats(files)

        # Find issues in changes
        for file_change in files:
            if file_change.is_bsl:
                issues = self._analyze_bsl_changes(file_change)
                result.issues.extend(issues)

        return result

    def parse_diff(self, diff_text: str) -> List[FileChange]:
        """
        Parse unified diff format.

        Args:
            diff_text: Raw diff text

        Returns:
            List of FileChange objects
        """
        files = []
        current_file = None
        current_hunk = None

        lines = diff_text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # New file header
            if line.startswith('diff --git'):
                if current_file:
                    files.append(current_file)
                current_file = self._parse_file_header(line, lines, i)
                i += 1
                continue

            # File mode/type info
            if line.startswith('new file mode'):
                if current_file:
                    current_file.change_type = 'added'
                i += 1
                continue

            if line.startswith('deleted file mode'):
                if current_file:
                    current_file.change_type = 'deleted'
                i += 1
                continue

            if line.startswith('rename from'):
                if current_file:
                    current_file.change_type = 'renamed'
                    current_file.old_path = line[12:].strip()
                i += 1
                continue

            # Hunk header
            if line.startswith('@@'):
                current_hunk = self._parse_hunk_header(line)
                if current_file and current_hunk:
                    current_file.hunks.append(current_hunk)
                i += 1
                continue

            # Hunk content
            if current_hunk:
                if line.startswith('+') and not line.startswith('+++'):
                    current_hunk.added_lines.append(line[1:])
                elif line.startswith('-') and not line.startswith('---'):
                    current_hunk.removed_lines.append(line[1:])
                elif line.startswith(' '):
                    current_hunk.context_lines.append(line[1:])

            i += 1

        # Don't forget last file
        if current_file:
            files.append(current_file)

        return files

    def _parse_file_header(
        self,
        header_line: str,
        lines: List[str],
        index: int
    ) -> FileChange:
        """Parse file header from diff."""
        # Extract path from "diff --git a/path b/path"
        match = re.search(r'diff --git a/(.*) b/(.*)', header_line)
        if match:
            old_path = match.group(1)
            new_path = match.group(2)
        else:
            # Fallback
            old_path = new_path = "unknown"

        # Check subsequent lines for more info
        change_type = 'modified'
        for j in range(index + 1, min(index + 5, len(lines))):
            if lines[j].startswith('new file'):
                change_type = 'added'
                break
            elif lines[j].startswith('deleted file'):
                change_type = 'deleted'
                break
            elif lines[j].startswith('rename'):
                change_type = 'renamed'
                break

        return FileChange(
            file_path=new_path,
            change_type=change_type,
            old_path=old_path if old_path != new_path else None,
        )

    def _parse_hunk_header(self, line: str) -> Optional[DiffHunk]:
        """Parse hunk header like @@ -1,5 +1,7 @@."""
        match = re.search(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if not match:
            return None

        return DiffHunk(
            old_start=int(match.group(1)),
            old_count=int(match.group(2) or 1),
            new_start=int(match.group(3)),
            new_count=int(match.group(4) or 1),
            content="",
        )

    def _calculate_stats(self, files: List[FileChange]) -> DiffStats:
        """Calculate statistics from files."""
        stats = DiffStats()
        stats.total_files = len(files)

        for f in files:
            if f.is_bsl:
                stats.bsl_files += 1

            stats.additions += f.additions
            stats.deletions += f.deletions

            if f.change_type == 'added':
                stats.files_added += 1
            elif f.change_type == 'deleted':
                stats.files_deleted += 1
            elif f.change_type == 'renamed':
                stats.files_renamed += 1
            else:
                stats.files_modified += 1

        return stats

    def _analyze_bsl_changes(self, file_change: FileChange) -> List[ReviewIssue]:
        """Analyze BSL file changes for issues."""
        issues = []

        # Combine all added lines for analysis
        added_content = "\n".join(
            line
            for hunk in file_change.hunks
            for line in hunk.added_lines
        )

        # Check security patterns
        for pattern, message in self.SECURITY_PATTERNS:
            matches = re.finditer(pattern, added_content, re.IGNORECASE)
            for match in matches:
                issue = self._create_issue(
                    title=message,
                    description=f"Обнаружен потенциально небезопасный код: {match.group(0)[:50]}",
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.SECURITY,
                    file_path=file_change.file_path,
                    code_snippet=match.group(0),
                )
                issues.append(issue)

        # Check performance patterns
        for pattern, message in self.PERFORMANCE_PATTERNS:
            matches = re.finditer(pattern, added_content, re.IGNORECASE)
            for match in matches:
                issue = self._create_issue(
                    title=message,
                    description="Потенциальная проблема производительности",
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.PERFORMANCE,
                    file_path=file_change.file_path,
                    code_snippet=match.group(0)[:100],
                )
                issues.append(issue)

        # Check style patterns
        for pattern, message in self.STYLE_PATTERNS:
            matches = re.finditer(pattern, added_content, re.IGNORECASE)
            for match in matches:
                issue = self._create_issue(
                    title=message,
                    description="Нарушение стиля кодирования",
                    severity=IssueSeverity.RECOMMENDATION,
                    category=IssueCategory.STYLE,
                    file_path=file_change.file_path,
                    code_snippet=match.group(0),
                )
                issues.append(issue)

        return issues

    def _create_issue(
        self,
        title: str,
        description: str,
        severity: IssueSeverity,
        category: IssueCategory,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        code_snippet: Optional[str] = None,
    ) -> ReviewIssue:
        """Create and number a review issue."""
        self._issue_counters[severity] += 1

        prefix = {
            IssueSeverity.CRITICAL: "CR",
            IssueSeverity.WARNING: "WRN",
            IssueSeverity.RECOMMENDATION: "REC",
        }.get(severity, "ISS")

        issue_id = f"{prefix}-{self._issue_counters[severity]:03d}"

        return ReviewIssue(
            id=issue_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            file_path=file_path,
            line_number=line_number,
            code_snippet=code_snippet,
        )

    def get_changed_functions(self, file_change: FileChange) -> List[str]:
        """
        Extract function/procedure names from changes.

        Args:
            file_change: File with changes

        Returns:
            List of function/procedure names
        """
        functions = []

        for hunk in file_change.hunks:
            for line in hunk.added_lines:
                # Match function definitions
                match = re.search(
                    r'(?:Функция|Процедура)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)',
                    line,
                    re.IGNORECASE
                )
                if match:
                    functions.append(match.group(1))

        return functions

    def reset_counters(self) -> None:
        """Reset issue counters."""
        self._issue_counters = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.WARNING: 0,
            IssueSeverity.RECOMMENDATION: 0,
        }


# Convenience functions
def parse_diff(diff_text: str) -> List[FileChange]:
    """
    Parse diff text into file changes.

    Args:
        diff_text: Unified diff format

    Returns:
        List of FileChange
    """
    analyzer = DiffAnalyzer()
    return analyzer.parse_diff(diff_text)


def analyze_changes(diff_text: str) -> AnalysisResult:
    """
    Analyze diff for review issues.

    Args:
        diff_text: Unified diff format

    Returns:
        AnalysisResult
    """
    analyzer = DiffAnalyzer()
    return analyzer.analyze(diff_text)


def get_diff_stats(diff_text: str) -> DiffStats:
    """
    Get statistics from diff.

    Args:
        diff_text: Unified diff format

    Returns:
        DiffStats
    """
    analyzer = DiffAnalyzer()
    result = analyzer.analyze(diff_text)
    return result.stats
