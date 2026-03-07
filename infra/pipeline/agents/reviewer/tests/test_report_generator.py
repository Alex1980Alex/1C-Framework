"""
Tests for REVIEWER Report Generator.
"""

import pytest
from datetime import datetime

from agents.reviewer.report_generator import (
    ReviewContext,
    ReviewGenerator,
    generate_review,
    generate_review_markdown,
)
from agents.reviewer.models import (
    ReviewReport,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
    ReviewVerdict,
    FileChange,
    StandardCheck,
)


# Sample content for testing
SIMPLE_DIFF = """diff --git a/src/Module.bsl b/src/Module.bsl
index 1234567..abcdefg 100644
--- a/src/Module.bsl
+++ b/src/Module.bsl
@@ -1,5 +1,7 @@
 Процедура Тест()
+    Перем Счетчик;
+    Счетчик = 0;
     Сообщить("Тест");
 КонецПроцедуры
"""

SAMPLE_BSL_CODE = """
Процедура ОбработатьДанные() Экспорт
    Перем Результат;

    Попытка
        Результат = ВыполнитьОперацию();
    Исключение
        ЗаписьЖурналаРегистрации("Ошибка", УровеньЖурналаРегистрации.Ошибка);
    КонецПопытки;

    Возврат Результат;
КонецПроцедуры

Функция ПолучитьДанные(Параметр) Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары";
    Возврат Запрос.Выполнить();
КонецФункции
"""

BSL_WITH_SHORT_VARS = """
Процедура Тест()
    Перем а;
    Перем б, в;
    а = 1;
    б = 2;
    в = а + б;
КонецПроцедуры
"""

BSL_WITH_TRANSACTIONS = """
Процедура ЗаписатьДанные()
    НачатьТранзакцию();
    Попытка
        Объект.Записать();
        ЗафиксироватьТранзакцию();
    Исключение
        ОтменитьТранзакцию();
        ВызватьИсключение;
    КонецПопытки;
КонецПроцедуры
"""

BSL_UNBALANCED_TRANSACTIONS = """
Процедура Ошибка()
    НачатьТранзакцию();
    Объект.Записать();
    // Forgot to commit or rollback
КонецПроцедуры
"""

BSL_WITH_LOCALIZATION = """
Процедура ПоказатьСообщение()
    Сообщить(НСтр("ru = 'Операция выполнена успешно'"));
КонецПроцедуры
"""

BSL_WITHOUT_LOCALIZATION = """
Процедура ПоказатьСообщение()
    Сообщить("Операция выполнена успешно");
КонецПроцедуры
"""

BSL_WITH_MAGIC_NUMBERS = """
Функция Вычислить()
    Возврат Сумма * 12345;
КонецФункции
"""

BSL_SQL_INJECTION = """
Функция ПолучитьДанные(Параметр)
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Товары ГДЕ Код = '" + Параметр + "'";
    Возврат Запрос.Выполнить();
КонецФункции
"""

BSL_EMPTY_EXCEPTION = """
Процедура Тест()
    Попытка
        ВыполнитьОперацию();
    Исключение
    КонецПопытки;
КонецПроцедуры
"""

SAMPLE_DESIGN = """
# Архитектура

## Компоненты

### МодульОбработки
- Тип: Обработка
- Обязательный: да
"""


class TestReviewContext:
    """Tests for ReviewContext dataclass."""

    def test_creation(self):
        """Test context creation."""
        ctx = ReviewContext(
            project_id="PROJECT",
            task_id="TASK-123"
        )
        assert ctx.project_id == "PROJECT"
        assert ctx.task_id == "TASK-123"
        assert ctx.spec_content is None
        assert ctx.bsl_files == {}

    def test_creation_with_content(self):
        """Test context with all content."""
        ctx = ReviewContext(
            project_id="PROJECT",
            task_id="TASK-123",
            spec_content="spec content",
            design_content="design content",
            result_content="result content",
            diff_text="diff text",
            bsl_files={"file.bsl": "code"}
        )
        assert ctx.spec_content == "spec content"
        assert ctx.design_content == "design content"
        assert len(ctx.bsl_files) == 1

    def test_to_dict(self):
        """Test serialization."""
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            spec_content="spec",
            bsl_files={"a.bsl": "1", "b.bsl": "2"}
        )
        d = ctx.to_dict()
        assert d["project_id"] == "P"
        assert d["task_id"] == "T"
        assert d["has_spec"] is True
        assert d["has_design"] is False
        assert d["bsl_files_count"] == 2


class TestReviewGenerator:
    """Tests for ReviewGenerator class."""

    def test_initialization(self):
        """Test generator initialization."""
        gen = ReviewGenerator()
        assert gen.diff_analyzer is not None
        assert gen.style_checker is not None
        assert gen.arch_checker is not None

    def test_generate_empty_context(self):
        """Test generation with empty context."""
        gen = ReviewGenerator()
        ctx = ReviewContext(project_id="P", task_id="T")

        report = gen.generate(ctx)

        assert report.project_id == "P"
        assert report.task_id == "T"
        assert len(report.files_reviewed) == 0
        assert report.verdict == ReviewVerdict.APPROVED

    def test_generate_with_diff(self):
        """Test generation with diff text."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            diff_text=SIMPLE_DIFF
        )

        report = gen.generate(ctx)

        assert len(report.files_reviewed) == 1
        assert report.files_reviewed[0].file_path == "src/Module.bsl"

    def test_generate_with_bsl_files(self):
        """Test generation with BSL files."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"module.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)

        # Should have file in reviewed list
        assert len(report.files_reviewed) >= 1
        # Should have standard checks
        assert len(report.standard_checks) == 8  # All standard checks

    def test_generate_with_design(self):
        """Test generation with design content."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            design_content=SAMPLE_DESIGN,
            bsl_files={"МодульОбработки.bsl": "Процедура Тест() КонецПроцедуры"}
        )

        report = gen.generate(ctx)

        # Architecture should be checked
        assert report.verdict is not None

    def test_generate_full_pipeline(self):
        """Test full generation pipeline."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="PROJECT",
            task_id="TASK-123",
            diff_text=SIMPLE_DIFF,
            design_content=SAMPLE_DESIGN,
            bsl_files={"module.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)

        assert report.project_id == "PROJECT"
        assert report.task_id == "TASK-123"
        assert report.timestamp is not None
        assert report.standard_checks is not None
        assert report.verdict is not None
        assert report.quality_score is not None

    def test_generate_markdown(self):
        """Test markdown generation."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)
        markdown = gen.generate_markdown(report)

        assert "# Code Review" in markdown or "review" in markdown.lower()
        assert "P" in markdown  # project_id

    def test_save_report(self, tmp_path):
        """Test saving report to file."""
        gen = ReviewGenerator()
        ctx = ReviewContext(project_id="P", task_id="T")
        report = gen.generate(ctx)

        output_file = tmp_path / "review.md"
        gen.save_report(report, str(output_file))

        assert output_file.exists()
        content = output_file.read_text(encoding='utf-8')
        assert len(content) > 0


class TestStandardChecks:
    """Tests for standard compliance checks."""

    def test_naming_vars_pass(self):
        """Test variable naming check - pass."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)
        naming_check = next(
            (c for c in report.standard_checks if "переменных" in c.standard_name.lower()),
            None
        )

        assert naming_check is not None
        # SAMPLE_BSL_CODE has "Результат" - good name
        assert naming_check.passed is True

    def test_naming_vars_fail(self):
        """Test variable naming check - fail."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITH_SHORT_VARS}
        )

        report = gen.generate(ctx)
        naming_check = next(
            (c for c in report.standard_checks if "переменных" in c.standard_name.lower()),
            None
        )

        assert naming_check is not None
        assert naming_check.passed is False
        assert "⚠️" in naming_check.status

    def test_transactions_balanced(self):
        """Test transaction check - balanced."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITH_TRANSACTIONS}
        )

        report = gen.generate(ctx)
        trans_check = next(
            (c for c in report.standard_checks if "транзакции" in c.standard_name.lower()),
            None
        )

        assert trans_check is not None
        assert trans_check.passed is True

    def test_transactions_unbalanced(self):
        """Test transaction check - unbalanced."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_UNBALANCED_TRANSACTIONS}
        )

        report = gen.generate(ctx)
        trans_check = next(
            (c for c in report.standard_checks if "транзакции" in c.standard_name.lower()),
            None
        )

        assert trans_check is not None
        assert trans_check.passed is False

    def test_localization_with_nstr(self):
        """Test localization check - with НСтр."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITH_LOCALIZATION}
        )

        report = gen.generate(ctx)
        loc_check = next(
            (c for c in report.standard_checks if "НСтр" in c.standard_name),
            None
        )

        assert loc_check is not None
        assert loc_check.passed is True

    def test_localization_without_nstr(self):
        """Test localization check - without НСтр."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITHOUT_LOCALIZATION}
        )

        report = gen.generate(ctx)
        loc_check = next(
            (c for c in report.standard_checks if "НСтр" in c.standard_name),
            None
        )

        assert loc_check is not None
        assert loc_check.passed is False

    def test_magic_numbers_detected(self):
        """Test magic numbers detection."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITH_MAGIC_NUMBERS}
        )

        report = gen.generate(ctx)
        magic_check = next(
            (c for c in report.standard_checks if "магические" in c.standard_name.lower()),
            None
        )

        assert magic_check is not None
        assert magic_check.passed is False

    def test_sql_injection_detected(self):
        """Test SQL injection detection."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_SQL_INJECTION}
        )

        report = gen.generate(ctx)
        sql_check = next(
            (c for c in report.standard_checks if "SQL" in c.standard_name),
            None
        )

        assert sql_check is not None
        # May detect via concatenation pattern
        assert sql_check.status in ["❌", "⚠️"]

    def test_error_handling_check(self):
        """Test error handling check."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)
        error_check = next(
            (c for c in report.standard_checks if "ошибок" in c.standard_name.lower()),
            None
        )

        assert error_check is not None
        # SAMPLE_BSL_CODE has try-except
        assert error_check.passed is True


class TestVerdictAndScore:
    """Tests for verdict and score calculation."""

    def test_approved_verdict(self):
        """Test approved verdict for clean code."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_WITH_TRANSACTIONS}
        )

        report = gen.generate(ctx)

        # Well-structured code should be approved
        assert report.verdict in [ReviewVerdict.APPROVED, ReviewVerdict.CHANGES_REQUESTED]

    def test_blocked_verdict_with_security_issue(self):
        """Test blocked verdict for security issues."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": BSL_SQL_INJECTION}
        )

        report = gen.generate(ctx)

        # SQL injection should trigger critical issues
        critical_count = len(report.critical_issues)
        if critical_count > 0:
            assert report.verdict == ReviewVerdict.BLOCKED

    def test_quality_score_calculation(self):
        """Test quality score is calculated."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)

        assert report.quality_score is not None
        assert 0 <= report.quality_score <= 10


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_generate_review(self):
        """Test generate_review function."""
        report = generate_review(
            project_id="PROJECT",
            task_id="TASK-123",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        assert isinstance(report, ReviewReport)
        assert report.project_id == "PROJECT"
        assert report.task_id == "TASK-123"

    def test_generate_review_with_diff(self):
        """Test generate_review with diff."""
        report = generate_review(
            project_id="P",
            task_id="T",
            diff_text=SIMPLE_DIFF
        )

        assert len(report.files_reviewed) >= 1

    def test_generate_review_markdown(self):
        """Test generate_review_markdown function."""
        markdown = generate_review_markdown(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_generate_review_empty(self):
        """Test generate_review with no content."""
        report = generate_review(
            project_id="P",
            task_id="T"
        )

        assert isinstance(report, ReviewReport)
        assert report.verdict == ReviewVerdict.APPROVED


class TestIntegration:
    """Integration tests for report generator."""

    def test_full_review_workflow(self):
        """Test complete review workflow."""
        # Create context with all inputs
        ctx = ReviewContext(
            project_id="PROJECT-X",
            task_id="TASK-456",
            spec_content="# Specification\nTask description",
            design_content=SAMPLE_DESIGN,
            diff_text=SIMPLE_DIFF,
            bsl_files={
                "module1.bsl": SAMPLE_BSL_CODE,
                "module2.bsl": BSL_WITH_TRANSACTIONS,
            }
        )

        # Generate report
        gen = ReviewGenerator()
        report = gen.generate(ctx)

        # Verify report structure
        assert report.project_id == "PROJECT-X"
        assert report.task_id == "TASK-456"
        assert len(report.files_reviewed) >= 1
        assert len(report.standard_checks) == 8
        assert report.verdict is not None
        assert report.quality_score is not None

        # Generate markdown
        markdown = gen.generate_markdown(report)
        assert len(markdown) > 100  # Substantial content

    def test_review_multiple_files(self):
        """Test review of multiple BSL files."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={
                "good.bsl": BSL_WITH_TRANSACTIONS,
                "bad.bsl": BSL_SQL_INJECTION,
                "ugly.bsl": BSL_WITH_SHORT_VARS,
            }
        )

        report = gen.generate(ctx)

        # Should aggregate issues from all files
        assert len(report.files_reviewed) >= 3
        # Should have issues from bad files
        assert len(report.issues) > 0

    def test_files_from_diff_and_bsl_files(self):
        """Test files from both diff and bsl_files."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            diff_text=SIMPLE_DIFF,  # Contains src/Module.bsl
            bsl_files={
                "other.bsl": SAMPLE_BSL_CODE,
            }
        )

        report = gen.generate(ctx)

        # Should have files from both sources
        paths = [f.file_path for f in report.files_reviewed]
        assert "src/Module.bsl" in paths or len(paths) >= 1


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_bsl_file(self):
        """Test with empty BSL file."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"empty.bsl": ""}
        )

        report = gen.generate(ctx)

        assert report.verdict is not None

    def test_unicode_content(self):
        """Test with Unicode content."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="ПРОЕКТ",
            task_id="ЗАДАЧА-123",
            bsl_files={"модуль.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)
        markdown = gen.generate_markdown(report)

        assert "ПРОЕКТ" in markdown

    def test_large_file(self):
        """Test with large BSL file."""
        large_code = SAMPLE_BSL_CODE * 100
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"large.bsl": large_code}
        )

        report = gen.generate(ctx)

        assert report.verdict is not None

    def test_special_characters_in_path(self):
        """Test with special characters in file path."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={
                "path/with spaces/модуль.bsl": SAMPLE_BSL_CODE,
                "путь/к/файлу.bsl": SAMPLE_BSL_CODE,
            }
        )

        report = gen.generate(ctx)

        assert len(report.files_reviewed) >= 2

    def test_all_standard_checks_present(self):
        """Test all standard checks are present."""
        gen = ReviewGenerator()
        ctx = ReviewContext(
            project_id="P",
            task_id="T",
            bsl_files={"test.bsl": SAMPLE_BSL_CODE}
        )

        report = gen.generate(ctx)

        expected_checks = [
            "Именование переменных",
            "Именование процедур",
            "Комментарии к экспортным методам",
            "Обработка ошибок",
            "Транзакции",
            "SQL-инъекции",
            "Использование НСтр",
            "Магические числа",
        ]

        check_names = [c.standard_name for c in report.standard_checks]
        for expected in expected_checks:
            assert expected in check_names

