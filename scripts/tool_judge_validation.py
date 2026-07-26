#!/usr/bin/env python3
"""Валидатор промоута LLM-судьи (roadmap 260725 J-P3).

Отвечает на единственный вопрос: **стоит ли доверять расхождениям судьи настолько,
чтобы они заводили диагностические задачи** — или слой остаётся чисто справочным.

Почему нужен отдельный слой, а не «посмотрим глазами»:
  - критерий фиксируется ДО окна замера (ревью-п.2), иначе решение о промоуте
    становится произвольным задним числом — ровно та ошибка, которой избежали
    ADR-035/tdd-guard, где порог (follow_rate ≥ 0.5) стоял заранее;
  - сырая доля подтверждённых расхождений **смещена ошибкой самого судьи**
    (паттерн judgy, ai-evals-course): судья с FPR=0.3 даёт завышенную «точность»,
    если её не скорректировать. Поправка ниже — `_corrected_precision`.

Контракт входа — `data/reports/tools/llm-judge.jsonl` (вердикты J-P1) плюс
опциональный файл разметки `data/reports/tools/judge-review.jsonl`:
``{"tool_use_id": ..., "confirmed": true|false, "category": "wrong_args"|...}``
Разметку ставит человек, разбирая расхождения; без неё валидатор честно
отвечает «нечего валидировать», а не выдумывает вердикт.

Выход: `data/reports/tools/judge-validation.json` + печать сводки.
Решение о промоуте — ВСЕГДА ручное; скрипт лишь считает и рекомендует.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports" / "tools"
JUDGE_LOG = REPORTS / "llm-judge.jsonl"
REVIEW_LOG = REPORTS / "judge-review.jsonl"
OUT_JSON = REPORTS / "judge-validation.json"

# Пороги — зафиксированы ДО окна замера (J-P3, ревью-п.2).
MIN_MISMATCHES = 5  # меньше — статистики нет, вердикт «мало данных»
PRECISION_THRESHOLD = 0.5  # ≥половины расхождений подтвердились как реальный дефект
# Таксономия провалов (deepeval-agent-reliability): промоутим не «расхождения вообще»,
# а конкретные категории, которые подтверждаются.
CATEGORIES = ("wrong_args", "empty_result", "result_unused", "wrong_tool", "other")


def _read_jsonl(path: Path) -> list[dict]:
    """Строки jsonl → список dict; битые строки пропускаются (лог не обязан быть чистым)."""
    if not path.exists():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _within(rec: dict, cutoff: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(rec.get("ts", ""))) >= cutoff
    except (TypeError, ValueError):
        return False


def collect_mismatches(records: list[dict], cutoff: datetime, threshold: float = 0.5) -> list[dict]:
    """Расхождения = оценённые вызовы с низким task_completion.

    Именно они — предмет валидации: технический успех при недостигнутой цели.
    """
    out = []
    for r in records:
        if r.get("status") != "scored" or not _within(r, cutoff):
            continue
        task = r.get("task_completion")
        try:
            if task is None or float(task) >= threshold:
                continue
        except (TypeError, ValueError):
            continue
        out.append(r)
    return out


def _corrected_precision(raw: float, tpr: float, fpr: float) -> float | None:
    """Поправка на ошибку САМОГО судьи (judgy, ai-evals-course).

    Наблюдаемая доля подтверждений `raw` смешивает истинные срабатывания с
    ложными: `raw = p·TPR + (1−p)·FPR`. Отсюда истинная доля
    `p = (raw − FPR) / (TPR − FPR)`. Без калибровки (TPR/FPR не замерены)
    возвращаем None — и печатаем сырое значение как есть, не выдавая его за
    честное. Вырожденный знаменатель = судья неотличим от монетки.
    """
    denom = tpr - fpr
    if denom <= 0:
        return None
    return max(0.0, min(1.0, (raw - fpr) / denom))


def validate(
    now: datetime | None = None,
    window_days: int = 14,
    judge_path: Path | None = None,
    review_path: Path | None = None,
    tpr: float | None = None,
    fpr: float | None = None,
) -> dict:
    """Посчитать precision расхождений (общий и по категориям) → вердикт."""
    now = now or datetime.now()
    cutoff = now - timedelta(days=window_days)
    judged = _read_jsonl(judge_path or JUDGE_LOG)
    reviews = {
        str(r.get("tool_use_id")): r
        for r in _read_jsonl(review_path or REVIEW_LOG)
        if r.get("tool_use_id")
    }
    mismatches = collect_mismatches(judged, cutoff)

    reviewed, confirmed = [], []
    per_cat: dict[str, list[bool]] = defaultdict(list)
    per_tool: dict[str, list[bool]] = defaultdict(list)
    for m in mismatches:
        rev = reviews.get(str(m.get("tool_use_id")))
        if rev is None or "confirmed" not in rev:
            continue  # неразмеченное расхождение в статистику не идёт
        ok = bool(rev["confirmed"])
        reviewed.append(m)
        if ok:
            confirmed.append(m)
        cat = str(rev.get("category") or "other")
        per_cat[cat if cat in CATEGORIES else "other"].append(ok)
        per_tool[str(m.get("tool") or "")].append(ok)

    n_reviewed = len(reviewed)
    raw_precision = (len(confirmed) / n_reviewed) if n_reviewed else 0.0
    corrected = None
    if tpr is not None and fpr is not None:
        corrected = _corrected_precision(raw_precision, tpr, fpr)
    effective = corrected if corrected is not None else raw_precision

    if n_reviewed < MIN_MISMATCHES:
        verdict = "insufficient-data"
        reason = (
            f"размечено {n_reviewed} расхождений из {len(mismatches)} найденных "
            f"(нужно ≥{MIN_MISMATCHES}) — разметь их в {REVIEW_LOG.name}"
        )
    elif effective >= PRECISION_THRESHOLD:
        verdict = "promote-candidate"
        reason = (
            f"precision {effective:.0%} ≥ {PRECISION_THRESHOLD:.0%} на {n_reviewed} размеченных — "
            "расхождения судьи оправдывают заведение диагностических задач"
        )
    else:
        verdict = "keep-advisory"
        reason = (
            f"precision {effective:.0%} < {PRECISION_THRESHOLD:.0%} на {n_reviewed} размеченных — "
            "слишком много ложных срабатываний для промоута"
        )

    categories = {
        cat: {
            "reviewed": len(vals),
            "confirmed": sum(vals),
            "precision": (sum(vals) / len(vals)) if vals else 0.0,
            # промоутим ПО КАТЕГОРИЯМ, а не «расхождения вообще»
            "promote": len(vals) >= MIN_MISMATCHES
            and (sum(vals) / len(vals)) >= PRECISION_THRESHOLD,
        }
        for cat, vals in sorted(per_cat.items())
    }
    return {
        "generated": now.isoformat(timespec="seconds"),
        "window_days": window_days,
        "mismatches_found": len(mismatches),
        "reviewed": n_reviewed,
        "confirmed": len(confirmed),
        "raw_precision": round(raw_precision, 3),
        "corrected_precision": None if corrected is None else round(corrected, 3),
        "judge_calibration": {"tpr": tpr, "fpr": fpr} if tpr is not None else None,
        "threshold": PRECISION_THRESHOLD,
        "min_mismatches": MIN_MISMATCHES,
        "verdict": verdict,
        "reason": reason,
        "categories": categories,
        "tools": {
            t: {"reviewed": len(v), "confirmed": sum(v)} for t, v in sorted(per_tool.items()) if t
        },
    }


def render(res: dict) -> str:
    """Человекочитаемая сводка (печатается в stdout)."""
    lines = [
        f"judge-validation: {res['verdict']}",
        f"  {res['reason']}",
        f"  окно {res['window_days']}д: найдено расхождений {res['mismatches_found']}, "
        f"размечено {res['reviewed']}, подтверждено {res['confirmed']}",
    ]
    if res.get("corrected_precision") is not None:
        lines.append(
            f"  precision: сырая {res['raw_precision']:.0%} → "
            f"с поправкой на ошибку судьи {res['corrected_precision']:.0%}"
        )
    elif res["reviewed"]:
        lines.append(
            f"  precision сырая {res['raw_precision']:.0%} "
            "(без калибровки судьи — смещена, см. --tpr/--fpr)"
        )
    for cat, v in res.get("categories", {}).items():
        if v["reviewed"]:
            mark = "→ promote" if v["promote"] else "→ advisory"
            lines.append(
                f"  [{cat}] {v['confirmed']}/{v['reviewed']} ({v['precision']:.0%}) {mark}"
            )
    lines.append("  ⚠ промоут в hard — только вручную по этому вердикту (ADR-035: не авто-флип)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Валидатор промоута LLM-судьи (260725 J-P3)")
    ap.add_argument("--window", type=int, default=14, help="окно в днях (default 14)")
    ap.add_argument("--tpr", type=float, help="TPR судьи с размеченного сабсета (калибровка)")
    ap.add_argument("--fpr", type=float, help="FPR судьи с размеченного сабсета (калибровка)")
    ap.add_argument("--json", action="store_true", help="печатать JSON вместо сводки")
    args = ap.parse_args(argv)

    res = validate(window_days=args.window, tpr=args.tpr, fpr=args.fpr)
    try:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # отчёт в stdout важнее файла
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
