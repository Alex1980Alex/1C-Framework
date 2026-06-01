"""Smoke tests for section 25 Part A memory-effectiveness analyzer (Qdrant-independent).

Feeds synthetic surfacing + lifecycle rows into the analyzer's pure functions
and asserts aggregates + rule-based recommendations. No external services.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _ROOT / "scripts" / "analyze_memory_effectiveness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_memory_effectiveness", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load_module()


def test_analyze_surfacing_aggregates():
    rows = [
        {"outcome": "injected", "cache": "miss", "tei": "ok",
         "gate": {"archived": 1, "below_floor": 2, "passed": 7},
         "arms": {"pattern_dense": 1, "pattern_lexical": 3}, "duration_ms": 100.0},
        {"outcome": "no-results", "cache": "miss", "tei": "down",
         "gate": {"archived": 0, "below_floor": 0, "passed": 0},
         "arms": {"pattern_dense": 0, "pattern_lexical": 0}, "duration_ms": 200.0},
        {"outcome": "injected-cached", "cache": "hit", "duration_ms": 5.0},
    ]
    s = M.analyze_surfacing(rows)
    assert s["total_invocations"] == 3
    assert s["no_results_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["cache_hit_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["tei_down_rate"] == pytest.approx(0.5, abs=1e-3)
    assert s["gate_breakdown"]["passed"] == 7
    assert s["arm_contribution"]["pattern_lexical"] == 3
    assert s["latency_ms"]["count"] == 3


def test_analyze_lifecycle_drift_and_reinforcement():
    rows = [
        {"event": "reinforce", "old_confidence": 0.70, "new_confidence": 0.73},
        {"event": "apply", "old_confidence": 0.50, "new_confidence": 0.48},
        {"event": "session", "applied": 3, "skipped": 1, "errors": 0, "candidates": 5},
        {"event": "server_start"},
    ]
    li = M.analyze_lifecycle(rows)
    assert li["total_events"] == 4
    assert li["confidence_mutations"] == 2
    assert li["confidence_drift_avg"] == pytest.approx(0.005, abs=1e-3)
    assert li["reinforcement"]["applied"] == 3
    assert li["reinforcement"]["apply_rate"] == pytest.approx(0.6, abs=1e-3)
    assert li["event_mix"]["server_start"] == 1


def test_recommendations_flag_tei_down():
    surf = M.analyze_surfacing(
        [{"outcome": "no-results", "tei": "down", "cache": "miss"} for _ in range(5)]
    )
    recs = M.recommendations(surf, M.analyze_lifecycle([]))
    assert any("tei_down_rate" in r for r in recs)
    assert any("no_results_rate" in r for r in recs)


def test_recommendations_empty_window():
    recs = M.recommendations(M.analyze_surfacing([]), M.analyze_lifecycle([]))
    assert len(recs) == 1
    assert "No surfacing data" in recs[0]


def test_build_report_and_render_smoke(tmp_path):
    M.SURFACING_LOG = tmp_path / "surf.log"
    M.LIFECYCLE_LOG = tmp_path / "life.log"
    rep = M.build_report(None, datetime(2026, 6, 1, 12, 0, 0))
    md = M.render_markdown(rep)
    assert "Memory Effectiveness Report" in md
    assert rep["surfacing_rows"] == 0
    assert isinstance(rep["recommendations"], list) and rep["recommendations"]


def test_percentile_and_pct_helpers():
    assert M._pct(1, 4) == 0.25
    assert M._pct(0, 0) == 0.0
    assert M._percentile([], 0.5) == 0.0
    assert M._percentile([10.0, 20.0, 30.0], 0.5) == 20.0
