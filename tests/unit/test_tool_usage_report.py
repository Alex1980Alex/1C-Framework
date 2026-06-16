"""Unit-тесты tool_usage_report (roadmap 260614 раздел W). marker: unit.

Агрегация по run_id + rollup на фейковых jsonl (tmp_path). Скрипт грузится importlib'ом
(stdlib-only, без shared-зависимости → collision-free).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_S = Path(__file__).resolve().parents[2] / "scripts" / "tool_usage_report.py"
_spec = importlib.util.spec_from_file_location("tool_usage_report_t", _S)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _write(p: Path, rows: list[dict]) -> None:
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


def test_aggregate_by_run_id(tmp_path):
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 10, "correlationid": "R1"},
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 20, "correlationid": "R1"},
        {"tool": "crud", "outcome": "error", "elapsed_ms": 100, "correlationid": "R1"},
        {"tool": "edt", "outcome": "allow", "elapsed_ms": 5, "correlationid": "R2"},  # другой run
    ])
    agg = mod.aggregate(run_id="R1", log=log)
    assert agg["edt"]["calls"] == 2 and agg["edt"]["errors"] == 0 and agg["edt"]["ms"] == 30
    assert agg["crud"]["calls"] == 1 and agg["crud"]["errors"] == 1


def test_rollup_and_report(tmp_path):
    eff = tmp_path / "eff.jsonl"
    _write(eff, [
        {"key": "R1", "tool": "edt", "calls": 2, "errors": 0, "ms": 30},
        {"key": "R2", "tool": "edt", "calls": 1, "errors": 1, "ms": 5},
    ])
    agg = mod.rollup(eff=eff)
    assert agg["edt"]["calls"] == 3 and agg["edt"]["errors"] == 1
    md = mod.report_md(agg, "ROLLUP")
    assert "`edt`" in md and "· назначение:" in md  # блочный формат


def test_append_eff(tmp_path):
    eff = tmp_path / "eff.jsonl"
    mod.append_eff({"edt": {"calls": 1, "errors": 0, "ms": 7}}, "R9", eff=eff)
    line = json.loads(eff.read_text(encoding="utf-8").strip())
    assert line["key"] == "R9" and line["tool"] == "edt" and line["calls"] == 1


# --- resolve_task_dir: единый источник папки (реестр) для TOOL-USAGE-REPORT.md ---

_PS = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "pipeline_state.py"


def _iso_ps(monkeypatch, tmp):
    """Изолированный pipeline_state (tmp-реестр), подменённый в mod._load_pipeline_state."""
    spec = importlib.util.spec_from_file_location("ps_for_tur_t", _PS)
    ps = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ps)
    tmp = Path(tmp).resolve()
    ps.PROJECT_ROOT = tmp
    ps.PIPELINE_DIR = tmp / "pipeline"
    ps.CURRENT_PTR = ps.PIPELINE_DIR / "CURRENT"
    ps.REGISTRY_PTR = ps.PIPELINE_DIR / "_1c_index.json"
    monkeypatch.setattr(mod, "_load_pipeline_state", lambda: ps)
    return ps


def test_resolve_task_dir_override(monkeypatch, tmp_path):
    _iso_ps(monkeypatch, tmp_path)
    assert mod.resolve_task_dir(task_dir=str(tmp_path / "manual")) == Path(tmp_path / "manual")


def test_resolve_slug_registry(monkeypatch, tmp_path):
    ps = _iso_ps(monkeypatch, tmp_path)
    td = Path(tmp_path).resolve() / "configuration" / "X" / "docs" / "T"
    td.mkdir(parents=True)
    ps.init_task("GKSTCPLK-1", title="1С-задача (run-1c-task): GKSTCPLK-1", task_dir=str(td))
    assert mod.resolve_task_dir(slug="gkstcplk-1") == td


def test_resolve_auto_current_1c(monkeypatch, tmp_path):
    ps = _iso_ps(monkeypatch, tmp_path)
    td = Path(tmp_path).resolve() / "configuration" / "Y" / "docs" / "W"
    td.mkdir(parents=True)
    ps.init_task("GKSTCPLK-2", title="1С-задача (run-1c-task): GKSTCPLK-2", task_dir=str(td))
    assert mod.resolve_task_dir() == td  # CURRENT=зарегистрированная 1С → авто в папку задачи


def test_resolve_auto_generic_none(monkeypatch, tmp_path):
    ps = _iso_ps(monkeypatch, tmp_path)
    ps.init_task("gen", title="Обычная задача")  # CURRENT=generic, не в реестре
    assert mod.resolve_task_dir() is None  # авто НЕ пишет (без сюрприза) → stdout


def test_resolve_slug_generic_honored(monkeypatch, tmp_path):
    ps = _iso_ps(monkeypatch, tmp_path)
    ps.init_task("gen", title="Обычная задача")
    assert mod.resolve_task_dir(slug="gen") == ps.PIPELINE_DIR / "gen"  # явный slug уважается


def test_resolve_loader_failure_best_effort(monkeypatch):
    monkeypatch.setattr(mod, "_load_pipeline_state", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert mod.resolve_task_dir(slug="x") is None  # сбой загрузки → None, не кидает
    assert mod.resolve_task_dir(task_dir="/explicit") == Path("/explicit")  # override до загрузчика


# --- классификация инструментов + группированный отчёт ---


def test_classify_tool():
    c = mod.classify_tool
    assert c("mcp__memory-orchestrator__unified_search") == "memory"
    assert c("mcp__vector-memory__search_patterns") == "memory"
    assert c("mcp__skill-learning__capture_pattern") == "memory"
    assert c("Skill") == "skills"
    assert c("WebSearch") == "research" and c("WebFetch") == "research"
    assert c("mcp__1c-mcp-crud__execute_query") == "config"  # read → анализ
    assert c("mcp__1c-mcp-crud__get_metadata_structure") == "config"
    assert c("mcp__bsl-semantic-search__bsl_search") == "config"
    assert c("mcp__edt-mcp__read_module_source") == "config"  # read split
    assert c("mcp__1c-mcp-crud__execute_code") == "impl"  # write/execute → кодирование
    assert c("mcp__edt-mcp__write_module_source") == "impl"
    assert c("mcp__edt-mcp__update_database") == "impl"
    assert c("mcp__mcp-onec-test-runner__run_all_tests") == "testing"
    assert c("Edit") == "infra" and c("Bash") == "infra" and c("Agent") == "infra"
    assert c("mcp__unknown-server__foo") == "infra"  # неизвестный сервер → infra


def test_tool_summary():
    assert mod.tool_summary("Edit") == "Точечная правка файла"
    assert mod.tool_summary("mcp__edt-mcp__write_module_source")  # known → непусто
    assert mod.tool_summary("mcp__x__some_op") == "some op"  # неизвестное MCP → суффикс


def test_report_md_grouped():
    by_tool = {
        "mcp__memory-orchestrator__unified_search": {"calls": 1, "errors": 0, "ms": 20},
        "Skill": {"calls": 5, "errors": 0, "ms": 100},
        "mcp__1c-mcp-crud__execute_query": {"calls": 2, "errors": 0, "ms": 40},
        "WebSearch": {"calls": 1, "errors": 0, "ms": 90},
        "mcp__1c-mcp-crud__execute_code": {"calls": 3, "errors": 0, "ms": 60},
        "Edit": {"calls": 10, "errors": 3, "ms": 500},
    }
    md = mod.report_md(by_tool, "TEST")
    # чеклист обязательных петель — все 4 присутствуют (использованы)
    assert "## Обязательные петли" in md
    for m in ("✓ **Память", "✓ **Скилы", "✓ **Анализ конфигурации", "✓ **Внешний анализ"):
        assert m in md, m
    # блочный формат: секции по категориям + назначение + результат под каждым инструментом
    assert "## Анализ конфигурации 1С · **обязательный**" in md
    assert "IMPLEMENTATION-PROGRESS.md" in md  # категория Кодирование (execute_code)
    assert "· назначение:" in md and "· результат:" in md
    assert "Точечная правка файла" in md  # саммари Edit
    assert "**`Edit`**" in md  # блок-заголовок инструмента


def test_report_md_results_rendered():
    # курируемый результат показывается под инструментом; отсутствующий → «—»
    by_tool = {"WebSearch": {"calls": 2, "errors": 0, "ms": 90}, "Edit": {"calls": 1, "errors": 0, "ms": 5}}
    res = {"WebSearch": "Infostart: data-driven печать = канон БСП"}
    md = mod.report_md(by_tool, "T", results=res)
    assert "· результат: Infostart: data-driven печать = канон БСП" in md
    assert "· результат: —" in md  # Edit без курируемого результата


def test_load_results(tmp_path):
    p = tmp_path / "TOOL-RESULTS.json"
    p.write_text('{"WebSearch": "нашёл X", "n": 5}', encoding="utf-8")
    r = mod.load_results(str(p))
    assert r["WebSearch"] == "нашёл X" and r["n"] == "5"  # значения приводятся к str
    assert mod.load_results(None, None) == {}  # нет источника → пусто
    assert mod.load_results(str(tmp_path / "nope.json")) == {}  # битый/нет файла → пусто


def test_report_md_missing_mandatory_marks_cross(monkeypatch):
    # нет research/анализа → ✗ в чеклисте; скилы есть → ✓
    md = mod.report_md({"Skill": {"calls": 1, "errors": 0, "ms": 1}}, "T")
    assert "✗ **Внешний анализ" in md and "✗ **Анализ конфигурации" in md
    assert "✓ **Скилы" in md


def test_report_md_empty_unchanged():
    md = mod.report_md({}, "T")
    assert "нет вызовов" in md


# --- ADR-022 P0.2: реальная латентность MCP через Pre/Post-пару ---


def test_aggregate_mcp_pre_post_real_latency(tmp_path):
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"category": "mcp_call", "event": "PreToolUse", "tool": "mcp__edt-mcp__update_database",
         "ts": "2026-06-17T10:00:00", "tool_call_id": "c1", "correlationid": "R1"},
        {"category": "mcp_call", "event": "PostToolUse", "tool": "mcp__edt-mcp__update_database",
         "ts": "2026-06-17T10:00:03", "tool_call_id": "c1", "outcome": "allow", "correlationid": "R1"},
    ])
    a = mod.aggregate(run_id="R1", log=log)["mcp__edt-mcp__update_database"]
    assert a["calls"] == 1                  # Pre+Post одного вызова не двоятся
    assert a["latency_real"] is True and a["paired"] == 1
    assert a["ms"] == 3000                  # реальные 3с (ts(post)−ts(pre)), не overhead хука
    assert a["errors"] == 0


def test_aggregate_mcp_pre_only_no_latency(tmp_path):
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"category": "mcp_call", "event": "PreToolUse", "tool": "mcp__x__op",
         "ts": "2026-06-17T10:00:00", "correlationid": "R1"},
    ])
    a = mod.aggregate(run_id="R1", log=log)["mcp__x__op"]
    assert a["calls"] == 1 and a["paired"] == 0 and a["latency_real"] is False and a["ms"] == 0


def test_aggregate_mcp_error_from_post(tmp_path):
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"category": "mcp_call", "event": "PreToolUse", "tool": "mcp__x__op",
         "ts": "2026-06-17T10:00:00", "correlationid": "R1"},
        {"category": "mcp_call", "event": "PostToolUse", "tool": "mcp__x__op",
         "ts": "2026-06-17T10:00:01", "outcome": "error", "error": "boom", "correlationid": "R1"},
    ])
    a = mod.aggregate(run_id="R1", log=log)["mcp__x__op"]
    assert a["errors"] == 1 and a["paired"] == 1 and a["ms"] == 1000


def test_aggregate_mcp_no_double_count_with_hook_row(tmp_path):
    # MCP-тул с mcp_call-парой + stray hook-auto-log строкой → hook не двоит calls/ms
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"category": "mcp_call", "event": "PreToolUse", "tool": "mcp__llm-rotation__llm_complete",
         "ts": "2026-06-17T10:00:00", "correlationid": "R1"},
        {"category": "mcp_call", "event": "PostToolUse", "tool": "mcp__llm-rotation__llm_complete",
         "ts": "2026-06-17T10:00:02", "outcome": "allow", "correlationid": "R1"},
        {"category": "hook", "tool": "mcp__llm-rotation__llm_complete", "elapsed_ms": 20,
         "outcome": "allow", "correlationid": "R1"},  # наблюдатель-хук — игнор
    ])
    a = mod.aggregate(run_id="R1", log=log)["mcp__llm-rotation__llm_complete"]
    assert a["calls"] == 1 and a["ms"] == 2000 and a["latency_real"] is True


def test_aggregate_non_mcp_overhead_unchanged(tmp_path):
    # нативный тул (нет category) — старое поведение: счёт строк + Σelapsed_ms, latency_real=False
    log = tmp_path / "log.jsonl"
    _write(log, [
        {"tool": "Edit", "outcome": "allow", "elapsed_ms": 10, "correlationid": "R1"},
        {"tool": "Edit", "outcome": "allow", "elapsed_ms": 20, "correlationid": "R1"},
    ])
    a = mod.aggregate(run_id="R1", log=log)["Edit"]
    assert a["calls"] == 2 and a["ms"] == 30 and a["latency_real"] is False


def test_report_md_latency_real_vs_overhead():
    by_tool = {
        "mcp__edt-mcp__update_database": {"calls": 1, "errors": 0, "ms": 3000, "paired": 1, "latency_real": True},
        "Edit": {"calls": 4, "errors": 0, "ms": 80, "latency_real": False},
    }
    md = mod.report_md(by_tool, "T")
    assert "3000ms" in md and "3000ms~" not in md   # реальная латентность MCP — без тильды
    assert "20ms~" in md                            # overhead хука — с тильдой
    assert "overhead хука" in md                    # footnote
