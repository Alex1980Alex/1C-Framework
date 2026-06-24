"""Unit: scripts/onec_search (ADR-040 Фаза 1+2) — пайплайн без сети (monkeypatch _http).

Сеть (SearXNG/TEI) изолирована в _http → подменяется. Тестируется парсинг, rerank-слияние,
graceful-fallback при недоступном TEI, markdown.
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
                {"title": "", "url": "u2"},  # пустой title отбрасывается
            ]
        },
    )
    r = _m.search_searxng("q", limit=10)
    assert len(r) == 1 and r[0]["engine"] == "yandex" and r[0]["url"] == "u1"


def test_search_searxng_graceful_when_down(monkeypatch):
    monkeypatch.setattr(_m, "_http", lambda *a, **k: None)  # SearXNG недоступен
    assert _m.search_searxng("q") == []


def test_rerank_reorders_by_score(monkeypatch):
    items = [{"title": "A", "content": ""}, {"title": "B", "content": ""}]
    monkeypatch.setattr(
        _m, "_http", lambda *a, **k: [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.1}]
    )
    r = _m.rerank_tei("q", items, top=10)
    assert [x["title"] for x in r] == ["B", "A"]  # переранжировано по score
    assert r[0]["rerank_score"] == 0.9


def test_rerank_graceful_when_tei_down(monkeypatch):
    items = [{"title": "A", "content": ""}, {"title": "B", "content": ""}]
    monkeypatch.setattr(_m, "_http", lambda *a, **k: None)  # TEI недоступен
    r = _m.rerank_tei("q", items, top=10)
    assert [x["title"] for x in r] == ["A", "B"]  # исходный порядок SearXNG (fallback)
    assert r[0]["rerank_score"] is None


def test_rerank_empty():
    assert _m.rerank_tei("q", [], top=5) == []


def test_to_markdown_empty():
    assert "Ничего" in _m.to_markdown("x", [])


def test_to_markdown_lists():
    md = _m.to_markdown("q", [{"title": "T", "url": "U", "engine": "bing", "rerank_score": 0.5}])
    assert "[bing]" in md and "U" in md and "score=0.5" in md
