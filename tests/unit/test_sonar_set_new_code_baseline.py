"""Unit: sonar_set_new_code_baseline (P2.2 roadmap 260706). marker: unit.

Покрытие чистой логики: pick_latest_before (выбор самого свежего анализа раньше даты),
_parse_dt, _UUID_RE (детект усечённого value). Live-часть (set/list) — не в unit.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_S = Path(__file__).resolve().parents[2] / "scripts" / "sonar_set_new_code_baseline.py"
_spec = importlib.util.spec_from_file_location("sonar_set_baseline_t", _S)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_ANALYSES = [
    {"key": "a-old", "date": "2026-07-01T10:00:00+0000"},
    {"key": "a-mid", "date": "2026-07-02T23:24:00+0000"},
    {"key": "a-new", "date": "2026-07-06T07:25:40+0000"},
]


def test_pick_latest_before_selects_newest_before():
    before = datetime(2026, 7, 3, tzinfo=UTC)
    assert (
        mod.pick_latest_before(_ANALYSES, before) == "a-mid"
    )  # a-new позже 07-03, a-old раньше a-mid


def test_pick_latest_before_none_when_all_after():
    before = datetime(2026, 6, 1, tzinfo=UTC)
    assert mod.pick_latest_before(_ANALYSES, before) is None


def test_pick_latest_before_strict_inequality():
    # анализ РОВНО на границе (>=) не выбирается (строго раньше)
    before = datetime(2026, 7, 2, 23, 24, tzinfo=UTC)
    assert mod.pick_latest_before(_ANALYSES, before) == "a-old"


def test_pick_latest_before_skips_unparsable_dates():
    analyses = [
        {"key": "bad", "date": "не-дата"},
        {"key": "ok", "date": "2026-07-01T00:00:00+0000"},
    ]
    before = datetime(2026, 7, 5, tzinfo=UTC)
    assert mod.pick_latest_before(analyses, before) == "ok"


def test_parse_dt_variants():
    assert mod._parse_dt("2026-07-06T07:25:40+0000") is not None
    assert mod._parse_dt("2026-07-06T07:25:40Z") is not None
    assert mod._parse_dt("garbage") is None
    assert mod._parse_dt(None) is None


def test_uuid_regex_detects_truncated():
    assert mod._UUID_RE.match("89f83883-46cb-4c6d-93a6-2cb6acaa85c5")  # полный
    assert not mod._UUID_RE.match("89f838")  # усечённый → предупреждение
    assert not mod._UUID_RE.match("")
