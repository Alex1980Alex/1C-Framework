"""Регрессия N-P2 (roadmap 260718): расширение покрытия probe + per-call логи.

N-P2.1 — probe покрывает 1С-контур (6× 1c-mcp-crud reachability) + skill-learning
         силос. 1С-инстансы severity=degraded (dev-инфобазы флапают → advisory,
         без авто-задачи), core-deps остаются broken.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load(mod_name, filename):
    spec = importlib.util.spec_from_file_location(mod_name, _SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


probe = _load("_probe_np2", "probe_mcp_health.py")
ath = _load("_ath_np2", "analyze_tool_health.py")

NOW = datetime(2026, 7, 18, 12, 0, 0)


# ── N-P2.1: config + probe helpers ────────────────────────────────────────────


def test_load_1c_instances_reads_mcp_json():
    """_load_1c_instances находит все 1c-mcp-crud* с непустым MCP_ONEC_URL."""
    inst = probe._load_1c_instances()
    names = {n for n, _ in inst}
    assert "1c-mcp-crud" in names
    assert any(n.startswith("1c-mcp-crud-") for n in names)  # хотя бы один инстанс
    assert all(url.startswith("http") for _, url in inst)


def test_dir_writable_ok(tmp_path):
    ok, _, err = probe._dir_writable(tmp_path)
    assert ok and not err


def test_dir_writable_missing(tmp_path):
    ok, _, err = probe._dir_writable(tmp_path / "nope")
    assert not ok and "missing" in err


def test_probe_all_includes_1c_and_skill_learning(monkeypatch):
    """probe_all добавляет skill-learning + 1С-инстансы поверх 4 core (N-P2.1)."""
    monkeypatch.setattr(
        probe, "_load_1c_instances", lambda: [("1c-mcp-crud", "http://localhost/x")]
    )
    monkeypatch.setattr(probe, "_http_ok", lambda *a, **k: (False, 1, "down"))
    monkeypatch.setattr(probe, "_sqlite_ok", lambda *a, **k: (False, 1, "down"))
    monkeypatch.setattr(probe, "_http_reachable", lambda *a, **k: (True, 1, ""))
    monkeypatch.setattr(probe, "_dir_writable", lambda *a, **k: (True, 1, ""))
    probes = probe.probe_all(timeout=0.1)
    targets = {p["target"]: p for p in probes}
    assert "skill-learning" in targets and targets["skill-learning"]["severity"] == "broken"
    assert "1c-mcp-crud" in targets and targets["1c-mcp-crud"]["severity"] == "degraded"
    assert targets["qdrant"]["severity"] == "broken"


def test_probe_1c_opt_out(monkeypatch):
    monkeypatch.setenv("MCP_PROBE_1C_DISABLE", "1")
    monkeypatch.setattr(probe, "_http_ok", lambda *a, **k: (True, 1, ""))
    monkeypatch.setattr(probe, "_sqlite_ok", lambda *a, **k: (True, 1, ""))
    monkeypatch.setattr(probe, "_dir_writable", lambda *a, **k: (True, 1, ""))
    probes = probe.probe_all(timeout=0.1)
    assert not any(p["target"].startswith("1c-mcp-crud") for p in probes)


# ── N-P2.1: severity flow (1С-инстанс down → degraded, не broken) ─────────────


def test_1c_instance_down_is_degraded_not_broken(tmp_path):
    """1С-инстанс down ≥2д → infra_alert level=degraded (advisory), тулы НЕ broken."""
    log = tmp_path / "mcp-health.jsonl"
    log.write_text(
        "\n".join(
            json.dumps(
                {
                    "ts": (NOW - timedelta(days=d)).isoformat(),
                    "target": "1c-mcp-crud-erp",
                    "ok": False,
                    "affects": ["1c-mcp-crud-erp"],
                    "severity": "degraded",
                }
            )
            for d in (3, 2, 1, 0)
        ),
        encoding="utf-8",
    )
    down = ath.mcp_down_deps(NOW, log=log)
    assert len(down) == 1 and down[0]["severity"] == "degraded"

    # gather → level degraded
    import types

    monkey = types.SimpleNamespace()
    orig = ath.MCP_HEALTH_LOG
    ath.MCP_HEALTH_LOG = log
    try:
        alerts = ath.gather_infra_alerts(NOW, with_sinks=False)
    finally:
        ath.MCP_HEALTH_LOG = orig
    assert len(alerts) == 1 and alerts[0]["level"] == "degraded"

    # apply НЕ форсит broken при degraded-инфре
    tools = {"mcp__1c-mcp-crud-erp__execute_query": {"verdict": "healthy", "reason": "ok"}}
    ath.apply_infra_to_tools(tools, alerts)
    assert tools["mcp__1c-mcp-crud-erp__execute_query"]["verdict"] == "healthy"


def test_core_dep_down_stays_broken(tmp_path):
    """core-dep (qdrant) down ≥2д → severity broken (регресс severity-по-умолчанию)."""
    log = tmp_path / "mcp-health.jsonl"
    log.write_text(
        "\n".join(
            json.dumps(
                {
                    "ts": (NOW - timedelta(days=d)).isoformat(),
                    "target": "qdrant",
                    "ok": False,
                    "affects": ["vector-memory"],
                    "severity": "broken",
                }
            )
            for d in (3, 2, 1, 0)
        ),
        encoding="utf-8",
    )
    down = ath.mcp_down_deps(NOW, log=log)
    assert down[0]["severity"] == "broken"


# ── N-P2.2: per-call лог memory-серверов (mcp_call_log wiring) ─────────────────


def test_ai_memory_call_tool_logs_unknown(tmp_path, monkeypatch):
    """Реальный сервер memory-ai: неизвестный тул → строка в mcp-memory-ai-calls.jsonl
    (ok=False, error_type=unknown_tool) — пин обёртки track_call (N-P2.2)."""
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(tmp_path / "memory_ai.db"))
    try:
        from src.memory.ai_memory import server as s
    except Exception:  # pragma: no cover - mcp/env недоступен
        pytest.skip("ai_memory server import unavailable")
    import asyncio

    assert s._MCP_SERVER_SLUG == "memory-ai"
    asyncio.run(s.call_tool("bogus_tool_xyz", {}))
    log = tmp_path / "mcp-memory-ai-calls.jsonl"
    assert log.exists()
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    hit = [r for r in rows if r.get("tool") == "bogus_tool_xyz"]
    assert hit and hit[0]["ok"] is False and hit[0]["error_type"] == "unknown_tool"
    assert all(r["server"] == "memory-ai" for r in rows)


@pytest.mark.parametrize(
    "rel,slug",
    [
        ("src/memory/vector_memory/server.py", "vector-memory"),
        ("src/memory/skill_learning/server.py", "skill-learning"),
        ("src/memory/ai_memory/server.py", "memory-ai"),
    ],
)
def test_server_call_tool_wrapped_in_track_call(rel, slug):
    """Структурный пин: call_tool каждого memory-сервера обёрнут track_call + slug."""
    src = (_ROOT / rel).read_text(encoding="utf-8")
    assert f'_MCP_SERVER_SLUG = "{slug}"' in src
    assert "with _track_call(_MCP_SERVER_SLUG, name)" in src
    assert "from scripts.mcp_call_log import track_call" in src
