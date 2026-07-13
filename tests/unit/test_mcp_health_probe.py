"""Регрессия P1.2 (roadmap 260713 B7): probe_mcp_health + SessionStart-хук.

Probe пробит зависимости (Qdrant/TEI HTTP + SQLite) без падений; хук молчит когда
всё up, сюрфейсит баннер при down, opt-out и graceful.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "probe_mcp_health.py"
_HOOK_PATH = _ROOT / ".claude" / "hooks" / "mcp-health-probe-on-start.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("_probe_mcp_health", _PROBE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── _http_ok / _sqlite_ok ────────────────────────────────────────────────────


def test_http_ok_error_is_caught():
    """Недостижимый URL → (False, ms, текст), без исключения."""
    probe = _load_probe()
    ok, ms, err = probe._http_ok("http://127.0.0.1:1/nope", timeout=0.2)
    assert ok is False
    assert isinstance(ms, int)
    assert err  # непустой текст ошибки


def test_sqlite_ok_missing_file():
    probe = _load_probe()
    ok, ms, err = probe._sqlite_ok(Path("/no/such/file.db"), timeout=0.5)
    assert ok is False and err == "file missing"


def test_sqlite_ok_real_db(tmp_path):
    import sqlite3

    probe = _load_probe()
    db = tmp_path / "t.db"
    sqlite3.connect(db).close()
    ok, ms, err = probe._sqlite_ok(db, timeout=0.5)
    assert ok is True and err == ""


# ── probe_all structure ──────────────────────────────────────────────────────


def test_probe_all_structure(monkeypatch):
    """probe_all даёт 4 цели с обязательными ключами и картой affects."""
    probe = _load_probe()
    monkeypatch.setattr(probe, "_http_ok", lambda *a, **k: (True, 5, ""))
    monkeypatch.setattr(probe, "_sqlite_ok", lambda *a, **k: (True, 1, ""))
    probes = probe.probe_all(timeout=0.5)
    targets = {p["target"] for p in probes}
    assert targets == {"qdrant", "tei", "memory-ai", "bsl-code-search"}
    for p in probes:
        assert {"target", "kind", "endpoint", "ok", "latency_ms", "error", "affects"} <= set(p)
        assert isinstance(p["affects"], list) and p["affects"]


def test_run_writes_jsonl_and_sidecar(tmp_path, monkeypatch):
    probe = _load_probe()
    monkeypatch.setattr(probe, "HEALTH_JSONL", tmp_path / "mcp-health.jsonl")
    monkeypatch.setattr(probe, "SIDECAR", tmp_path / "_mcp_health.json")

    # qdrant down, остальное up
    def fake_http(url, timeout, post=None):
        return (False, 100, "boom") if "6333" in url or "healthz" in url else (True, 5, "")

    monkeypatch.setattr(probe, "_http_ok", fake_http)
    monkeypatch.setattr(probe, "_sqlite_ok", lambda *a, **k: (True, 1, ""))

    summary = probe.run(timeout=0.5, now=datetime(2026, 7, 14, 12, 0, 0))
    assert summary["total"] == 4
    assert any(d["target"] == "qdrant" for d in summary["down"])
    # sidecar записан
    sc = json.loads((tmp_path / "_mcp_health.json").read_text(encoding="utf-8"))
    assert sc["up"] == summary["up"]
    # jsonl содержит 4 строки
    lines = (tmp_path / "mcp-health.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4


# ── SessionStart hook ────────────────────────────────────────────────────────


def _load_hook(monkeypatch, run_return):
    """Загрузить хук с фейковым probe_mcp_health.run (через sys.modules)."""
    fake = ModuleType("probe_mcp_health")
    fake.run = lambda **k: run_return
    monkeypatch.setitem(sys.modules, "probe_mcp_health", fake)
    spec = importlib.util.spec_from_file_location("_mcp_health_hook", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hook_quiet_when_all_up(monkeypatch):
    mod = _load_hook(monkeypatch, {"down": [], "total": 4, "up": 4})
    out = mod.McpHealthProbe().execute(mod.HookInput({}))
    assert out is None


def test_hook_banner_when_down(monkeypatch):
    run_return = {
        "down": [
            {
                "target": "qdrant",
                "endpoint": "http://x/healthz",
                "error": "boom",
                "affects": ["vector-memory", "bsl-semantic-search"],
            }
        ],
        "total": 4,
        "up": 3,
    }
    mod = _load_hook(monkeypatch, run_return)
    out = mod.McpHealthProbe().execute(mod.HookInput({}))
    assert out is not None
    msg = out._data.get("systemMessage", "")
    assert "qdrant" in msg and "vector-memory" in msg


def test_hook_opt_out(monkeypatch):
    mod = _load_hook(monkeypatch, {"down": [{"target": "qdrant"}], "total": 4, "up": 3})
    monkeypatch.setenv("MCP_HEALTH_PROBE_DISABLE", "1")
    out = mod.McpHealthProbe().execute(mod.HookInput({}))
    assert out is None


def test_hook_graceful_when_probe_raises(monkeypatch):
    def boom(**k):
        raise RuntimeError("probe exploded")

    fake = ModuleType("probe_mcp_health")
    fake.run = boom
    monkeypatch.setitem(sys.modules, "probe_mcp_health", fake)
    spec = importlib.util.spec_from_file_location("_mcp_health_hook2", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = mod.McpHealthProbe().execute(mod.HookInput({}))
    assert out is None  # graceful — не ломает старт
