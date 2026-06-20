"""D2-guard (аудит 43.5): контракт SetFit-гейта в пути хука.

Пиннит, что `setfit_prob` (без инъекции model=) идёт через **warm-serve по HTTP**, а НЕ грузит
модель in-process (~6с) — иначе хук `onec-task-input` (timeout 5s) резался бы. Рефактор, вернувший
in-process `_load_model` в путь хука, должен ронять эти тесты.
"""

import importlib.util
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "onec_setfit_gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("onec_setfit_gate", _MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.unit
def test_setfit_prob_routes_through_http_serve_not_inprocess(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "is_enabled", lambda: True)
    serve_calls, load_calls = [], []
    monkeypatch.setattr(m, "_serve_prob", lambda t: serve_calls.append(t) or 0.91)
    monkeypatch.setattr(m, "_load_model", lambda: load_calls.append(1) or None)
    assert m.setfit_prob("Доработать проведение документа") == 0.91
    assert len(serve_calls) == 1  # пошёл в warm-serve (HTTP)
    assert not load_calls  # НЕ грузил модель in-process в пути хука (5s budget)


@pytest.mark.unit
def test_disabled_returns_none_and_skips_serve(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "is_enabled", lambda: False)

    def _boom(_t):
        raise AssertionError("_serve_prob не должен вызываться при выключенном гейте")

    monkeypatch.setattr(m, "_serve_prob", _boom)
    assert m.setfit_prob("любой текст") is None


@pytest.mark.unit
def test_http_timeout_under_hook_budget():
    # HTTP-таймаут warm-serve обязан быть < 5s таймаута хука onec-task-input,
    # иначе медленный serve съедал бы бюджет до отката на TF-IDF.
    m = _load()
    assert 0 < m._HTTP_TIMEOUT < 5.0


@pytest.mark.unit
def test_model_injection_is_inprocess(monkeypatch):
    # Прямая инъекция model= (тесты) — единственный легитимный in-process путь (warm-serve обходится).
    m = _load()
    monkeypatch.setattr(m, "is_enabled", lambda: True)

    class _Fake:
        def predict_proba(self, _texts):
            return [[0.2, 0.8]]

    assert m.setfit_prob("x", model=_Fake()) == 0.8


@pytest.mark.unit
def test_setfit_prob_never_raises(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "is_enabled", lambda: True)

    def _boom(_t):
        raise RuntimeError("serve down hard")

    monkeypatch.setattr(m, "_serve_prob", _boom)
    assert m.setfit_prob("x") is None  # best-effort: гасит исключение → None (→ TF-IDF)
