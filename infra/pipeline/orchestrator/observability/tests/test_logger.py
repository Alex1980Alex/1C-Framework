"""Tests for structured logging module."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from .logger import (
    LogLevel,
    LogContext,
    LogEntry,
    PipelineLogger,
    ConsoleHandler,
    FileHandler,
    MemoryHandler,
    configure_logging,
    get_logger,
    get_memory_handler,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_level_values(self):
        """Test log level values."""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"

    def test_level_comparison(self):
        """Test log level comparison."""
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL

    def test_level_numeric(self):
        """Test numeric level values."""
        assert LogLevel.DEBUG.numeric == 10
        assert LogLevel.INFO.numeric == 20
        assert LogLevel.WARNING.numeric == 30
        assert LogLevel.ERROR.numeric == 40
        assert LogLevel.CRITICAL.numeric == 50


class TestLogContext:
    """Tests for LogContext dataclass."""

    def test_create_empty_context(self):
        """Test creating empty context."""
        ctx = LogContext()
        assert ctx.pipeline_id is None
        assert ctx.session_id is None
        assert ctx.extra == {}

    def test_create_context_with_values(self):
        """Test creating context with values."""
        ctx = LogContext(
            pipeline_id="pipe-123",
            session_id="sess-456",
            agent_name="test-agent",
            phase="execution",
            step=5,
        )
        assert ctx.pipeline_id == "pipe-123"
        assert ctx.session_id == "sess-456"
        assert ctx.agent_name == "test-agent"
        assert ctx.phase == "execution"
        assert ctx.step == 5

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = LogContext(
            pipeline_id="pipe-123",
            agent_name="test",
        )
        result = ctx.to_dict()
        assert result["pipeline_id"] == "pipe-123"
        assert result["agent_name"] == "test"
        assert "session_id" not in result  # None values excluded

    def test_context_from_dict(self):
        """Test context deserialization."""
        data = {
            "pipeline_id": "pipe-123",
            "agent_name": "test",
            "step": 3,
        }
        ctx = LogContext.from_dict(data)
        assert ctx.pipeline_id == "pipe-123"
        assert ctx.agent_name == "test"
        assert ctx.step == 3

    def test_context_with_extra(self):
        """Test adding extra fields to context."""
        ctx = LogContext(pipeline_id="pipe-123")
        new_ctx = ctx.with_extra(custom_field="value", count=42)

        assert new_ctx.pipeline_id == "pipe-123"
        assert new_ctx.extra["custom_field"] == "value"
        assert new_ctx.extra["count"] == 42
        assert ctx.extra == {}  # Original unchanged


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_create_entry(self):
        """Test creating log entry."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test message",
            logger_name="test",
        )
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.logger_name == "test"

    def test_entry_to_dict(self):
        """Test entry serialization."""
        entry = LogEntry(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            level=LogLevel.WARNING,
            message="Warning message",
            logger_name="test.logger",
            duration_ms=123.45,
        )
        result = entry.to_dict()
        assert result["level"] == "warning"
        assert result["message"] == "Warning message"
        assert result["logger"] == "test.logger"
        assert result["duration_ms"] == 123.45

    def test_entry_to_json(self):
        """Test JSON serialization."""
        entry = LogEntry(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            level=LogLevel.INFO,
            message="Test",
            logger_name="test",
        )
        json_str = entry.to_json()
        parsed = json.loads(json_str)
        assert parsed["level"] == "info"
        assert parsed["message"] == "Test"

    def test_entry_from_dict(self):
        """Test entry deserialization."""
        data = {
            "timestamp": "2024-01-01T12:00:00",
            "level": "error",
            "message": "Error occurred",
            "logger": "test",
        }
        entry = LogEntry.from_dict(data)
        assert entry.level == LogLevel.ERROR
        assert entry.message == "Error occurred"


class TestMemoryHandler:
    """Tests for MemoryHandler."""

    def test_handler_stores_entries(self):
        """Test that handler stores entries."""
        handler = MemoryHandler(max_entries=100)
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test",
            logger_name="test",
        )
        handler.handle(entry)

        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].message == "Test"

    def test_handler_respects_min_level(self):
        """Test level filtering."""
        handler = MemoryHandler(min_level=LogLevel.WARNING)

        debug_entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.DEBUG,
            message="Debug",
            logger_name="test",
        )
        warning_entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.WARNING,
            message="Warning",
            logger_name="test",
        )

        handler.handle(debug_entry)
        handler.handle(warning_entry)

        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].message == "Warning"

    def test_handler_max_entries(self):
        """Test max entries limit."""
        handler = MemoryHandler(max_entries=3)

        for i in range(5):
            entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message=f"Message {i}",
                logger_name="test",
            )
            handler.handle(entry)

        entries = handler.get_entries()
        assert len(entries) == 3
        assert entries[0].message == "Message 2"
        assert entries[2].message == "Message 4"

    def test_handler_clear(self):
        """Test clearing entries."""
        handler = MemoryHandler()
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test",
            logger_name="test",
        )
        handler.handle(entry)

        handler.clear()
        assert len(handler.get_entries()) == 0

    def test_filter_by_level(self):
        """Test filtering by level."""
        handler = MemoryHandler()

        for level in [LogLevel.DEBUG, LogLevel.INFO, LogLevel.ERROR]:
            entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                message=f"{level.value} message",
                logger_name="test",
            )
            handler.handle(entry)

        errors = handler.get_entries(level=LogLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].level == LogLevel.ERROR


class TestFileHandler:
    """Tests for FileHandler."""

    def test_handler_writes_to_file(self):
        """Test file writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            handler = FileHandler(log_path)

            entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="Test message",
                logger_name="test",
            )
            handler.handle(entry)

            assert log_path.exists()
            content = log_path.read_text()
            assert "Test message" in content

    def test_handler_writes_json(self):
        """Test JSON format in file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            handler = FileHandler(log_path)

            entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="JSON test",
                logger_name="test",
            )
            handler.handle(entry)

            content = log_path.read_text().strip()
            parsed = json.loads(content)
            assert parsed["message"] == "JSON test"


class TestPipelineLogger:
    """Tests for PipelineLogger."""

    def test_logger_creation(self):
        """Test logger creation."""
        logger = PipelineLogger("test")
        assert logger.name == "test"

    def test_logger_with_handler(self):
        """Test logging with handler."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        logger.info("Test info message")

        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0].message == "Test info message"
        assert entries[0].level == LogLevel.INFO

    def test_all_log_levels(self):
        """Test all log levels."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        logger.debug("Debug")
        logger.info("Info")
        logger.warning("Warning")
        logger.error("Error")
        logger.critical("Critical")

        entries = handler.get_entries()
        assert len(entries) == 5
        assert entries[0].level == LogLevel.DEBUG
        assert entries[4].level == LogLevel.CRITICAL

    def test_logger_with_context(self):
        """Test logging with context."""
        handler = MemoryHandler()
        ctx = LogContext(pipeline_id="pipe-123")
        logger = PipelineLogger("test", context=ctx, handlers=[handler])

        logger.info("Contextual message")

        entries = handler.get_entries()
        assert entries[0].context.pipeline_id == "pipe-123"

    def test_logger_with_context_manager(self):
        """Test context manager for temporary context."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        with logger.with_context(LogContext(agent_name="temp-agent")):
            logger.info("Inside context")

        logger.info("Outside context")

        entries = handler.get_entries()
        assert entries[0].context.agent_name == "temp-agent"
        assert entries[1].context is None

    def test_logger_child(self):
        """Test child logger creation."""
        handler = MemoryHandler()
        parent = PipelineLogger("parent", handlers=[handler])
        child = parent.child("child")

        child.info("Child message")

        entries = handler.get_entries()
        assert entries[0].logger_name == "parent.child"

    def test_logger_exception(self):
        """Test exception logging."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.exception("Caught exception", e)

        entries = handler.get_entries()
        assert entries[0].level == LogLevel.ERROR
        assert entries[0].exception == "Test error"
        assert "ValueError" in entries[0].stack_trace

    def test_logger_timed(self):
        """Test timed context manager."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        with logger.timed("Operation"):
            pass  # Simulate work

        entries = handler.get_entries()
        assert len(entries) == 2  # Start and complete
        assert "Starting" in entries[0].message
        assert "Completed" in entries[1].message
        assert entries[1].duration_ms is not None

    def test_logger_metadata(self):
        """Test logging with metadata."""
        handler = MemoryHandler()
        logger = PipelineLogger("test", handlers=[handler])

        logger.info("With metadata", user_id="123", action="test")

        entries = handler.get_entries()
        assert entries[0].metadata["user_id"] == "123"
        assert entries[0].metadata["action"] == "test"


class TestGlobalLogging:
    """Tests for global logging functions."""

    def test_configure_and_get_logger(self):
        """Test global configuration."""
        configure_logging(level=LogLevel.INFO, console=False, memory=True)

        logger = get_logger("test.global")
        logger.info("Global test")

        handler = get_memory_handler()
        assert handler is not None
        entries = handler.get_entries(logger_name="test.global")
        assert len(entries) >= 1
