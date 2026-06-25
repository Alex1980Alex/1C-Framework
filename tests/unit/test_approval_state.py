"""Unit-тесты shared/approval_state.py (ADR-041 R1 — единый источник OpenSpec-approval). marker: unit.

Collision-immune: модуль грузится через importlib из .claude/hooks/shared (НЕ `from shared import`,
который в общем pytest-прогоне резолвится в src/shared — см. memory feedback-hook-src-shared-collision).
tmp_path-фикстуры строят синтетический openspec/changes/ → детерминично, без чтения реального репо.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location(
    "approval_state_t", _HOOKS / "shared" / "approval_state.py"
)
ast_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ast_mod)


def _mk_change(
    root: Path, name: str, status: str | None, body: str = "", profile: str | None = None
):
    d = root / "openspec" / "changes" / name
    d.mkdir(parents=True, exist_ok=True)
    yaml = ""
    if profile:
        yaml += f"profile: {profile}\n"
    if status is not None:
        yaml += f"approval:\n  status: {status}\n"
    (d / ".openspec.yaml").write_text(yaml or "x: 1\n", encoding="utf-8")
    (d / "proposal.md").write_text(body or f"# {name}\n", encoding="utf-8")
    return d


def test_read_approval_status_block_inline_none(tmp_path):
    d = _mk_change(tmp_path, "gkstcplk-1-x", "approved")
    y = str(d / ".openspec.yaml")
    assert ast_mod.read_approval_status(y) == "approved"
    (d / ".openspec.yaml").write_text("approval: {status: pending}\n", encoding="utf-8")
    assert ast_mod.read_approval_status(y) == "pending"  # inline-форма
    (d / ".openspec.yaml").write_text("x: 1\n", encoding="utf-8")
    assert ast_mod.read_approval_status(y) is None  # нет секции
    assert ast_mod.read_approval_status(str(tmp_path / "nope.yaml")) is None  # нет файла


def test_read_profile_default_and_value(tmp_path):
    d = _mk_change(tmp_path, "gkstcplk-2-x", "approved", profile="python-framework")
    assert ast_mod.read_profile(str(d / ".openspec.yaml")) == "python-framework"
    d2 = _mk_change(tmp_path, "gkstcplk-3-x", "approved")
    assert ast_mod.read_profile(str(d2 / ".openspec.yaml")) == "1c-bsl"  # backward-compat default


def test_list_active_changes_excludes_archive(tmp_path):
    _mk_change(tmp_path, "gkstcplk-10-a", "approved")
    _mk_change(tmp_path, "gkstcplk-11-b", "pending")
    arch = tmp_path / "openspec" / "changes" / "archive" / "old"
    arch.mkdir(parents=True)
    (arch / ".openspec.yaml").write_text("approval:\n  status: approved\n", encoding="utf-8")
    names = {n for n, _ in ast_mod.list_active_changes(str(tmp_path))}
    assert names == {"gkstcplk-10-a", "gkstcplk-11-b"}  # archive исключён


def test_change_matches_jira_name_body_empty(tmp_path):
    d = _mk_change(tmp_path, "gkstcplk-2507-foo", "approved")
    y = str(d / ".openspec.yaml")
    assert ast_mod.change_matches_jira("gkstcplk-2507-foo", y, "GKSTCPLK-2507") is True  # имя
    d2 = _mk_change(tmp_path, "feature-bar", "approved", body="relates to GKSTCPLK-2599")
    y2 = str(d2 / ".openspec.yaml")
    assert ast_mod.change_matches_jira("feature-bar", y2, "GKSTCPLK-2599") is True  # тело proposal
    assert ast_mod.change_matches_jira("feature-bar", y2, "GKSTCPLK-9999") is False
    assert ast_mod.change_matches_jira("x", y, "") is False  # пустой токен


def test_openspec_status_for_jira(tmp_path):
    _mk_change(tmp_path, "gkstcplk-2507-foo", "approved")
    _mk_change(tmp_path, "gkstcplk-2600-bar", "pending")
    assert ast_mod.openspec_status_for_jira("GKSTCPLK-2507", str(tmp_path)) == "approved"
    assert ast_mod.openspec_status_for_jira("GKSTCPLK-2600", str(tmp_path)) == "pending"
    assert (
        ast_mod.openspec_status_for_jira("GKSTCPLK-0000", str(tmp_path)) is None
    )  # нет связанного
    assert ast_mod.openspec_status_for_jira("", str(tmp_path)) is None


def test_is_design_approved_via_openspec(tmp_path):
    _mk_change(tmp_path, "gkstcplk-2507-foo", "approved")
    _mk_change(tmp_path, "gkstcplk-2600-bar", "pending")
    f = ast_mod.is_design_approved_via_openspec
    assert f("/implement GKSTCPLK-2507 x", str(tmp_path)) is True
    assert f("/implement GKSTCPLK-2600 x", str(tmp_path)) is False  # pending ≠ approved
    assert f("реализовать без джиры", str(tmp_path)) is False  # нет JIRA
    assert f("GKSTCPLK-0000 нет change", str(tmp_path)) is False  # нет связанного change


def test_best_effort_no_openspec_dir(tmp_path):
    # нет openspec/changes → пусто/None/False, не кидает (fail-open контракт)
    assert ast_mod.list_active_changes(str(tmp_path)) == []
    assert ast_mod.openspec_status_for_jira("GKSTCPLK-1", str(tmp_path)) is None
    assert ast_mod.is_design_approved_via_openspec("GKSTCPLK-1 x", str(tmp_path)) is False
