"""J-P3 (roadmap 260725): валидатор промоута LLM-судьи.

Ключевые инварианты:
  - порог зафиксирован ДО окна (не подгоняется задним числом);
  - неразмеченные расхождения НЕ идут в статистику (иначе precision выдуман);
  - сырая precision корректируется на ошибку самого судьи (judgy-паттерн);
  - вердикт промоута — рекомендация, промоут остаётся ручным.
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
SCRIPT = ROOT / "scripts" / "tool_judge_validation.py"
NOW = datetime(2026, 7, 25, 12, 0, 0)


@pytest.fixture(scope="module")
def tjv():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("tool_judge_validation", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _judge_file(tmp_path: Path, n: int, task: float = 0.2, ts: datetime = NOW) -> Path:
    recs = [
        {
            "ts": ts.isoformat(timespec="seconds"),
            "status": "scored",
            "tool": "execute_query",
            "tool_use_id": f"id-{i}",
            "argument_correctness": 0.9,
            "task_completion": task,
        }
        for i in range(n)
    ]
    p = tmp_path / "llm-judge.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    return p


def _review_file(tmp_path: Path, verdicts: list[bool], category: str = "empty_result") -> Path:
    recs = [
        {"tool_use_id": f"id-{i}", "confirmed": ok, "category": category}
        for i, ok in enumerate(verdicts)
    ]
    p = tmp_path / "judge-review.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")
    return p


# ── сбор расхождений ──────────────────────────────────────────────────────────


def test_only_low_task_completion_counts(tjv):
    cutoff = NOW - timedelta(days=14)
    recs = [
        {"ts": NOW.isoformat(), "status": "scored", "task_completion": 0.2},
        {"ts": NOW.isoformat(), "status": "scored", "task_completion": 0.9},
    ]
    assert len(tjv.collect_mismatches(recs, cutoff)) == 1


def test_outside_window_excluded(tjv):
    cutoff = NOW - timedelta(days=14)
    old = {"ts": (NOW - timedelta(days=30)).isoformat(), "status": "scored", "task_completion": 0.1}
    assert tjv.collect_mismatches([old], cutoff) == []


def test_non_scored_records_ignored(tjv):
    cutoff = NOW - timedelta(days=14)
    recs = [{"ts": NOW.isoformat(), "status": "content_disabled", "task_completion": 0.0}]
    assert tjv.collect_mismatches(recs, cutoff) == []


# ── вердикты ──────────────────────────────────────────────────────────────────


def test_insufficient_data_without_review(tjv, tmp_path):
    """Нет разметки → честное «нечего валидировать», а не выдуманный вердикт."""
    jf = _judge_file(tmp_path, 10)
    res = tjv.validate(NOW, 14, jf, tmp_path / "нет.jsonl")
    assert res["verdict"] == "insufficient-data"
    assert res["mismatches_found"] == 10 and res["reviewed"] == 0


def test_insufficient_below_min_samples(tjv, tmp_path):
    jf = _judge_file(tmp_path, 4)
    rf = _review_file(tmp_path, [True, True, True, True])
    res = tjv.validate(NOW, 14, jf, rf)
    assert res["verdict"] == "insufficient-data"


def test_promote_candidate_on_high_precision(tjv, tmp_path):
    jf = _judge_file(tmp_path, 6)
    rf = _review_file(tmp_path, [True, True, True, True, False, False])
    res = tjv.validate(NOW, 14, jf, rf)
    assert res["verdict"] == "promote-candidate"
    assert res["raw_precision"] == pytest.approx(4 / 6, abs=0.01)


def test_keep_advisory_on_low_precision(tjv, tmp_path):
    jf = _judge_file(tmp_path, 6)
    rf = _review_file(tmp_path, [True, False, False, False, False, False])
    res = tjv.validate(NOW, 14, jf, rf)
    assert res["verdict"] == "keep-advisory"


def test_unreviewed_mismatches_excluded_from_precision(tjv, tmp_path):
    """Разметка есть только для части — precision считается по ней, не по всем."""
    jf = _judge_file(tmp_path, 20)
    rf = _review_file(tmp_path, [True] * 5)  # размечены только id-0..id-4
    res = tjv.validate(NOW, 14, jf, rf)
    assert res["mismatches_found"] == 20 and res["reviewed"] == 5
    assert res["raw_precision"] == 1.0


# ── поправка на ошибку судьи (judgy) ──────────────────────────────────────────


def test_corrected_precision_lowers_biased_raw(tjv):
    """Судья с FPR=0.3 завышает сырую точность — поправка обязана её снизить."""
    corrected = tjv._corrected_precision(0.6, tpr=0.9, fpr=0.3)
    assert corrected is not None and corrected < 0.6


def test_corrected_precision_none_when_judge_is_coinflip(tjv):
    """TPR == FPR: судья неотличим от монетки, честный ответ — «не знаю»."""
    assert tjv._corrected_precision(0.7, tpr=0.5, fpr=0.5) is None


def test_calibration_can_flip_verdict_to_advisory(tjv, tmp_path):
    """Главное следствие поправки: смещённый «промоут» становится advisory."""
    jf = _judge_file(tmp_path, 6)
    rf = _review_file(tmp_path, [True, True, True, True, False, False])  # сырая 67%
    raw = tjv.validate(NOW, 14, jf, rf)
    assert raw["verdict"] == "promote-candidate"
    # судья с высоким FPR: 67% сырых подтверждений → 47% истинных (ниже порога)
    calibrated = tjv.validate(NOW, 14, jf, rf, tpr=0.8, fpr=0.55)
    assert calibrated["corrected_precision"] < calibrated["raw_precision"]
    assert calibrated["verdict"] == "keep-advisory"


# ── таксономия категорий ──────────────────────────────────────────────────────


def test_categories_promoted_independently(tjv, tmp_path):
    """Промоут по категориям, а не «расхождения вообще» (deepeval-паттерн)."""
    recs = []
    reviews = []
    for i in range(6):  # empty_result: 6/6 подтверждено
        recs.append(
            {
                "ts": NOW.isoformat(),
                "status": "scored",
                "tool": "t",
                "tool_use_id": f"e-{i}",
                "task_completion": 0.1,
            }
        )
        reviews.append({"tool_use_id": f"e-{i}", "confirmed": True, "category": "empty_result"})
    for i in range(6):  # wrong_tool: 0/6 подтверждено
        recs.append(
            {
                "ts": NOW.isoformat(),
                "status": "scored",
                "tool": "t",
                "tool_use_id": f"w-{i}",
                "task_completion": 0.1,
            }
        )
        reviews.append({"tool_use_id": f"w-{i}", "confirmed": False, "category": "wrong_tool"})
    jf = tmp_path / "llm-judge.jsonl"
    jf.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    rf = tmp_path / "judge-review.jsonl"
    rf.write_text("\n".join(json.dumps(r) for r in reviews), encoding="utf-8")

    res = tjv.validate(NOW, 14, jf, rf)
    assert res["categories"]["empty_result"]["promote"] is True
    assert res["categories"]["wrong_tool"]["promote"] is False


def test_unknown_category_folded_into_other(tjv, tmp_path):
    jf = _judge_file(tmp_path, 5)
    rf = _review_file(tmp_path, [True] * 5, category="выдуманная")
    res = tjv.validate(NOW, 14, jf, rf)
    assert "other" in res["categories"] and "выдуманная" not in res["categories"]


# ── прочее ────────────────────────────────────────────────────────────────────


def test_thresholds_are_fixed_constants(tjv):
    """Пороги живут в коде, а не подбираются по данным (ревью-п.2)."""
    assert tjv.PRECISION_THRESHOLD == 0.5 and tjv.MIN_MISMATCHES == 5


def test_render_mentions_manual_promotion(tjv, tmp_path):
    jf = _judge_file(tmp_path, 6)
    rf = _review_file(tmp_path, [True] * 6)
    out = tjv.render(tjv.validate(NOW, 14, jf, rf))
    assert "вручную" in out


def test_corrupt_lines_survive(tjv, tmp_path):
    jf = tmp_path / "llm-judge.jsonl"
    jf.write_text("{битая строка\n", encoding="utf-8")
    res = tjv.validate(NOW, 14, jf, tmp_path / "нет.jsonl")
    assert res["verdict"] == "insufficient-data"
