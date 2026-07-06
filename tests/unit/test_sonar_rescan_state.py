"""Unit: контракт sonar_rescan_state (детект /src/ + evaluate-ветки гейта).

Гейт onec-task-completion-stop блокирует завершение по результату evaluate(); эти тесты
фиксируют его решения по всем веткам (missing/stale/skipped/fail/uncovered/edits-after/ok)
+ фильтр продакшн-кода `_is_config_bsl` (только /src/, scratch-.bsl в docs исключены).
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

from shared import sonar_rescan_state as srs

pytestmark = pytest.mark.unit

NOW = datetime.now()
PAST = datetime(2000, 1, 1)
FUTURE = datetime(2999, 1, 1)


# ── _is_config_bsl ───────────────────────────────────────────────────────────
def test_is_config_bsl_accepts_src_bsl():
    assert srs._is_config_bsl(
        "ИБTransportManagementDevelop/Конфигурация/src/CommonModules/x/Module.bsl"
    )
    assert srs._is_config_bsl("a/SRC/b/ManagerModule.BSL")  # регистронезависимо


def test_is_config_bsl_rejects_non_src_and_non_bsl():
    assert not srs._is_config_bsl(
        "configuration/260304_JIRA/docs/x/обработка/Форма_Модуль.bsl"
    )  # нет /src/
    assert not srs._is_config_bsl("scripts/foo.py")
    assert not srs._is_config_bsl("ИБ/Конфигурация/src/README.md")  # не .bsl


def test_is_config_bsl_excludes_configuration_tree_entirely():
    # ADR-048 (approve 2026-07-06): configuration/<JIRA> = ведение задач, вне Sonar-скоупа
    # и вне детекта гейта — даже .bsl под /src/ исторических дампов конфигураций
    assert not srs._is_config_bsl(
        "configuration/260304_JIRA/Конфигурация/src/CommonModules/x/Module.bsl"
    )
    assert not srs._is_config_bsl("CONFIGURATION/999_X/Конфигурация/src/M/Module.bsl")


def test_is_config_bsl_detects_registry_configs_incl_mfm():
    # ADR-048 A7 вар.а: MFM/Конфигурация — свой проект utp-mfm, В скоупе → детектится
    # (не dead-lock, потому что сканируется: sonar_sources STABLE_ROOTS += MFM)
    assert srs._is_config_bsl("MFM/Конфигурация/src/CommonModules/x/Module.bsl")
    assert srs._is_config_bsl("ИБTransportManagementDevelop/Конфигурация/src/M/Module.bsl")
    assert srs._is_config_bsl("TransportManagementDevelop_SVETLY/Конфигурация/src/M/Module.bsl")
    # configuration/<JIRA> (ведение задач) по-прежнему исключён
    assert not srs._is_config_bsl("configuration/260304_JIRA/Конфигурация/src/M/Module.bsl")


def test_is_config_bsl_excludes_nonproduct_trees():
    # НЕ продакшн-конфиги в Sonar-скоупе → не детектим (иначе detected-but-not-scanned
    # dead-block): external/ (BSL-расширение MCP), tools/ (dev-тулинг + тест-фикстуры .bsl)
    assert not srs._is_config_bsl("external/1c_mcp/src/1c_ext/CommonModules/x/Module.bsl")
    assert not srs._is_config_bsl("tools/bsl-debug-server/src/test/resources/a/src/M.bsl")


# ── evaluate: ветки решения гейта ────────────────────────────────────────────
def _patch(monkeypatch, changed, state, newest=0.0):
    monkeypatch.setattr(srs, "changed_bsl_paths", lambda root: set(changed))
    monkeypatch.setattr(srs, "read_state", lambda root: state)
    monkeypatch.setattr(srs, "newest_mtime", lambda root, paths: newest)


def test_evaluate_no_bsl_allows(monkeypatch):
    _patch(monkeypatch, [], None)
    ok, status, _ = srs.evaluate(".", NOW)
    assert ok and status == "no-bsl"


def test_evaluate_missing_state_blocks(monkeypatch):
    _patch(monkeypatch, ["a/src/x.bsl"], None)
    ok, status, _ = srs.evaluate(".", PAST)
    assert not ok and status == "missing"


def test_evaluate_stale_blocks(monkeypatch):
    # state из прошлой сессии (ts < session_start) → stale
    _patch(
        monkeypatch,
        ["a/src/x.bsl"],
        {"ts": PAST.isoformat(), "pass": True, "files_verified": ["a/src/x.bsl"]},
    )
    ok, status, _ = srs.evaluate(".", NOW)
    assert not ok and status == "stale"


def test_evaluate_skipped_allows(monkeypatch):
    # Sonar был недоступен при verify → skip (reachability, без дедлока)
    _patch(monkeypatch, ["a/src/x.bsl"], {"ts": NOW.isoformat(), "skipped": True})
    ok, status, _ = srs.evaluate(".", PAST)
    assert ok and status == "skipped"


def test_evaluate_scan_stale_blocks(monkeypatch):
    # анализ Sonar устарел относительно правок → отдельный статус stale-scan (R2 code-verify)
    _patch(
        monkeypatch,
        ["a/src/x.bsl"],
        {
            "ts": NOW.isoformat(),
            "pass": False,
            "scan_stale": True,
            "files_verified": ["a/src/x.bsl"],
        },
    )
    ok, status, _ = srs.evaluate(".", PAST)
    assert not ok and status == "stale-scan"


def test_evaluate_ts_none_blocks_even_without_session_start(monkeypatch):
    # state без валидной метки времени → stale даже при session_start=None (R1 code-verify)
    _patch(monkeypatch, ["a/src/x.bsl"], {"pass": True, "files_verified": ["a/src/x.bsl"]})
    ok, status, _ = srs.evaluate(".", None)
    assert not ok and status == "stale"


def test_evaluate_fail_blocks(monkeypatch):
    _patch(
        monkeypatch,
        ["a/src/x.bsl"],
        {
            "ts": NOW.isoformat(),
            "pass": False,
            "fail_files": ["a/src/x.bsl (3 BLOCKER/CRITICAL)"],
            "files_verified": ["a/src/x.bsl"],
        },
    )
    ok, status, _ = srs.evaluate(".", PAST)
    assert not ok and status == "fail"


def test_evaluate_uncovered_blocks(monkeypatch):
    # проверен только один из двух изменённых → uncovered
    _patch(
        monkeypatch,
        ["a/src/x.bsl", "b/src/y.bsl"],
        {"ts": NOW.isoformat(), "pass": True, "files_verified": ["a/src/x.bsl"]},
    )
    ok, status, _ = srs.evaluate(".", PAST)
    assert not ok and status == "uncovered"


def test_evaluate_edits_after_blocks(monkeypatch):
    # правка .bsl ПОСЛЕ verify (newest mtime > ts) → edits-after
    _patch(
        monkeypatch,
        ["a/src/x.bsl"],
        {"ts": NOW.isoformat(), "pass": True, "files_verified": ["a/src/x.bsl"]},
        newest=FUTURE.timestamp(),
    )
    ok, status, _ = srs.evaluate(".", PAST)
    assert not ok and status == "edits-after"


def test_evaluate_pass_allows(monkeypatch):
    _patch(
        monkeypatch,
        ["a/src/x.bsl"],
        {"ts": NOW.isoformat(), "pass": True, "files_verified": ["a/src/x.bsl"]},
        newest=0.0,
    )
    ok, status, _ = srs.evaluate(".", PAST)
    assert ok and status == "ok"


# --- changed-lines дельта (сервер-независимый Clean-as-You-Code) ---


def test_parse_hunk_new_ranges_variants():
    diff = (
        "@@ -10,2 +12,3 @@ Процедура Х()\n"
        "@@ -20 +25 @@\n"  # без счётчиков → 1 строка
        "@@ -30,4 +33,0 @@\n"  # чистое удаление → диапазона нет
    )
    assert srs.parse_hunk_new_ranges(diff) == [(12, 14), (25, 25)]


def test_parse_hunk_new_ranges_ignores_non_headers():
    # строки контента с "@@" внутри не матчатся (якорь ^)
    assert srs.parse_hunk_new_ranges("+ Текст @@ -1 +2 @@ в середине\n") == []


def test_owning_tree_resolves_submodule(monkeypatch, tmp_path):
    monkeypatch.setattr(srs, "_submodule_paths", lambda root: ["sub/conf"])
    tree, rel = srs._owning_tree(tmp_path, "sub/conf/src/M/Module.bsl")
    assert tree == tmp_path / "sub/conf"
    assert rel == "src/M/Module.bsl"
    tree2, rel2 = srs._owning_tree(tmp_path, "src/Other.bsl")
    assert tree2 == tmp_path
    assert rel2 == "src/Other.bsl"


class _FakeRun:
    def __init__(self, returncode, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_changed_line_ranges_untracked_returns_none(monkeypatch, tmp_path):
    # untracked файл → None (все строки новые, fail-closed)
    monkeypatch.setattr(srs, "_submodule_paths", lambda root: [])
    monkeypatch.setattr(srs.subprocess, "run", lambda *a, **k: _FakeRun(1))
    assert srs.changed_line_ranges(tmp_path, "src/New.bsl") is None


def test_changed_line_ranges_tracked_parses_hunks(monkeypatch, tmp_path):
    monkeypatch.setattr(srs, "_submodule_paths", lambda root: [])

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:
            return _FakeRun(0)
        assert "-w" in cmd  # whitespace-only правки не считаются моими
        return _FakeRun(0, "@@ -5,2 +7,4 @@\n+а\n+б\n+в\n+г\n")

    monkeypatch.setattr(srs.subprocess, "run", fake_run)
    assert srs.changed_line_ranges(tmp_path, "src/M.bsl") == [(7, 10)]


def test_changed_line_ranges_whitespace_only_empty(monkeypatch, tmp_path):
    # дифф -w пуст (только whitespace/EOL-churn) → [] — содержательно моих строк нет
    monkeypatch.setattr(srs, "_submodule_paths", lambda root: [])

    def fake_run(cmd, **kw):
        return _FakeRun(0, "")

    monkeypatch.setattr(srs.subprocess, "run", fake_run)
    assert srs.changed_line_ranges(tmp_path, "src/M.bsl") == []
