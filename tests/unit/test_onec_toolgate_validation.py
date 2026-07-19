"""Unit-тесты валидатора ADR-035 Фазы 1 (scripts/onec_toolgate_validation.py). marker: unit.

Покрытие: collect_metrics — presence_rate per-tool, пороги (MIN_SAMPLES=8, PROMOTE_RATE=0.6),
вердикт promote-candidate/keep-advisory/insufficient-data, агрегированный recommendation,
фильтр окна по ts. Collision-immune (importlib; модуль сам добавляет scripts/ в sys.path).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "onec_toolgate_validation.py"
_spec = importlib.util.spec_from_file_location("onec_toolgate_validation_t", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_NOW = datetime(2026, 6, 25)  # внутри окна 2026-06-22 → 2026-07-06
_TS = "2026-06-23T10:00:00"  # >= WINDOW_START


def _write_events(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps({"ts": _TS, **r}) for r in rows), encoding="utf-8")


def _event(impact=False, debug_trace=False, ref_search=False, config_edit=False) -> dict:
    return {
        "impact": impact,
        "debug_trace": debug_trace,
        "ref_search": ref_search,
        "config_edit": config_edit,
    }


def test_insufficient_data_empty(tmp_path, monkeypatch):
    log = tmp_path / "e.jsonl"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["total_tasks"] == 0
    assert m["recommendation"] == "insufficient-data"
    assert m["per_tool"]["impact"]["verdict"] == "insufficient-data"


def test_insufficient_data_below_min(tmp_path, monkeypatch):
    log = tmp_path / "e.jsonl"
    _write_events(log, [_event(impact=True) for _ in range(5)])  # < MIN_SAMPLES (8)
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["total_tasks"] == 5
    assert m["recommendation"] == "insufficient-data"


def test_promote_candidate_vs_keep_advisory(tmp_path, monkeypatch):
    # 10 задач: impact в 7 (0.7 >= 0.6 → promote-candidate), ref_search в 2 (0.2 → keep-advisory),
    # debug_trace в 0 → keep-advisory.
    rows = [_event(impact=True, ref_search=(i < 2)) for i in range(7)]
    rows += [_event(impact=False) for _ in range(3)]
    log = tmp_path / "e.jsonl"
    _write_events(log, rows)
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["total_tasks"] == 10
    assert m["per_tool"]["impact"]["rate"] == 0.7
    assert m["per_tool"]["impact"]["verdict"] == "promote-candidate"
    assert m["per_tool"]["ref_search"]["verdict"] == "keep-advisory"
    assert m["per_tool"]["debug_trace"]["verdict"] == "keep-advisory"
    assert m["recommendation"] == "promote-candidate (manual-review): impact"


def test_keep_advisory_when_none_reach_threshold(tmp_path, monkeypatch):
    # 8 задач, каждый tool в 3 (0.375 < 0.6) → нет кандидатов → keep-advisory
    log = tmp_path / "e.jsonl"
    _write_events(
        log, [_event(impact=(i < 3), debug_trace=(i < 3), ref_search=(i < 3)) for i in range(8)]
    )
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["recommendation"] == "keep-advisory"


def test_window_filter_excludes_old(tmp_path, monkeypatch):
    # запись до WINDOW_START (2026-06-22) исключается из окна
    log = tmp_path / "e.jsonl"
    rows = [json.dumps({"ts": "2026-06-01T00:00:00", **_event(impact=True)})]  # вне окна
    rows += [json.dumps({"ts": _TS, **_event(impact=True)})]  # в окне
    log.write_text("\n".join(rows), encoding="utf-8")
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["total_tasks"] == 1  # только запись в окне


def test_evaluate_contract(tmp_path, monkeypatch):
    # evaluate(m) → dict[str,bool], читается баннером; ключи стабильны
    log = tmp_path / "e.jsonl"
    log.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    crit = mod.evaluate(m)
    assert isinstance(crit, dict) and all(isinstance(v, bool) for v in crit.values())
    assert "day" in m  # требуется acceptance_banner


def test_impact_rate_on_applicable_honest_denominator(tmp_path, monkeypatch):
    """В2 260718 W1: impact_rate_on_applicable считается ТОЛЬКО на записях с полем
    impact_applicable (старые без поля не искажают знаменатель)."""
    log = tmp_path / "e.jsonl"
    _write_events(
        log,
        [
            {"impact_applicable": True, "impact": True, "config_edit": True},  # applicable + used
            {
                "impact_applicable": True,
                "impact": False,
                "config_edit": True,
            },  # applicable + missed
            {"impact_applicable": False, "impact": False, "config_edit": True},  # not applicable
            {"config_edit": True, "impact": False},  # старая запись без поля → не в знаменателе
        ],
    )
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["applicable_tasks"] == 2  # только 2 с impact_applicable=True
    assert m["impact_rate_on_applicable"] == 0.5  # 1 used / 2 applicable


def test_impact_rate_on_applicable_none_when_no_field(tmp_path, monkeypatch):
    """Старые записи без impact_applicable → applicable_tasks=0 → rate None (не 0, не крэш)."""
    log = tmp_path / "e.jsonl"
    _write_events(log, [_event(impact=True, config_edit=True) for _ in range(10)])
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["applicable_tasks"] == 0
    assert m["impact_rate_on_applicable"] is None


def test_yaxunit_rate_on_applicable_honest_denominator(tmp_path, monkeypatch):
    """Рек.3 2026-07-19: yaxunit_rate_on_applicable — ТОЛЬКО на записях с yaxunit_applicable
    (старые без поля не искажают знаменатель); presence — по yaxunit_smoke."""
    log = tmp_path / "e.jsonl"
    _write_events(
        log,
        [
            {"yaxunit_applicable": True, "yaxunit_smoke": True, "config_edit": True},  # appl + used
            {
                "yaxunit_applicable": True,
                "yaxunit_smoke": False,
                "config_edit": True,
            },  # appl + missed
            {"yaxunit_applicable": False, "yaxunit_smoke": False, "config_edit": True},  # not appl
            {"config_edit": True},  # старая запись без поля → не в знаменателе
        ],
    )
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["yaxunit_applicable_tasks"] == 2  # только 2 с yaxunit_applicable=True
    assert m["yaxunit_rate_on_applicable"] == 0.5  # 1 used / 2 applicable


def test_yaxunit_rate_none_when_no_field(tmp_path, monkeypatch):
    """Старые записи без yaxunit_applicable → yaxunit_applicable_tasks=0 → rate None (не крэш)."""
    log = tmp_path / "e.jsonl"
    _write_events(log, [{"config_edit": True} for _ in range(5)])
    monkeypatch.setattr(mod, "EVENTS_LOG", log)
    m = mod.collect_metrics(now=_NOW)
    assert m["yaxunit_applicable_tasks"] == 0
    assert m["yaxunit_rate_on_applicable"] is None
