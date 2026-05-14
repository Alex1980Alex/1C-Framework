"""L3 confidence decay service.

Applies time-based linear decay to `confidence` field of learned_patterns
points. Patterns that were once high-confidence but haven't been re-applied
gradually lose confidence — preventing «затвердевшие» drafts from blocking
fresher candidates and counter-balancing the asymmetric +0.02/-0.01 update
in `vector_memory/server.py:handle_apply_pattern`.

Algorithm:
    days_idle = (now - last_applied OR updated_at OR created_at).days
    decay     = decay_rate * (days_idle / 30.0)         # monthly cadence
    new_conf  = max(min_confidence, old_conf - decay)

`decay_rate` is read per-point from payload (default 0.05 if missing).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class WikiDecayService:
    """Apply time-based decay to learned_patterns confidence."""

    DEFAULT_DECAY_RATE = 0.05  # per 30 days
    DEFAULT_BATCH_SIZE = 100

    def __init__(
        self,
        qdrant_client: Any,
        collection_name: str = "learned_patterns",
        min_confidence: float = 0.0,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.client = qdrant_client
        self.collection_name = collection_name
        self.min_confidence = min_confidence
        self.batch_size = batch_size

    async def decay_all(self, dry_run: bool = False) -> dict[str, int]:
        """Apply decay to all points in collection. Returns counters."""
        now = datetime.now()
        decayed = 0
        skipped = 0
        total = 0
        offset = None

        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=self.batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not points:
                break
            for point in points:
                total += 1
                result = self._decay_point(point, now, dry_run)
                if result == "decayed":
                    decayed += 1
                else:
                    skipped += 1
            if offset is None:
                break

        return {
            "total": total,
            "decayed": decayed,
            "skipped": skipped,
            "dry_run": int(dry_run),
        }

    def _decay_point(self, point: Any, now: datetime, dry_run: bool) -> str:
        """Process one point. Returns 'decayed' or 'skipped'."""
        payload = point.payload or {}
        old_conf = payload.get("confidence")
        if old_conf is None or not isinstance(old_conf, (int, float)):
            return "skipped"

        decay_rate = payload.get("decay_rate", self.DEFAULT_DECAY_RATE)

        ts_str = (
            payload.get("last_applied")
            or payload.get("updated_at")
            or payload.get("created_at")
        )
        if not ts_str:
            return "skipped"
        try:
            last_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if last_ts.tzinfo is not None:
                last_ts = last_ts.replace(tzinfo=None)
        except (ValueError, AttributeError):
            return "skipped"

        days_idle = (now - last_ts).days
        if days_idle <= 0:
            return "skipped"

        decay = decay_rate * (days_idle / 30.0)
        new_conf = max(self.min_confidence, old_conf - decay)
        if new_conf >= old_conf:
            return "skipped"

        if not dry_run:
            try:
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload={
                        "confidence": new_conf,
                        "decay_applied_at": now.isoformat(),
                    },
                    points=[point.id],
                )
            except Exception as exc:
                logger.warning("[DECAY] Failed for %s: %s", point.id, exc)
                return "skipped"

        logger.debug(
            "[DECAY] %s: %.3f -> %.3f (idle %d days, rate %.3f)",
            point.id, old_conf, new_conf, days_idle, decay_rate,
        )
        return "decayed"
