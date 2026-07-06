"""Unit: реестр Sonar-проектов по конфигурациям (ADR-048 P3.A). marker: unit.

Collision-immune (importlib). Покрытие: project_for_path (маппинг/None вне реестра),
detect-скоуп ↔ реестр (paired-инвариант), CLI --list-json.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_S = Path(__file__).resolve().parents[2] / "scripts" / "sonar_projects.py"
_spec = importlib.util.spec_from_file_location("sonar_projects_t", _S)
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


def test_project_for_path_maps_ib_and_svetly():
    r = sp.project_for_path(
        "ИБTransportManagementDevelop/Конфигурация/src/CommonModules/x/Module.bsl"
    )
    assert r is not None
    key, root, rel_in = r
    assert key == "utp-ib"
    assert root == "ИБTransportManagementDevelop/Конфигурация"
    assert rel_in == "src/CommonModules/x/Module.bsl"

    r2 = sp.project_for_path("TransportManagementDevelop_SVETLY/Конфигурация/src/M/Module.bsl")
    assert r2 is not None and r2[0] == "utp-svetly" and r2[2] == "src/M/Module.bsl"


def test_project_for_path_backslash_normalized():
    r = sp.project_for_path(r"ИБTransportManagementDevelop\Конфигурация\src\M\Module.bsl")
    assert r is not None and r[0] == "utp-ib"


def test_project_for_path_maps_mfm():
    # ADR-048 A7 вар.а: MFM/Конфигурация → utp-mfm (свой проект)
    r = sp.project_for_path("MFM/Конфигурация/src/CommonModules/x/Module.bsl")
    assert r is not None and r[0] == "utp-mfm" and r[2] == "src/CommonModules/x/Module.bsl"


def test_project_for_path_outside_registry_is_none():
    # configuration/<JIRA> (ведение задач), framework — вне реестра
    assert sp.project_for_path("configuration/260304_JIRA/Конфигурация/src/M/Module.bsl") is None
    assert sp.project_for_path("scripts/foo.py") is None


def test_project_for_path_prefix_not_substring():
    # корень матчится префиксно, а не как подстрока в середине пути
    assert sp.project_for_path("x/ИБTransportManagementDevelop/Конфигурация/src/M.bsl") is None


def test_projects_have_required_keys():
    for p in sp.PROJECTS:
        assert set(p) >= {"key", "root", "name"}
    keys = [p["key"] for p in sp.PROJECTS]
    assert keys == ["utp-ib", "utp-svetly", "utp-mfm"]  # 3 проекта (ADR-048 A7 вар.а: utp-mfm вкл.)


def test_roots_matches_declared():
    # roots() — подмножество объявленных корней (только существующие с .bsl); форма forward-slash
    declared = {p["root"] for p in sp.PROJECTS}
    for r in sp.roots():
        assert r in declared


def test_split_enabled_env(monkeypatch):
    # P3.A: SONAR_SPLIT_PROJECTS управляет split-режимом; default OFF (legacy mono)
    monkeypatch.delenv("SONAR_SPLIT_PROJECTS", raising=False)
    assert sp.split_enabled() is False
    for on in ("1", "true", "yes", "on", "ON", " 1 "):
        monkeypatch.setenv("SONAR_SPLIT_PROJECTS", on)
        assert sp.split_enabled() is True
    for off in ("0", "false", "", "no"):
        monkeypatch.setenv("SONAR_SPLIT_PROJECTS", off)
        assert sp.split_enabled() is False


def test_cli_list_json(capsysbinary):
    # capsysbinary — встроенная фикстура pytest (бинарный stdout; наш CLI пишет UTF-8 байтами)
    assert sp.main(["--list-json"]) == 0
    raw = capsysbinary.readouterr().out
    data = json.loads(raw.decode("utf-8"))
    assert isinstance(data, list)
    for p in data:
        assert {"key", "root", "name"} <= set(p)
