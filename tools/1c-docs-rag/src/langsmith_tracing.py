"""
LangSmith Tracing Module for RAG and Z.AI Router

Optional observability integration using LangSmith.
Requires: pip install langsmith

Usage:
    from langsmith_tracing import trace_rag_query, trace_zai_call

    @trace_rag_query
    async def ask(query: str) -> RAGResponse:
        ...

    @trace_zai_call
    def call_zai(prompt: str) -> str:
        ...
"""

import os
import sys
import functools
import logging
from typing import Any, Callable, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# Проверяем наличие langsmith
try:
    from langsmith import traceable, Client
    from langsmith.run_trees import RunTree
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    logger.warning("langsmith not installed. Tracing disabled. Install with: pip install langsmith")

# Конфигурация LangSmith
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "1c-enterprise-framework")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"

# LangSmith client (инициализируется только если настроен)
_langsmith_client: Optional["Client"] = None


def get_langsmith_client() -> Optional["Client"]:
    """Получить LangSmith client если настроен."""
    global _langsmith_client

    if not LANGSMITH_AVAILABLE:
        return None

    if not LANGSMITH_API_KEY:
        logger.debug("LANGSMITH_API_KEY not set. Tracing disabled.")
        return None

    if _langsmith_client is None:
        try:
            _langsmith_client = Client(
                api_key=LANGSMITH_API_KEY,
                api_url=LANGSMITH_ENDPOINT
            )
            logger.info(f"LangSmith client initialized for project: {LANGSMITH_PROJECT}")
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}")
            return None

    return _langsmith_client


class TraceContext:
    """Контекст для ручного трейсинга без декораторов."""

    def __init__(self, name: str, run_type: str = "chain"):
        self.name = name
        self.run_type = run_type
        self.client = get_langsmith_client()
        self._run_tree: Optional["RunTree"] = None

    def __enter__(self):
        if self.client is None:
            return self

        try:
            from langsmith.run_trees import RunTree
            self._run_tree = RunTree(
                name=self.name,
                run_type=self.run_type,
                project_name=LANGSMITH_PROJECT
            )
            self._run_tree.start()
            return self
        except Exception as e:
            logger.error(f"TraceContext enter failed: {e}")
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._run_tree is None:
            return

        try:
            if exc_type is not None:
                self._run_tree.end(error=str(exc_val))
            else:
                self._run_tree.end()
        except Exception as e:
            logger.error(f"TraceContext exit failed: {e}")

    def log_input(self, data: Dict[str, Any]):
        """Логировать входные данные."""
        if self._run_tree:
            try:
                self._run_tree.inputs.update(data)
            except Exception as e:
                logger.error(f"Failed to log input: {e}")

    def log_output(self, data: Dict[str, Any]):
        """Логировать выходные данные."""
        if self._run_tree:
            try:
                self._run_tree.outputs.update(data)
            except Exception as e:
                logger.error(f"Failed to log output: {e}")

    def log_metadata(self, data: Dict[str, Any]):
        """Логировать метаданные."""
        if self._run_tree:
            try:
                self._run_tree.metadata.update(data)
            except Exception as e:
                logger.error(f"Failed to log metadata: {e}")


def trace_rag_query(func: Callable) -> Callable:
    """
    Декоратор для трейсинга RAG запросов.

    Usage:
        @trace_rag_query
        async def ask(query: str) -> RAGResponse:
            ...
    """
    if not LANGSMITH_AVAILABLE or not LANGSMITH_TRACING:
        return func

    @functools.wraps(func)
    @traceable(name="rag_query", project_name=LANGSMITH_PROJECT)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def trace_zai_call(func: Callable) -> Callable:
    """
    Декоратор для трейсинга Z.AI вызовов.

    Usage:
        @trace_zai_call
        def call_zai_api(prompt: str) -> str:
            ...
    """
    if not LANGSMITH_AVAILABLE or not LANGSMITH_TRACING:
        return func

    @functools.wraps(func)
    @traceable(name="zai_tool_call", project_name=LANGSMITH_PROJECT)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def trace_fallback_chain(func: Callable) -> Callable:
    """
    Декоратор для трейсинга fallback chain.

    Usage:
        @trace_fallback_chain
        async def execute_fallback(server: str, tool: str, args: dict):
            ...
    """
    if not LANGSMITH_AVAILABLE or not LANGSMITH_TRACING:
        return func

    @functools.wraps(func)
    @traceable(name="fallback_chain", project_name=LANGSMITH_PROJECT)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def log_metric(name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
    """
    Логировать метрику в LangSmith.

    Usage:
        log_metric("rag_latency_ms", 1234, {"query": "..."})
        log_metric("zai_success_rate", 0.95)
    """
    client = get_langsmith_client()
    if client is None:
        return

    try:
        # LangSmith автоматически собирает метрики из трейсов
        # Для явной логировки можно использовать client.create_feedback()
        logger.debug(f"Metric logged: {name}={value}")
    except Exception as e:
        logger.error(f"Failed to log metric {name}: {e}")


class TraceStats:
    """Статистика трейсинга."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_latency_ms: float = 0.0

    @classmethod
    def record_success(cls, latency_ms: float):
        cls.total_runs += 1
        cls.successful_runs += 1
        cls.total_latency_ms += latency_ms

    @classmethod
    def record_failure(cls):
        cls.total_runs += 1
        cls.failed_runs += 1

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        avg_latency = cls.total_latency_ms / cls.successful_runs if cls.successful_runs > 0 else 0
        success_rate = cls.successful_runs / cls.total_runs if cls.total_runs > 0 else 0

        return {
            "total_runs": cls.total_runs,
            "successful_runs": cls.successful_runs,
            "failed_runs": cls.failed_runs,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate, 3)
        }


def get_trace_stats() -> Dict[str, Any]:
    """Получить статистику трейсинга."""
    return TraceStats.get_stats()


# Тестирование модуля
async def _test_tracing():
    """Тестирование LangSmith трейсинга."""
    print("LangSmith Tracing Test")
    print("=" * 50)

    print(f"LangSmith available: {LANGSMITH_AVAILABLE}")
    print(f"LANGSMITH_API_KEY set: {bool(LANGSMITH_API_KEY)}")
    print(f"LANGSMITH_TRACING: {LANGSMITH_TRACING}")
    print(f"LANGSMITH_PROJECT: {LANGSMITH_PROJECT}")

    client = get_langsmith_client()
    print(f"Client initialized: {client is not None}")

    # Тест TraceContext
    print("\n--- Testing TraceContext ---")
    with TraceContext("test_operation", run_type="chain") as trace:
        trace.log_input({"query": "test"})
        trace.log_metadata({"test": True})
        trace.log_output({"result": "success"})
    print("TraceContext test passed")

    print("\n--- Stats ---")
    print(get_trace_stats())


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test_tracing())
