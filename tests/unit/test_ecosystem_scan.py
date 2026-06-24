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
    assert len(r) == 1  # один тайтл из 2 источников → схлопнут (cross-source dedup)
    # per-source нормировка: топ каждого источника → eng_norm=1.0 → blended tie; семантика
    # «keeps-max» покрыта test_engagement_rank::test_dedup_by_entity_keeps_best


def test_per_source_normalization_prevents_domination():
    # GitHub-звёзды (1000) НЕ должны топить релевантный HN (eng 2): per-source норма → оба eng_norm=1.0
    items = [
        {
            "source": "GitHub",
            "title": "langgraph orchestration toolkit",
            "url": "g",
            "engagement": 1000,
        },
        {
            "source": "HN",
            "title": "langgraph orchestration discussion",
            "url": "h",
            "engagement": 2,
        },
    ]
    r = _m.build_ranked("langgraph orchestration", items, top=10, min_relevance=0.5)
    assert {it["source"] for it in r} == {"GitHub", "HN"}  # оба источника представлены
    # топ каждого источника получил eng_norm=1.0 → balls близкие (не доминирование звёздами)
    assert all(abs(it["blended"] - r[0]["blended"]) < 0.2 for it in r)


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


def test_query_weights_by_type():
    # #3 query-adaptive: precision (ошибка/версия) → релевантность важнее
    assert _m._query_weights("rankify ImportError fix") == (0.85, 0.15)
    assert _m._query_weights("django 4.2 upgrade") == (0.85, 0.15)
    # discovery (best/trending/2026) → популярность важнее
    assert _m._query_weights("best RAG framework 2026") == (0.5, 0.5)
    # нейтрально → дефолт
    assert _m._query_weights("langgraph memory") == (0.7, 0.3)


def test_map_query_to_tags():
    # #1 query→tag: синонимы сводятся к каноническому тегу
    assert _m._map_query_to_tags("langgraph memory agent") == ["ai"]
    assert _m._map_query_to_tags("rust async runtime") == ["rust"]
    # нет совпадения тега → пусто (источник пропускается, не зашумляем generic-лентой)
    assert _m._map_query_to_tags("гкс печать ттн снятие") == []
    # ограничение количества тегов
    assert len(_m._map_query_to_tags("python rust go java", limit=2)) == 2


def test_cache_roundtrip_and_ttl(tmp_path):
    # #4 кеш: save → load round-trip + TTL
    p = tmp_path / "scan.json"
    items = [{"source": "HN", "title": "T", "url": "U", "engagement": 3, "blended": 0.5}]
    _m._cache_save(p, "q", 30, items)
    assert p.exists()
    assert _m._cache_load(p, ttl_hours=12.0) == items  # свежий → hit
    assert _m._cache_load(p, ttl_hours=0.0) is None  # TTL=0 → протух
    assert _m._cache_load(tmp_path / "nope.json", 12.0) is None  # нет файла → None
