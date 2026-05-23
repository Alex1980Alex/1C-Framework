"""Async event bus system with pub/sub semantics and wildcard pattern matching.

Provides a singleton EventBus for decoupled async communication between
components. Supports wildcard subscriptions, backpressure handling, and
background event dispatching.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_bus_instance: EventBus | None = None


@dataclass
class Event:
    """Represents an event flowing through the bus."""

    event_id: str
    event_type: str
    data: dict[str, Any]
    timestamp: datetime
    source: str | None = None


@dataclass
class Subscription:
    """Represents a subscription to one or more event patterns."""

    subscription_id: str
    pattern: str
    queue: asyncio.Queue[Event]
    created_at: datetime


@dataclass
class EventBusConfig:
    """Configuration for EventBus behavior."""

    max_queue_size: int = 1000
    max_subscribers: int = 100
    dispatch_timeout: float = 5.0
    enable_logging: bool = True


@dataclass
class EventBusStats:
    """Runtime statistics for the EventBus."""

    published_count: int = 0
    subscriber_count: int = 0
    dropped_count: int = 0


class EventBus:
    """Async event bus with wildcard pattern matching and backpressure.

    Uses asyncio.Queue for pub/sub with configurable overflow behavior.
    Events are dispatched to subscribers via a background task.

    Example::

        bus = get_event_bus()
        await bus.start()

        sub = await bus.subscribe("memory.*")
        await bus.publish("memory.save", {"key": "x", "value": 42})

        event = await sub.queue.get()
        print(event.data)  # {'key': 'x', 'value': 42}

        await bus.stop()
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        self._config: EventBusConfig = config or EventBusConfig()
        self._subscribers: dict[str, Subscription] = {}
        self._dispatch_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._dispatch_task: asyncio.Task[None] | None = None
        self._stats = EventBusStats()
        self._running: bool = False
        self._lock = asyncio.Lock()

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the background dispatch task."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        if self._config.enable_logging:
            logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the dispatch task and clean up."""
        if not self._running:
            return
        self._running = False

        # Signal the dispatch loop to exit by pushing a sentinel.
        sentinel = Event(
            event_id="__shutdown__",
            event_type="__shutdown__",
            data={},
            timestamp=datetime.now(tz=UTC),
            source=None,
        )
        await self._dispatch_queue.put(sentinel)

        if self._dispatch_task is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._dispatch_task), timeout=self._config.dispatch_timeout
                )
            except TimeoutError:
                self._dispatch_task.cancel()
                try:
                    await self._dispatch_task
                except asyncio.CancelledError:
                    pass
            self._dispatch_task = None

        if self._config.enable_logging:
            logger.info("EventBus stopped")

    # -- Pub/Sub API ---------------------------------------------------------

    async def publish(
        self, event_type: str, data: dict[str, Any], source: str | None = None
    ) -> str:
        """Publish an event to all matching subscribers.

        Args:
            event_type: Dotted event type string (e.g. ``"memory.save"``).
            data: Arbitrary payload dictionary.
            source: Optional source identifier.

        Returns:
            The ``event_id`` of the published event.
        """
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            data=data,
            timestamp=datetime.now(tz=UTC),
            source=source,
        )
        await self._dispatch_queue.put(event)
        self._stats.published_count += 1

        if self._config.enable_logging:
            logger.debug("Published event %s of type %s", event.event_id, event_type)

        return event.event_id

    async def subscribe(
        self,
        pattern: str,
        queue: asyncio.Queue[Event] | None = None,
    ) -> Subscription:
        """Subscribe to events matching *pattern*.

        Args:
            pattern: Wildcard pattern. ``*`` matches a single level,
                ``**`` matches multiple levels.
            queue: Optional pre-existing queue. A new bounded queue is
                created when ``None``.

        Returns:
            A :class:`Subscription` handle.

        Raises:
            RuntimeError: If the subscriber limit has been reached.
        """
        async with self._lock:
            if len(self._subscribers) >= self._config.max_subscribers:
                raise RuntimeError(
                    f"Maximum subscriber limit ({self._config.max_subscribers}) reached"
                )

            sub_id = str(uuid.uuid4())
            sub_queue: asyncio.Queue[Event] = (
                queue if queue is not None else asyncio.Queue(maxsize=self._config.max_queue_size)
            )

            subscription = Subscription(
                subscription_id=sub_id,
                pattern=pattern,
                queue=sub_queue,
                created_at=datetime.now(tz=UTC),
            )
            self._subscribers[sub_id] = subscription
            self._stats.subscriber_count = len(self._subscribers)

            if self._config.enable_logging:
                logger.info("Subscription %s registered for pattern '%s'", sub_id, pattern)

            return subscription

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription by its ID."""
        async with self._lock:
            removed = self._subscribers.pop(subscription_id, None)
            if removed is not None:
                self._stats.subscriber_count = len(self._subscribers)
                if self._config.enable_logging:
                    logger.info("Subscription %s removed", subscription_id)

    def get_stats(self) -> EventBusStats:
        """Return a snapshot of bus statistics."""
        self._stats.subscriber_count = len(self._subscribers)
        return EventBusStats(
            published_count=self._stats.published_count,
            subscriber_count=self._stats.subscriber_count,
            dropped_count=self._stats.dropped_count,
        )

    # -- Internal dispatch ---------------------------------------------------

    async def _dispatch_loop(self) -> None:
        """Background loop that fans out events to matching subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._dispatch_queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if event.event_type == "__shutdown__":
                break

            await self._fan_out(event)

    async def _fan_out(self, event: Event) -> None:
        """Deliver *event* to every subscriber whose pattern matches."""
        for subscription in list(self._subscribers.values()):
            if not _match_pattern(subscription.pattern, event.event_type):
                continue

            try:
                subscription.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest item to make room (backpressure).
                try:
                    subscription.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    subscription.queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass
                self._stats.dropped_count += 1
                if self._config.enable_logging:
                    logger.warning(
                        "Dropped event %s for subscription %s (queue full)",
                        event.event_id,
                        subscription.subscription_id,
                    )


# -- Pattern matching --------------------------------------------------------


def _match_pattern(pattern: str, event_type: str) -> bool:
    """Match *event_type* against a wildcard *pattern*.

    Rules:
      - ``*`` matches exactly one dot-separated segment.
      - ``**`` matches zero or more segments.
      - Literal segments must match exactly.
    """
    if pattern == event_type:
        return True

    pattern_parts = pattern.split(".")
    type_parts = event_type.split(".")

    return _match_parts(pattern_parts, type_parts)


def _match_parts(pattern_parts: list[str], type_parts: list[str]) -> bool:
    """Recursive segment-level matching."""
    if not pattern_parts and not type_parts:
        return True

    if not pattern_parts:
        return False

    if pattern_parts[0] == "**":
        rest = pattern_parts[1:]
        for i in range(len(type_parts) + 1):
            if _match_parts(rest, type_parts[i:]):
                return True
        return False

    if not type_parts:
        return False

    if pattern_parts[0] == "*" or pattern_parts[0] == type_parts[0]:
        return _match_parts(pattern_parts[1:], type_parts[1:])

    return False


# -- Singleton accessors -----------------------------------------------------


def get_event_bus(config: EventBusConfig | None = None) -> EventBus:
    """Return the global :class:`EventBus` instance, creating it if needed."""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = EventBus(config)
    return _bus_instance


def reset_event_bus() -> None:
    """Destroy the global :class:`EventBus` instance (for testing)."""
    global _bus_instance
    _bus_instance = None


__all__ = [
    "Event",
    "EventBus",
    "EventBusConfig",
    "EventBusStats",
    "Subscription",
    "get_event_bus",
    "reset_event_bus",
]
