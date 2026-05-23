"""
REVIEWER Agent - Code Review for BSL/1C.

Components:
- DiffAnalyzer - анализ изменений в коде
- StyleChecker - проверка code style
- ArchChecker - проверка архитектуры
- ReviewGenerator - генерация review.md
- ReviewerAgent - главный оркестратор
"""

from agents.reviewer.agent import ReviewerAgent, create_reviewer, run_review
from agents.reviewer.arch_checker import ArchChecker, check_architecture
from agents.reviewer.diff_analyzer import DiffAnalyzer, analyze_changes, parse_diff
from agents.reviewer.models import (
    ArchIssue,
    DiffHunk,
    FileChange,
    IssueCategory,
    IssueSeverity,
    ReviewIssue,
    ReviewReport,
    ReviewVerdict,
    StyleViolation,
)
from agents.reviewer.report_generator import ReviewGenerator, generate_review
from agents.reviewer.style_checker import StyleChecker, check_style

__all__ = [
    # Models
    "ReviewIssue",
    "IssueSeverity",
    "IssueCategory",
    "FileChange",
    "DiffHunk",
    "StyleViolation",
    "ArchIssue",
    "ReviewReport",
    "ReviewVerdict",
    # Components
    "DiffAnalyzer",
    "StyleChecker",
    "ArchChecker",
    "ReviewGenerator",
    "ReviewerAgent",
    # Functions
    "parse_diff",
    "analyze_changes",
    "check_style",
    "check_architecture",
    "generate_review",
    "create_reviewer",
    "run_review",
]
