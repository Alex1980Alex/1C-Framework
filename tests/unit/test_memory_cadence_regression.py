"""Регрессия P1.4 (roadmap 260713 B8): freshness/regression-детектор memory-sinks в каденс.

`_check_regressions` парсит `[REGRESSION]`-строку из observability-отчёта (subprocess);
при фаере каденса регрессия сюрфейсится в баннер. Без реального subprocess — replaced.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "memory-maintenance-cadence.py"


def _load():
    spec = importlib.util.spec_from_file_location("_mmc", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── _check_regressions ───────────────────────────────────────────────────────


def _exists_stub(mod, monkeypatch, python_ok=True, script_ok=True):
    """Заменить Path-константы на SimpleNamespace с управляемым exists (subprocess замокан → str не важен)."""
    monkeypatch.setattr(mod, "PYTHON_EXE", SimpleNamespace(exists=lambda: python_ok))
    monkeypatch.setattr(mod, "OBS_SCRIPT", SimpleNamespace(exists=lambda: script_ok))


def test_check_regressions_parses_marker(monkeypatch):
    mod = _load()
    _exists_stub(mod, monkeypatch)
    out = "some markdown\n[REGRESSION] 3 stale sink(s): ['propagation', 'circuit', 'links']\ndone"
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=out))
    got = mod._check_regressions()
    assert got is not None and got.startswith("[REGRESSION]") and "propagation" in got


def test_check_regressions_none_when_no_marker(monkeypatch):
    mod = _load()
    _exists_stub(mod, monkeypatch)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="all fresh"))
    assert mod._check_regressions() is None


def test_check_regressions_none_on_timeout(monkeypatch):
    mod = _load()
    _exists_stub(mod, monkeypatch)

    def boom(*a, **k):
        raise mod.subprocess.TimeoutExpired(cmd="x", timeout=8)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod._check_regressions() is None


def test_check_regressions_none_when_script_missing(monkeypatch):
    mod = _load()
    _exists_stub(mod, monkeypatch, script_ok=False)
    assert mod._check_regressions() is None


# ── cadence fire surfaces regression ─────────────────────────────────────────


def test_cadence_fire_surfaces_regression(monkeypatch, tmp_path):
    mod = _load()
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "DEFAULT_EVERY", 1)  # этот Stop зафаерит
    monkeypatch.setattr(mod, "_launch", lambda apply: True)
    monkeypatch.setattr(
        mod, "_check_regressions", lambda: "[REGRESSION] 2 stale sink(s): ['circuit', 'links']"
    )
    # seed state (не cold-start) с pending, чтобы порог сработал
    mod._save_state({"pending_sessions": ["s0"], "first_seen": "x", "last_fire": None})

    out = mod.MemoryMaintenanceCadence().execute(
        mod.HookInput({"reason": "stop", "session_id": "s1"})
    )
    assert out is not None
    msg = out._data.get("systemMessage", "")
    assert "Cadence fired" in msg
    assert "[REGRESSION]" in msg and "circuit" in msg


def test_cadence_no_fire_below_threshold(monkeypatch, tmp_path):
    """Ниже порога каденс не фаерит и регрессию не дёргает."""
    mod = _load()
    monkeypatch.setattr(mod, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "DEFAULT_EVERY", 10)
    called = []
    monkeypatch.setattr(mod, "_check_regressions", lambda: called.append(1))
    mod._save_state({"pending_sessions": ["s0"], "first_seen": "x", "last_fire": None})
    out = mod.MemoryMaintenanceCadence().execute(
        mod.HookInput({"reason": "stop", "session_id": "s1"})
    )
    assert out is None
    assert called == []  # регрессию не проверяем впустую каждый Stop
