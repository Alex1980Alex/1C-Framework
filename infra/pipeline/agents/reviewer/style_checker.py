"""
Style Checker for REVIEWER Agent.

Checks BSL code against 1C coding standards.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Pattern
import re

from agents.reviewer.models import (
    StyleViolation,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
)


@dataclass
class StyleRule:
    """Definition of a style rule."""
    id: str
    name: str
    description: str
    pattern: str
    severity: IssueSeverity = IssueSeverity.WARNING
    recommendation: Optional[str] = None
    is_negative: bool = True  # True = pattern should NOT match

    def __post_init__(self):
        """Compile pattern."""
        self._compiled: Optional[Pattern] = None
        try:
            self._compiled = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
        except re.error:
            pass

    @property
    def compiled_pattern(self) -> Optional[Pattern]:
        """Get compiled regex pattern."""
        return self._compiled


@dataclass
class StyleCheckResult:
    """Result of style checking."""
    violations: List[StyleViolation] = field(default_factory=list)
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    score: float = 100.0  # 0-100

    @property
    def passed(self) -> bool:
        """Check if all rules passed."""
        return len(self.violations) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "violations_count": len(self.violations),
            "passed_rules": len(self.passed_rules),
            "failed_rules": len(self.failed_rules),
            "score": round(self.score, 1),
            "passed": self.passed,
        }


class StyleChecker:
    """
    Checks BSL code style against 1C standards.

    Implements checks for:
    - Variable naming
    - Procedure/function naming
    - Comments
    - Code structure
    - Error handling
    - Transactions

    Usage:
        checker = StyleChecker()
        result = checker.check(bsl_code, file_path)
        for violation in result.violations:
            print(f"{violation.rule_name}: {violation.message}")
    """

    # Default style rules for BSL
    DEFAULT_RULES = [
        # Naming rules
        StyleRule(
            id="N001",
            name="Неинформативное имя переменной",
            description="Переменные должны иметь осмысленные имена",
            pattern=r'\bПерем\s+[а-яa-z]{1,2}\s*[,;]',
            severity=IssueSeverity.WARNING,
            recommendation="Используйте описательные имена: СуммаДокумента, КоличествоСтрок",
        ),
        StyleRule(
            id="N002",
            name="Транслит в именах",
            description="Не используйте транслит в именах переменных",
            pattern=r'\b(?:Summa|Kolichestvo|Dokument|Spravochnik|Poluchit|Ustanovit)[А-Яа-яA-Za-z_]*\b',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Используйте русские или английские имена: Сумма, Amount",
        ),
        StyleRule(
            id="N003",
            name="Имя процедуры не начинается с глагола",
            description="Процедуры должны начинаться с глагола",
            pattern=r'Процедура\s+(?!(?:Выполнить|Записать|Удалить|Создать|Получить|Установить|Проверить|Обработать|Заполнить|Рассчитать|Сформировать|Открыть|Закрыть|Добавить|Изменить|Показать|Скрыть|Обновить|Найти|Очистить|При|До|После)[А-Яа-я])[А-Яа-яA-Za-z_]+\s*\(',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Начинайте имя процедуры с глагола: ЗаписатьДанные(), ОбработатьСобытие()",
        ),

        # Structure rules
        StyleRule(
            id="S001",
            name="Слишком длинная строка",
            description="Строка превышает рекомендуемую длину в 120 символов",
            pattern=r'^.{121,}$',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Разбейте строку на несколько строк",
        ),
        StyleRule(
            id="S002",
            name="Множественное объявление переменных",
            description="Не объявляйте много переменных в одной строке",
            pattern=r'\bПерем\s+[А-Яа-яA-Za-z_]+\s*,\s*[А-Яа-яA-Za-z_]+\s*,\s*[А-Яа-яA-Za-z_]+\s*,',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Объявляйте каждую переменную на отдельной строке",
        ),
        StyleRule(
            id="S003",
            name="Глубокая вложенность",
            description="Слишком глубокая вложенность условий/циклов",
            pattern=r'(?:Если|Для|Пока|Попытка)[\s\S]*?(?:Если|Для|Пока|Попытка)[\s\S]*?(?:Если|Для|Пока|Попытка)[\s\S]*?(?:Если|Для|Пока|Попытка)',
            severity=IssueSeverity.WARNING,
            recommendation="Используйте ранний выход или выделите в отдельную процедуру",
        ),

        # Error handling rules
        StyleRule(
            id="E001",
            name="Пустой обработчик исключения",
            description="Обработчик исключения не содержит кода",
            pattern=r'Исключение\s*[\r\n]+\s*КонецПопытки',
            severity=IssueSeverity.CRITICAL,
            recommendation="Добавьте обработку ошибки или логирование",
        ),
        StyleRule(
            id="E002",
            name="Подавление всех исключений",
            description="Не используйте пустой Попытка/Исключение",
            pattern=r'Попытка\s*[\r\n]+\s*[^\r\n]+\s*[\r\n]+\s*Исключение\s*[\r\n]+\s*КонецПопытки',
            severity=IssueSeverity.WARNING,
            recommendation="Обрабатывайте конкретные типы ошибок",
        ),

        # Security rules
        StyleRule(
            id="SEC001",
            name="SQL-инъекция",
            description="Конкатенация строк в тексте запроса",
            pattern=r'Запрос\.Текст\s*=\s*["\'][^"\']*["\']\s*\+',
            severity=IssueSeverity.CRITICAL,
            recommendation="Используйте параметры запроса: &ИмяПараметра",
        ),
        StyleRule(
            id="SEC002",
            name="Конкатенация в условии запроса",
            description="Небезопасная конкатенация в WHERE",
            pattern=r'(?:ГДЕ|WHERE)\s*[^=]*=\s*["\'][^"\']*["\']\s*\+',
            severity=IssueSeverity.CRITICAL,
            recommendation="Используйте параметры: ГДЕ Поле = &Параметр",
        ),
        StyleRule(
            id="SEC003",
            name="Использование Выполнить()",
            description="Динамическое выполнение кода",
            pattern=r'\bВыполнить\s*\(',
            severity=IssueSeverity.WARNING,
            recommendation="Избегайте динамического выполнения кода",
        ),

        # Performance rules
        StyleRule(
            id="P001",
            name="SELECT * в запросе",
            description="Выбор всех полей неэффективен",
            pattern=r'ВЫБРАТЬ\s+\*\s+ИЗ',
            severity=IssueSeverity.WARNING,
            recommendation="Указывайте только нужные поля",
        ),
        StyleRule(
            id="P002",
            name="Запрос без ограничения",
            description="Запрос без ПЕРВЫЕ или условия может вернуть много данных",
            pattern=r'ВЫБРАТЬ\s+(?!ПЕРВЫЕ)[^;]*ИЗ\s+(?:Справочник|Документ|РегистрСведений)\.[^\s]+\s*(?:;|$)',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Добавьте ПЕРВЫЕ N или условие ГДЕ",
        ),

        # Documentation rules
        StyleRule(
            id="D001",
            name="Отсутствует описание процедуры",
            description="Экспортная процедура/функция без комментария",
            pattern=r'(?<!//[^\n]*\n)(?:Процедура|Функция)\s+[А-Яа-яA-Za-z_]+[^)]*\)\s+Экспорт',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation="Добавьте комментарий с описанием назначения и параметров",
        ),

        # Transaction rules
        StyleRule(
            id="T001",
            name="НачатьТранзакцию без Попытки",
            description="Транзакция должна быть в блоке Попытка",
            pattern=r'НачатьТранзакцию\s*\(\s*\)\s*;(?![^;]*Попытка)',
            severity=IssueSeverity.WARNING,
            recommendation="Оберните транзакцию в Попытка/Исключение",
        ),

        # Localization rules
        StyleRule(
            id="L001",
            name="Текст без НСтр",
            description="Строковый литерал должен быть обёрнут в НСтр",
            pattern=r'(?:Сообщить|Предупреждение|Вопрос)\s*\(\s*"[^"]+"\s*[,)]',
            severity=IssueSeverity.RECOMMENDATION,
            recommendation='Используйте НСтр("ru = \'Текст\'")',
        ),
    ]

    def __init__(self, rules: Optional[List[StyleRule]] = None) -> None:
        """
        Initialize checker.

        Args:
            rules: Custom rules (uses defaults if not provided)
        """
        self.rules = rules or self.DEFAULT_RULES.copy()
        self._violation_counter = 0

    def check(
        self,
        code: str,
        file_path: str = "unknown.bsl"
    ) -> StyleCheckResult:
        """
        Check code against style rules.

        Args:
            code: BSL source code
            file_path: Path to file (for reporting)

        Returns:
            StyleCheckResult with violations
        """
        result = StyleCheckResult()
        lines = code.split('\n')

        for rule in self.rules:
            if rule.compiled_pattern is None:
                continue

            violations = self._check_rule(rule, code, lines, file_path)

            if violations:
                result.violations.extend(violations)
                result.failed_rules.append(rule.id)
            else:
                result.passed_rules.append(rule.id)

        # Calculate score
        result.score = self._calculate_score(result)

        return result

    def check_file(self, file_path: str) -> StyleCheckResult:
        """
        Check file against style rules.

        Args:
            file_path: Path to BSL file

        Returns:
            StyleCheckResult
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.check(code, file_path)
        except Exception as e:
            result = StyleCheckResult()
            result.violations.append(StyleViolation(
                rule_id="ERR",
                rule_name="Ошибка чтения файла",
                file_path=file_path,
                line_number=0,
                message=str(e),
                severity=IssueSeverity.WARNING,
            ))
            return result

    def _check_rule(
        self,
        rule: StyleRule,
        code: str,
        lines: List[str],
        file_path: str
    ) -> List[StyleViolation]:
        """Check a single rule against code."""
        violations = []
        pattern = rule.compiled_pattern

        if pattern is None:
            return violations

        # Find all matches
        for match in pattern.finditer(code):
            if rule.is_negative:
                # Pattern matched = violation
                line_num = code[:match.start()].count('\n') + 1
                code_line = lines[line_num - 1] if line_num <= len(lines) else ""

                self._violation_counter += 1
                violations.append(StyleViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    file_path=file_path,
                    line_number=line_num,
                    message=rule.description,
                    severity=rule.severity,
                    code_line=code_line.strip(),
                ))

        return violations

    def _calculate_score(self, result: StyleCheckResult) -> float:
        """Calculate style score (0-100)."""
        if not result.violations:
            return 100.0

        score = 100.0
        for violation in result.violations:
            if violation.severity == IssueSeverity.CRITICAL:
                score -= 15.0
            elif violation.severity == IssueSeverity.WARNING:
                score -= 5.0
            else:
                score -= 1.0

        return max(0.0, score)

    def add_rule(self, rule: StyleRule) -> None:
        """Add a custom rule."""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        original_len = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        return len(self.rules) < original_len

    def get_rule(self, rule_id: str) -> Optional[StyleRule]:
        """Get a rule by ID."""
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def to_review_issues(
        self,
        result: StyleCheckResult
    ) -> List[ReviewIssue]:
        """
        Convert violations to review issues.

        Args:
            result: Style check result

        Returns:
            List of ReviewIssue
        """
        issues = []
        counter = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.WARNING: 0,
            IssueSeverity.RECOMMENDATION: 0,
        }

        for violation in result.violations:
            counter[violation.severity] += 1
            prefix = {
                IssueSeverity.CRITICAL: "CR",
                IssueSeverity.WARNING: "WRN",
                IssueSeverity.RECOMMENDATION: "REC",
            }.get(violation.severity, "ISS")

            issue = ReviewIssue(
                id=f"{prefix}-{counter[violation.severity]:03d}",
                title=violation.rule_name,
                description=violation.message,
                severity=violation.severity,
                category=IssueCategory.STYLE,
                file_path=violation.file_path,
                line_number=violation.line_number,
                code_snippet=violation.code_line,
                recommendation=self.get_rule(violation.rule_id).recommendation
                if self.get_rule(violation.rule_id) else None,
            )
            issues.append(issue)

        return issues


# Factory for specific checker configurations
def create_strict_checker() -> StyleChecker:
    """Create checker with strict rules (all warnings become critical)."""
    checker = StyleChecker()
    for rule in checker.rules:
        if rule.severity == IssueSeverity.WARNING:
            rule.severity = IssueSeverity.CRITICAL
    return checker


def create_minimal_checker() -> StyleChecker:
    """Create checker with only critical rules."""
    rules = [r for r in StyleChecker.DEFAULT_RULES if r.severity == IssueSeverity.CRITICAL]
    return StyleChecker(rules)


# Convenience functions
def check_style(code: str, file_path: str = "unknown.bsl") -> StyleCheckResult:
    """
    Check BSL code style.

    Args:
        code: BSL source code
        file_path: Path for reporting

    Returns:
        StyleCheckResult
    """
    checker = StyleChecker()
    return checker.check(code, file_path)


def check_file_style(file_path: str) -> StyleCheckResult:
    """
    Check BSL file style.

    Args:
        file_path: Path to BSL file

    Returns:
        StyleCheckResult
    """
    checker = StyleChecker()
    return checker.check_file(file_path)
