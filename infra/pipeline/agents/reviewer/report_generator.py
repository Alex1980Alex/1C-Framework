"""
Report Generator for REVIEWER Agent.

Generates review.md artifact from analysis results.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from agents.reviewer.models import (
    ReviewReport,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    ReviewVerdict,
    FileChange,
    StandardCheck,
)
from agents.reviewer.diff_analyzer import DiffAnalyzer, AnalysisResult
from agents.reviewer.style_checker import StyleChecker, StyleCheckResult
from agents.reviewer.arch_checker import ArchChecker, ArchCheckResult


@dataclass
class ReviewContext:
    """Context for review generation."""
    project_id: str
    task_id: str
    spec_content: Optional[str] = None
    design_content: Optional[str] = None
    result_content: Optional[str] = None
    diff_text: Optional[str] = None
    bsl_files: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "has_spec": self.spec_content is not None,
            "has_design": self.design_content is not None,
            "has_result": self.result_content is not None,
            "has_diff": self.diff_text is not None,
            "bsl_files_count": len(self.bsl_files),
        }


class ReviewGenerator:
    """
    Generates review.md from analysis components.

    Orchestrates:
    - DiffAnalyzer for change analysis
    - StyleChecker for code style
    - ArchChecker for architecture
    - Standard checks for 1C compliance

    Usage:
        generator = ReviewGenerator()
        context = ReviewContext(
            project_id="PROJECT",
            task_id="TASK-123",
            diff_text=diff,
            bsl_files={"path": "content"}
        )
        report = generator.generate(context)
        markdown = report.to_markdown()
    """

    # Standard checks for 1C development
    STANDARD_CHECKS = [
        ("Именование переменных", "naming_vars"),
        ("Именование процедур", "naming_procs"),
        ("Комментарии к экспортным методам", "comments"),
        ("Обработка ошибок", "error_handling"),
        ("Транзакции", "transactions"),
        ("SQL-инъекции", "sql_injection"),
        ("Использование НСтр", "localization"),
        ("Магические числа", "magic_numbers"),
    ]

    def __init__(self) -> None:
        """Initialize generator with analyzers."""
        self.diff_analyzer = DiffAnalyzer()
        self.style_checker = StyleChecker()
        self.arch_checker = ArchChecker()

    def generate(self, context: ReviewContext) -> ReviewReport:
        """
        Generate complete review report.

        Args:
            context: Review context with all inputs

        Returns:
            ReviewReport ready for markdown generation
        """
        report = ReviewReport(
            project_id=context.project_id,
            task_id=context.task_id,
            timestamp=datetime.now(),
        )

        # Phase 1: Analyze diff
        if context.diff_text:
            diff_result = self.diff_analyzer.analyze(context.diff_text)
            report.files_reviewed = diff_result.files
            report.issues.extend(diff_result.issues)

        # Phase 2: Check code style for each BSL file
        for file_path, content in context.bsl_files.items():
            style_result = self.style_checker.check(content, file_path)
            style_issues = self.style_checker.to_review_issues(style_result)
            report.issues.extend(style_issues)

            # Add file to reviewed if not already from diff
            if not any(f.file_path == file_path for f in report.files_reviewed):
                report.files_reviewed.append(FileChange(
                    file_path=file_path,
                    change_type="reviewed",
                ))

        # Phase 3: Check architecture
        if context.design_content:
            implemented_files = [f.file_path for f in report.files_reviewed]
            arch_result = self.arch_checker.check(
                self.arch_checker.parse_design(context.design_content),
                implemented_files,
                context.bsl_files,
            )
            arch_issues = self.arch_checker.to_review_issues(arch_result)
            report.issues.extend(arch_issues)

        # Phase 4: Standard checks
        report.standard_checks = self._run_standard_checks(
            context.bsl_files,
            report.issues
        )

        # Phase 5: Determine verdict and score
        report.verdict = report.determine_verdict()
        report.quality_score = report.calculate_quality_score()

        return report

    def _run_standard_checks(
        self,
        bsl_files: Dict[str, str],
        existing_issues: List[ReviewIssue]
    ) -> List[StandardCheck]:
        """Run standard compliance checks."""
        checks = []

        # Aggregate all BSL code
        all_code = "\n".join(bsl_files.values())

        # Check each standard
        for name, check_type in self.STANDARD_CHECKS:
            passed, status, comment = self._check_standard(
                check_type,
                all_code,
                existing_issues
            )
            checks.append(StandardCheck(
                standard_name=name,
                passed=passed,
                status=status,
                comment=comment,
            ))

        return checks

    def _check_standard(
        self,
        check_type: str,
        code: str,
        issues: List[ReviewIssue]
    ) -> tuple:
        """Check single standard, return (passed, status, comment)."""
        import re

        if check_type == "naming_vars":
            # Check for short variable names
            short_vars = re.findall(r'\bПерем\s+[а-яa-z]{1,2}\s*[,;]', code, re.IGNORECASE)
            if short_vars:
                return False, "⚠️", f"Найдено {len(short_vars)} коротких имён"
            return True, "✅", "Имена информативны"

        elif check_type == "naming_procs":
            # Check procedure naming (should start with verb)
            bad_procs = [i for i in issues if "N003" in str(i.id)]
            if bad_procs:
                return False, "⚠️", f"Найдено {len(bad_procs)} нарушений"
            return True, "✅", "Именование корректно"

        elif check_type == "comments":
            # Check for export functions without comments
            exports = re.findall(r'(?:Функция|Процедура)\s+\w+[^)]*\)\s+Экспорт', code)
            commented = re.findall(r'//[^\n]*\n\s*(?:Функция|Процедура)\s+\w+[^)]*\)\s+Экспорт', code)
            if exports and len(commented) < len(exports) * 0.5:
                return False, "⚠️", f"{len(exports) - len(commented)} без комментариев"
            return True, "✅", "Экспортные методы задокументированы"

        elif check_type == "error_handling":
            # Check for empty exception handlers
            empty_handlers = [i for i in issues if i.id and "E001" in i.id]
            if empty_handlers:
                return False, "❌", f"Найдено {len(empty_handlers)} пустых обработчиков"
            # Check for any try-except
            if 'Попытка' in code and 'КонецПопытки' in code:
                return True, "✅", "Обработка ошибок присутствует"
            return True, "⚠️", "Явная обработка ошибок не обнаружена"

        elif check_type == "transactions":
            # Check transaction pattern
            begin_trans = code.count('НачатьТранзакцию')
            commit_trans = code.count('ЗафиксироватьТранзакцию')
            rollback = code.count('ОтменитьТранзакцию')

            if begin_trans > 0:
                if begin_trans != commit_trans:
                    return False, "❌", "Несбалансированные транзакции"
                if rollback < begin_trans:
                    return False, "⚠️", "Возможен rollback без обработки"
                return True, "✅", f"{begin_trans} транзакций корректно"
            return True, "✅", "Транзакции не используются"

        elif check_type == "sql_injection":
            # Check for SQL injection patterns
            sql_issues = [i for i in issues if i.category == IssueCategory.SECURITY]
            if sql_issues:
                return False, "❌", f"Найдено {len(sql_issues)} уязвимостей"
            # Check for safe query patterns
            if 'Запрос.Текст' in code and ('+" ' in code or "+ '" in code):
                return False, "⚠️", "Возможна конкатенация в запросах"
            return True, "✅", "SQL-инъекции не обнаружены"

        elif check_type == "localization":
            # Check for localization
            messages = re.findall(r'(?:Сообщить|Предупреждение)\s*\(\s*"[^"]+"\s*[,)]', code)
            nstr_messages = re.findall(r'НСтр\s*\(\s*"', code)
            if messages and not nstr_messages:
                return False, "⚠️", "Строки без НСтр()"
            if nstr_messages:
                return True, "✅", "Локализация используется"
            return True, "⚠️", "Сообщения пользователю не найдены"

        elif check_type == "magic_numbers":
            # Check for magic numbers
            magic = re.findall(r'(?<!["\'])\b\d{4,}\b(?!["\'])', code)
            if magic:
                # Filter out dates and common values
                filtered = [m for m in magic if not (m.startswith('20') and len(m) == 8)]
                if filtered:
                    return False, "⚠️", f"Найдено {len(filtered)} магических чисел"
            return True, "✅", "Магические числа не обнаружены"

        return True, "⚠️", "Проверка не выполнена"

    def generate_markdown(self, report: ReviewReport) -> str:
        """
        Generate markdown content for review.md.

        Args:
            report: ReviewReport to convert

        Returns:
            Markdown string
        """
        return report.to_markdown()

    def save_report(
        self,
        report: ReviewReport,
        output_path: str
    ) -> None:
        """
        Save report to file.

        Args:
            report: ReviewReport to save
            output_path: Path to review.md
        """
        markdown = self.generate_markdown(report)
        Path(output_path).write_text(markdown, encoding='utf-8')


# Convenience functions
def generate_review(
    project_id: str,
    task_id: str,
    diff_text: Optional[str] = None,
    bsl_files: Optional[Dict[str, str]] = None,
    design_content: Optional[str] = None,
) -> ReviewReport:
    """
    Generate code review report.

    Args:
        project_id: Project identifier
        task_id: Task identifier
        diff_text: Git diff text (optional)
        bsl_files: Dict of file_path -> content (optional)
        design_content: Content of design.md (optional)

    Returns:
        ReviewReport
    """
    context = ReviewContext(
        project_id=project_id,
        task_id=task_id,
        diff_text=diff_text,
        bsl_files=bsl_files or {},
        design_content=design_content,
    )

    generator = ReviewGenerator()
    return generator.generate(context)


def generate_review_markdown(
    project_id: str,
    task_id: str,
    diff_text: Optional[str] = None,
    bsl_files: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate review markdown directly.

    Args:
        project_id: Project identifier
        task_id: Task identifier
        diff_text: Git diff text (optional)
        bsl_files: Dict of file_path -> content (optional)

    Returns:
        Markdown string
    """
    report = generate_review(project_id, task_id, diff_text, bsl_files)
    return report.to_markdown()
