"""
Output Formatter - форматирование вывода CLI.

Поддержка различных форматов вывода: text, json, markdown, table.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json
import sys


class OutputFormat(Enum):
    """Формат вывода."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    TABLE = "table"


class Color(Enum):
    """ANSI цвета для терминала."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Цвета текста
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Яркие цвета
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"

    # Фон
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class Symbol:
    """Unicode символы для вывода."""

    # Статусы
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    PENDING = "⏳"
    RUNNING = "🔄"
    SKIPPED = "⏭️"

    # Прогресс
    ARROW_RIGHT = "→"
    ARROW_DOWN = "↓"
    BULLET = "•"
    CHECK = "✓"
    CROSS = "✗"

    # Структура
    TREE_BRANCH = "├──"
    TREE_LAST = "└──"
    TREE_VERTICAL = "│"

    # Агенты
    AGENT_INIT = "🔍"
    AGENT_SPEC = "📋"
    AGENT_ARCH = "🏗️"
    AGENT_IMPL = "💻"
    AGENT_TEST = "🧪"
    AGENT_REVIEW = "📝"

    @classmethod
    def for_status(cls, status: str) -> str:
        """Символ для статуса."""
        mapping = {
            "success": cls.SUCCESS,
            "completed": cls.SUCCESS,
            "error": cls.ERROR,
            "failed": cls.ERROR,
            "warning": cls.WARNING,
            "info": cls.INFO,
            "pending": cls.PENDING,
            "running": cls.RUNNING,
            "in_progress": cls.RUNNING,
            "skipped": cls.SKIPPED,
        }
        return mapping.get(status.lower(), cls.BULLET)

    @classmethod
    def for_agent(cls, agent: str) -> str:
        """Символ для агента."""
        mapping = {
            "initializer": cls.AGENT_INIT,
            "pm-spec": cls.AGENT_SPEC,
            "architect": cls.AGENT_ARCH,
            "implementer": cls.AGENT_IMPL,
            "qa": cls.AGENT_TEST,
            "reviewer": cls.AGENT_REVIEW,
        }
        return mapping.get(agent.lower(), cls.BULLET)


@dataclass
class TableColumn:
    """Колонка таблицы."""

    header: str
    key: str
    width: Optional[int] = None
    align: str = "left"  # left, right, center


class OutputFormatter:
    """Форматтер вывода CLI."""

    def __init__(
        self,
        format: OutputFormat = OutputFormat.TEXT,
        color_enabled: bool = True,
        unicode_enabled: bool = True,
        output_stream=None
    ):
        self.format = format
        self.output = output_stream or sys.stdout  # ВАЖНО: до _supports_color()
        self.color_enabled = color_enabled and self._supports_color()
        self.unicode_enabled = unicode_enabled

    def _supports_color(self) -> bool:
        """Проверка поддержки цветов терминалом."""
        if not hasattr(self.output, "isatty"):
            return False
        if not self.output.isatty():
            return False
        # Windows проверка
        if sys.platform == "win32":
            return True  # Windows 10+ поддерживает ANSI
        return True

    def _colorize(self, text: str, *colors: Color) -> str:
        """Применение цвета к тексту."""
        if not self.color_enabled:
            return text
        color_codes = "".join(c.value for c in colors)
        return f"{color_codes}{text}{Color.RESET.value}"

    def _symbol(self, symbol: str, fallback: str = "*") -> str:
        """Получение символа или fallback."""
        if self.unicode_enabled:
            return symbol
        return fallback

    # === Основные методы вывода ===

    def print(self, message: str = "", end: str = "\n") -> None:
        """Базовый вывод."""
        print(message, end=end, file=self.output)

    def success(self, message: str) -> None:
        """Сообщение об успехе."""
        symbol = self._symbol(Symbol.SUCCESS, "[OK]")
        colored = self._colorize(f"{symbol} {message}", Color.GREEN)
        self.print(colored)

    def error(self, message: str) -> None:
        """Сообщение об ошибке."""
        symbol = self._symbol(Symbol.ERROR, "[ERROR]")
        colored = self._colorize(f"{symbol} {message}", Color.RED)
        self.print(colored)

    def warning(self, message: str) -> None:
        """Предупреждение."""
        symbol = self._symbol(Symbol.WARNING, "[WARN]")
        colored = self._colorize(f"{symbol} {message}", Color.YELLOW)
        self.print(colored)

    def info(self, message: str) -> None:
        """Информационное сообщение."""
        symbol = self._symbol(Symbol.INFO, "[INFO]")
        colored = self._colorize(f"{symbol} {message}", Color.CYAN)
        self.print(colored)

    def header(self, title: str, level: int = 1) -> None:
        """Заголовок."""
        if self.format == OutputFormat.MARKDOWN:
            prefix = "#" * level
            self.print(f"{prefix} {title}")
        elif self.format == OutputFormat.JSON:
            pass  # JSON не имеет заголовков
        else:
            colored = self._colorize(title, Color.BOLD, Color.BRIGHT_CYAN)
            if level == 1:
                line = "=" * len(title)
                self.print(colored)
                self.print(self._colorize(line, Color.CYAN))
            else:
                self.print(colored)

    def section(self, title: str) -> None:
        """Секция."""
        self.print()
        self.header(title, level=2)
        self.print()

    # === Форматированный вывод ===

    def table(
        self,
        data: List[Dict[str, Any]],
        columns: List[TableColumn],
        title: Optional[str] = None
    ) -> None:
        """Вывод таблицы."""
        if self.format == OutputFormat.JSON:
            self.print(json.dumps(data, indent=2, ensure_ascii=False))
            return

        if self.format == OutputFormat.MARKDOWN:
            self._table_markdown(data, columns, title)
            return

        self._table_text(data, columns, title)

    def _table_text(
        self,
        data: List[Dict[str, Any]],
        columns: List[TableColumn],
        title: Optional[str] = None
    ) -> None:
        """Текстовая таблица."""
        if title:
            self.header(title, level=2)

        if not data:
            self.print("  (нет данных)")
            return

        # Вычисление ширины колонок
        widths = {}
        for col in columns:
            if col.width:
                widths[col.key] = col.width
            else:
                header_len = len(col.header)
                max_data_len = max(
                    len(str(row.get(col.key, "")))
                    for row in data
                ) if data else 0
                widths[col.key] = max(header_len, max_data_len) + 2

        # Заголовок
        header_row = "│"
        for col in columns:
            w = widths[col.key]
            header_row += f" {col.header:<{w}} │"

        separator = "├" + "┼".join("─" * (widths[col.key] + 2) for col in columns) + "┤"
        top_border = "┌" + "┬".join("─" * (widths[col.key] + 2) for col in columns) + "┐"
        bottom_border = "└" + "┴".join("─" * (widths[col.key] + 2) for col in columns) + "┘"

        self.print(top_border)
        self.print(self._colorize(header_row, Color.BOLD))
        self.print(separator)

        # Данные
        for row in data:
            data_row = "│"
            for col in columns:
                w = widths[col.key]
                value = str(row.get(col.key, ""))
                if col.align == "right":
                    data_row += f" {value:>{w}} │"
                elif col.align == "center":
                    data_row += f" {value:^{w}} │"
                else:
                    data_row += f" {value:<{w}} │"
            self.print(data_row)

        self.print(bottom_border)

    def _table_markdown(
        self,
        data: List[Dict[str, Any]],
        columns: List[TableColumn],
        title: Optional[str] = None
    ) -> None:
        """Markdown таблица."""
        if title:
            self.print(f"## {title}")
            self.print()

        if not data:
            self.print("_(нет данных)_")
            return

        # Заголовок
        header = "| " + " | ".join(col.header for col in columns) + " |"
        separator = "| " + " | ".join(
            ":---" if col.align == "left" else
            "---:" if col.align == "right" else
            ":---:"
            for col in columns
        ) + " |"

        self.print(header)
        self.print(separator)

        # Данные
        for row in data:
            values = [str(row.get(col.key, "")) for col in columns]
            self.print("| " + " | ".join(values) + " |")

    def list(
        self,
        items: List[str],
        title: Optional[str] = None,
        numbered: bool = False
    ) -> None:
        """Вывод списка."""
        if title:
            self.header(title, level=2)

        if not items:
            self.print("  (пусто)")
            return

        for i, item in enumerate(items, 1):
            if numbered:
                prefix = f"{i}."
            else:
                prefix = self._symbol(Symbol.BULLET, "-")
            self.print(f"  {prefix} {item}")

    def tree(
        self,
        data: Dict[str, Any],
        title: Optional[str] = None,
        indent: int = 0
    ) -> None:
        """Вывод дерева."""
        if title and indent == 0:
            self.header(title, level=2)

        prefix = "  " * indent

        if isinstance(data, dict):
            items = list(data.items())
            for i, (key, value) in enumerate(items):
                is_last = i == len(items) - 1
                branch = self._symbol(
                    Symbol.TREE_LAST if is_last else Symbol.TREE_BRANCH,
                    "+-" if is_last else "|-"
                )
                self.print(f"{prefix}{branch} {self._colorize(key, Color.BOLD)}")

                if isinstance(value, (dict, list)):
                    self.tree(value, indent=indent + 1)
                else:
                    next_prefix = "  " * (indent + 1)
                    self.print(f"{next_prefix}  {value}")
        elif isinstance(data, list):
            for item in data:
                bullet = self._symbol(Symbol.BULLET, "-")
                self.print(f"{prefix}  {bullet} {item}")

    def progress(
        self,
        current: int,
        total: int,
        message: str = "",
        width: int = 40
    ) -> None:
        """Прогресс-бар."""
        if self.format == OutputFormat.JSON:
            self.print(json.dumps({
                "current": current,
                "total": total,
                "percentage": (current / total * 100) if total > 0 else 0,
                "message": message
            }))
            return

        percentage = (current / total * 100) if total > 0 else 0
        filled = int(width * current / total) if total > 0 else 0
        empty = width - filled

        bar = self._colorize("█" * filled, Color.GREEN) + "░" * empty
        self.print(f"\r[{bar}] {percentage:5.1f}% {message}", end="")

        if current >= total:
            self.print()  # Новая строка в конце

    def status(
        self,
        items: List[Dict[str, Any]],
        title: Optional[str] = None
    ) -> None:
        """Вывод статусов."""
        if title:
            self.header(title, level=2)

        for item in items:
            name = item.get("name", "")
            status = item.get("status", "unknown")
            details = item.get("details", "")

            symbol = self._symbol(Symbol.for_status(status), f"[{status.upper()}]")

            color = {
                "success": Color.GREEN,
                "completed": Color.GREEN,
                "error": Color.RED,
                "failed": Color.RED,
                "warning": Color.YELLOW,
                "pending": Color.DIM,
                "running": Color.CYAN,
            }.get(status.lower(), Color.WHITE)

            line = f"  {symbol} {self._colorize(name, Color.BOLD)}"
            if details:
                line += f" - {self._colorize(details, Color.DIM)}"

            self.print(line)

    # === JSON вывод ===

    def json_output(self, data: Any) -> None:
        """Прямой JSON вывод."""
        self.print(json.dumps(data, indent=2, ensure_ascii=False))

    # === Специальные форматы для pipeline ===

    def pipeline_status(
        self,
        phases: List[Dict[str, Any]],
        current_phase: Optional[str] = None
    ) -> None:
        """Статус pipeline."""
        self.header("Pipeline Status", level=1)
        self.print()

        for phase in phases:
            name = phase.get("name", "")
            status = phase.get("status", "pending")
            agent = phase.get("agent", "")
            duration = phase.get("duration", "")

            is_current = name == current_phase
            symbol = self._symbol(Symbol.for_agent(agent), "")

            if is_current:
                prefix = self._colorize("►", Color.BRIGHT_CYAN)
            else:
                prefix = " "

            status_symbol = self._symbol(Symbol.for_status(status))

            line = f"  {prefix} {symbol} {self._colorize(name, Color.BOLD)}"
            line += f" [{status_symbol} {status}]"

            if duration:
                line += f" ({duration})"

            self.print(line)

    def artifact_summary(self, artifacts: List[Dict[str, Any]]) -> None:
        """Сводка артефактов."""
        self.section("Артефакты")

        columns = [
            TableColumn("Имя", "name"),
            TableColumn("Тип", "type"),
            TableColumn("Размер", "size", align="right"),
            TableColumn("Статус", "status"),
        ]

        self.table(artifacts, columns)
