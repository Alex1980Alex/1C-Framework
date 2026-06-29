"""Unit: shared/llm_health.is_provider_down — graceful-сигнал для ZAIWriteGuard."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "hooks"))
from shared import llm_health

pytestmark = pytest.mark.unit


def _write(tmp_path: Path, fname: str, rows: list[dict]) -> None:
    (tmp_path / fname).write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def test_down_on_recent_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    _write(
        tmp_path,
        "llm-rotation-metrics.jsonl",
        [
            {"ts": _now(), "success": False, "provider": "error"},
            {"ts": _now(), "success": False, "provider": "error"},
        ],
    )
    assert llm_health.is_provider_down() is True


def test_up_on_recent_successes(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    _write(
        tmp_path,
        "llm-rotation-metrics.jsonl",
        [
            {"ts": _now(), "success": True, "provider": "zai-glm5"},
            {"ts": _now(), "success": True, "provider": "zai-glm5"},
        ],
    )
    assert llm_health.is_provider_down() is False


def test_old_failures_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    _write(
        tmp_path,
        "llm-rotation-metrics.jsonl",
        [
            {"ts": old, "success": False, "provider": "error"},
            {"ts": old, "success": False, "provider": "error"},
        ],
    )
    assert llm_health.is_provider_down() is False


def test_no_data_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    assert llm_health.is_provider_down() is False


def test_error_marker_in_completions(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    _write(
        tmp_path,
        "llm-rotation-completions.jsonl",
        [
            {"ts": _now(), "error": "No available providers"},
            {"ts": _now(), "error": "All failed. Tried: ['zai-glm5']"},
        ],
    )
    assert llm_health.is_provider_down() is True


def test_single_failure_does_not_disarm(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_health, "_DATA", tmp_path)
    _write(
        tmp_path,
        "llm-rotation-metrics.jsonl",
        [
            {"ts": _now(), "success": True, "provider": "zai-glm5"},
            {"ts": _now(), "success": True, "provider": "zai-glm5"},
            {"ts": _now(), "success": False, "provider": "error"},
        ],
    )
    assert llm_health.is_provider_down() is False
