"""Unit: onec_search authority×recency (ADR-040 B) — trust-tiers + recency, без сети."""

import importlib.util
import sys
from datetime import UTC
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_spec = importlib.util.spec_from_file_location("onec_search", _ROOT / "scripts" / "onec_search.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)

pytestmark = pytest.mark.unit


def test_source_trust_tiers():
    assert _m._source_trust("https://its.1c.ru/db/x") == 1.0
    assert _m._source_trust("https://v8.1c.ru/platforma/x") == 1.0
    assert _m._source_trust("https://infostart.ru/1c/articles/1") == 0.9
    assert (
        _m._source_trust("https://forum.infostart.ru/forum9/topic1") == 0.8
    )  # специфичнее infostart.ru
    assert _m._source_trust("https://random-blog.ru/x") == 0.7


def test_recency_boost():
    from datetime import datetime, timezone

    recent = datetime.now(UTC).replace(microsecond=0).isoformat()
    assert _m._recency_boost({"published": recent}) == 0.30
    assert _m._recency_boost({"published": "2010-01-01T00:00:00+00:00"}) == 0.0
    assert _m._recency_boost({"title": "Новинка 2026 года"}) == 0.10  # год-фоллбэк
    assert _m._recency_boost({"title": "без даты и года"}) == 0.0


def test_apply_authority_recency_resorts():
    # одинаковая relevance, но доверенный (its.1c.ru) поднимается над блогом
    ranked = [
        {"title": "blog", "url": "https://blog.ru/x", "rerank_score": 0.8},
        {"title": "vendor", "url": "https://its.1c.ru/db/x", "rerank_score": 0.8},
    ]
    out = _m._apply_authority_recency(ranked)
    assert out[0]["url"].startswith("https://its.1c.ru")  # доверенный источник выше
    assert all("final" in it and "trust" in it for it in out)


def test_apply_authority_recency_no_mutation():
    ranked = [{"title": "a", "url": "https://its.1c.ru/x", "rerank_score": 0.5}]
    _m._apply_authority_recency(ranked)
    assert "final" not in ranked[0]  # вход не мутирован
