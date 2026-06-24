"""Unit: scripts/ecosystem_scan (ADR-039 V2) — чистое ядро build_ranked / to_markdown / _relevance.

Тестируется БЕЗ сети (синтетические items). Сеть (fetch_*) изолирована и здесь не вызывается.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_IMPORT_OK = True
try:
    _spec = importlib.util.spec_from_file_location(
        "ecosystem_scan", _ROOT / "scripts" / "ecosystem_scan.py"
    )
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
except Exception:
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="ecosystem_scan import failed"),
]


def _items():
    return [
        {
            "source": "GitHub",
            "title": "langgraph orchestration toolkit",
            "url": "u1",
            "engagement": 40,
        },
        {"source": "HN", "title": "LangGraph orchestration patterns", "url": "u2", "engagement": 5},
        {
            "source": "Reddit/r/x",
            "title": "unrelated cooking recipes",
            "url": "u3",
            "engagement": 999,
        },
    ]


def test_build_ranked_filters_irrelevant_despite_engagement():
    r = _m.build_ranked("langgraph orchestration", _items(), top=10, min_relevance=0.5)
    titles = [it["title"] for it in r]
    assert r  # релевантные есть
    assert all("cooking" not in t for t in titles)  # eng=999, но нерелевантное отсеяно
    assert "blended" in r[0]


def test_build_ranked_dedup_cross_source_keeps_max():
    dup = [
        {"source": "HN", "title": "LangGraph Orchestration Patterns", "url": "a", "engagement": 5},
        {
            "source": "GitHub",
            "title": "langgraph orchestration patterns",
            "url": "b",
            "engagement": 50,
        },
    ]
    r = _m.build_ranked("langgraph orchestration patterns", dup, min_relevance=0.5)
    assert len(r) == 1  # один тайтл из 2 источников → схлопнут
    assert r[0]["engagement"] == 50  # оставлен максимум по blended


def test_build_ranked_empty_when_nothing_relevant():
    items = [{"source": "HN", "title": "cooking pasta", "url": "u", "engagement": 10}]
    assert _m.build_ranked("quantum embeddings", items, min_relevance=0.5) == []


def test_to_markdown_empty():
    assert "Ничего" in _m.to_markdown("x", [], 30)


def test_to_markdown_lists_items():
    md = _m.to_markdown(
        "q", [{"source": "HN", "title": "T", "url": "U", "engagement": 3, "blended": 0.5}], 30
    )
    assert "[HN]" in md and "U" in md and "engagement=3" in md


def test_relevance_high_vs_low():
    variants = (
        _m.expand_queries("langgraph orchestration")
        if _m.HAS_ENGAGEMENT
        else ["langgraph orchestration"]
    )
    high = _m._relevance(variants, "langgraph orchestration guide")
    low = _m._relevance(variants, "totally different unrelated topic")
    assert high > low
