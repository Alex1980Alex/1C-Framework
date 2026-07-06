"""Unit: P0.1 roadmap 260706 — CE-wait + двухканальная freshness в sonar_rescan_verify.

Гонка I4: сканер завершается (exit 0) до финализации Compute Engine → project_analyses?ps=1
отдаёт предыдущий анализ → ложный scan_stale. Фикс: wait_ce (poll ce/activity_status) +
freshness = max(project_analyses, project_branches/list).
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sonar_rescan_verify.py"
_spec = importlib.util.spec_from_file_location("sonar_rescan_verify_p0", _SCRIPT)
srv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srv)


# ── wait_ce ──────────────────────────────────────────────────────────────────
def test_wait_ce_polls_until_idle(monkeypatch):
    seq = [
        {"pending": 2, "inProgress": 1},
        {"pending": 0, "inProgress": 1},
        {"pending": 0, "inProgress": 0},
    ]
    calls = {"n": 0}

    def fake_api(host, path, token=None, timeout=30, retries=3):
        assert "ce/activity_status" in path
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]

    monkeypatch.setattr(srv, "api", fake_api)
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    assert srv.wait_ce("h", "p", None, timeout_s=60, poll_s=0) is True
    assert calls["n"] == 3


def test_wait_ce_timeout_returns_false(monkeypatch):
    # CE «висит» (pending=1 всегда) → по дедлайну False (честный stale-путь)
    monkeypatch.setattr(srv, "api", lambda *a, **k: {"pending": 1, "inProgress": 0})
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    t = {"v": 0.0}

    def fake_monotonic():
        t["v"] += 10.0
        return t["v"]

    monkeypatch.setattr(srv.time, "monotonic", fake_monotonic)
    assert srv.wait_ce("h", "p", None, timeout_s=15) is False


def test_wait_ce_zero_timeout_skips_api(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("API не должен вызываться при timeout_s=0")

    monkeypatch.setattr(srv, "api", boom)
    assert srv.wait_ce("h", "p", None, timeout_s=0) is True


def test_wait_ce_transient_errors_do_not_abort(monkeypatch):
    # первая попытка — сетевой сбой, вторая — idle → True (транзиент не прерывает ожидание)
    calls = {"n": 0}

    def flaky_api(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("down")
        return {"pending": 0, "inProgress": 0}

    monkeypatch.setattr(srv, "api", flaky_api)
    monkeypatch.setattr(srv.time, "sleep", lambda s: None)
    assert srv.wait_ce("h", "p", None, timeout_s=60, poll_s=0) is True
    assert calls["n"] == 2


# ── branches_analysis_dt ─────────────────────────────────────────────────────
def test_branches_analysis_dt_takes_max(monkeypatch):
    monkeypatch.setattr(
        srv,
        "api",
        lambda *a, **k: {
            "branches": [
                {"analysisDate": "2026-07-06T05:19:03+0000"},
                {"analysisDate": "2026-07-06T05:29:35+0000"},  # свежайшая
                {"analysisDate": None},
            ]
        },
    )
    dt = srv.branches_analysis_dt("h", "p", None)
    assert dt is not None
    assert dt.isoformat().startswith("2026-07-06T05:29:35")


def test_branches_analysis_dt_error_returns_none(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(srv, "api", boom)
    assert srv.branches_analysis_dt("h", "p", None) is None


def test_branches_analysis_dt_empty_returns_none(monkeypatch):
    monkeypatch.setattr(srv, "api", lambda *a, **k: {"branches": []})
    assert srv.branches_analysis_dt("h", "p", None) is None


# ── run-sonar-analysis.ps1: BOM-инвариант ────────────────────────────────────
def test_run_sonar_ps1_has_utf8_bom():
    """PS 5.1 читает ps1 БЕЗ BOM как cp1251: байт 0x94 из «—» внутри двойной строки
    превращается в типографскую `”` (валидный string-делимитер PowerShell!) → строка
    рвётся, parse error «Missing closing '}'». BOM обязателен (roadmap 260706, R3)."""
    ps1 = Path(__file__).resolve().parents[2] / "scripts" / "run-sonar-analysis.ps1"
    assert ps1.read_bytes()[:3] == b"\xef\xbb\xbf", "run-sonar-analysis.ps1 потерял UTF-8 BOM"
