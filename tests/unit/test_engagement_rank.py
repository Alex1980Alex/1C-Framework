"""Unit: shared/engagement_rank (ADR-039) — expand_queries / blended_score / rank_items / dedup.

Чистые stdlib-функции (приём из last30days-skill): расширение запросов, слияние
relevance×engagement, дедуп по сущности. Тестируются без сети/зависимостей.
"""

import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_IMPORT_OK = True
try:
    from shared.engagement_rank import (
        blended_score,
        dedup_by_entity,
        expand_queries,
        rank_items,
    )
except Exception:
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="engagement_rank import failed"),
]


def test_expand_queries_basic():
    out = expand_queries("LangGraph multi-agent orchestration", max_variants=4)
    assert out[0] == "LangGraph multi-agent orchestration"  # оригинал первым
    assert len(out) <= 4 and len(out) == len(set(out))  # cap + дедуп
    assert any("langgraph" in v for v in out)  # lower-вариант присутствует


def test_expand_queries_empty_and_extra():
    assert expand_queries("") == []
    out = expand_queries("RAG", extra_terms=["2026"], max_variants=4)
    assert any("RAG 2026" == v for v in out)


def test_blended_relevance_only_equals_weight():
    # engagement=0 → blended = w_relevance * relevance
    assert blended_score(1.0, 0, w_relevance=0.7, w_engagement=0.3) == 0.7
    assert blended_score(0.5, 0) == round(0.7 * 0.5, 4)


def test_blended_clamps_and_engagement_boost():
    assert blended_score(1.5, 0) == 0.7  # relevance клампится в 1.0
    low = blended_score(0.5, 0)
    high = blended_score(0.5, 50, engagement_cap=50)  # eng насыщает → +0.3
    assert high > low
    assert high == round(0.7 * 0.5 + 0.3 * 1.0, 4)


def test_rank_items_engagement_changes_order():
    items = [
        {"id": "A", "relevance": 0.80, "engagement": 0},
        {"id": "B", "relevance": 0.75, "engagement": 50},
    ]
    ranked = rank_items(items, engagement_cap=50)
    # при relevance-only A>B; с блендом популярный B обгоняет A
    assert ranked[0]["id"] == "B"
    assert ranked[0]["blended"] > ranked[1]["blended"]
    assert items[0].get("blended") is None  # входные не мутируются (копии)


def test_dedup_by_entity_keeps_best():
    items = [
        {"e": "x", "blended": 0.5},
        {"e": "x", "blended": 0.8},
        {"e": "y", "blended": 0.6},
    ]
    out = dedup_by_entity(items, lambda it: it["e"])
    assert [it["e"] for it in out] == ["x", "y"]  # отсортировано по score убыв.
    assert out[0]["blended"] == 0.8  # из дублей x остался максимум


def test_dedup_none_key_stays_unique():
    items = [{"blended": 0.5}, {"blended": 0.7}]
    out = dedup_by_entity(items, lambda it: None)  # неключуемые → не схлопываются
    assert len(out) == 2


def test_dedup_entity_key_raises_keeps_unique():
    items = [{"blended": 0.5}, {"blended": 0.7}]

    def boom(_it):
        raise ValueError("boom")

    out = dedup_by_entity(items, boom)  # исключение в ключе → fallback на уникальность
    assert len(out) == 2
