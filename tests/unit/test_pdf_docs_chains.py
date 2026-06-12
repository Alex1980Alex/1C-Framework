"""Unit-цепочки pdf-docs (roadmap 260612 P1, тест-карта §3 блок A).

Детерминированные функции БЕЗ Qdrant/TEI:
- A2 payload-контракт wiki-точки (`wiki_page_payload` / `wiki_page_point_id`)
- A3 alias-резолюция (`resolve_physical_collection` на fake-клиенте)
- A5 MRL truncate query/passage путей (`maybe_truncate_vectors`, `truncate_renorm`)

Live-слой (A1 index_pdf, A2 re-run, A5 dim-проба против Qdrant) — процедурные
прогоны, вердикты в §18 роадмапа.
"""

from __future__ import annotations

import math
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# CI unit-job ставит только .[dev,morphology] — qdrant_client отсутствует,
# а scripts/eval_* импортируют его на module-level → collection error.
pytest.importorskip("qdrant_client")

from scripts.eval_hermes_phase4 import wiki_page_payload, wiki_page_point_id
from scripts.eval_pdf_docs_golden import truncate_renorm
from src.framework_search.indexer import (
    maybe_truncate_vectors,
    resolve_physical_collection,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# A2 — payload-контракт wiki-точки
# ---------------------------------------------------------------------------


class TestWikiPayloadContract:
    RAW = '---\nentity_type: "Module"\nother: 1\n---\nТело про [[Цель|якорь]] и [[ПрямаяСсылка]].'

    def test_contract_fields(self):
        p = wiki_page_payload(self.RAW, "ОбщийМодуль", "docs/wiki/entities/x.md")
        assert p is not None
        assert set(p.keys()) == {"name", "entity_type", "text", "file_path"}
        assert p["name"] == "ОбщийМодуль"
        assert p["entity_type"] == "Module"
        assert p["file_path"] == "docs/wiki/entities/x.md"

    def test_frontmatter_stripped_wikilinks_unwrapped(self):
        p = wiki_page_payload(self.RAW, "s", "p")
        assert p is not None
        assert "entity_type:" not in p["text"]
        assert "[[" not in p["text"]
        assert "якорь" in p["text"]
        assert "ПрямаяСсылка" in p["text"]

    def test_empty_page_returns_none(self):
        assert wiki_page_payload("---\nfoo: 1\n---\n   \n", "s", "p") is None
        assert wiki_page_payload("", "s", "p") is None

    def test_text_capped_2000(self):
        p = wiki_page_payload("x" * 5000, "s", "p")
        assert p is not None
        assert len(p["text"]) == 2000


class TestWikiPointIdIdempotency:
    def test_deterministic(self):
        assert wiki_page_point_id("Page") == wiki_page_point_id("Page")

    def test_distinct_pages_distinct_ids(self):
        assert wiki_page_point_id("PageA") != wiki_page_point_id("PageB")

    def test_uuid5_url_namespace(self):
        # Контракт со старым индексером: те же id, что у точек в продакшн-коллекции
        assert wiki_page_point_id("Page") == str(uuid.uuid5(uuid.NAMESPACE_URL, "Page"))


# ---------------------------------------------------------------------------
# A3 — alias-резолюция
# ---------------------------------------------------------------------------


def _fake_client(alias_pairs: list[tuple[str, str]], fail: bool = False):
    def get_aliases():
        if fail:
            raise ConnectionError("qdrant down")
        return SimpleNamespace(
            aliases=[
                SimpleNamespace(alias_name=a, collection_name=c) for a, c in alias_pairs
            ]
        )

    return SimpleNamespace(get_aliases=get_aliases)


class TestAliasResolution:
    def test_alias_resolves_to_physical(self):
        client = _fake_client([("pdf_documents", "pdf_documents_mrl_1024")])
        assert resolve_physical_collection(client, "pdf_documents") == "pdf_documents_mrl_1024"

    def test_non_alias_passthrough(self):
        client = _fake_client([("pdf_documents", "pdf_documents_mrl_1024")])
        assert resolve_physical_collection(client, "wiki_pages_v1") == "wiki_pages_v1"

    def test_qdrant_down_fail_soft_passthrough(self):
        client = _fake_client([], fail=True)
        assert resolve_physical_collection(client, "pdf_documents") == "pdf_documents"


# ---------------------------------------------------------------------------
# A5 — MRL truncate (passage-путь индексера + query-путь eval-раннера)
# ---------------------------------------------------------------------------


def _l2(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


class TestMrlTruncatePassagePath:
    def test_truncates_and_renorms(self):
        vec = [1.0] * 4096
        out = maybe_truncate_vectors([vec], 1024)
        assert len(out[0]) == 1024
        assert _l2(out[0]) == pytest.approx(1.0, abs=1e-5)

    def test_short_vector_noop(self):
        vec = [0.5] * 1024
        out = maybe_truncate_vectors([vec], 1024)
        assert out[0] == vec  # не пере-нормирует уже короткий вектор

    def test_zero_vector_no_nan(self):
        out = maybe_truncate_vectors([[0.0] * 4096], 1024)
        assert all(x == 0.0 for x in out[0])


class TestDocsFreshness:
    """P3.2 staleness-метрика (compute_docs_freshness, pure)."""

    def test_fresh_and_stale(self):
        from datetime import datetime

        from src.memory.maintenance.dashboard import compute_docs_freshness

        now = datetime.fromisoformat("2026-06-12T12:00:00+03:00")
        out = compute_docs_freshness(
            {
                "pdf_documents": "2026-05-22T01:00:00+03:00",  # 21.5d
                "wiki_pages_v1": "2026-04-01T00:00:00+03:00",  # 72d
            },
            {"pdf_documents": 830, "wiki_pages_v1": 2822},
            now=now,
            max_age_days=30,
        )
        assert out["pdf_documents"]["stale"] is False
        assert out["pdf_documents"]["age_days"] == pytest.approx(21.5, abs=0.1)
        assert out["wiki_pages_v1"]["stale"] is True
        assert out["pdf_documents"]["points"] == 830

    def test_missing_run_end_is_stale(self):
        from datetime import datetime

        from src.memory.maintenance.dashboard import compute_docs_freshness

        out = compute_docs_freshness(
            {"wiki_pages_v1": None},
            {},
            now=datetime(2026, 6, 12),
        )
        assert out["wiki_pages_v1"]["stale"] is True
        assert out["wiki_pages_v1"]["age_days"] is None
        assert out["wiki_pages_v1"]["points"] is None

    def test_malformed_timestamp_is_stale(self):
        from datetime import datetime

        from src.memory.maintenance.dashboard import compute_docs_freshness

        out = compute_docs_freshness(
            {"pdf_documents": "not-a-date"},
            {"pdf_documents": 1},
            now=datetime(2026, 6, 12),
        )
        assert out["pdf_documents"]["stale"] is True


class TestMrlTruncateQueryPath:
    def test_truncates_and_renorms(self):
        vec = [float(i % 7) for i in range(4096)]
        out = truncate_renorm(vec, 1024)
        assert len(out) == 1024
        assert _l2(out) == pytest.approx(1.0, abs=1e-5)

    def test_query_passage_paths_agree(self):
        """Запросный (eval) и пассажный (индексер) MRL-пути дают один вектор —
        защита от дрейфа двух реализаций truncate+renorm."""
        vec = [float(i % 13) - 6.0 for i in range(4096)]
        q = truncate_renorm(vec, 1024)
        p = maybe_truncate_vectors([vec], 1024)[0]
        assert q == pytest.approx(p, abs=1e-6)
