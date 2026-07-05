"""Unit tests for the per-skill eval harness (audit 260705 §БП G2), pure logic only.

The live LLM path (run_live) needs providers; here we test the deterministic core
(load_evals discovery, score_output assertions, aggregate delta) with synthetic
completions — no LLM.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "eval_skills", str(_ROOT / "scripts" / "eval_skills.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def test_score_all_expect_present_passes():
    r = MOD.score_output("используй ЗначениеРеквизитаОбъекта", ["ЗначениеРеквизитаОбъекта"], [])
    assert r["passed"] and r["expect_hits"] == 1


def test_score_missing_expect_fails():
    r = MOD.score_output("прямое обращение по ссылке", ["ЗначениеРеквизитаОбъекта"], [])
    assert not r["passed"] and r["expect_hits"] == 0


def test_score_must_not_violation_fails():
    r = MOD.score_output("используй Ссылка.Реквизит", ["Ссылка"], [r"Ссылка\.Реквизит"])
    assert not r["passed"]
    assert r["violations"]


def test_score_case_insensitive_regex():
    r = MOD.score_output("FEAT: добавил", [r"feat|fix"], [])
    assert r["passed"]


def test_aggregate_delta_positive():
    # baseline fails, with-skill passes -> delta +1.0
    per = [
        {"id": "a", "baseline": {"passed": False}, "with_skill": {"passed": True}},
        {"id": "b", "baseline": {"passed": True}, "with_skill": {"passed": True}},
    ]
    agg = MOD.aggregate(per)
    assert agg["baseline_pass"] == 0.5
    assert agg["skill_pass"] == 1.0
    assert agg["delta"] == 0.5
    assert agg["regressions"] == []


def test_aggregate_detects_regression():
    # skill made a passing baseline case fail -> regression recorded
    per = [{"id": "x", "baseline": {"passed": True}, "with_skill": {"passed": False}}]
    agg = MOD.aggregate(per)
    assert agg["delta"] == -1.0
    assert agg["regressions"] == ["x"]


def test_evaluate_offline_end_to_end():
    cases = [{"id": "c1", "prompt": "?", "expect": ["ЗначениеРеквизитаОбъекта"], "must_not": []}]
    completions = {
        "c1": {"baseline": "прямое обращение", "with_skill": "зовём ЗначениеРеквизитаОбъекта"}
    }
    out = MOD.evaluate_offline("body", cases, completions)
    assert out["aggregate"]["delta"] == 1.0  # skill flips fail->pass


def test_load_evals_discovers_pilots():
    got = MOD.load_evals()
    # at least the 3 pilot skills opted in
    assert "code-verify" in got
    assert got["code-verify"]["cases"]
    assert got["code-verify"]["body"]  # SKILL.md body stripped of frontmatter


def test_strip_frontmatter():
    assert MOD._strip_frontmatter("---\nname: x\n---\nbody").strip() == "body"
    assert MOD._strip_frontmatter("no frontmatter") == "no frontmatter"
