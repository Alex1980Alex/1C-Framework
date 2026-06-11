"""Quick fixes F5 + F13 — roadmap 260611 P3 (+ §18 live re-run follow-ups).

F5: ``_pattern_from_payload`` maps ``expired_at`` payload → model, so
``get_pattern`` no longer answers ``archived:true`` with ``expired_at:null``.

F13: WikiPromoter is idempotent — promotion stamps ``promoted_to`` on the
source point (the marker finally has a writer), re-runs pre-filter on it, and
``_append_log`` skips drafts already mentioned in log.md.

Cold-start warmup (§18 live re-run finding): ``_warmup_qdrant`` pre-pays the
qdrant_client import at server start (fail-soft), and ``_get_qdrant`` lazy
init is lock-guarded against the warmup thread racing the first tool call.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("qdrant_client")

from src.memory.librarian.wiki_promoter import WikiPromoter
from src.memory.vector_memory.server import _pattern_from_payload

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# F5 — expired_at mapping
# ---------------------------------------------------------------------------


def test_pattern_from_payload_maps_expired_at():
    base = {"pattern_type": "code-convention", "content": "x", "confidence": 0.5}
    archived = _pattern_from_payload("pid", {**base, "expired_at": "2026-06-01T00:00:00"})
    assert archived.expired_at is not None
    assert archived.expired_at.isoformat().startswith("2026-06-01")

    live = _pattern_from_payload("pid", base)
    assert live.expired_at is None


# ---------------------------------------------------------------------------
# F13 — idempotent promotion
# ---------------------------------------------------------------------------


class _FakeQdrant:
    """Just enough of the qdrant client for scan_and_promote."""

    def __init__(self, payloads: dict[str, dict]):
        self.payloads = payloads

    def scroll(self, collection_name, scroll_filter, with_payload, with_vectors, limit):
        points = [
            SimpleNamespace(id=pid, payload=dict(pl), vector=[0.5] * 8)
            for pid, pl in self.payloads.items()
        ]
        return points, None

    def query_points(self, collection_name, query, limit, with_payload):
        return SimpleNamespace(points=[])  # no similar neighbours

    def set_payload(self, collection_name, payload, points):
        for pid in points:
            self.payloads[pid].update(payload)


def _promotable_payload(name: str) -> dict:
    return {
        "pattern_type": "code-convention",
        "name": name,
        "content": "always frobnicate the widget",
        "description": "test",
        "confidence": 0.95,
        "application_count": 20,
        "updated_at": datetime.now().isoformat(),
        "tags": [],
    }


def _promoter(tmp_path, client) -> WikiPromoter:
    log = tmp_path / "log.md"
    log.write_text("# Wiki Log\n", encoding="utf-8")
    return WikiPromoter(
        qdrant_client=client,
        wiki_drafts_dir=tmp_path / "drafts",
        wiki_log_path=log,
    )


async def test_double_promote_is_idempotent(tmp_path):
    client = _FakeQdrant({"pt1": _promotable_payload("Frobnicate Widget")})
    wp = _promoter(tmp_path, client)

    first = await wp.scan_and_promote()
    assert first == ["frobnicate-widget"]
    # The marker now has a writer (F13 layer 1).
    assert client.payloads["pt1"]["promoted_to"] == "frobnicate-widget"

    second = await wp.scan_and_promote()
    assert second == []  # pre-filter on own promoted_to (layer 2)

    log_text = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert log_text.count("docs/wiki/drafts/frobnicate-widget.md") == 1


def test_append_log_skips_existing_mention(tmp_path):
    client = _FakeQdrant({})
    wp = _promoter(tmp_path, client)

    wp._append_log("some-slug", "Some Slug", 0.9)
    wp._append_log("some-slug", "Some Slug", 0.9)  # F13 layer 3: substring dedup

    log_text = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert log_text.count("docs/wiki/drafts/some-slug.md") == 1
