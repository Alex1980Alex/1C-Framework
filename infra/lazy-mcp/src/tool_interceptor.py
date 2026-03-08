#!/usr/bin/env python3
"""
MCP Tool Interceptor

Автоматический перехват и маршрутизация MCP tool calls через Z.AI.
Категоризирует инструменты по A/B/C и направляет на нужный провайдер.

Версия: 1.0
Дата: 2026-01-17
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_stderr(msg: str) -> None:
    """Логирование в stderr для MCP совместимости"""
    print(msg, file=sys.stderr, flush=True)


class ToolCategory(Enum):
    """Категории инструментов для маршрутизации"""
    A = "a"  # 100% Z.AI - детерминированные операции
    B = "b"  # 70-90% Z.AI + валидация Claude
    C = "c"  # 0% Z.AI - только Claude


class RoutingDecision(Enum):
    """Решение о маршрутизации"""
    ZAI_ONLY = "zai_only"
    ZAI_WITH_VALIDATION = "zai_validation"
    CLAUDE_ONLY = "claude_only"


@dataclass
class InterceptResult:
    """Результат перехвата"""
    intercepted: bool
    category: Optional[ToolCategory] = None
    decision: Optional[RoutingDecision] = None
    result: Any = None
    error: Optional[str] = None
    latency_ms: int = 0
    provider: str = "direct"


# Классификация инструментов по категориям
# На основе Z.AI-MCP-TOOLS-CLASSIFICATION.md v2.0
TOOL_CLASSIFICATION: Dict[str, Dict[str, ToolCategory]] = {
    # /1c-development - 99% Category A
    "ast-grep-mcp": {
        "*": ToolCategory.A,  # Все инструменты детерминированные
    },
    "bsl-platform-context": {
        "*": ToolCategory.A,  # Справочные операции
    },
    "bsl-semantic-search": {
        "*": ToolCategory.A,
        "intelligent_search": ToolCategory.B,  # Нужна интерпретация
    },

    # /documentation - 85% Category A
    "1c-docs-rag": {
        "*": ToolCategory.A,
        "ask_docs": ToolCategory.B,  # RAG ответ - валидация
        "validate_solution": ToolCategory.C,  # Экспертиза Claude
    },
    "auto-documenter": {
        "generate_dependency_graph": ToolCategory.A,
        "generate_documentation": ToolCategory.B,
        "autotestplan": ToolCategory.B,
        "generate_inline_docs": ToolCategory.B,
        "autoreview": ToolCategory.C,  # Экспертиза Claude
    },

    # /memory - 97% Category A
    "unified-memory": {
        "*": ToolCategory.A,
        "forget_memory": ToolCategory.B,
        "evaluate_forget_scores": ToolCategory.B,
    },
    "memory-ai": {
        "*": ToolCategory.A,
    },
    "conversation-memory": {
        "*": ToolCategory.A,
        "get_project_summary": ToolCategory.B,
    },
    "vector-memory": {
        "*": ToolCategory.A,
        "merge_patterns": ToolCategory.B,
    },

    # /learning - 71% Category A
    "skill-learning": {
        "get_pending_patterns": ToolCategory.A,
        "get_learning_stats": ToolCategory.A,
        "health_check": ToolCategory.A,
        "capture_pattern": ToolCategory.B,
        "batch_capture": ToolCategory.B,
        "confirm_pattern": ToolCategory.C,
        "reject_pattern": ToolCategory.C,
    },

    # /file-operations - 100% Category A
    "ripgrep": {
        "*": ToolCategory.A,
    },
    "filesystem": {
        "*": ToolCategory.A,
    },

    # /reasoning - 8% Category A (в основном Category C)
    "sequential-thinking": {
        "*": ToolCategory.C,  # Core reasoning
    },
    "deep-code-reasoning": {
        "get_conversation_status": ToolCategory.A,
        "*": ToolCategory.C,  # Deep analysis
    },

    # /web - 92% Category A
    "brave": {
        "*": ToolCategory.A,
    },
    "puppeteer": {
        "*": ToolCategory.A,
        "evaluate": ToolCategory.B,
    },

    # /browser - 97% Category A
    "playwright": {
        "*": ToolCategory.A,
        "playwright_evaluate": ToolCategory.B,
    },

    # /code-analysis
    "serena": {
        "*": ToolCategory.A,  # LSP операции детерминированные
    },

    # /utils
    "github": {
        "search": ToolCategory.A,
        "list": ToolCategory.A,
        "get": ToolCategory.A,
        "create_pr": ToolCategory.C,
        "review": ToolCategory.C,
        "*": ToolCategory.A,
    },

    # IDE tools
    "ide": {
        "getDiagnostics": ToolCategory.A,
        "executeCode": ToolCategory.B,
    },

    # Task Master
    "task-master-ai": {
        "*": ToolCategory.A,
        "expand_task": ToolCategory.B,
    },

    # BSL Debugger - отладка 1С кода (Category A - детерминированные)
    "bsl-debugger": {
        "*": ToolCategory.A,  # Все операции отладки детерминированные
        "connect_debugger": ToolCategory.A,
        "set_breakpoint": ToolCategory.A,
        "get_call_stack": ToolCategory.A,
        "evaluate_expression": ToolCategory.B,  # Может требовать интерпретации
        "get_local_variables": ToolCategory.A,
        "step_over": ToolCategory.A,
        "step_into": ToolCategory.A,
        "continue_execution": ToolCategory.A,
    },

    # MCP Reasoner - reasoning стратегии (Category C - только Claude)
    "mcp-reasoner": {
        "*": ToolCategory.C,  # MCTS/Beam Search - reasoning задачи
    },
}

# Серверы где ВСЕ инструменты Category A (для оптимизации)
CATEGORY_A_SERVERS = {
    "ast-grep-mcp",
    "bsl-platform-context",
    "memory-ai",
    "ripgrep",
    "brave",
}

# Серверы Category C (никогда не через Z.AI)
CATEGORY_C_SERVERS = {
    "sequential-thinking",
    "mcp-reasoner",  # MCTS/Beam Search reasoning
}


class ToolInterceptor:
    """
    Перехватчик MCP tool calls для маршрутизации через Z.AI.

    Архитектура:
    ┌───────────────────────────────────────────────────────────┐
    │                    ToolInterceptor                         │
    │  • Классифицирует инструмент (A/B/C)                       │
    │  • Решает: Z.AI / Z.AI+валидация / Claude                  │
    │  • Выполняет через ZaiClient или возвращает для Claude    │
    └───────────────────────────────────────────────────────────┘
    """

    def __init__(
        self,
        zai_client: Optional[Any] = None,
        enable_metrics: bool = True,
        enable_caching: bool = True,
        cache_ttl_seconds: int = 300
    ):
        """
        Инициализация интерцептора.

        Args:
            zai_client: Клиент Z.AI (lazy init если None)
            enable_metrics: Включить сбор метрик
            enable_caching: Включить кэширование результатов Cat.A
            cache_ttl_seconds: TTL кэша в секундах
        """
        self._zai_client = zai_client
        self._zai_initialized = False
        self.enable_metrics = enable_metrics
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl_seconds

        # Кэш для Category A инструментов
        self._cache: Dict[str, Tuple[Any, float]] = {}

        # Метрики
        self.metrics = {
            "total_calls": 0,
            "zai_routed": 0,
            "claude_routed": 0,
            "hybrid_routed": 0,
            "cache_hits": 0,
            "errors": 0,
            "total_latency_ms": 0,
            "total_tokens_saved": 0,
        }

        # Путь к метрикам
        self.metrics_path = Path(os.environ.get(
            "LAZY_MCP_METRICS_PATH",
            "D:/1C-Enterprise_Framework/cache/metrics/lazy-mcp-routing.json"
        ))

        log_stderr("[tool-interceptor] Initialized")

    async def _get_zai_client(self) -> Optional[Any]:
        """Lazy init Z.AI клиента"""
        if not self._zai_initialized:
            try:
                # Импортируем zai_client из zai-hooks-proxy
                zai_proxy_path = Path("D:/1C-Enterprise_Framework/scripts/mcp/zai-hooks-proxy")
                if zai_proxy_path.exists():
                    sys.path.insert(0, str(zai_proxy_path))
                    from zai_client import get_client
                    self._zai_client = get_client()
                    self._zai_initialized = True
                    log_stderr("[tool-interceptor] Z.AI client initialized")
            except Exception as e:
                log_stderr(f"[tool-interceptor] Warning: Z.AI client not available: {e}")
                self._zai_client = None
                self._zai_initialized = True

        return self._zai_client

    def classify_tool(self, server_name: str, tool_name: str) -> ToolCategory:
        """
        Классифицировать инструмент по категории.

        Args:
            server_name: Имя MCP сервера
            tool_name: Имя инструмента

        Returns:
            ToolCategory (A, B или C)
        """
        # Быстрая проверка Category A серверов
        if server_name in CATEGORY_A_SERVERS:
            return ToolCategory.A

        # Быстрая проверка Category C серверов
        if server_name in CATEGORY_C_SERVERS:
            return ToolCategory.C

        # Детальная классификация
        server_config = TOOL_CLASSIFICATION.get(server_name, {})

        # Специфический инструмент
        if tool_name in server_config:
            return server_config[tool_name]

        # Wildcard для сервера
        if "*" in server_config:
            return server_config["*"]

        # По умолчанию - Category A (большинство MCP ops детерминированные)
        return ToolCategory.A

    def get_routing_decision(
        self,
        category: ToolCategory,
        tool_name: str,
        args: Dict[str, Any]
    ) -> RoutingDecision:
        """
        Определить решение о маршрутизации.

        Args:
            category: Категория инструмента
            tool_name: Имя инструмента
            args: Аргументы вызова

        Returns:
            RoutingDecision
        """
        if category == ToolCategory.A:
            return RoutingDecision.ZAI_ONLY
        elif category == ToolCategory.B:
            return RoutingDecision.ZAI_WITH_VALIDATION
        else:
            return RoutingDecision.CLAUDE_ONLY

    def _get_cache_key(self, server_name: str, tool_name: str, args: Dict) -> str:
        """Сгенерировать ключ кэша"""
        args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
        return f"{server_name}:{tool_name}:{args_str}"

    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Проверить кэш"""
        if not self.enable_caching:
            return None

        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self.metrics["cache_hits"] += 1
                return result
            else:
                del self._cache[cache_key]

        return None

    def _save_to_cache(self, cache_key: str, result: Any) -> None:
        """Сохранить в кэш"""
        if self.enable_caching:
            self._cache[cache_key] = (result, time.time())

    async def intercept(
        self,
        server_name: str,
        tool_name: str,
        args: Dict[str, Any],
        execute_direct: Optional[callable] = None
    ) -> InterceptResult:
        """
        Перехватить и маршрутизировать вызов инструмента.

        Args:
            server_name: Имя MCP сервера
            tool_name: Имя инструмента
            args: Аргументы вызова
            execute_direct: Callback для прямого выполнения (fallback)

        Returns:
            InterceptResult с результатом или инструкцией для Claude
        """
        start_time = time.time()
        self.metrics["total_calls"] += 1

        try:
            # 1. Классификация
            category = self.classify_tool(server_name, tool_name)
            decision = self.get_routing_decision(category, tool_name, args)

            log_stderr(
                f"[tool-interceptor] {server_name}/{tool_name} -> "
                f"Category {category.value.upper()}, Decision: {decision.value}"
            )

            # 2. Проверка кэша для Category A
            if category == ToolCategory.A:
                cache_key = self._get_cache_key(server_name, tool_name, args)
                cached = self._check_cache(cache_key)
                if cached is not None:
                    latency = int((time.time() - start_time) * 1000)
                    return InterceptResult(
                        intercepted=True,
                        category=category,
                        decision=decision,
                        result=cached,
                        latency_ms=latency,
                        provider="cache"
                    )

            # 3. Маршрутизация
            if decision == RoutingDecision.CLAUDE_ONLY:
                # Category C - не перехватываем, Claude выполняет напрямую
                self.metrics["claude_routed"] += 1
                return InterceptResult(
                    intercepted=False,
                    category=category,
                    decision=decision,
                    provider="claude"
                )

            # 4. Попытка выполнить через Z.AI
            zai_client = await self._get_zai_client()

            if zai_client is None:
                # Z.AI недоступен - fallback на прямое выполнение
                log_stderr("[tool-interceptor] Z.AI unavailable, using direct execution")
                if execute_direct:
                    result = await execute_direct(server_name, tool_name, args)
                    latency = int((time.time() - start_time) * 1000)
                    return InterceptResult(
                        intercepted=True,
                        category=category,
                        decision=decision,
                        result=result,
                        latency_ms=latency,
                        provider="direct_fallback"
                    )
                else:
                    return InterceptResult(
                        intercepted=False,
                        category=category,
                        decision=decision,
                        error="Z.AI unavailable and no fallback provided"
                    )

            # 5. Выполнение через Z.AI
            try:
                # Формируем промпт для Z.AI
                prompt = self._build_zai_prompt(server_name, tool_name, args)

                # Вызываем Z.AI
                zai_response = await zai_client.execute(prompt)

                if decision == RoutingDecision.ZAI_ONLY:
                    # Category A - результат Z.AI финальный
                    self.metrics["zai_routed"] += 1

                    # Кэшируем результат
                    if category == ToolCategory.A:
                        cache_key = self._get_cache_key(server_name, tool_name, args)
                        self._save_to_cache(cache_key, zai_response)

                    latency = int((time.time() - start_time) * 1000)
                    self.metrics["total_latency_ms"] += latency

                    return InterceptResult(
                        intercepted=True,
                        category=category,
                        decision=decision,
                        result=zai_response,
                        latency_ms=latency,
                        provider="zai"
                    )
                else:
                    # Category B - нужна валидация Claude
                    self.metrics["hybrid_routed"] += 1
                    latency = int((time.time() - start_time) * 1000)

                    return InterceptResult(
                        intercepted=True,
                        category=category,
                        decision=decision,
                        result={
                            "zai_result": asdict(zai_response) if hasattr(zai_response, '__dataclass_fields__') else zai_response,
                            "needs_validation": True,
                            "validation_prompt": self._build_validation_prompt(
                                server_name, tool_name, args, zai_response
                            )
                        },
                        latency_ms=latency,
                        provider="zai_hybrid"
                    )

            except Exception as e:
                log_stderr(f"[tool-interceptor] Z.AI error: {e}")
                self.metrics["errors"] += 1

                # Fallback на прямое выполнение
                if execute_direct:
                    result = await execute_direct(server_name, tool_name, args)
                    latency = int((time.time() - start_time) * 1000)
                    return InterceptResult(
                        intercepted=True,
                        category=category,
                        decision=decision,
                        result=result,
                        latency_ms=latency,
                        provider="direct_fallback",
                        error=f"Z.AI failed: {e}"
                    )

                return InterceptResult(
                    intercepted=False,
                    category=category,
                    decision=decision,
                    error=str(e)
                )

        except Exception as e:
            self.metrics["errors"] += 1
            log_stderr(f"[tool-interceptor] Error: {e}")
            return InterceptResult(
                intercepted=False,
                error=str(e)
            )

    def _build_zai_prompt(
        self,
        server_name: str,
        tool_name: str,
        args: Dict[str, Any]
    ) -> str:
        """Сформировать промпт для Z.AI"""
        return f"""Execute MCP tool and return result as JSON:

Server: {server_name}
Tool: {tool_name}
Arguments: {json.dumps(args, ensure_ascii=False, indent=2)}

Return the tool execution result in JSON format."""

    def _build_validation_prompt(
        self,
        server_name: str,
        tool_name: str,
        args: Dict[str, Any],
        zai_result: Any
    ) -> str:
        """Сформировать промпт для валидации Claude"""
        return f"""Validate Z.AI result for MCP tool call:

Tool: {server_name}/{tool_name}
Arguments: {json.dumps(args, ensure_ascii=False)}

Z.AI Result:
{json.dumps(zai_result, ensure_ascii=False, indent=2)}

Is this result correct and complete? If not, provide the corrected result."""

    def save_metrics(self) -> None:
        """Сохранить метрики в файл"""
        if not self.enable_metrics:
            return

        try:
            self.metrics_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.metrics_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "metrics": self.metrics,
                    "classification_stats": {
                        "category_a_servers": list(CATEGORY_A_SERVERS),
                        "category_c_servers": list(CATEGORY_C_SERVERS),
                    }
                }, f, indent=2, ensure_ascii=False)

        except Exception as e:
            log_stderr(f"[tool-interceptor] Failed to save metrics: {e}")

    def get_classification_summary(self) -> Dict[str, Any]:
        """Получить сводку по классификации"""
        total_a = len(CATEGORY_A_SERVERS)
        total_c = len(CATEGORY_C_SERVERS)

        return {
            "category_a_servers": list(CATEGORY_A_SERVERS),
            "category_c_servers": list(CATEGORY_C_SERVERS),
            "detailed_classification_servers": list(TOOL_CLASSIFICATION.keys()),
            "summary": {
                "always_zai": total_a,
                "always_claude": total_c,
                "detailed_routing": len(TOOL_CLASSIFICATION)
            }
        }


# Глобальный экземпляр интерцептора
_interceptor: Optional[ToolInterceptor] = None


def get_interceptor() -> ToolInterceptor:
    """Получить глобальный экземпляр интерцептора"""
    global _interceptor
    if _interceptor is None:
        _interceptor = ToolInterceptor()
    return _interceptor


async def intercept_tool_call(
    server_name: str,
    tool_name: str,
    args: Dict[str, Any],
    execute_direct: Optional[callable] = None
) -> InterceptResult:
    """
    Удобная функция для перехвата вызова инструмента.

    Args:
        server_name: Имя MCP сервера
        tool_name: Имя инструмента
        args: Аргументы
        execute_direct: Callback для прямого выполнения

    Returns:
        InterceptResult
    """
    interceptor = get_interceptor()
    return await interceptor.intercept(server_name, tool_name, args, execute_direct)


if __name__ == "__main__":
    # Тест классификации
    interceptor = ToolInterceptor()

    test_cases = [
        ("ast-grep-mcp", "find_code"),
        ("bsl-platform-context", "search"),
        ("1c-docs-rag", "ask_docs"),
        ("1c-docs-rag", "validate_solution"),
        ("sequential-thinking", "sequentialthinking"),
        ("memory-ai", "save_important_message"),
    ]

    print("\nTool Classification Test:")
    print("-" * 60)
    for server, tool in test_cases:
        category = interceptor.classify_tool(server, tool)
        decision = interceptor.get_routing_decision(category, tool, {})
        print(f"{server}/{tool}: Category {category.value.upper()} -> {decision.value}")

    print("\n" + "-" * 60)
    print(json.dumps(interceptor.get_classification_summary(), indent=2))
