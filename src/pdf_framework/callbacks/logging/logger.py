"""Structured logging for the framework."""

import logging
import sys
from typing import Any

from src.pdf_framework.config import Settings


class FrameworkLogger:
    """Centralized structured logging."""

    def __init__(self, name: str = "pdf_framework", settings: Settings | None = None):
        self._logger = logging.getLogger(name)
        self._settings = settings

        if not self._logger.handlers:
            self._setup()

    def _setup(self) -> None:
        level = "INFO"
        fmt = "text"
        if self._settings:
            level = self._settings.log_level
            fmt = self._settings.log_format

        self._logger.setLevel(getattr(logging, level, logging.INFO))

        handler = logging.StreamHandler(sys.stdout)

        if fmt == "json":
            formatter = logging.Formatter(
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","message":"%(message)s"}'
            )
        else:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(self._format(msg, kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(self._format(msg, kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(self._format(msg, kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(self._format(msg, kwargs))

    @staticmethod
    def _format(msg: str, kwargs: dict[str, Any]) -> str:
        if kwargs:
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} | {extras}"
        return msg
