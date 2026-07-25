"""Unit: scripts/onec_search (ADR-040 Ф1-4) — пайплайн без сети/браузера (monkeypatch _http/_infostart_engagement)."""

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
        "onec_search", _ROOT / "scripts" / "onec_search.py"
    )
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
except Exception:
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="onec_search import failed"),
]


def test_search_searxng_parses(monkeypatch):
    monkeypatch.setattr(
        _m,
        "_http",
        lambda *a, **k: {
            "results": [
                {"title": "T1", "url": "u1", "content": "c1", "engine": "yandex"},
                {"title": "", "url": "u2"},
            ]
        },
    )
    r = _m.search_searxng("q", limit=10)
    assert len(r) == 1 and r[0]["engine"] == "yandex" and r[0]["url"] == "u1"


def test_search_searxng_graceful_when_down(monkeypatch):
    monkeypatch.setattr(_m, "_http", lambda *a, **k: None)
    assert _m.search_searxng("q") == []


def test_rerank_reorders_by_score(monkeypatch):
    items = [{"title": "A", "content": ""}, {"title": "B", "content": ""}]
    monkeypatch.setattr(
        _m, "_http", lambda *a, **k: [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.1}]
    )
    r = _m.rerank_tei("q", items, top=10)
    assert [x["title"] for x in r] == ["B", "A"] and r[0]["rerank_score"] == 0.9


def test_rerank_graceful_when_tei_down(monkeypatch):
    items = [{"title": "A", "content": ""}, {"title": "B", "content": ""}]
    monkeypatch.setattr(_m, "_http", lambda *a, **k: None)
    r = _m.rerank_tei("q", items, top=10)
    assert [x["title"] for x in r] == ["A", "B"] and r[0]["rerank_score"] is None


def test_rerank_empty():
    assert _m.rerank_tei("q", [], top=5) == []


def test_to_markdown_empty():
    assert "Ничего" in _m.to_markdown("x", [])


def test_to_markdown_lists():
    md = _m.to_markdown("q", [{"title": "T", "url": "U", "engine": "bing", "rerank_score": 0.5}])
    assert "[bing]" in md and "U" in md and "score=0.5" in md


def test_rrf_fuse_combines_and_dedups():
    l1 = [{"title": "A", "url": "ua"}, {"title": "B", "url": "ub"}]
    l2 = [{"title": "B", "url": "ub"}, {"title": "C", "url": "uc"}]
    fused = _m._rrf_fuse([l1, l2])
    urls = [it["url"] for it in fused]
    assert urls[0] == "ub" and set(urls) == {"ua", "ub", "uc"}
    assert all("rrf_score" in it for it in fused)


def test_rrf_fuse_empty():
    assert _m._rrf_fuse([]) == []
    assert _m._rrf_fuse([[]]) == []


def test_search_fusion_multi_query(monkeypatch):
    monkeypatch.setattr(_m, "_HAS_ENGAGEMENT", True)
    monkeypatch.setattr(_m, "expand_queries", lambda q, **k: [q, q + " вариант"])
    calls = {"n": 0}

    def fake_searx(query, **kw):
        calls["n"] += 1
        return [{"title": f"R{calls['n']}", "url": f"u{calls['n']}", "content": ""}]

    monkeypatch.setattr(_m, "search_searxng", fake_searx)
    monkeypatch.setattr(_m, "rerank_tei", lambda q, items, top=10: items[:top])
    r = _m.search("тест", top=5)
    assert calls["n"] == 2 and len(r) >= 1


def test_search_no_fusion_single_query(monkeypatch):
    calls = {"n": 0}

    def fake_searx(query, **kw):
        calls["n"] += 1
        return [{"title": "R", "url": "u", "content": ""}]

    monkeypatch.setattr(_m, "search_searxng", fake_searx)
    monkeypatch.setattr(_m, "rerank_tei", lambda q, items, top=10: items[:top])
    _m.search("тест", top=5, fusion=False)
    assert calls["n"] == 1


def test_parse_infostart_views():
    # Ф4: разметка Infostart <p class=properties><b>Просмотры</b> <i>N</i>
    html = '<div class="title">Статистика:</div><p class="properties"><b>Просмотры</b> <i>16905</i></p>'
    assert _m._parse_infostart_views(html) == 16905
    assert _m._parse_infostart_views("<p>нет статистики</p>") is None


def test_enrich_engagement_blends_infostart(monkeypatch):
    # Ф4: infostart-items получают views + blended (relevance x engagement)
    monkeypatch.setattr(_m, "_HAS_ENGAGEMENT", True)
    monkeypatch.setattr(
        _m, "_infostart_engagement", lambda url: {"a": 100, "b": 10000}.get(url.rsplit("/", 1)[-1])
    )
    ranked = [
        {"title": "A", "url": "https://infostart.ru/x/a", "rerank_score": 0.6},
        {"title": "B", "url": "https://infostart.ru/x/b", "rerank_score": 0.55},
    ]
    out = _m._enrich_engagement(ranked, top_k=5)
    assert all("blended" in it for it in out)
    assert {it.get("views") for it in out} == {100, 10000}


def test_enrich_engagement_no_views_unchanged(monkeypatch):
    monkeypatch.setattr(_m, "_HAS_ENGAGEMENT", True)
    monkeypatch.setattr(_m, "_infostart_engagement", lambda url: None)
    ranked = [{"title": "A", "url": "https://infostart.ru/x/a", "rerank_score": 0.6}]
    assert _m._enrich_engagement(ranked) == ranked


def test_enrich_engagement_skips_non_infostart(monkeypatch):
    monkeypatch.setattr(_m, "_HAS_ENGAGEMENT", True)
    calls = {"n": 0}

    def fake_eng(url):
        calls["n"] += 1
        return 500

    monkeypatch.setattr(_m, "_infostart_engagement", fake_eng)
    ranked = [{"title": "G", "url": "https://github.com/x", "rerank_score": 0.7}]
    _m._enrich_engagement(ranked)
    assert calls["n"] == 0  # не-infostart не рендерится
