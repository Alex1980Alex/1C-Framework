"""Unit-тесты onec-state-first-guard (ADR-026): детект 1С-файла + активного pipeline-state.

Детерминированы (marker `unit`, без сети/1С): тестируют чистые хелперы через importlib
(имя файла хука с дефисами → spec_from_file_location).
"""

import importlib.util
import json
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "onec-state-first-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("onec_state_first_guard", _HOOK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.unit
def test_is_1c_file_detection():
    m = _load()
    # 1С-файлы задачи (под деревом конфигурации заказчика)
    assert m._is_1c_file(
        "ИБTransportManagementDevelop/Конфигурация/src/Documents/гкс_X/ObjectModule.bsl"
    )
    assert m._is_1c_file("configuration/260304_GKSTCPLK-2182/.../X.mdo")
    assert m._is_1c_file(
        r"C:\1С-Framework\ИБTransportManagementDevelop\Конфигурация\src\...\Form.form"
    )
    # НЕ задачи: framework-python, reference-дамп, docs
    assert not m._is_1c_file("src/pdf_framework/foo.py")
    assert not m._is_1c_file("external/1c-reference-src/trade/Documents/X/Ext/ObjectModule.bsl")
    assert not m._is_1c_file("docs/readme.md")


@pytest.mark.unit
def test_has_active_1c_pipeline(tmp_path, monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "PROJECT_ROOT", str(tmp_path))
    (tmp_path / "pipeline").mkdir()

    # нет пайплайнов → False
    assert m._has_active_1c_pipeline() is False

    d = tmp_path / "pipeline" / "t"
    d.mkdir()
    sp = d / ".pipeline-state.json"

    # активная 1С-задача (title-префикс + stage<5) → True
    sp.write_text(
        json.dumps({"title": "1С-задача (run-1c-task): GKSTCPLK-1", "current_stage": 3}),
        encoding="utf-8",
    )
    assert m._has_active_1c_pipeline() is True

    # завершена (stage 5) → False
    sp.write_text(
        json.dumps({"title": "1С-задача (run-1c-task): GKSTCPLK-1", "current_stage": 5}),
        encoding="utf-8",
    )
    assert m._has_active_1c_pipeline() is False

    # generic (не 1С-title) → не считается
    sp.write_text(json.dumps({"title": "State-first guard", "current_stage": 2}), encoding="utf-8")
    assert m._has_active_1c_pipeline() is False
