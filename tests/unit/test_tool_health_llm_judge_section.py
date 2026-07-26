"""J-P2 (roadmap 260725): семантическая секция LLM-судьи в отчёте tool-health.

Главный инвариант — **advisory**: судья добавляет вторую сигнатуру, но НЕ двигает
rule-вердикты (broken/degraded/healthy). Плюс: выключенный слой не притворяется
чистым (`content_disabled` виден), окно уважается, битые строки не роняют отчёт.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "analyze_tool_health.py"


@pytest.fixture(scope="module")
def ath():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("analyze_tool_health_j2", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOW = datetime(2026, 7, 25, 12, 0, 0)


def _write_judge(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "llm-judge.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return p


def _scored(tool: str, arg: float, task: float, ts: datetime = NOW) -> dict:
    return {
        "ts": ts.isoformat(timespec="seconds"),
        "status": "scored",
        "tool": tool,
        "argument_correctness": arg,
        "task_completion": task,
    }


# ── агрегация ─────────────────────────────────────────────────────────────────


def test_medians_computed(ath, tmp_path):
    src = _write_judge(
        tmp_path,
        [
            _scored("execute_query", 0.9, 0.8),
            _scored("execute_query", 0.7, 0.4),
            _scored("execute_query", 0.8, 0.6),
        ],
    )
    out = ath.read_judge_verdicts(NOW, 14, {}, src)
    stats = out["tools"]["execute_query"]
    assert stats["scored"] == 3
    assert stats["median_arg"] == 0.8 and stats["median_task"] == 0.6


def test_missing_file_is_empty(ath, tmp_path):
    assert ath.read_judge_verdicts(NOW, 14, {}, tmp_path / "нет.jsonl") == {}


def test_outside_window_ignored(ath, tmp_path):
    src = _write_judge(tmp_path, [_scored("t", 0.1, 0.1, NOW - timedelta(days=30))])
    assert ath.read_judge_verdicts(NOW, 14, {}, src) == {}


def test_corrupt_lines_do_not_break(ath, tmp_path):
    p = tmp_path / "llm-judge.jsonl"
    p.write_text("{битая\n" + json.dumps(_scored("t", 0.5, 0.5)) + "\n", encoding="utf-8")
    out = ath.read_judge_verdicts(NOW, 14, {}, p)
    assert out["tools"]["t"]["scored"] == 1


# ── расхождение с rule-слоем ──────────────────────────────────────────────────


def test_mismatch_flagged_when_rule_healthy(ath, tmp_path):
    """Ровно тот класс, что правила не видят: ok=true, но цель не достигнута."""
    src = _write_judge(tmp_path, [_scored("execute_query", 0.9, 0.2) for _ in range(3)])
    out = ath.read_judge_verdicts(NOW, 14, {"execute_query": {"verdict": "healthy"}}, src)
    assert out["tools"]["execute_query"]["mismatch"] is True


def test_no_mismatch_below_min_samples(ath, tmp_path):
    """Две низкие оценки — ещё не сигнал (шум); нужен статистический минимум."""
    src = _write_judge(tmp_path, [_scored("t", 0.9, 0.1), _scored("t", 0.9, 0.2)])
    out = ath.read_judge_verdicts(NOW, 14, {"t": {"verdict": "healthy"}}, src)
    assert out["tools"]["t"]["mismatch"] is False


def test_no_mismatch_when_rule_already_alerts(ath, tmp_path):
    """Если rule уже кричит broken — судья не дублирует сигнал."""
    src = _write_judge(tmp_path, [_scored("t", 0.5, 0.1) for _ in range(5)])
    out = ath.read_judge_verdicts(NOW, 14, {"t": {"verdict": "broken"}}, src)
    assert out["tools"]["t"]["mismatch"] is False


def test_high_task_completion_is_no_mismatch(ath, tmp_path):
    src = _write_judge(tmp_path, [_scored("t", 0.9, 0.9) for _ in range(4)])
    out = ath.read_judge_verdicts(NOW, 14, {"t": {"verdict": "healthy"}}, src)
    assert out["tools"]["t"]["mismatch"] is False


# ── fail-loud: выключенный слой не выглядит чистым ────────────────────────────


def test_content_disabled_surfaced(ath, tmp_path):
    src = _write_judge(
        tmp_path,
        [
            {
                "ts": NOW.isoformat(),
                "status": "content_disabled",
                "reason": "content off: MCP_CALL_LOG_CONTENT",
            }
        ],
    )
    out = ath.read_judge_verdicts(NOW, 14, {}, src)
    assert "MCP_CALL_LOG_CONTENT" in out["content_disabled"]
    assert "tools" not in out


def test_scored_data_wins_over_stale_disabled_marker(ath, tmp_path):
    """Есть свежие оценки → слой работает; старый маркер не должен вводить в заблуждение."""
    src = _write_judge(
        tmp_path,
        [
            {"ts": NOW.isoformat(), "status": "content_disabled", "reason": "off"},
            _scored("t", 0.8, 0.8),
        ],
    )
    out = ath.read_judge_verdicts(NOW, 14, {}, src)
    assert "tools" in out and "content_disabled" not in out


# ── рендер + инвариант advisory ───────────────────────────────────────────────


def test_section_rendered(ath):
    health = {
        "generated": NOW.isoformat(),
        "tools": {},
        "llm_judge": {
            "tools": {
                "execute_query": {
                    "scored": 4,
                    "median_arg": 0.9,
                    "median_task": 0.3,
                    "mismatch": True,
                }
            }
        },
    }
    md = ath.render_md(health, 14)
    assert "Семантика (LLM-judge, advisory)" in md
    assert "execute_query" in md and "⚠ да" in md


def test_disabled_note_rendered(ath):
    health = {
        "generated": NOW.isoformat(),
        "tools": {},
        "llm_judge": {"content_disabled": "content off"},
    }
    md = ath.render_md(health, 14)
    assert "Судья не работал" in md


def test_section_absent_without_judge_data(ath):
    md = ath.render_md({"generated": NOW.isoformat(), "tools": {}}, 14)
    assert "LLM-judge" not in md


def test_judge_never_changes_rule_verdicts(ath, tmp_path):
    """ГЛАВНЫЙ инвариант J-P2: агрегация судьи не мутирует вердикты rule-слоя."""
    tools = {"t": {"verdict": "healthy", "reason": "ok"}}
    snapshot = json.dumps(tools, sort_keys=True)
    src = _write_judge(tmp_path, [_scored("t", 0.1, 0.1) for _ in range(10)])
    ath.read_judge_verdicts(NOW, 14, tools, src)
    assert json.dumps(tools, sort_keys=True) == snapshot
