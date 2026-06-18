"""Unit-тесты SetFit-гейта детектора 1С (ADR-025, слой ②). marker: unit.

Покрытие: graceful degradation (выключен/нет модели/сбой → None), извлечение вероятности
позитивного класса, парсинг env (enable/threshold/model_dir), data-shaping тренировочного
скрипта (to_examples/partition/summarize/dry_run, без ML-стека). Collision-immune к
src/shared↔hooks/shared (загрузка модулей через spec_from_file_location, не `import shared`).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_GATE = _ROOT / ".claude" / "hooks" / "shared" / "onec_setfit_gate.py"
_TRAIN = _ROOT / "scripts" / "train_onec_setfit.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load("onec_setfit_gate_t", _GATE)
train = _load("train_onec_setfit_t", _TRAIN)


class _FakeModel:
    """Заглушка SetFitModel: predict_proba → [[neg, pos], ...]."""

    def __init__(self, pos: float):
        self._pos = pos

    def predict_proba(self, texts):
        return [[1.0 - self._pos, self._pos] for _ in texts]


class _BoomModel:
    def predict_proba(self, texts):
        raise RuntimeError("boom")


# --- graceful degradation: None при выключенном/сломанном гейте ---


def test_disabled_returns_none(monkeypatch):
    # гейт выключен (дефолт) → None ДАЖЕ с переданной моделью (короткое замыкание до загрузки)
    monkeypatch.delenv("ONEC_SETFIT_ENABLE", raising=False)
    assert gate.setfit_prob("доработать проведение", model=_FakeModel(0.99)) is None


def test_enabled_no_model_none(monkeypatch, tmp_path):
    # включён, но обученной модели нет → None (caller падает на TF-IDF)
    monkeypatch.setenv("ONEC_SETFIT_ENABLE", "1")
    monkeypatch.setenv("ONEC_SETFIT_MODEL_DIR", str(tmp_path / "no-such-model"))
    gate._model_cache = gate._UNSET  # сбросить кэш загрузки на процесс
    assert gate.setfit_prob("доработать проведение") is None


def test_enabled_fake_model_returns_pos_prob(monkeypatch):
    monkeypatch.setenv("ONEC_SETFIT_ENABLE", "1")
    assert gate.setfit_prob("исправить ошибку проведения", model=_FakeModel(0.83)) == pytest.approx(0.83)


def test_enabled_model_raises_is_graceful(monkeypatch):
    # модель кидает → best-effort None, не исключение
    monkeypatch.setenv("ONEC_SETFIT_ENABLE", "1")
    assert gate.setfit_prob("любой текст", model=_BoomModel()) is None


# --- извлечение вероятности позитивного класса ---


def test_positive_prob_two_columns_last():
    # метки [0,1] → последний столбец = P(is_1c)
    assert gate._positive_prob([[0.2, 0.8]]) == pytest.approx(0.8)


def test_positive_prob_single_and_bad():
    assert gate._positive_prob([[0.42]]) == pytest.approx(0.42)  # вырожденный одно-классовый
    assert gate._positive_prob([[]]) is None
    assert gate._positive_prob("не массив") is None


# --- парсинг env ---


@pytest.mark.parametrize("val,exp", [("1", True), ("true", True), ("YES", True), ("on", True),
                                     ("0", False), ("", False), ("off", False)])
def test_is_enabled_parsing(monkeypatch, val, exp):
    monkeypatch.setenv("ONEC_SETFIT_ENABLE", val)
    assert gate.is_enabled() is exp


def test_threshold_default_env_and_bad(monkeypatch, tmp_path):
    monkeypatch.setenv("ONEC_SETFIT_MODEL_DIR", str(tmp_path))  # пустой каталог → нет meta.json → дефолт
    monkeypatch.delenv("ONEC_SETFIT_THRESHOLD", raising=False)
    assert gate.threshold() == 0.5
    monkeypatch.setenv("ONEC_SETFIT_THRESHOLD", "0.7")
    assert gate.threshold() == 0.7
    monkeypatch.setenv("ONEC_SETFIT_THRESHOLD", "не-число")
    assert gate.threshold() == 0.5  # битый env → дефолт, не падаем


def test_model_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ONEC_SETFIT_MODEL_DIR", str(tmp_path / "m"))
    assert gate.model_dir() == tmp_path / "m"


def test_status_keys(monkeypatch):
    monkeypatch.delenv("ONEC_SETFIT_ENABLE", raising=False)
    st = gate.status()
    assert set(st) == {"enabled", "deps_installed", "model_dir", "model_present", "threshold", "backend", "cv_f1"}
    assert st["enabled"] is False


# --- data-shaping тренировочного скрипта (без ML-стека) ---


def test_to_texts_e5_prefix():
    rows = [{"text": "доработать форму", "is_1c": True}, {"text": "как работает RAG", "is_1c": False}]
    assert train.to_texts(rows, "cointegrated/rubert-tiny2") == ["доработать форму", "как работает RAG"]
    e5 = train.to_texts(rows, "intfloat/multilingual-e5-small")
    assert e5[0].startswith("query: ") and e5[0].endswith("доработать форму")  # e5 — префикс (model card)


def test_split_of_explicit_and_deterministic():
    assert train.split_of("a", {"split": "train"}) == "train"
    assert train.split_of("b", {"split": "test"}) == "test"
    assert train.split_of("x", {}) in ("train", "test")  # нет поля → sha1%5
    assert train.split_of("x", {}) == train.split_of("x", {})  # детерминирован


def test_summarize_and_dry_run_counts(capsys):
    rows = [{"text": "доработать", "is_1c": True, "split": "train"},
            {"text": "создать", "is_1c": False, "split": "train"},
            {"text": "обмен", "is_1c": True, "split": "test"}]
    s = train.summarize(rows)
    assert s["n"] == 3 and s["pos"] == 2 and s["neg"] == 1 and s["train"] == 2 and s["test"] == 1
    out = train.dry_run(rows)  # печатает + возвращает сводку
    assert out == s
    assert "DRY-RUN" in capsys.readouterr().out


def test_load_rows_drops_quarantine(tmp_path):
    p = tmp_path / "gt.json"
    p.write_text(json.dumps([
        {"text": "доработать", "is_1c": True},
        {"text": "leak", "is_1c": True, "split": "quarantine"},
    ], ensure_ascii=False), encoding="utf-8")
    rows = train.load_rows(p)
    assert len(rows) == 1 and rows[0]["text"] == "доработать"
