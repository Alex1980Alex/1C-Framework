"""Fallback Strategies for Pipeline Resilience.

Implements fallback patterns including fallback chains,
cached results, and alternative service calls.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Optional, Callable, Any, TypeVar, Dict, List,
    Generic, Awaitable, Union
)
from functools import wraps
import asyncio
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FallbackType(Enum):
    """Types of fallback strategies."""

    DEFAULT_VALUE = "default_value"      # Return a default value
    CACHED_RESULT = "cached_result"      # Return cached result
    ALTERNATIVE_SERVICE = "alternative_service"  # Call alternative
    DEGRADED_RESPONSE = "degraded_response"  # Partial/degraded response
    QUEUE_FOR_LATER = "queue_for_later"  # Queue for later processing
    SKIP = "skip"                        # Skip this operation
    FAIL = "fail"                        # Fail immediately


@dataclass
class FallbackResult(Generic[T]):
    """Result of a fallback operation."""

    success: bool
    value: Optional[T] = None
    fallback_type: Optional[FallbackType] = None
    fallback_name: Optional[str] = None
    original_error: Optional[Exception] = None
    execution_time_ms: float = 0.0
    message: Optional[str] = None

    @property
    def used_fallback(self) -> bool:
        """Check if fallback was used."""
        return self.fallback_type is not None


@dataclass
class FallbackStrategy(Generic[T]):
    """A single fallback strategy."""

    name: str
    fallback_type: FallbackType
    handler: Callable[..., Union[T, Awaitable[T]]]
    priority: int = 0
    condition: Optional[Callable[[Exception], bool]] = None
    timeout_seconds: Optional[float] = None

    async def execute(
        self,
        original_error: Exception,
        *args,
        **kwargs
    ) -> FallbackResult[T]:
        """Execute this fallback strategy.

        Args:
            original_error: The error that triggered fallback
            *args: Original function arguments
            **kwargs: Original function keyword arguments

        Returns:
            FallbackResult with success status and value
        """
        start_time = datetime.now()

        # Check condition
        if self.condition and not self.condition(original_error):
            return FallbackResult(
                success=False,
                fallback_type=self.fallback_type,
                fallback_name=self.name,
                original_error=original_error,
                message="Condition not met",
            )

        try:
            # Execute handler
            if asyncio.iscoroutinefunction(self.handler):
                if self.timeout_seconds:
                    value = await asyncio.wait_for(
                        self.handler(*args, **kwargs),
                        timeout=self.timeout_seconds
                    )
                else:
                    value = await self.handler(*args, **kwargs)
            else:
                value = self.handler(*args, **kwargs)

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            return FallbackResult(
                success=True,
                value=value,
                fallback_type=self.fallback_type,
                fallback_name=self.name,
                original_error=original_error,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.warning(f"Fallback {self.name} failed: {e}")

            return FallbackResult(
                success=False,
                fallback_type=self.fallback_type,
                fallback_name=self.name,
                original_error=original_error,
                execution_time_ms=elapsed_ms,
                message=str(e),
            )


class FallbackChain(Generic[T]):
    """Chain of fallback strategies executed in order."""

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._strategies: List[FallbackStrategy[T]] = []
        self._last_result: Optional[FallbackResult[T]] = None

    @property
    def name(self) -> str:
        """Get chain name."""
        return self._name

    @property
    def last_result(self) -> Optional[FallbackResult[T]]:
        """Get last execution result."""
        return self._last_result

    def add(self, strategy: FallbackStrategy[T]) -> "FallbackChain[T]":
        """Add a strategy to the chain.

        Args:
            strategy: FallbackStrategy to add

        Returns:
            Self for chaining
        """
        self._strategies.append(strategy)
        # Sort by priority (lower = higher priority)
        self._strategies.sort(key=lambda s: s.priority)
        return self

    def add_default_value(
        self,
        name: str,
        value: T,
        priority: int = 100,
        condition: Optional[Callable[[Exception], bool]] = None,
    ) -> "FallbackChain[T]":
        """Add a default value fallback.

        Args:
            name: Strategy name
            value: Default value to return
            priority: Execution priority
            condition: Optional condition function

        Returns:
            Self for chaining
        """
        return self.add(FallbackStrategy(
            name=name,
            fallback_type=FallbackType.DEFAULT_VALUE,
            handler=lambda *args, **kwargs: value,
            priority=priority,
            condition=condition,
        ))

    def add_handler(
        self,
        name: str,
        handler: Callable[..., Union[T, Awaitable[T]]],
        fallback_type: FallbackType = FallbackType.ALTERNATIVE_SERVICE,
        priority: int = 50,
        condition: Optional[Callable[[Exception], bool]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> "FallbackChain[T]":
        """Add a handler-based fallback.

        Args:
            name: Strategy name
            handler: Fallback handler function
            fallback_type: Type of fallback
            priority: Execution priority
            condition: Optional condition function
            timeout_seconds: Optional timeout

        Returns:
            Self for chaining
        """
        return self.add(FallbackStrategy(
            name=name,
            fallback_type=fallback_type,
            handler=handler,
            priority=priority,
            condition=condition,
            timeout_seconds=timeout_seconds,
        ))

    async def execute(
        self,
        error: Exception,
        *args,
        **kwargs
    ) -> FallbackResult[T]:
        """Execute fallback chain.

        Tries each strategy in order until one succeeds.

        Args:
            error: The error that triggered fallback
            *args: Original function arguments
            **kwargs: Original function keyword arguments

        Returns:
            FallbackResult from first successful strategy
        """
        for strategy in self._strategies:
            result = await strategy.execute(error, *args, **kwargs)
            self._last_result = result

            if result.success:
                logger.info(
                    f"Fallback chain '{self._name}': "
                    f"strategy '{strategy.name}' succeeded"
                )
                return result

            logger.debug(
                f"Fallback chain '{self._name}': "
                f"strategy '{strategy.name}' failed, trying next"
            )

        # All strategies failed
        return FallbackResult(
            success=False,
            original_error=error,
            message=f"All {len(self._strategies)} fallback strategies failed",
        )


class FallbackRegistry:
    """Registry for managing fallback chains."""

    def __init__(self) -> None:
        self._chains: Dict[str, FallbackChain] = {}
        self._default_chain: Optional[str] = None

    def register(
        self,
        chain: FallbackChain,
        set_default: bool = False
    ) -> None:
        """Register a fallback chain.

        Args:
            chain: FallbackChain to register
            set_default: Whether to set as default chain
        """
        self._chains[chain.name] = chain
        if set_default or self._default_chain is None:
            self._default_chain = chain.name

    def get(self, name: str) -> Optional[FallbackChain]:
        """Get a fallback chain by name.

        Args:
            name: Chain name

        Returns:
            FallbackChain or None
        """
        return self._chains.get(name)

    def get_default(self) -> Optional[FallbackChain]:
        """Get the default fallback chain.

        Returns:
            Default FallbackChain or None
        """
        if self._default_chain:
            return self._chains.get(self._default_chain)
        return None

    def remove(self, name: str) -> None:
        """Remove a fallback chain.

        Args:
            name: Chain name to remove
        """
        if name in self._chains:
            del self._chains[name]
            if self._default_chain == name:
                self._default_chain = None

    def list_chains(self) -> List[str]:
        """List all registered chain names.

        Returns:
            List of chain names
        """
        return list(self._chains.keys())


# Global registry instance
_global_registry = FallbackRegistry()


def get_global_registry() -> FallbackRegistry:
    """Get the global fallback registry.

    Returns:
        Global FallbackRegistry instance
    """
    return _global_registry


class CachedFallback(Generic[T]):
    """Fallback that uses cached results."""

    def __init__(
        self,
        max_age_seconds: float = 300.0,
        max_entries: int = 100
    ):
        self._cache: Dict[str, tuple[T, datetime]] = {}
        self._max_age = max_age_seconds
        self._max_entries = max_entries

    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments."""
        return str((args, sorted(kwargs.items())))

    def store(self, value: T, *args, **kwargs) -> None:
        """Store a value in cache.

        Args:
            value: Value to cache
            *args: Key arguments
            **kwargs: Key keyword arguments
        """
        key = self._make_key(*args, **kwargs)
        self._cache[key] = (value, datetime.now())

        # Evict old entries if needed
        if len(self._cache) > self._max_entries:
            # Remove oldest entries
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1][1]
            )
            for old_key, _ in sorted_items[:len(self._cache) - self._max_entries]:
                del self._cache[old_key]

    def get(self, *args, **kwargs) -> Optional[T]:
        """Get cached value.

        Args:
            *args: Key arguments
            **kwargs: Key keyword arguments

        Returns:
            Cached value or None
        """
        key = self._make_key(*args, **kwargs)
        if key not in self._cache:
            return None

        value, stored_at = self._cache[key]
        age = (datetime.now() - stored_at).total_seconds()

        if age > self._max_age:
            del self._cache[key]
            return None

        return value

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def create_strategy(
        self,
        name: str = "cached_fallback",
        priority: int = 10
    ) -> FallbackStrategy[T]:
        """Create a fallback strategy using this cache.

        Args:
            name: Strategy name
            priority: Strategy priority

        Returns:
            FallbackStrategy instance
        """
        async def handler(*args, **kwargs) -> T:
            cached = self.get(*args, **kwargs)
            if cached is None:
                raise ValueError("No cached value available")
            return cached

        return FallbackStrategy(
            name=name,
            fallback_type=FallbackType.CACHED_RESULT,
            handler=handler,
            priority=priority,
        )


def with_fallback(
    fallback_chain: Optional[FallbackChain[T]] = None,
    default_value: Optional[T] = None,
    on_fallback: Optional[Callable[[FallbackResult], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for adding fallback behavior.

    Args:
        fallback_chain: FallbackChain to use
        default_value: Default value if no chain provided
        on_fallback: Callback when fallback is used

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Create simple chain if only default_value provided
        chain = fallback_chain
        if chain is None and default_value is not None:
            chain = FallbackChain[T](name=f"{func.__name__}_fallback")
            chain.add_default_value(
                name="default",
                value=default_value,
                priority=100
            )

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            except Exception as e:
                if chain is None:
                    raise

                logger.warning(f"Function {func.__name__} failed, trying fallback: {e}")
                result = await chain.execute(e, *args, **kwargs)

                if on_fallback:
                    on_fallback(result)

                if result.success:
                    return result.value
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if chain is None:
                    raise

                logger.warning(f"Function {func.__name__} failed, trying fallback: {e}")
                result = asyncio.run(chain.execute(e, *args, **kwargs))

                if on_fallback:
                    on_fallback(result)

                if result.success:
                    return result.value
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Utility functions for common fallback patterns

def create_timeout_fallback(
    name: str,
    default_value: T,
    priority: int = 50
) -> FallbackStrategy[T]:
    """Create fallback for timeout errors.

    Args:
        name: Strategy name
        default_value: Value to return on timeout
        priority: Strategy priority

    Returns:
        FallbackStrategy for timeouts
    """
    def is_timeout(error: Exception) -> bool:
        return (
            isinstance(error, asyncio.TimeoutError) or
            "timeout" in str(error).lower()
        )

    return FallbackStrategy(
        name=name,
        fallback_type=FallbackType.DEFAULT_VALUE,
        handler=lambda *args, **kwargs: default_value,
        priority=priority,
        condition=is_timeout,
    )


def create_network_fallback(
    name: str,
    handler: Callable[..., Union[T, Awaitable[T]]],
    priority: int = 30
) -> FallbackStrategy[T]:
    """Create fallback for network errors.

    Args:
        name: Strategy name
        handler: Fallback handler
        priority: Strategy priority

    Returns:
        FallbackStrategy for network errors
    """
    def is_network_error(error: Exception) -> bool:
        error_type = type(error).__name__.lower()
        error_msg = str(error).lower()
        return (
            "connection" in error_type or
            "network" in error_type or
            "socket" in error_type or
            "connection" in error_msg or
            "network" in error_msg
        )

    return FallbackStrategy(
        name=name,
        fallback_type=FallbackType.ALTERNATIVE_SERVICE,
        handler=handler,
        priority=priority,
        condition=is_network_error,
    )
