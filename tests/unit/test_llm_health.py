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


def test_data_dir_env_override_read_at_call_time(tmp_path, monkeypatch):
    """LLM_HEALTH_DATA_DIR читается В МОМЕНТ ВЫЗОВА, а не на импорте.

    Пин по замечанию ревьюера 2026-07-26: (1) сам override не был закреплён ничем —
    его удаление оставляло весь набор зелёным; (2) при связывании на импорте
    monkeypatch.setenv в уже загруженном модуле был бы молчаливым no-op, то есть
    изоляция тестов оказалась бы фиктивной (класс мёртвой CLAUDE_SESSION_STATE_PATH).
    """
    import json
    from datetime import datetime

    from shared import llm_health as m

    fresh = datetime.now().isoformat()
    (tmp_path / "llm-rotation-completions.jsonl").write_text(
        "\n".join(
            json.dumps({"ts": fresh, "provider": "none", "model": "none", "error": "All failed"})
            for _ in range(3)
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_HEALTH_DATA_DIR", str(tmp_path))
    assert m._data_dir() == tmp_path
    assert m.is_provider_down() is True, "env-override не применился => изоляция фиктивна"

    # пустой каталог => провайдер считается живым (fail-closed для гарда)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("LLM_HEALTH_DATA_DIR", str(empty))
    assert m.is_provider_down() is False

    # переменная снята => возвращаемся к дефолту модуля, прод не затронут
    monkeypatch.delenv("LLM_HEALTH_DATA_DIR", raising=False)
    assert m._data_dir() == m._DATA
