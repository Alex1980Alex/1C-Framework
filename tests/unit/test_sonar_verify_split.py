"""Unit: split-режим verify (P3.A.wiring roadmap 260706). marker: unit.

Покрытие ЧИСТОЙ логики группировки `_group_by_project` (маппинг изменённых .bsl по проектам
реестра + unmapped). Live per-project verify (verify_project/_run_split) — API, не в unit.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import sonar_rescan_verify as v


def test_group_by_project_splits_registry_configs():
    changed = [
        "ИБTransportManagementDevelop/Конфигурация/src/CommonModules/x/Module.bsl",
        "TransportManagementDevelop_SVETLY/Конфигурация/src/Documents/y/ManagerModule.bsl",
        "MFM/Конфигурация/src/CommonModules/z/Module.bsl",
    ]
    groups, unmapped = v._group_by_project(changed)
    assert set(groups) == {"utp-ib", "utp-svetly", "utp-mfm"}
    assert unmapped == []
    # comp_rel = путь ВНУТРИ конфигурации (projectBaseDir=корень конфига), repo_rel — полный
    repo_rel, comp_rel = groups["utp-ib"]["files"][0]
    assert repo_rel == changed[0]
    assert comp_rel == "src/CommonModules/x/Module.bsl"
    assert groups["utp-svetly"]["root"] == "TransportManagementDevelop_SVETLY/Конфигурация"


def test_group_by_project_unmapped_outside_registry():
    # вне корней реестра (framework-дамп, чужой путь) → unmapped (fail-closed у вызывающего)
    changed = ["src/bsl/foo/src/Bar.bsl", "other/src/M.bsl"]
    groups, unmapped = v._group_by_project(changed)
    assert groups == {}
    assert set(unmapped) == set(changed)


def test_group_by_project_multiple_files_same_project():
    changed = ["MFM/Конфигурация/src/a/M1.bsl", "MFM/Конфигурация/src/b/M2.bsl"]
    groups, unmapped = v._group_by_project(changed)
    assert list(groups) == ["utp-mfm"]
    assert len(groups["utp-mfm"]["files"]) == 2
    assert unmapped == []


def test_group_by_project_backslash_normalized():
    changed = [r"MFM\Конфигурация\src\a\M1.bsl"]
    groups, _ = v._group_by_project(changed)
    assert list(groups) == ["utp-mfm"]
    assert groups["utp-mfm"]["files"][0][1] == "src/a/M1.bsl"


def test_print_project_notes_no_crash(capsys):
    # диагностический вывод не падает и печатает ⚠ по флагам
    res = {
        "project": "utp-ib",
        "baseline_degenerate": True,
        "new_total": 100,
        "all_total": 120,
        "issues_truncated": True,
        "scan_stale": True,
    }
    v._print_project_notes(res, tagged=True)
    out = capsys.readouterr().out
    assert "utp-ib" in out and "ВЫРОЖДЕН" in out and "СТАРШЕ" in out


def _fake_vp(**overrides):
    """Фабрика мока verify_project (агрегат-логика _run_split без API)."""

    def vp(host, project, token, files, severities, wait_ce_s):
        repo_rels = [fr for fr, _ in files]
        base = {
            "project": project,
            "pass": True,
            "scan_stale": False,
            "last_analysis": "2026-07-06T08:00:00",
            "fail_files": [],
            "verified": repo_rels,
            "baseline_degenerate": False,
            "new_total": 0,
            "all_total": 0,
            "issues_truncated": False,
        }
        base.update(overrides.get(project, {}))
        return base

    return vp


def _capture_state(monkeypatch):
    captured = {}
    monkeypatch.setattr(v, "write_state", lambda root, data: captured.update(data))
    return captured


def test_run_split_fail_aggregates(monkeypatch):
    # utp-mfm с fail → агрегат pass=False, rc=1, projects:{} обоих, last_analysis=max
    monkeypatch.setattr(
        v,
        "verify_project",
        _fake_vp(
            **{
                "utp-mfm": {
                    "pass": False,
                    "fail_files": ["MFM/…/b.bsl (1 BLOCKER)"],
                    "last_analysis": "2026-07-06T07:00:00",
                }
            }
        ),
    )
    captured = _capture_state(monkeypatch)
    args = types.SimpleNamespace(host="h", token="t", wait_ce=0.0)
    changed = ["ИБTransportManagementDevelop/Конфигурация/src/a.bsl", "MFM/Конфигурация/src/b.bsl"]
    rc = v._run_split(args, changed, datetime(2026, 7, 6, 9, 0, 0), ["BLOCKER"])
    assert rc == 1
    assert captured["pass"] is False and captured["split"] is True
    assert set(captured["projects"]) == {"utp-ib", "utp-mfm"}
    assert len(captured["fail_files"]) == 1
    assert captured["last_analysis"] == "2026-07-06T08:00:00"  # max по проектам


def test_run_split_all_pass(monkeypatch):
    monkeypatch.setattr(v, "verify_project", _fake_vp())
    captured = _capture_state(monkeypatch)
    args = types.SimpleNamespace(host="h", token="t", wait_ce=0.0)
    changed = ["MFM/Конфигурация/src/b.bsl"]
    rc = v._run_split(args, changed, datetime(2026, 7, 6, 9, 0, 0), ["BLOCKER"])
    assert rc == 0 and captured["pass"] is True
    assert captured["files_verified"] == changed


def test_run_split_unmapped_fail_closed(monkeypatch):
    monkeypatch.setattr(v, "verify_project", _fake_vp())
    captured = _capture_state(monkeypatch)
    args = types.SimpleNamespace(host="h", token="t", wait_ce=0.0)
    rc = v._run_split(args, ["weird/src/x.bsl"], datetime(2026, 7, 6, 9, 0, 0), ["BLOCKER"])
    assert rc == 1 and captured["pass"] is False
    assert any("не сопоставлен" in f for f in captured["fail_files"])
    assert captured["projects"] == {}
