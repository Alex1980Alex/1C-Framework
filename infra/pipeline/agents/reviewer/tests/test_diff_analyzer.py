"""
Tests for REVIEWER DiffAnalyzer.
"""

import pytest

from agents.reviewer.diff_analyzer import (
    DiffStats,
    AnalysisResult,
    DiffAnalyzer,
    parse_diff,
    analyze_changes,
    get_diff_stats,
)
from agents.reviewer.models import (
    FileChange,
    DiffHunk,
    IssueSeverity,
    IssueCategory,
)


# Sample diffs for testing
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

NEW_FILE_DIFF = """diff --git a/src/NewModule.bsl b/src/NewModule.bsl
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/src/NewModule.bsl
@@ -0,0 +1,5 @@
+Функция НоваяФункция()
+    Возврат 42;
+КонецФункции
"""

DELETED_FILE_DIFF = """diff --git a/src/OldModule.bsl b/src/OldModule.bsl
deleted file mode 100644
index abcdefg..0000000
--- a/src/OldModule.bsl
+++ /dev/null
@@ -1,3 +0,0 @@
-Процедура Старая()
-КонецПроцедуры
"""

RENAMED_FILE_DIFF = """diff --git a/src/Old.bsl b/src/New.bsl
rename from src/Old.bsl
rename to src/New.bsl
index 1234567..abcdefg 100644
--- a/src/Old.bsl
+++ b/src/New.bsl
@@ -1,3 +1,4 @@
 Процедура Тест()
+    // Добавлен комментарий
 КонецПроцедуры
"""

SECURITY_ISSUE_DIFF = """diff --git a/src/Query.bsl b/src/Query.bsl
index 1234567..abcdefg 100644
--- a/src/Query.bsl
+++ b/src/Query.bsl
@@ -1,5 +1,8 @@
 Функция ПолучитьДанные(Параметр)
+    Запрос = Новый Запрос;
+    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары ГДЕ Наименование = '" + Параметр + "'";
+    Возврат Запрос.Выполнить();
 КонецФункции
"""

PERFORMANCE_ISSUE_DIFF = """diff --git a/src/Loop.bsl b/src/Loop.bsl
index 1234567..abcdefg 100644
--- a/src/Loop.bsl
+++ b/src/Loop.bsl
@@ -1,5 +1,10 @@
 Процедура ОбработатьДанные()
+    ВЫБРАТЬ * ИЗ Справочник.Товары
+    Для Каждого Элемент Из Коллекция Цикл
+        Запрос = Новый Запрос;
+        Запрос.Выполнить();
+    КонецЦикла;
 КонецПроцедуры
"""

STYLE_ISSUE_DIFF = """diff --git a/src/Style.bsl b/src/Style.bsl
index 1234567..abcdefg 100644
--- a/src/Style.bsl
+++ b/src/Style.bsl
@@ -1,5 +1,10 @@
 Процедура Тест()
+    Перем а;
+    Перем б, в;
+    Попытка
+    Исключение
+    КонецПопытки
 КонецПроцедуры
"""

MULTI_FILE_DIFF = """diff --git a/src/Module1.bsl b/src/Module1.bsl
index 1234567..abcdefg 100644
--- a/src/Module1.bsl
+++ b/src/Module1.bsl
@@ -1,5 +1,7 @@
 Процедура Первая()
+    // Изменение 1
 КонецПроцедуры
diff --git a/src/Module2.py b/src/Module2.py
index 1234567..abcdefg 100644
--- a/src/Module2.py
+++ b/src/Module2.py
@@ -1,3 +1,5 @@
 def test():
+    # Change
     pass
diff --git a/src/Module3.bsl b/src/Module3.bsl
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/src/Module3.bsl
@@ -0,0 +1,3 @@
+Функция Новая()
+КонецФункции
"""


class TestDiffStats:
    """Tests for DiffStats dataclass."""

    def test_creation(self):
        """Test stats creation."""
        stats = DiffStats(
            total_files=5,
            bsl_files=3,
            additions=100,
            deletions=50
        )
        assert stats.total_files == 5
        assert stats.bsl_files == 3

    def test_total_changes(self):
        """Test total changes calculation."""
        stats = DiffStats(additions=100, deletions=50)
        assert stats.total_changes == 150

    def test_to_dict(self):
        """Test serialization."""
        stats = DiffStats(
            total_files=3,
            bsl_files=2,
            additions=10,
            deletions=5
        )
        d = stats.to_dict()
        assert d["total_files"] == 3
        assert d["bsl_files"] == 2
        assert d["total_changes"] == 15


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_creation(self):
        """Test result creation."""
        result = AnalysisResult()
        assert result.files == []
        assert result.issues == []

    def test_to_dict(self):
        """Test serialization."""
        result = AnalysisResult()
        result.files.append(FileChange(
            file_path="test.bsl",
            change_type="modified"
        ))
        d = result.to_dict()
        assert d["files_count"] == 1
        assert d["issues_count"] == 0


class TestDiffAnalyzer:
    """Tests for DiffAnalyzer class."""

    def test_parse_simple_diff(self):
        """Test parsing simple diff."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(SIMPLE_DIFF)

        assert len(files) == 1
        assert files[0].file_path == "src/Module.bsl"
        assert files[0].change_type == "modified"
        assert files[0].is_bsl is True

    def test_parse_new_file_diff(self):
        """Test parsing new file diff."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(NEW_FILE_DIFF)

        assert len(files) == 1
        assert files[0].file_path == "src/NewModule.bsl"
        assert files[0].change_type == "added"

    def test_parse_deleted_file_diff(self):
        """Test parsing deleted file diff."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(DELETED_FILE_DIFF)

        assert len(files) == 1
        assert files[0].file_path == "src/OldModule.bsl"
        assert files[0].change_type == "deleted"

    def test_parse_renamed_file_diff(self):
        """Test parsing renamed file diff."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(RENAMED_FILE_DIFF)

        assert len(files) == 1
        assert files[0].file_path == "src/New.bsl"
        assert files[0].change_type == "renamed"
        assert files[0].old_path == "src/Old.bsl"

    def test_parse_multi_file_diff(self):
        """Test parsing multi-file diff."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(MULTI_FILE_DIFF)

        assert len(files) == 3
        assert files[0].file_path == "src/Module1.bsl"
        assert files[1].file_path == "src/Module2.py"
        assert files[2].file_path == "src/Module3.bsl"

    def test_parse_hunk_lines(self):
        """Test parsing added/removed lines in hunks."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(SIMPLE_DIFF)

        assert len(files[0].hunks) == 1
        hunk = files[0].hunks[0]
        assert len(hunk.added_lines) == 2
        assert "Перем Счетчик;" in hunk.added_lines[0]

    def test_analyze_simple_diff(self):
        """Test analyzing simple diff."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SIMPLE_DIFF)

        assert len(result.files) == 1
        assert result.stats.total_files == 1
        assert result.stats.bsl_files == 1

    def test_analyze_multi_file_stats(self):
        """Test stats for multi-file diff."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(MULTI_FILE_DIFF)

        assert result.stats.total_files == 3
        assert result.stats.bsl_files == 2  # Module1.bsl and Module3.bsl
        assert result.stats.files_modified >= 1
        assert result.stats.files_added >= 1

    def test_detect_security_issues(self):
        """Test detection of security issues."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SECURITY_ISSUE_DIFF)

        security_issues = [
            i for i in result.issues
            if i.category == IssueCategory.SECURITY
        ]
        assert len(security_issues) >= 1
        assert any(i.severity == IssueSeverity.CRITICAL for i in security_issues)

    def test_detect_performance_issues(self):
        """Test detection of performance issues."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(PERFORMANCE_ISSUE_DIFF)

        performance_issues = [
            i for i in result.issues
            if i.category == IssueCategory.PERFORMANCE
        ]
        # Should detect SELECT *
        assert any("*" in str(i.title) for i in performance_issues)

    def test_detect_style_issues(self):
        """Test detection of style issues."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(STYLE_ISSUE_DIFF)

        style_issues = [
            i for i in result.issues
            if i.category == IssueCategory.STYLE
        ]
        # Should detect short variable name and empty exception handler
        assert len(style_issues) >= 1

    def test_issue_id_generation(self):
        """Test that issues get proper IDs."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SECURITY_ISSUE_DIFF)

        for issue in result.issues:
            assert issue.id is not None
            assert len(issue.id) > 0
            # Should have format like CR-001, WRN-001, REC-001
            assert "-" in issue.id

    def test_reset_counters(self):
        """Test counter reset."""
        analyzer = DiffAnalyzer()

        # Analyze once
        analyzer.analyze(SECURITY_ISSUE_DIFF)

        # Reset and analyze again
        analyzer.reset_counters()
        result = analyzer.analyze(SECURITY_ISSUE_DIFF)

        # IDs should start from 001 again
        if result.issues:
            assert "001" in result.issues[0].id

    def test_get_changed_functions(self):
        """Test extraction of changed functions."""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(NEW_FILE_DIFF)

        functions = analyzer.get_changed_functions(files[0])
        assert "НоваяФункция" in functions

    def test_empty_diff(self):
        """Test handling empty diff."""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze("")

        assert len(result.files) == 0
        assert result.stats.total_files == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_parse_diff(self):
        """Test parse_diff function."""
        files = parse_diff(SIMPLE_DIFF)
        assert len(files) == 1
        assert files[0].is_bsl is True

    def test_analyze_changes(self):
        """Test analyze_changes function."""
        result = analyze_changes(SIMPLE_DIFF)
        assert isinstance(result, AnalysisResult)
        assert len(result.files) == 1

    def test_get_diff_stats(self):
        """Test get_diff_stats function."""
        stats = get_diff_stats(MULTI_FILE_DIFF)
        assert stats.total_files == 3
        assert stats.bsl_files == 2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_non_bsl_files_no_issues(self):
        """Test that non-BSL files don't generate BSL-specific issues."""
        diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
+password = "secret123"
 def test():
     pass
"""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(diff)

        # Python files shouldn't be analyzed for BSL patterns
        assert len(result.files) == 1
        assert result.files[0].is_bsl is False
        # Issues list might be empty since it's not BSL
        bsl_issues = [i for i in result.issues if i.file_path and i.file_path.endswith('.bsl')]
        assert len(bsl_issues) == 0

    def test_malformed_hunk_header(self):
        """Test handling malformed hunk header."""
        diff = """diff --git a/test.bsl b/test.bsl
index 1234567..abcdefg 100644
--- a/test.bsl
+++ b/test.bsl
@@ invalid header @@
+some content
"""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(diff)

        # Should still parse the file, just no hunks
        assert len(files) == 1
        assert len(files[0].hunks) == 0

    def test_binary_file_diff(self):
        """Test handling binary file diff."""
        diff = """diff --git a/image.png b/image.png
new file mode 100644
index 0000000..abcdefg
Binary files /dev/null and b/image.png differ
"""
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(diff)

        assert len(result.files) == 1
        assert result.files[0].is_bsl is False

    def test_diff_with_context_lines(self):
        """Test parsing diff with context lines."""
        diff = """diff --git a/test.bsl b/test.bsl
index 1234567..abcdefg 100644
--- a/test.bsl
+++ b/test.bsl
@@ -1,5 +1,6 @@
 // Context line 1
 // Context line 2
+// Added line
 // Context line 3
 // Context line 4
"""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(diff)

        hunk = files[0].hunks[0]
        assert len(hunk.added_lines) == 1
        assert len(hunk.context_lines) == 4

    def test_multiple_hunks_in_file(self):
        """Test file with multiple hunks."""
        diff = """diff --git a/test.bsl b/test.bsl
index 1234567..abcdefg 100644
--- a/test.bsl
+++ b/test.bsl
@@ -1,3 +1,4 @@
 Процедура Первая()
+    // Изменение 1
 КонецПроцедуры
@@ -10,3 +11,4 @@
 Процедура Вторая()
+    // Изменение 2
 КонецПроцедуры
"""
        analyzer = DiffAnalyzer()
        files = analyzer.parse_diff(diff)

        assert len(files) == 1
        assert len(files[0].hunks) == 2
        assert files[0].hunks[0].old_start == 1
        assert files[0].hunks[1].old_start == 10

