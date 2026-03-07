"""Structured logging for pipeline observability.

Provides comprehensive logging capabilities with:
- Structured JSON output for machine parsing
- Contextual logging with request/session tracking
- Multiple log levels with filtering
- Log rotation and persistence
"""

from __future__ import annotations

import json
import sys
import logging
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, TextIO
from pathlib import Path
import threading
from contextlib import contextmanager


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50,
        }
        return levels[self]

    def __ge__(self, other: "LogLevel") -> bool:
        return self.numeric >= other.numeric

    def __gt__(self, other: "LogLevel") -> bool:
        return self.numeric > other.numeric

    def __le__(self, other: "LogLevel") -> bool:
        return self.numeric <= other.numeric

    def __lt__(self, other: "LogLevel") -> bool:
        return self.numeric < other.numeric


@dataclass
class LogContext:
    """Context for log entries with correlation IDs."""

    pipeline_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_name: Optional[str] = None
    phase: Optional[str] = None
    step: Optional[int] = None
    user_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        if self.pipeline_id:
            result["pipeline_id"] = self.pipeline_id
        if self.session_id:
            result["session_id"] = self.session_id
        if self.request_id:
            result["request_id"] = self.request_id
        if self.task_id:
            result["task_id"] = self.task_id
        if self.agent_name:
            result["agent_name"] = self.agent_name
        if self.phase:
            result["phase"] = self.phase
        if self.step is not None:
            result["step"] = self.step
        if self.user_id:
            result["user_id"] = self.user_id
        if self.extra:
            result["extra"] = self.extra
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogContext":
        """Create from dictionary."""
        return cls(
            pipeline_id=data.get("pipeline_id"),
            session_id=data.get("session_id"),
            request_id=data.get("request_id"),
            task_id=data.get("task_id"),
            agent_name=data.get("agent_name"),
            phase=data.get("phase"),
            step=data.get("step"),
            user_id=data.get("user_id"),
            extra=data.get("extra", {}),
        )

    def with_extra(self, **kwargs) -> "LogContext":
        """Create new context with additional extra fields."""
        new_extra = {**self.extra, **kwargs}
        return LogContext(
            pipeline_id=self.pipeline_id,
            session_id=self.session_id,
            request_id=self.request_id,
            task_id=self.task_id,
            agent_name=self.agent_name,
            phase=self.phase,
            step=self.step,
            user_id=self.user_id,
            extra=new_extra,
        )


@dataclass
class LogEntry:
    """A structured log entry."""

    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    context: Optional[LogContext] = None
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "logger": self.logger_name,
        }

        if self.context:
            result["context"] = self.context.to_dict()
        if self.exception:
            result["exception"] = self.exception
        if self.stack_trace:
            result["stack_trace"] = self.stack_trace
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            level=LogLevel(data["level"]),
            message=data["message"],
            logger_name=data["logger"],
            context=LogContext.from_dict(data["context"]) if data.get("context") else None,
            exception=data.get("exception"),
            stack_trace=data.get("stack_trace"),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {}),
        )


class LogHandler:
    """Base class for log handlers."""

    def __init__(self, min_level: LogLevel = LogLevel.DEBUG) -> None:
        self.min_level = min_level

    def should_log(self, level: LogLevel) -> bool:
        """Check if entry should be logged."""
        return level >= self.min_level

    def handle(self, entry: LogEntry) -> None:
        """Handle a log entry."""
        raise NotImplementedError


class ConsoleHandler(LogHandler):
    """Handler that writes to console with optional color."""

    COLORS = {
        LogLevel.DEBUG: "\033[36m",     # Cyan
        LogLevel.INFO: "\033[32m",      # Green
        LogLevel.WARNING: "\033[33m",   # Yellow
        LogLevel.ERROR: "\033[31m",     # Red
        LogLevel.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(
        self,
        min_level: LogLevel = LogLevel.DEBUG,
        stream: TextIO = sys.stderr,
        use_color: bool = True,
        json_format: bool = False,
    ):
        super().__init__(min_level)
        self.stream = stream
        self.use_color = use_color and stream.isatty()
        self.json_format = json_format

    def handle(self, entry: LogEntry) -> None:
        """Write entry to console."""
        if not self.should_log(entry.level):
            return

        if self.json_format:
            line = entry.to_json()
        else:
            # Human-readable format
            timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            level = entry.level.value.upper().ljust(8)

            if self.use_color:
                color = self.COLORS.get(entry.level, "")
                line = f"{timestamp} {color}{level}{self.RESET} [{entry.logger_name}] {entry.message}"
            else:
                line = f"{timestamp} {level} [{entry.logger_name}] {entry.message}"

            if entry.exception:
                line += f"\n  Exception: {entry.exception}"
            if entry.stack_trace:
                line += f"\n{entry.stack_trace}"

        print(line, file=self.stream)


class FileHandler(LogHandler):
    """Handler that writes JSON logs to file with rotation."""

    def __init__(
        self,
        file_path: Path,
        min_level: LogLevel = LogLevel.DEBUG,
        max_size_mb: float = 10.0,
        backup_count: int = 5,
    ):
        super().__init__(min_level)
        self.file_path = Path(file_path)
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.backup_count = backup_count
        self._lock = threading.Lock()

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def handle(self, entry: LogEntry) -> None:
        """Write entry to file."""
        if not self.should_log(entry.level):
            return

        with self._lock:
            self._maybe_rotate()

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")

    def _maybe_rotate(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.file_path.exists():
            return

        if self.file_path.stat().st_size < self.max_size_bytes:
            return

        # Rotate existing backups
        for i in range(self.backup_count - 1, 0, -1):
            src = self.file_path.with_suffix(f".{i}.log")
            dst = self.file_path.with_suffix(f".{i + 1}.log")
            if src.exists():
                src.rename(dst)

        # Rotate current file
        backup = self.file_path.with_suffix(".1.log")
        self.file_path.rename(backup)


class MemoryHandler(LogHandler):
    """Handler that keeps entries in memory for inspection."""

    def __init__(
        self,
        min_level: LogLevel = LogLevel.DEBUG,
        max_entries: int = 1000,
    ):
        super().__init__(min_level)
        self.max_entries = max_entries
        self._entries: List[LogEntry] = []
        self._lock = threading.Lock()

    def handle(self, entry: LogEntry) -> None:
        """Store entry in memory."""
        if not self.should_log(entry.level):
            return

        with self._lock:
            self._entries.append(entry)

            # Trim if needed
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]

    def get_entries(
        self,
        level: Optional[LogLevel] = None,
        logger_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[LogEntry]:
        """Get stored entries with optional filtering."""
        with self._lock:
            entries = list(self._entries)

        if level:
            entries = [e for e in entries if e.level >= level]

        if logger_name:
            entries = [e for e in entries if e.logger_name == logger_name]

        if limit:
            entries = entries[-limit:]

        return entries

    def clear(self) -> None:
        """Clear all stored entries."""
        with self._lock:
            self._entries.clear()


class PipelineLogger:
    """Structured logger for pipeline operations."""

    def __init__(
        self,
        name: str,
        context: Optional[LogContext] = None,
        handlers: Optional[List[LogHandler]] = None,
    ):
        self.name = name
        self._context = context
        self._handlers = handlers or []
        self._local = threading.local()

    @property
    def context(self) -> Optional[LogContext]:
        """Get current context (thread-local or default)."""
        return getattr(self._local, "context", None) or self._context

    def add_handler(self, handler: LogHandler) -> None:
        """Add a log handler."""
        self._handlers.append(handler)

    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a log handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    @contextmanager
    def with_context(self, context: LogContext):
        """Temporarily use a different context."""
        old_context = getattr(self._local, "context", None)
        self._local.context = context
        try:
            yield
        finally:
            self._local.context = old_context

    def child(self, name: str, context: Optional[LogContext] = None) -> "PipelineLogger":
        """Create a child logger with inherited handlers."""
        child_name = f"{self.name}.{name}"
        child_context = context or self.context
        return PipelineLogger(
            name=child_name,
            context=child_context,
            handlers=list(self._handlers),
        )

    def _log(
        self,
        level: LogLevel,
        message: str,
        exception: Optional[str] = None,
        stack_trace: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **metadata,
    ) -> LogEntry:
        """Create and dispatch a log entry."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            logger_name=self.name,
            context=self.context,
            exception=exception,
            stack_trace=stack_trace,
            duration_ms=duration_ms,
            metadata=metadata,
        )

        for handler in self._handlers:
            try:
                handler.handle(entry)
            except Exception:
                pass  # Don't let handler errors break logging

        return entry

    def debug(self, message: str, **metadata) -> LogEntry:
        """Log at DEBUG level."""
        return self._log(LogLevel.DEBUG, message, **metadata)

    def info(self, message: str, **metadata) -> LogEntry:
        """Log at INFO level."""
        return self._log(LogLevel.INFO, message, **metadata)

    def warning(self, message: str, **metadata) -> LogEntry:
        """Log at WARNING level."""
        return self._log(LogLevel.WARNING, message, **metadata)

    def error(
        self,
        message: str,
        exception: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **metadata,
    ) -> LogEntry:
        """Log at ERROR level."""
        return self._log(
            LogLevel.ERROR,
            message,
            exception=exception,
            stack_trace=stack_trace,
            **metadata,
        )

    def critical(
        self,
        message: str,
        exception: Optional[str] = None,
        stack_trace: Optional[str] = None,
        **metadata,
    ) -> LogEntry:
        """Log at CRITICAL level."""
        return self._log(
            LogLevel.CRITICAL,
            message,
            exception=exception,
            stack_trace=stack_trace,
            **metadata,
        )

    def exception(self, message: str, exc: Exception, **metadata) -> LogEntry:
        """Log an exception with stack trace."""
        import traceback

        return self.error(
            message,
            exception=str(exc),
            stack_trace=traceback.format_exc(),
            **metadata,
        )

    @contextmanager
    def timed(self, message: str, level: LogLevel = LogLevel.INFO, **metadata):
        """Context manager for timing operations."""
        start = datetime.now()
        self._log(level, f"Starting: {message}", **metadata)

        try:
            yield
            duration_ms = (datetime.now() - start).total_seconds() * 1000
            self._log(
                level,
                f"Completed: {message}",
                duration_ms=duration_ms,
                **metadata,
            )
        except Exception as e:
            duration_ms = (datetime.now() - start).total_seconds() * 1000
            import traceback
            self._log(
                LogLevel.ERROR,
                f"Failed: {message}",
                exception=str(e),
                stack_trace=traceback.format_exc(),
                duration_ms=duration_ms,
                **metadata,
            )
            raise


# Global logger registry
_loggers: Dict[str, PipelineLogger] = {}
_default_handlers: List[LogHandler] = []
_config_lock = threading.Lock()


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    console: bool = True,
    console_json: bool = False,
    file_path: Optional[Path] = None,
    memory: bool = False,
    memory_max_entries: int = 1000,
) -> None:
    """Configure global logging settings."""
    global _default_handlers

    with _config_lock:
        _default_handlers.clear()

        if console:
            _default_handlers.append(
                ConsoleHandler(
                    min_level=level,
                    json_format=console_json,
                )
            )

        if file_path:
            _default_handlers.append(
                FileHandler(
                    file_path=file_path,
                    min_level=level,
                )
            )

        if memory:
            _default_handlers.append(
                MemoryHandler(
                    min_level=level,
                    max_entries=memory_max_entries,
                )
            )


def get_logger(
    name: str,
    context: Optional[LogContext] = None,
) -> PipelineLogger:
    """Get or create a logger by name."""
    with _config_lock:
        if name not in _loggers:
            logger = PipelineLogger(
                name=name,
                context=context,
                handlers=list(_default_handlers),
            )
            _loggers[name] = logger

        return _loggers[name]


def get_memory_handler() -> Optional[MemoryHandler]:
    """Get the global memory handler if configured."""
    for handler in _default_handlers:
        if isinstance(handler, MemoryHandler):
            return handler
    return None
