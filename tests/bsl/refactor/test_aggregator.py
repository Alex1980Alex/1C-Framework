from __future__ import annotations

import json
from pathlib import Path

from scripts.aggregate_refactor_telemetry import aggregate


def _make_events(n: int, kind: str = "module_export_proc", success: bool = True) -> list[dict]:
    events = []
    for i in range(n):
        events.append(
            {
                "timestamp": f"2026-04-17T10:{i % 60:02d}:00+00:00",
                "uri": "file:///test.bsl",
                "symbol_kind": kind,
                "old_name": None,
                "new_name": f"Name{i}",
                "primary_backend": "multilspy",
                "fallback_used": False,
                "applied": True,
                "rolled_back": not success if i % 4 == 0 else False,
                "duration_ms": 100 + i * 10,
                "error_code": None,
                "classifier_confidence": 0.95,
                "matrix_confidence": 0.95,
                "token_matched": True,
            }
        )
    return events


def test_aggregator_skips_under_min_samples():
    events = _make_events(19)
    summary, proposals = aggregate(events, min_samples=20, delta_threshold=0.05)
    assert len(proposals) == 0
    assert "module_export_proc / multilspy" in summary


def test_aggregator_emits_proposal_above_delta():
    events = _make_events(25, success=False)
    summary, proposals = aggregate(
        events,
        current_confidence={"module_export_proc": 0.95},
        min_samples=20,
        delta_threshold=0.05,
    )
    assert "module_export_proc" in proposals
    proposed = proposals["module_export_proc"]
    assert proposed < 0.95
    assert proposed >= 0.1


def test_aggregator_synthetic_dataset():
    synthetic = Path(__file__).resolve().parents[3] / "data" / "refactor-telemetry-synthetic.jsonl"
    assert synthetic.exists(), (
        f"Synthetic DoD dataset missing at {synthetic}. "
        "R4.4 requires this artefact to validate the aggregator end-to-end."
    )
    events = [
        json.loads(line) for line in synthetic.read_text(encoding="utf-8").strip().splitlines()
    ]
    assert len(events) == 20
    summary, proposals = aggregate(
        events,
        current_confidence={"module_export_proc": 0.50},
        min_samples=20,
        delta_threshold=0.05,
    )
    assert "module_export_proc / multilspy" in summary
    assert "total_calls: 20" in summary
    assert len(proposals) == 1
    assert 0.9 < proposals["module_export_proc"] < 1.0
