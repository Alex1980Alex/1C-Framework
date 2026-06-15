"""Unit-тесты tool_usage_report (roadmap 260614 раздел W). marker: unit.

Агрегация по run_id + rollup на фейковых jsonl (tmp_path). Скрипт грузится importlib'ом
(stdlib-only, без shared-зависимости → collision-free).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_S = Path(__file__).resolve().parents[2] / "scripts" / "tool_usage_report.py"
_spec = importlib.util.spec_from_file_location("tool_usage_report_t", _S)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _write(p: Path, rows: list[dict]) -> None:
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def test_aggregate_by_run_id(tmp_path):
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 10, "correlationid": "R1"},
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 20, "correlationid": "R1"},
        {"tool": "crud", "outcome": "error", "elapsed_ms": 100, "correlationid": "R1"},
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 5, "correlationid": "R2"},  # другой run
    ])
    agg = mod.aggregate(run_id="R1", log=log)
    assert agg["edt"]["calls"] == 2 and agg["edt"]["errors"] == 0 and agg["edt"]["ms"] == 30
    assert agg["crud"]["calls"] == 1 and agg["crud"]["errors"] == 1


def test_rollup_and_report(tmp_path):
    eff = tmp_path / "eff.jsonl"
    _write(eff, [
        {"key": "R1", "tool": "edt", "calls": 2, "errors": 0, "ms": 30},
        {"key": "R2", "tool": "edt", "calls": 1, "errors": 1, "ms": 5},
    ])
    agg = mod.rollup(eff=eff)
    assert agg["edt"]["calls"] == 3 and agg["edt"]["errors"] == 1
    md = mod.report_md(agg, "ROLLUP")
    assert "edt" in md and "| tool |" in md


def test_append_eff(tmp_path):
    eff = tmp_path / "eff.jsonl"
    mod.append_eff({"edt": {"calls": 1, "errors": 0, "ms": 7}}, "R9", eff=eff)
    line = json.loads(eff.read_text(encoding="utf-8").strip())
    assert line["key"] == "R9" and line["tool"] == "edt" and line["calls"] == 1
