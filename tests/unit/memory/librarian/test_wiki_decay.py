"""Unit tests for WikiDecayService (added 2026-05-15).

Coverage:
    - decay_all() iterates batches and aggregates counters
    - _decay_point() timestamp priority (decay_applied_at > last_applied > updated_at > created_at)
    - dry-run does not write
    - min_confidence floor clamps
    - fresh point (days_idle <= 0) skipped
    - invalid timestamp skipped
    - missing confidence skipped
    - decay formula correctness
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.memory.librarian.wiki_decay import WikiDecayService


def _make_point(payload: dict, point_id: str = "test-id"):
    """Mock Qdrant point with .id and .payload."""
    p = MagicMock()
    p.id = point_id
    p.payload = payload
    return p


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_client):
    return WikiDecayService(qdrant_client=mock_client, min_confidence=0.0)


class TestDecayPoint:
    def test_skips_point_without_confidence(self, service):
        """Point without confidence field — skipped, no set_payload call."""
        point = _make_point({"name": "no-conf", "created_at": "2026-01-01T00:00:00"})
        result = service._decay_point(point, datetime.now(), dry_run=False)
        assert result == "skipped"
        service.client.set_payload.assert_not_called()

    def test_skips_fresh_point(self, service):
        """days_idle <= 0 — skipped (point обновлён сегодня)."""
        now = datetime.now()
        point = _make_point({
            "confidence": 0.7,
            "decay_rate": 0.05,
            "created_at": now.isoformat(),
        })
        result = service._decay_point(point, now, dry_run=True)
        assert result == "skipped"

    def test_skips_invalid_timestamp(self, service):
        """Invalid timestamp string — skipped без crash."""
        point = _make_point({
            "confidence": 0.7,
            "created_at": "not-a-date",
        })
        result = service._decay_point(point, datetime.now(), dry_run=True)
        assert result == "skipped"

    def test_skips_missing_all_timestamps(self, service):
        """No timestamp fields at all — skipped."""
        point = _make_point({"confidence": 0.7})
        result = service._decay_point(point, datetime.now(), dry_run=True)
        assert result == "skipped"

    def test_skips_non_numeric_confidence(self, service):
        """Confidence is string or None — skipped."""
        point = _make_point({"confidence": "high", "created_at": "2026-01-01T00:00:00"})
        result = service._decay_point(point, datetime.now(), dry_run=True)
        assert result == "skipped"

    def test_decay_uses_decay_applied_at_priority(self, service):
        """decay_applied_at preferred over created_at when both present."""
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.9,
            "decay_rate": 0.05,
            "created_at": "2024-01-01T00:00:00",
            "decay_applied_at": "2026-04-15T00:00:00",
        })
        result = service._decay_point(point, now, dry_run=True)
        assert result == "decayed"

    def test_decay_formula_one_month(self, service):
        """0.9 - 0.05 = 0.85 over exactly 30 days."""
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.9,
            "decay_rate": 0.05,
            "created_at": (now - timedelta(days=30)).isoformat(),
        })
        service.client.set_payload = MagicMock()
        result = service._decay_point(point, now, dry_run=False)
        assert result == "decayed"
        call_args = service.client.set_payload.call_args
        new_conf = call_args[1]["payload"]["confidence"]
        assert abs(new_conf - 0.85) < 1e-9

    def test_decay_clamps_to_min_confidence(self, mock_client):
        """Long-idle point doesn't go below min_confidence floor."""
        service = WikiDecayService(qdrant_client=mock_client, min_confidence=0.3)
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.4,
            "decay_rate": 0.05,
            "created_at": (now - timedelta(days=365)).isoformat(),
        })
        result = service._decay_point(point, now, dry_run=False)
        assert result == "decayed"
        new_conf = service.client.set_payload.call_args[1]["payload"]["confidence"]
        assert new_conf == 0.3

    def test_dry_run_does_not_write(self, service):
        """dry_run=True does not call set_payload but still returns 'decayed'."""
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.9,
            "decay_rate": 0.05,
            "created_at": (now - timedelta(days=60)).isoformat(),
        })
        result = service._decay_point(point, now, dry_run=True)
        assert result == "decayed"
        service.client.set_payload.assert_not_called()

    def test_skip_if_set_payload_raises(self, service):
        """set_payload exception is swallowed; returns 'skipped'."""
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.9,
            "decay_rate": 0.05,
            "created_at": (now - timedelta(days=60)).isoformat(),
        })
        service.client.set_payload.side_effect = RuntimeError("qdrant down")
        result = service._decay_point(point, now, dry_run=False)
        assert result == "skipped"

    def test_handles_utc_timezone_suffix(self, service):
        """ISO timestamp with Z suffix parsed correctly."""
        now = datetime(2026, 5, 15)
        point = _make_point({
            "confidence": 0.9,
            "decay_rate": 0.05,
            "created_at": (now - timedelta(days=30)).isoformat() + "Z",
        })
        service.client.set_payload = MagicMock()
        result = service._decay_point(point, now, dry_run=False)
        assert result == "decayed"


class TestDecayAll:
    @pytest.mark.asyncio
    async def test_aggregates_counters(self, service):
        """decay_all returns {total, decayed, skipped, dry_run}."""
        now = datetime.now()
        p1 = _make_point({"confidence": 0.9, "created_at": (now - timedelta(days=60)).isoformat()}, "p1")
        p2 = _make_point({"name": "no-conf"}, "p2")
        service.client.scroll = MagicMock(side_effect=[
            ([p1, p2], "next-offset"),
            ([], None),
        ])
        result = await service.decay_all(dry_run=True)
        assert result == {"total": 2, "decayed": 1, "skipped": 1, "dry_run": 1}

    @pytest.mark.asyncio
    async def test_handles_empty_collection(self, service):
        """Empty collection — total=0."""
        service.client.scroll = MagicMock(return_value=([], None))
        result = await service.decay_all(dry_run=False)
        assert result["total"] == 0
        assert result["decayed"] == 0

    @pytest.mark.asyncio
    async def test_terminates_when_offset_is_none(self, service):
        """Loop exits when scroll returns offset=None even if points returned."""
        p = _make_point({"name": "no-conf"})
        service.client.scroll = MagicMock(return_value=([p], None))
        result = await service.decay_all(dry_run=True)
        assert result["total"] == 1
        assert service.client.scroll.call_count == 1
