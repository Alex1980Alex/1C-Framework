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
