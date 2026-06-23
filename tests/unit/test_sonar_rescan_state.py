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
