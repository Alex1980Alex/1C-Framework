"""
REVIEWER Agent - Code Review for BSL/1C.

Components:
- DiffAnalyzer - анализ изменений в коде
- StyleChecker - проверка code style
- ArchChecker - проверка архитектуры
- ReviewGenerator - генерация review.md
- ReviewerAgent - главный оркестратор
"""

from agents.reviewer.models import (
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    FileChange,
    DiffHunk,
    StyleViolation,
    ArchIssue,
    ReviewReport,
    ReviewVerdict,
)

from agents.reviewer.diff_analyzer import DiffAnalyzer, parse_diff, analyze_changes
from agents.reviewer.style_checker import StyleChecker, check_style
from agents.reviewer.arch_checker import ArchChecker, check_architecture
from agents.reviewer.report_generator import ReviewGenerator, generate_review
from agents.reviewer.agent import ReviewerAgent, create_reviewer, run_review

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
