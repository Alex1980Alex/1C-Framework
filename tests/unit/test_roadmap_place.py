"""Tests for scripts/roadmap_place.py — reproducible roadmap-placement heuristic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "roadmap_place.py"
_spec = importlib.util.spec_from_file_location("roadmap_place", _SCRIPT)
rp = importlib.util.module_from_spec(_spec)
sys.modules["roadmap_place"] = rp
_spec.loader.exec_module(rp)


def test_date_key():
    assert rp._date_key("260718_ROADMAP_X.md") == 260718
    assert rp._date_key("no-date.md") == 0


def test_rank_orders_by_matched_then_hits_then_date():
    files = {
        "260101_A.md": "qa_run qa_run codepilot",  # 2 terms, 3 hits
        "260202_B.md": "qa_run only here",  # 1 term, 1 hit
        "250101_C.md": "unrelated",  # 0 terms → excluded
    }
    out = rp.rank(files, ["qa_run", "codepilot"])
    assert [c["name"] for c in out] == ["260101_A.md", "260202_B.md"]
    assert out[0]["n_matched"] == 2 and out[0]["hits"] == 3
    assert all(c["n_matched"] > 0 for c in out)  # zero-match excluded


def test_rank_tiebreak_by_date():
    files = {
        "260101_old.md": "qa_run",
        "260718_new.md": "qa_run",  # same n_matched+hits → newer wins
    }
    out = rp.rank(files, ["qa_run"])
    assert out[0]["name"] == "260718_new.md"


def test_best_sections_tracks_heading_unique():
    text = "# Top\nintro\n## S1\nline with qa_run here\nmore\n## S2\nqa_run again\n## S3\nqa_run"
    secs = rp.best_sections(text, ["qa_run"], k=3)
    assert secs == ["S1", "S2", "S3"]


def test_best_sections_k_limit_and_no_heading():
    assert rp.best_sections("qa_run before any heading", ["qa_run"]) == []
    text = "## A\nqa_run\n## B\nqa_run\n## C\nqa_run"
    assert rp.best_sections(text, ["qa_run"], k=2) == ["A", "B"]


def test_suggest_create_when_no_candidates():
    assert rp.suggest([], ["x"])["action"] == "create"


def test_suggest_attach_when_two_terms_matched():
    cands = [{"name": "260718_X.md", "n_matched": 2, "hits": 5, "date": 260718}]
    s = rp.suggest(cands, ["a", "b"])
    assert s["action"] == "attach" and s["target"] == "260718_X.md"


def test_suggest_attach_single_strong_term():
    cands = [{"name": "260718_X.md", "n_matched": 1, "hits": 3, "date": 260718}]
    assert rp.suggest(cands, ["a"])["action"] == "attach"


def test_suggest_weak_link_attach_or_create():
    cands = [{"name": "260718_X.md", "n_matched": 1, "hits": 1, "date": 260718}]
    assert rp.suggest(cands, ["a", "b", "c"])["action"] == "attach_or_create"


def test_live_qa_run_attaches_to_1c_tooling_audit():
    """End-to-end on the real roadmap dir: qa_* lineage → 260718_1C_TOOLING_AUDIT."""
    if not rp.ROADMAP_DIR.is_dir():
        pytest.skip("roadmap dir absent")
    files = {
        p.name: p.read_text(encoding="utf-8", errors="replace") for p in rp.ROADMAP_DIR.glob("*.md")
    }
    cands = rp.rank(files, ["qa_run", "codepilot", "getThickClientInfo"])
    assert cands, "expected at least one candidate"
    assert "260718_ROADMAP_1C_TOOLING_AUDIT" in cands[0]["name"]
    assert rp.suggest(cands, ["qa_run", "codepilot", "getThickClientInfo"])["action"] == "attach"
