"""
Tests for CLI output formatting module.

Тесты для модуля форматирования вывода CLI.

Версия: 1.0.0
Дата: 2025-12-23
"""

import json
import pytest
from io import StringIO
from unittest.mock import patch

from cli.output import (
    OutputFormatter,
    OutputFormat,
    Color,
    Symbol,
    TableColumn,
)


class TestColor:
    """Тесты для enum Color."""

    def test_reset_exists(self):
        """Тест наличия RESET кода."""
        assert Color.RESET is not None
        assert "\033[" in Color.RESET.value

    def test_color_codes(self):
        """Тест цветовых кодов."""
        assert Color.RED is not None
        assert Color.GREEN is not None
        assert Color.YELLOW is not None
        assert Color.BLUE is not None
        assert Color.CYAN is not None
        assert Color.MAGENTA is not None
        assert Color.WHITE is not None

    def test_style_codes(self):
        """Тест стилевых кодов."""
        assert Color.BOLD is not None
        assert Color.DIM is not None

    def test_color_format(self):
        """Тест формата цветовых кодов."""
        # Все коды должны содержать ESC sequence
        for color in Color:
            assert isinstance(color.value, str)
            assert "\033[" in color.value


class TestSymbol:
    """Тесты для класса Symbol."""

    def test_status_symbols(self):
        """Тест символов статуса."""
        assert Symbol.SUCCESS is not None
        assert Symbol.ERROR is not None
        assert Symbol.WARNING is not None
        assert Symbol.INFO is not None

    def test_progress_symbols(self):
        """Тест символов прогресса."""
        assert Symbol.RUNNING is not None
        assert Symbol.PENDING is not None

    def test_arrow_symbols(self):
        """Тест символов стрелок."""
        assert Symbol.ARROW_RIGHT is not None
        assert Symbol.ARROW_DOWN is not None

    def test_for_status_success(self):
        """Тест Symbol.for_status для success."""
        result = Symbol.for_status("success")
        assert result == Symbol.SUCCESS

    def test_for_status_error(self):
        """Тест Symbol.for_status для error."""
        result = Symbol.for_status("error")
        assert result == Symbol.ERROR

    def test_for_status_unknown(self):
        """Тест Symbol.for_status для неизвестного."""
        result = Symbol.for_status("unknown_status")
        assert result == Symbol.BULLET

    def test_for_agent(self):
        """Тест Symbol.for_agent."""
        result = Symbol.for_agent("initializer")
        assert result == Symbol.AGENT_INIT


class TestOutputFormat:
    """Тесты для OutputFormat enum."""

    def test_output_formats(self):
        """Тест значений формата вывода."""
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.TABLE.value == "table"


class TestTableColumn:
    """Тесты для TableColumn."""

    def test_create_column(self):
        """Тест создания колонки."""
        col = TableColumn(header="Name", key="name")
        assert col.header == "Name"
        assert col.key == "name"
        assert col.width is None
        assert col.align == "left"

    def test_column_with_width(self):
        """Тест колонки с шириной."""
        col = TableColumn(header="ID", key="id", width=10, align="right")
        assert col.width == 10
        assert col.align == "right"


class TestOutputFormatter:
    """Тесты для OutputFormatter."""

    def test_create_formatter_default(self):
        """Тест создания форматтера по умолчанию."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output)

        assert formatter is not None
        assert formatter.format == OutputFormat.TEXT

    def test_create_formatter_json(self):
        """Тест создания форматтера JSON."""
        output = StringIO()
        formatter = OutputFormatter(format=OutputFormat.JSON, output_stream=output)

        assert formatter.format == OutputFormat.JSON

    def test_create_formatter_no_colors(self):
        """Тест создания форматтера без цветов."""
        output = StringIO()
        formatter = OutputFormatter(color_enabled=False, output_stream=output)

        assert formatter.color_enabled is False

    def test_create_formatter_no_unicode(self):
        """Тест создания форматтера без Unicode."""
        output = StringIO()
        formatter = OutputFormatter(unicode_enabled=False, output_stream=output)

        assert formatter.unicode_enabled is False

    def test_print_message(self):
        """Тест базового вывода."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output)

        formatter.print("Hello World")

        assert "Hello World" in output.getvalue()

    def test_success_message(self):
        """Тест сообщения об успехе."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.success("Operation completed")

        result = output.getvalue()
        assert "Operation completed" in result

    def test_error_message(self):
        """Тест сообщения об ошибке."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.error("Something failed")

        result = output.getvalue()
        assert "Something failed" in result

    def test_warning_message(self):
        """Тест предупреждения."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.warning("Be careful")

        result = output.getvalue()
        assert "Be careful" in result

    def test_info_message(self):
        """Тест информационного сообщения."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.info("Some info")

        result = output.getvalue()
        assert "Some info" in result

    def test_header(self):
        """Тест заголовка."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.header("My Header")

        result = output.getvalue()
        assert "My Header" in result

    def test_section(self):
        """Тест секции."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.section("My Section")

        result = output.getvalue()
        assert "My Section" in result

    def test_table_output(self):
        """Тест вывода таблицы."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        columns = [
            TableColumn("Name", "name"),
            TableColumn("Value", "value"),
        ]
        data = [
            {"name": "foo", "value": "123"},
            {"name": "bar", "value": "456"},
        ]

        formatter.table(data, columns)

        result = output.getvalue()
        assert "Name" in result
        assert "Value" in result
        assert "foo" in result
        assert "123" in result

    def test_table_empty(self):
        """Тест пустой таблицы."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        columns = [
            TableColumn("A", "a"),
            TableColumn("B", "b"),
        ]

        formatter.table([], columns)

        result = output.getvalue()
        assert "нет данных" in result

    def test_list_output(self):
        """Тест вывода списка."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        items = ["Item 1", "Item 2", "Item 3"]
        formatter.list(items)

        result = output.getvalue()
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result

    def test_list_numbered(self):
        """Тест нумерованного списка."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        items = ["First", "Second"]
        formatter.list(items, numbered=True)

        result = output.getvalue()
        assert "1." in result
        assert "First" in result

    def test_list_empty(self):
        """Тест пустого списка."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.list([])

        result = output.getvalue()
        assert "пусто" in result

    def test_json_output(self):
        """Тест JSON вывода."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output)

        data = {"key": "value", "number": 42}
        formatter.json_output(data)

        result = output.getvalue()
        # Должен быть валидным JSON
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_status_output(self):
        """Тест вывода статусов."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        items = [
            {"name": "Task 1", "status": "success"},
            {"name": "Task 2", "status": "error"},
        ]

        formatter.status(items)

        result = output.getvalue()
        assert "Task 1" in result
        assert "Task 2" in result

    def test_tree_output(self):
        """Тест древовидного вывода."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        data = {
            "root": {
                "child1": "value1",
                "child2": "value2"
            }
        }

        formatter.tree(data)

        result = output.getvalue()
        assert "root" in result

    def test_progress_bar(self):
        """Тест прогресс-бара."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        formatter.progress(50, 100, "Processing")

        result = output.getvalue()
        assert "50" in result  # percentage

    def test_colorize_disabled(self):
        """Тест _colorize с выключенными цветами."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        result = formatter._colorize("test", Color.RED)

        assert result == "test"
        assert Color.RED.value not in result

    def test_symbol_fallback(self):
        """Тест _symbol fallback."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, unicode_enabled=False)

        result = formatter._symbol(Symbol.SUCCESS, "[OK]")

        assert result == "[OK]"

    def test_symbol_unicode(self):
        """Тест _symbol с unicode."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, unicode_enabled=True)

        result = formatter._symbol(Symbol.SUCCESS, "[OK]")

        assert result == Symbol.SUCCESS


class TestOutputFormatterMarkdown:
    """Тесты markdown форматирования."""

    def test_header_markdown(self):
        """Тест заголовка в markdown."""
        output = StringIO()
        formatter = OutputFormatter(format=OutputFormat.MARKDOWN, output_stream=output)

        formatter.header("My Header", level=2)

        result = output.getvalue()
        assert "## My Header" in result

    def test_table_markdown(self):
        """Тест таблицы в markdown."""
        output = StringIO()
        formatter = OutputFormatter(format=OutputFormat.MARKDOWN, output_stream=output)

        columns = [
            TableColumn("Name", "name"),
            TableColumn("Value", "value"),
        ]
        data = [
            {"name": "foo", "value": "123"},
        ]

        formatter.table(data, columns)

        result = output.getvalue()
        assert "|" in result
        assert "Name" in result


class TestOutputFormatterJSON:
    """Тесты JSON форматирования."""

    def test_table_json(self):
        """Тест таблицы в JSON формате."""
        output = StringIO()
        formatter = OutputFormatter(format=OutputFormat.JSON, output_stream=output)

        columns = [
            TableColumn("Name", "name"),
        ]
        data = [
            {"name": "test"},
        ]

        formatter.table(data, columns)

        result = output.getvalue()
        parsed = json.loads(result)
        assert parsed[0]["name"] == "test"


class TestPipelineSpecificOutput:
    """Тесты специфичных для pipeline выводов."""

    def test_pipeline_status(self):
        """Тест вывода статуса pipeline."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        phases = [
            {"name": "Init", "agent": "initializer", "status": "completed"},
            {"name": "Spec", "agent": "pm-spec", "status": "running"},
        ]

        formatter.pipeline_status(phases, current_phase="Spec")

        result = output.getvalue()
        assert "Init" in result
        assert "Spec" in result

    def test_artifact_summary(self):
        """Тест сводки артефактов."""
        output = StringIO()
        formatter = OutputFormatter(output_stream=output, color_enabled=False)

        artifacts = [
            {"name": "spec.md", "type": "spec", "size": "10 KB", "status": "ok"},
        ]

        formatter.artifact_summary(artifacts)

        result = output.getvalue()
        assert "spec.md" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
