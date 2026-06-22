"""Unit-тесты onec-task-completion-stop (единый task-completion gate 1С). marker: unit.

Collision-immune (importlib). Покрытие: _collect_signals (recall/capture/research/skill/config_edit по
фактическим tool_use; .md-capture только в `.claude/`; 1С-методика vs прочие методики),
_onec_pipeline_updated (сессионный детект) + _incomplete_onec_pipeline (H5 межсессионный).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "onec-task-completion-stop.py"
_spec = importlib.util.spec_from_file_location("onec_task_completion_stop_t", _HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _transcript(p: Path, tool_uses: list[tuple[str, dict]]) -> None:
    p.write_text(
        "\n".join(
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": n, "input": i}],
                    }
                }
            )
            for n, i in tool_uses
        ),
        encoding="utf-8",
    )


def test_collect_all_signals(tmp_path):
    t = tmp_path / "t.json"
    _transcript(
        t,
        [
            ("mcp__memory-orchestrator__unified_search", {}),
            ("mcp__skill-learning__capture_pattern", {}),
            ("WebSearch", {"query": "1с infostart"}),
            ("Skill", {"skill": "analyze-1c-task-v2"}),
        ],
    )
    assert mod._collect_signals(str(t)) == {
        "recall": True,
        "capture": True,
        "research": True,
        "skill": True,
        "config_edit": False,
        # ADR-035 Фаза 1 — advisory T1-T2 (в этом транскрипте отсутствуют)
        "impact": False,
        "debug_trace": False,
        "ref_search": False,
    }


def test_collect_none(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Read", {"file_path": "x"}), ("Bash", {"command": "echo"})])
    assert mod._collect_signals(str(t)) == {
        "recall": False,
        "capture": False,
        "research": False,
        "skill": False,
        "config_edit": False,
        "impact": False,
        "debug_trace": False,
        "ref_search": False,
    }


def test_collect_partial(tmp_path):
    # recall + research есть, capture + skill нет
    t = tmp_path / "t.json"
    _transcript(
        t,
        [
            ("mcp__vector-memory__search_patterns", {}),
            ("WebFetch", {"url": "https://github.com/x"}),
        ],
    )
    sig = mod._collect_signals(str(t))
    assert sig["recall"] and sig["research"] and not sig["capture"] and not sig["skill"]


def test_collect_md_capture_only_in_claude(tmp_path):
    # .md в курируемой памяти (`.claude/.../memory/`) = capture; src/memory/ — нет (N6)
    t = tmp_path / "t.json"
    _transcript(t, [("Write", {"file_path": "C:/Users/x/.claude/projects/p/memory/f.md"})])
    assert mod._collect_signals(str(t))["capture"] is True
    t2 = tmp_path / "t2.json"
    _transcript(t2, [("Write", {"file_path": "src/memory/README.md"})])
    assert mod._collect_signals(str(t2))["capture"] is False


def test_collect_skill_non_1c_not_counted(tmp_path):
    t = tmp_path / "t.json"
    _transcript(t, [("Skill", {"skill": "deployment"})])
    assert mod._collect_signals(str(t))["skill"] is False


def test_collect_config_edit(tmp_path):
    # H5: правка 1С-кода в сессии (.bsl / configuration/) → config_edit True; прочее → False
    t = tmp_path / "t.json"
    _transcript(t, [("Edit", {"file_path": "C:/1С-Framework/configuration/X/Module.bsl"})])
    assert mod._collect_signals(str(t))["config_edit"] is True
    t2 = tmp_path / "t2.json"
    _transcript(t2, [("Edit", {"file_path": "scripts/foo.py"})])
    assert mod._collect_signals(str(t2))["config_edit"] is False


def _isolate_pipeline(monkeypatch, pdir):
    """Изолировать энумерацию пайплайнов на тестовую папку pdir (пустой реестр).

    Патчим mod.PIPELINE_DIR (graceful-fallback хука) ВСЕГДА; и shared.pipeline_state.* — best-effort
    (при коллизии src/shared↔hooks/shared в полном прогоне `from shared import pipeline_state` падает
    и в хуке, и тут — хук уходит в fallback glob(mod.PIPELINE_DIR), которого достаточно). См. памятку
    feedback-hook-src-shared-collision."""
    monkeypatch.setattr(mod, "PIPELINE_DIR", pdir)
    try:
        from shared import pipeline_state as _ps

        if hasattr(_ps, "iter_states"):
            monkeypatch.setattr(_ps, "PIPELINE_DIR", pdir)
            monkeypatch.setattr(_ps, "REGISTRY_PTR", pdir / "_no_registry.json")
    except Exception:
        pass  # коллизия src/shared → хук использует fallback glob(mod.PIPELINE_DIR)


def test_onec_pipeline_updated_this_session(tmp_path, monkeypatch):
    _isolate_pipeline(monkeypatch, tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача (run-1c-task): zz", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_pipeline_updated(datetime(2026, 6, 15)) == "task1"
    assert mod._onec_pipeline_updated(None) is None


def test_onec_pipeline_lookalike_excluded(tmp_path, monkeypatch):
    _isolate_pipeline(monkeypatch, tmp_path)
    d = tmp_path / "task1"
    d.mkdir()
    (d / ".pipeline-state.json").write_text(
        json.dumps({"title": "1С-задача из чата: x", "updated_at": "2027-01-01T00:00:00"}),
        encoding="utf-8",
    )
    assert mod._onec_pipeline_updated(datetime(2026, 6, 15)) is None


def test_incomplete_onec_pipeline_h5(tmp_path, monkeypatch):
    # H5: межсессионная задача — этапы не все done → возвращает slug
    inc = tmp_path / "inc"
    inc.mkdir()
    _isolate_pipeline(monkeypatch, inc)
    d = inc / "task_h5"
    d.mkdir(parents=True)
    (d / ".pipeline-state.json").write_text(
        json.dumps(
            {
                "title": "1С-задача (run-1c-task): h5",
                "stages": [{"status": "done"}, {"status": "pending"}],
            }
        ),
        encoding="utf-8",
    )
    assert mod._incomplete_onec_pipeline() == "task_h5"
    # все этапы done → None
    done = tmp_path / "done"
    done.mkdir()
    _isolate_pipeline(monkeypatch, done)
    d2 = done / "task_done"
    d2.mkdir(parents=True)
    (d2 / ".pipeline-state.json").write_text(
        json.dumps(
            {
                "title": "1С-задача (run-1c-task): dd",
                "stages": [{"status": "done"}, {"status": "done"}],
            }
        ),
        encoding="utf-8",
    )
    assert mod._incomplete_onec_pipeline() is None


# ─── ADR-035 Фаза 1 — advisory T1-T2 ────────────────────────────────────────


def test_collect_advisory_t1_t2(tmp_path):
    # T1 impact + T1 BP-trace (содержательный) + T2 reference-search детектятся
    t = tmp_path / "t.json"
    _transcript(
        t,
        [
            ("mcp__bsl-semantic-search__bsl_impact_analysis", {}),
            ("mcp__1c-debug-hmr__debug_stack_trace", {}),
            ("mcp__bsl-semantic-search__bsl_search", {}),
        ],
    )
    sig = mod._collect_signals(str(t))
    assert sig["impact"] and sig["debug_trace"] and sig["ref_search"]
    # advisory не подменяют hard-сигналы
    assert not sig["recall"] and not sig["capture"] and not sig["research"]


def test_debug_trace_narrowed_to_substantive(tmp_path):
    # connection-проверки (ping/health/targets) НЕ считаются BP-trace; реальная трассировка — да
    for tool, expected in [
        ("mcp__1c-debug-hmr__debug_ping", False),
        ("mcp__1c-debug-hmr__debug_health_check", False),
        ("mcp__1c-debug-hmr__debug_targets", False),
        ("mcp__1c-debug-hmr__debug_stack_trace", True),
        ("mcp__1c-debug__debug_set_breakpoint", True),
        ("mcp__1c-debug-hmr__debug_variables", True),
    ]:
        t = tmp_path / "dt.json"
        _transcript(t, [(tool, {})])
        assert mod._collect_signals(str(t))["debug_trace"] is expected, tool


def test_advisory_absent_does_not_block(tmp_path):
    # ИНВАРИАНТ ADR-035: hard-петли есть, T1-T2 отсутствуют → блок-условие
    # all(recall,capture,research) остаётся True (advisory НЕ влияет на блок).
    t = tmp_path / "t.json"
    _transcript(
        t,
        [
            ("mcp__memory-orchestrator__unified_search", {}),
            ("mcp__skill-learning__capture_pattern", {}),
            ("WebSearch", {"query": "x"}),
        ],
    )
    sig = mod._collect_signals(str(t))
    assert not (sig["impact"] or sig["debug_trace"] or sig["ref_search"])
    assert all(sig[k] for k in ("recall", "capture", "research")) is True


def test_log_advisory_event_rotation(tmp_path, monkeypatch):
    # FIFO-ротация: лог обрезается до ADVISORY_LOG_CAP последних записей, последняя — present
    log = tmp_path / "events.jsonl"
    monkeypatch.setattr(mod, "ADVISORY_EVENTS_LOG", log)
    monkeypatch.setattr(mod, "ADVISORY_LOG_CAP", 3)
    sig = {"impact": False, "debug_trace": False, "ref_search": False, "config_edit": True}
    for i in range(6):
        mod._log_advisory_event(f"slug-{i}", sig, hard_blocked=False)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # обрезано до cap
    assert json.loads(lines[-1])["slug"] == "slug-5"  # последняя запись сохранена
    assert json.loads(lines[0])["slug"] == "slug-3"  # старые вытеснены (FIFO)
