"""
Tests for REVIEWER StyleChecker.
"""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from agents.reviewer.style_checker import (
    StyleRule,
    StyleCheckResult,
    StyleChecker,
    create_strict_checker,
    create_minimal_checker,
    check_style,
    check_file_style,
)
from agents.reviewer.models import (
    StyleViolation,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
)


# Sample BSL code for testing
CLEAN_CODE = """
Процедура ОбработатьДанные(ДанныеДляОбработки)
    Перем РезультатОбработки;

    Если ЗначениеЗаполнено(ДанныеДляОбработки) Тогда
        РезультатОбработки = ВыполнитьОбработку(ДанныеДляОбработки);
    КонецЕсли;
КонецПроцедуры
"""

SHORT_VARIABLE_CODE = """
Процедура Тест()
    Перем а;
    Перем б, в;
    а = 1;
КонецПроцедуры
"""

EMPTY_EXCEPTION_CODE = """
Процедура ОбработатьОшибку()
    Попытка
        ВыполнитьДействие();
    Исключение
    КонецПопытки
КонецПроцедуры
"""

SQL_INJECTION_CODE = """
Функция ПолучитьДанные(Параметр)
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары ГДЕ Наименование = '" + Параметр + "'";
    Возврат Запрос.Выполнить();
КонецФункции
"""

SELECT_ALL_CODE = """
Функция ПолучитьВсеТовары()
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары";
    Возврат Запрос.Выполнить();
КонецФункции
"""

EXECUTE_CODE = """
Процедура ВыполнитьКод(КодДляВыполнения)
    Выполнить(КодДляВыполнения);
КонецПроцедуры
"""

TRANSLITERATION_CODE = """
Функция ПолучитьSummaDocumenta()
    Перем SummaDokumenta;
    SummaDokumenta = 0;
    Возврат SummaDokumenta;
КонецФункции
"""

MULTI_VARIABLE_CODE = """
Процедура Тест()
    Перем Переменная1, Переменная2, Переменная3, Переменная4;
КонецПроцедуры
"""

LONG_LINE_CODE = """
Процедура Тест()
    ОченьДлинноеИмяПеременной = ОченьДлинноеИмяФункции(ОченьДлинныйПараметр1, ОченьДлинныйПараметр2, ОченьДлинныйПараметр3, ОченьДлинныйПараметр4, ОченьДлинныйПараметр5);
КонецПроцедуры
"""

EXPORT_WITHOUT_COMMENT_CODE = """
Функция ПолучитьДанные() Экспорт
    Возврат Неопределено;
КонецФункции
"""

MESSAGE_WITHOUT_NSTR_CODE = """
Процедура ПоказатьСообщение()
    Сообщить("Текст сообщения без локализации");
КонецПроцедуры
"""

TRANSACTION_WITHOUT_TRY_CODE = """
Процедура ЗаписатьДанные()
    НачатьТранзакцию();
    ЗаписатьДокумент();
    ЗафиксироватьТранзакцию();
КонецПроцедуры
"""

DEEP_NESTING_CODE = """
Процедура СложнаяОбработка()
    Если Условие1 Тогда
        Для Каждого Элемент Из Коллекция Цикл
            Если Условие2 Тогда
                Пока Условие3 Цикл
                    ВыполнитьДействие();
                КонецЦикла;
            КонецЕсли;
        КонецЦикла;
    КонецЕсли;
КонецПроцедуры
"""


class TestStyleRule:
    """Tests for StyleRule dataclass."""

    def test_creation(self):
        """Test rule creation."""
        rule = StyleRule(
            id="TEST001",
            name="Test Rule",
            description="Test description",
            pattern=r'\bТест\b',
        )
        assert rule.id == "TEST001"
        assert rule.name == "Test Rule"
        assert rule.severity == IssueSeverity.WARNING
        assert rule.is_negative is True

    def test_pattern_compilation(self):
        """Test pattern compilation."""
        rule = StyleRule(
            id="TEST",
            name="Test",
            description="Test",
            pattern=r'\bПерем\b',
        )
        assert rule.compiled_pattern is not None

    def test_invalid_pattern(self):
        """Test invalid regex pattern."""
        rule = StyleRule(
            id="TEST",
            name="Test",
            description="Test",
            pattern=r'[invalid',  # Invalid regex
        )
        assert rule.compiled_pattern is None

    def test_custom_severity(self):
        """Test custom severity."""
        rule = StyleRule(
            id="TEST",
            name="Test",
            description="Test",
            pattern=r'test',
            severity=IssueSeverity.CRITICAL,
        )
        assert rule.severity == IssueSeverity.CRITICAL


class TestStyleCheckResult:
    """Tests for StyleCheckResult dataclass."""

    def test_empty_result(self):
        """Test empty result."""
        result = StyleCheckResult()
        assert result.violations == []
        assert result.passed is True
        assert result.score == 100.0

    def test_with_violations(self):
        """Test result with violations."""
        result = StyleCheckResult()
        result.violations.append(StyleViolation(
            rule_id="N001",
            rule_name="Test",
            file_path="test.bsl",
            line_number=1,
            message="Test",
        ))
        assert result.passed is False

    def test_to_dict(self):
        """Test serialization."""
        result = StyleCheckResult(
            passed_rules=["R1", "R2"],
            failed_rules=["R3"],
            score=85.5,
        )
        d = result.to_dict()
        assert d["passed_rules"] == 2
        assert d["failed_rules"] == 1
        assert d["score"] == 85.5


class TestStyleChecker:
    """Tests for StyleChecker class."""

    def test_default_rules(self):
        """Test default rules are loaded."""
        checker = StyleChecker()
        assert len(checker.rules) > 0
        assert any(r.id == "N001" for r in checker.rules)
        assert any(r.id == "SEC001" for r in checker.rules)

    def test_custom_rules(self):
        """Test custom rules."""
        custom_rules = [
            StyleRule(
                id="CUSTOM001",
                name="Custom Rule",
                description="Custom",
                pattern=r'\bCustomPattern\b',
            )
        ]
        checker = StyleChecker(rules=custom_rules)
        assert len(checker.rules) == 1
        assert checker.rules[0].id == "CUSTOM001"

    def test_check_clean_code(self):
        """Test checking clean code."""
        checker = StyleChecker()
        result = checker.check(CLEAN_CODE, "test.bsl")
        # Clean code may still have some recommendations
        critical = [v for v in result.violations if v.severity == IssueSeverity.CRITICAL]
        assert len(critical) == 0

    def test_check_short_variables(self):
        """Test detection of short variable names."""
        checker = StyleChecker()
        result = checker.check(SHORT_VARIABLE_CODE, "test.bsl")

        naming_violations = [v for v in result.violations if v.rule_id == "N001"]
        assert len(naming_violations) >= 1

    def test_check_empty_exception(self):
        """Test detection of empty exception handler."""
        checker = StyleChecker()
        result = checker.check(EMPTY_EXCEPTION_CODE, "test.bsl")

        empty_handler = [v for v in result.violations if v.rule_id == "E001"]
        assert len(empty_handler) >= 1
        assert empty_handler[0].severity == IssueSeverity.CRITICAL

    def test_check_sql_injection(self):
        """Test detection of SQL injection pattern."""
        checker = StyleChecker()
        result = checker.check(SQL_INJECTION_CODE, "test.bsl")

        sql_issues = [v for v in result.violations if v.rule_id in ("SEC001", "SEC002")]
        assert len(sql_issues) >= 1

    def test_check_select_all(self):
        """Test detection of SELECT *."""
        checker = StyleChecker()
        result = checker.check(SELECT_ALL_CODE, "test.bsl")

        select_all = [v for v in result.violations if v.rule_id == "P001"]
        assert len(select_all) >= 1

    def test_check_execute_code(self):
        """Test detection of Выполнить()."""
        checker = StyleChecker()
        result = checker.check(EXECUTE_CODE, "test.bsl")

        execute_issues = [v for v in result.violations if v.rule_id == "SEC003"]
        assert len(execute_issues) >= 1

    def test_check_transliteration(self):
        """Test detection of transliteration."""
        checker = StyleChecker()
        result = checker.check(TRANSLITERATION_CODE, "test.bsl")

        translit = [v for v in result.violations if v.rule_id == "N002"]
        assert len(translit) >= 1

    def test_check_multi_variable(self):
        """Test detection of multiple variable declaration."""
        checker = StyleChecker()
        result = checker.check(MULTI_VARIABLE_CODE, "test.bsl")

        multi_var = [v for v in result.violations if v.rule_id == "S002"]
        assert len(multi_var) >= 1

    def test_check_long_line(self):
        """Test detection of long lines."""
        checker = StyleChecker()
        result = checker.check(LONG_LINE_CODE, "test.bsl")

        long_lines = [v for v in result.violations if v.rule_id == "S001"]
        assert len(long_lines) >= 1

    def test_check_export_without_comment(self):
        """Test detection of export without comment."""
        checker = StyleChecker()
        result = checker.check(EXPORT_WITHOUT_COMMENT_CODE, "test.bsl")

        doc_issues = [v for v in result.violations if v.rule_id == "D001"]
        assert len(doc_issues) >= 1

    def test_check_message_without_nstr(self):
        """Test detection of message without НСтр."""
        checker = StyleChecker()
        result = checker.check(MESSAGE_WITHOUT_NSTR_CODE, "test.bsl")

        nstr_issues = [v for v in result.violations if v.rule_id == "L001"]
        assert len(nstr_issues) >= 1

    def test_check_deep_nesting(self):
        """Test detection of deep nesting."""
        checker = StyleChecker()
        result = checker.check(DEEP_NESTING_CODE, "test.bsl")

        nesting = [v for v in result.violations if v.rule_id == "S003"]
        assert len(nesting) >= 1

    def test_line_numbers(self):
        """Test violation line numbers."""
        checker = StyleChecker()
        result = checker.check(SHORT_VARIABLE_CODE, "test.bsl")

        for violation in result.violations:
            assert violation.line_number > 0

    def test_score_calculation(self):
        """Test score calculation."""
        checker = StyleChecker()

        # Clean code should have high score
        clean_result = checker.check(CLEAN_CODE, "test.bsl")
        assert clean_result.score >= 80.0

        # Code with critical issues should have low score
        critical_result = checker.check(EMPTY_EXCEPTION_CODE, "test.bsl")
        assert critical_result.score < 100.0

    def test_add_rule(self):
        """Test adding a rule."""
        checker = StyleChecker()
        initial_count = len(checker.rules)

        checker.add_rule(StyleRule(
            id="NEW001",
            name="New Rule",
            description="New",
            pattern=r'\bNewPattern\b',
        ))

        assert len(checker.rules) == initial_count + 1
        assert any(r.id == "NEW001" for r in checker.rules)

    def test_remove_rule(self):
        """Test removing a rule."""
        checker = StyleChecker()
        initial_count = len(checker.rules)

        removed = checker.remove_rule("N001")

        assert removed is True
        assert len(checker.rules) == initial_count - 1
        assert not any(r.id == "N001" for r in checker.rules)

    def test_remove_nonexistent_rule(self):
        """Test removing nonexistent rule."""
        checker = StyleChecker()
        removed = checker.remove_rule("NONEXISTENT")
        assert removed is False

    def test_get_rule(self):
        """Test getting a rule by ID."""
        checker = StyleChecker()

        rule = checker.get_rule("N001")
        assert rule is not None
        assert rule.id == "N001"

        nonexistent = checker.get_rule("NONEXISTENT")
        assert nonexistent is None

    def test_to_review_issues(self):
        """Test conversion to review issues."""
        checker = StyleChecker()
        result = checker.check(SHORT_VARIABLE_CODE, "test.bsl")

        issues = checker.to_review_issues(result)

        assert len(issues) == len(result.violations)
        for issue in issues:
            assert isinstance(issue, ReviewIssue)
            assert issue.category == IssueCategory.STYLE
            assert issue.id is not None
            assert "-" in issue.id  # Format like CR-001

    def test_issue_id_prefixes(self):
        """Test issue ID prefixes by severity."""
        checker = StyleChecker()

        # Test with code that has critical and warning issues
        combined_code = EMPTY_EXCEPTION_CODE + SHORT_VARIABLE_CODE
        result = checker.check(combined_code, "test.bsl")
        issues = checker.to_review_issues(result)

        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                assert issue.id.startswith("CR-")
            elif issue.severity == IssueSeverity.WARNING:
                assert issue.id.startswith("WRN-")
            elif issue.severity == IssueSeverity.RECOMMENDATION:
                assert issue.id.startswith("REC-")


class TestStyleCheckerFile:
    """Tests for file-based checking."""

    def test_check_file(self, tmp_path):
        """Test checking a file."""
        # Create temporary file
        file_path = tmp_path / "test.bsl"
        file_path.write_text(CLEAN_CODE, encoding='utf-8')

        checker = StyleChecker()
        result = checker.check_file(str(file_path))

        assert isinstance(result, StyleCheckResult)

    def test_check_nonexistent_file(self):
        """Test checking nonexistent file."""
        checker = StyleChecker()
        result = checker.check_file("/nonexistent/path/file.bsl")

        assert len(result.violations) == 1
        assert result.violations[0].rule_id == "ERR"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_strict_checker(self):
        """Test strict checker creation."""
        checker = create_strict_checker()

        # All warnings should become critical
        for rule in checker.rules:
            assert rule.severity in (IssueSeverity.CRITICAL, IssueSeverity.RECOMMENDATION)

    def test_create_minimal_checker(self):
        """Test minimal checker creation."""
        checker = create_minimal_checker()

        # Only critical rules
        for rule in checker.rules:
            assert rule.severity == IssueSeverity.CRITICAL


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_check_style(self):
        """Test check_style function."""
        result = check_style(CLEAN_CODE, "test.bsl")
        assert isinstance(result, StyleCheckResult)

    def test_check_style_with_issues(self):
        """Test check_style with issues."""
        result = check_style(SHORT_VARIABLE_CODE, "test.bsl")
        assert len(result.violations) > 0

    def test_check_file_style(self, tmp_path):
        """Test check_file_style function."""
        file_path = tmp_path / "test.bsl"
        file_path.write_text(CLEAN_CODE, encoding='utf-8')

        result = check_file_style(str(file_path))
        assert isinstance(result, StyleCheckResult)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_code(self):
        """Test checking empty code."""
        checker = StyleChecker()
        result = checker.check("", "test.bsl")

        assert result.passed is True
        assert result.score == 100.0

    def test_whitespace_only(self):
        """Test checking whitespace only."""
        checker = StyleChecker()
        result = checker.check("   \n\n   \n", "test.bsl")

        assert result.score == 100.0

    def test_comments_only(self):
        """Test checking comments only."""
        code = """
// Это комментарий
// Еще один комментарий
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        assert result.score == 100.0

    def test_multiple_issues_same_rule(self):
        """Test multiple violations of same rule."""
        code = """
Процедура Тест()
    Перем а;
    Перем б;
    Перем в;
КонецПроцедуры
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        n001_violations = [v for v in result.violations if v.rule_id == "N001"]
        assert len(n001_violations) == 3

    def test_unicode_handling(self):
        """Test Unicode in code."""
        code = """
Процедура Тест()
    // Комментарий с символами: © ® ™ € £ ¥
    Сообщение = "Привет мир! 你好世界";
КонецПроцедуры
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        # Should not crash on Unicode
        assert isinstance(result, StyleCheckResult)

    def test_mixed_encoding_patterns(self):
        """Test code with mixed Russian/English."""
        code = """
Function GetDannyeDocumenta()
    Var Result;
    Result = ПолучитьДанные();
    Return Result;
EndFunction
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        assert isinstance(result, StyleCheckResult)

    def test_case_insensitivity(self):
        """Test case insensitive matching."""
        # Lowercase keywords should match too
        code = """
процедура тест()
    перем переменная;
    переменная = 1;
конецпроцедуры
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        assert isinstance(result, StyleCheckResult)

    def test_multiline_patterns(self):
        """Test multiline pattern matching."""
        code = """
Попытка
    ОченьДолгаяОперация();
    ЕщеОднаОперация();
    ТретьяОперация();
Исключение
КонецПопытки
"""
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        empty_handler = [v for v in result.violations if v.rule_id == "E001"]
        assert len(empty_handler) >= 1

    def test_code_in_string_not_matched(self):
        """Test that code in strings is not matched as violations."""
        # SQL keywords in string literals should not trigger some rules
        code = '''
Функция ПолучитьТекстЗапроса()
    Возврат "ВЫБРАТЬ Наименование ИЗ Справочник.Товары";
КонецФункции
'''
        checker = StyleChecker()
        result = checker.check(code, "test.bsl")

        # Should not have SELECT * violation since query selects specific field
        select_all = [v for v in result.violations if v.rule_id == "P001"]
        assert len(select_all) == 0

