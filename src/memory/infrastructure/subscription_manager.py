"""Subscription Manager — managed subscriptions with heartbeat and stale cleanup.

Wraps EventBus subscriptions with client tracking, heartbeat monitoring,
and automatic cleanup of stale/dead subscriptions.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .event_bus import Event, EventBus, Subscription

logger = logging.getLogger(__name__)


@dataclass
class ManagedSubscription:
    """A subscription with client tracking and heartbeat metadata."""

    subscription_id: str
    client_id: str
    pattern: str
    bus_subscription: Subscription
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    delivered_count: int = 0

    @property
    def age_seconds(self) -> float:
        return (datetime.now(tz=UTC) - self.created_at).total_seconds()

    @property
    def heartbeat_age_seconds(self) -> float:
        return (datetime.now(tz=UTC) - self.last_heartbeat).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "client_id": self.client_id,
            "pattern": self.pattern,
            "created_at": self.created_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "heartbeat_age_seconds": round(self.heartbeat_age_seconds, 1),
            "delivered_count": self.delivered_count,
            "metadata": self.metadata,
        }


@dataclass
class SubscriptionManagerConfig:
    """Configuration for SubscriptionManager."""

    heartbeat_interval: float = 30.0
    stale_timeout: float = 120.0
    max_subscriptions_per_client: int = 10
    enable_auto_cleanup: bool = True


class SubscriptionManager:
    """Manages EventBus subscriptions with heartbeat tracking and stale cleanup.

    Provides a higher-level API over EventBus for client-aware subscription
    management. Each subscription is tracked with heartbeat timestamps and
    automatically cleaned up when stale.

    Usage::

        mgr = SubscriptionManager(event_bus)
        await mgr.start()

        sub = await mgr.create("client-1", "memory.*")
        events = await mgr.get_events(sub.subscription_id, max_events=5)
        await mgr.heartbeat(sub.subscription_id)

        await mgr.stop()
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: SubscriptionManagerConfig | None = None,
    ) -> None:
        self._bus = event_bus
        self._config = config or SubscriptionManagerConfig()
        self._subscriptions: dict[str, ManagedSubscription] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._total_created: int = 0
        self._total_removed: int = 0
        self._total_stale_cleaned: int = 0

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the background cleanup task."""
        if self._running:
            return
        self._running = True
        if self._config.enable_auto_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SubscriptionManager started")

    async def stop(self) -> None:
        """Stop cleanup and remove all subscriptions."""
        self._running = False
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Unsubscribe all managed subscriptions
        for sub in list(self._subscriptions.values()):
            await self._bus.unsubscribe(sub.subscription_id)
        self._subscriptions.clear()
        logger.info("SubscriptionManager stopped")

    # -- Public API ----------------------------------------------------------

    async def create(
        self,
        client_id: str,
        pattern: str,
        metadata: dict[str, Any] | None = None,
    ) -> ManagedSubscription:
        """Create a new managed subscription for a client.

        Args:
            client_id: Identifier for the subscribing client.
            pattern: Event pattern (supports wildcards).
            metadata: Optional metadata to attach.

        Returns:
            A :class:`ManagedSubscription` handle.

        Raises:
            RuntimeError: If the per-client subscription limit is reached.
        """
        client_subs = [s for s in self._subscriptions.values() if s.client_id == client_id]
        if len(client_subs) >= self._config.max_subscriptions_per_client:
            raise RuntimeError(
                f"Client '{client_id}' has reached the subscription limit "
                f"({self._config.max_subscriptions_per_client})"
            )

        bus_sub = await self._bus.subscribe(pattern)
        managed = ManagedSubscription(
            subscription_id=bus_sub.subscription_id,
            client_id=client_id,
            pattern=pattern,
            bus_subscription=bus_sub,
            metadata=metadata or {},
        )
        self._subscriptions[bus_sub.subscription_id] = managed
        self._total_created += 1
        logger.info(
            "Created subscription %s for client '%s' on pattern '%s'",
            bus_sub.subscription_id,
            client_id,
            pattern,
        )
        return managed

    async def remove(self, subscription_id: str) -> bool:
        """Remove a managed subscription.

        Returns:
            True if the subscription existed and was removed.
        """
        managed = self._subscriptions.pop(subscription_id, None)
        if managed is None:
            return False
        await self._bus.unsubscribe(subscription_id)
        self._total_removed += 1
        logger.info("Removed subscription %s", subscription_id)
        return True

    async def heartbeat(self, subscription_id: str) -> bool:
        """Update the heartbeat timestamp for a subscription.

        Returns:
            True if subscription exists and was updated.
        """
        managed = self._subscriptions.get(subscription_id)
        if managed is None:
            return False
        managed.last_heartbeat = datetime.now(tz=UTC)
        return True

    async def get_events(
        self,
        subscription_id: str,
        max_events: int = 10,
    ) -> list[dict[str, Any]]:
        """Drain pending events from a subscription's queue.

        Args:
            subscription_id: The subscription to poll.
            max_events: Maximum events to return.

        Returns:
            List of event dicts (up to *max_events*).

        Raises:
            KeyError: If subscription_id is unknown.
        """
        managed = self._subscriptions.get(subscription_id)
        if managed is None:
            raise KeyError(f"Unknown subscription: {subscription_id}")

        events: list[dict[str, Any]] = []
        queue = managed.bus_subscription.queue
        for _ in range(max_events):
            try:
                event: Event = queue.get_nowait()
                events.append(
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "data": event.data,
                        "timestamp": event.timestamp.isoformat()
                        if isinstance(event.timestamp, datetime)
                        else str(event.timestamp),
                        "source": event.source,
                    }
                )
                managed.delivered_count += 1
            except asyncio.QueueEmpty:
                break
        return events

    async def list_subscriptions(
        self,
        client_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List managed subscriptions, optionally filtered by client.

        Args:
            client_id: If set, only return subscriptions for this client.

        Returns:
            List of subscription dicts.
        """
        subs = self._subscriptions.values()
        if client_id is not None:
            subs = [s for s in subs if s.client_id == client_id]
        return [s.to_dict() for s in subs]

    def get_stats(self) -> dict[str, Any]:
        """Return subscription manager statistics."""
        active = len(self._subscriptions)
        stale = sum(
            1
            for s in self._subscriptions.values()
            if s.heartbeat_age_seconds > self._config.stale_timeout
        )
        return {
            "active_subscriptions": active,
            "stale_subscriptions": stale,
            "total_created": self._total_created,
            "total_removed": self._total_removed,
            "total_stale_cleaned": self._total_stale_cleaned,
            "config": {
                "heartbeat_interval": self._config.heartbeat_interval,
                "stale_timeout": self._config.stale_timeout,
                "max_per_client": self._config.max_subscriptions_per_client,
            },
        }

    # -- Background cleanup --------------------------------------------------

    async def _cleanup_loop(self) -> None:
        """Periodically remove stale subscriptions."""
        try:
            while self._running:
                await asyncio.sleep(self._config.heartbeat_interval)
                if self._running:
                    await self._cleanup_stale()
        except asyncio.CancelledError:
            return

    async def _cleanup_stale(self) -> None:
        """Remove subscriptions that haven't sent a heartbeat in time."""
        stale_ids = [
            sid
            for sid, sub in self._subscriptions.items()
            if sub.heartbeat_age_seconds > self._config.stale_timeout
        ]
        for sid in stale_ids:
            await self.remove(sid)
            self._total_stale_cleaned += 1
            logger.info("Cleaned up stale subscription %s", sid)


__all__ = [
    "ManagedSubscription",
    "SubscriptionManager",
    "SubscriptionManagerConfig",
]
