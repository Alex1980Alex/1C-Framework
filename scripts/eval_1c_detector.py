#!/usr/bin/env python3
"""Offline eval для детектора 1С-задач (classify_1c_task / route_1c_task).

Клон по духу scripts/eval-skill-router.py, но задача проще: бинарная(+weak)
классификация, не мульти-лейбл роутинг. Считает:
  * is_1c P/R/F1 (positive = 1С-задача) — ядро;
  * route_class accuracy + confusion (none / ask / confident);
  * confidence-сепарацию по классам (после калибровки #2 — mean confidence
    должен расти none < ask < confident);
  * честный train/test split (поле `split` ∨ детерминированный sha1%5) —
    ДИАГНОСТИЧЕСКИЙ (детектор не учится на GT, веса хардкод офлайн).

In-process через importlib (функции чистые) — быстро, без subprocess.
GT — JSON-массив (data/1c-detector-ground-truth.json).

Usage:
    python scripts/eval_1c_detector.py [--json] [--split train|test|all] [--verbose]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH = PROJECT_DIR / "data" / "1c-detector-ground-truth.json"
BRIDGE = PROJECT_DIR / ".claude" / "hooks" / "shared" / "pipeline_1c_bridge.py"

_CLASSES = ("none", "ask", "confident")
_BANDS = ("simple", "medium", "complex")


def load_bridge():
    spec = importlib.util.spec_from_file_location("pipeline_1c_bridge_eval", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def route_class_of(flow: str) -> str:
    """flow → класс маршрута. auto/ask_flow/gated = «уверенно повёл» = confident."""
    if flow == "none":
        return "none"
    if flow == "ask_1c":
        return "ask"
    return "confident"  # auto | ask_flow | gated


def split_of(text: str, sample: dict) -> str:
    s = sample.get("split")
    if s in ("train", "test"):
        return s
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return "test" if h % 5 == 0 else "train"


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else (1.0 if fn == 0 else 0.0)
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def evaluate(rows: list[dict], llm_tail: bool = False) -> dict:
    bridge = load_bridge()
    classify = None
    if llm_tail:  # #3 stage-3: на mid-band TF-IDF зовём LLM-классификатор (замер потолка)
        spec = importlib.util.spec_from_file_location(
            "onec_llm_tail_eval", BRIDGE.parent / "onec_llm_tail.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        classify = mod.llm_classify
    tp = fp = fn = tn = 0
    cls_tot = {c: 0 for c in _CLASSES}
    cls_ok = {c: 0 for c in _CLASSES}
    confusion = {c: {d: 0 for d in _CLASSES} for c in _CLASSES}
    conf_by_class: dict[str, list[float]] = {c: [] for c in _CLASSES}
    misses = []
    # complexity-band (Находка 3, 2026-06-18): валидация simple/medium/complex + детект auto-мисроутов.
    # Полоса достижима ТОЛЬКО на confident-входе (route_1c_task: non-confident → ask_1c минуя complexity),
    # поэтому считаем лишь по строкам, где GT задал `complexity` И предикт confident. auto_misroute =
    # GT-сложность medium/complex, а flow=auto (substantial-задача авто-прогоняется мимо гейта ревью).
    band_tot = {b: 0 for b in _BANDS}
    band_ok = {b: 0 for b in _BANDS}
    band_confusion = {b: {d: 0 for d in _BANDS} for b in _BANDS}
    auto_misroutes = []
    for s in rows:
        text = s["text"]
        exp_1c = bool(s["is_1c"])
        exp_cls = s["route_class"]
        r = bridge.route_1c_task(text)
        pred_1c = bool(r.get("is_1c"))
        pred_cls = route_class_of(r.get("flow", "none"))
        conf = r.get("confidence")
        exp_band = s.get("complexity")
        if exp_band in _BANDS and pred_cls == "confident":
            pred_band = r.get("complexity")
            band_tot[exp_band] += 1
            if pred_band in _BANDS:
                band_confusion[exp_band][pred_band] += 1
            if pred_band == exp_band:
                band_ok[exp_band] += 1
            if exp_band in ("medium", "complex") and r.get("flow") == "auto":
                auto_misroutes.append({"text": text[:70], "exp": exp_band, "got_flow": "auto"})
        # #3 stage-3: mid-band TF-IDF (не confident, 0.40≤sem<0.85) → LLM решает по смыслу
        sem = r.get("semantic_sim", 0.0) or 0.0
        if classify and not r.get("confident_1c") and 0.40 <= sem < 0.85:
            v = classify(text)
            if v is not None:
                pred_1c = v
                pred_cls = "ask" if v else "none"
        if exp_1c and pred_1c:
            tp += 1
        elif exp_1c and not pred_1c:
            fn += 1
        elif not exp_1c and pred_1c:
            fp += 1
        else:
            tn += 1
        cls_tot[exp_cls] += 1
        confusion[exp_cls][pred_cls] += 1
        if pred_cls == exp_cls:
            cls_ok[exp_cls] += 1
        else:
            misses.append(
                {"text": text[:60], "exp": exp_cls, "got": pred_cls, "conf": conf, "is_1c": pred_1c}
            )
        if isinstance(conf, (int, float)):
            conf_by_class[exp_cls].append(float(conf))

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "n": len(rows),
        "is_1c": prf(tp, fp, fn) | {"tn": tn},
        "route_class_accuracy": round(sum(cls_ok.values()) / len(rows), 4) if rows else None,
        "per_class": {
            c: {"acc": round(cls_ok[c] / cls_tot[c], 4) if cls_tot[c] else None, "n": cls_tot[c]}
            for c in _CLASSES
        },
        "confusion": confusion,
        "confidence_mean_by_class": {c: mean(conf_by_class[c]) for c in _CLASSES},
        "complexity_band": {
            "n": sum(band_tot.values()),
            "accuracy": round(sum(band_ok.values()) / sum(band_tot.values()), 4)
            if sum(band_tot.values())
            else None,
            "per_band": {
                b: {
                    "acc": round(band_ok[b] / band_tot[b], 4) if band_tot[b] else None,
                    "n": band_tot[b],
                }
                for b in _BANDS
            },
            "confusion": band_confusion,
            "auto_misroutes": auto_misroutes,
        },
        "misses": misses,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eval 1С-detector (is_1c + route_class)")
    ap.add_argument("--ground-truth", default=str(GROUND_TRUTH))
    ap.add_argument("--split", choices=["train", "test", "all"], default="all")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument(
        "--llm-tail",
        action="store_true",
        help="#3 stage-3: на mid-band TF-IDF звать LLM-классификатор (замер потолка; медленно)",
    )
    ap.add_argument(
        "--setfit",
        action="store_true",
        help="ADR-025: семантический слой ② через SetFit-гейт (нужна обученная модель; иначе graceful → TF-IDF)",
    )
    # P4.3 (roadmap 260703): регрессионные пороги для CI-гейта детектора. exit 1 при падении ниже
    # пола (текущее is_1c F1≈0.97 / route-acc≈0.97 — полы 0.90 дают запас, но ловят реальный регресс
    # правки регекса). Без флагов → чисто отчёт (advisory).
    ap.add_argument(
        "--min-f1", type=float, default=None, help="P4.3: exit 1 если is_1c F1 < порога"
    )
    ap.add_argument(
        "--min-route-acc",
        type=float,
        default=None,
        help="P4.3: exit 1 если route_class_accuracy < порога",
    )
    args = ap.parse_args(argv)
    if args.setfit:  # включить SetFit-гейт для этого прогона (route_1c_task подхватит env)
        os.environ["ONEC_SETFIT_ENABLE"] = "1"

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    gt = Path(args.ground_truth)
    if not gt.exists():
        print(f"ERROR: ground truth not found: {gt}", file=sys.stderr)
        return 1
    rows = json.loads(gt.read_text(encoding="utf-8"))
    rows = [s for s in rows if s.get("split") != "quarantine"]
    if args.split in ("train", "test"):
        rows = [s for s in rows if split_of(s["text"], s) == args.split]

    rep = evaluate(rows, llm_tail=args.llm_tail)
    rep["split"] = args.split

    def _regression_rc() -> int:
        """P4.3: 1 если метрика ниже заданного пола (CI-гейт), иначе 0.

        Guard `is not None`: при вырожденном (пустом/отфильтрованном) GT route_class_accuracy
        может быть None → без guard'а `None < 0.90` дал бы TypeError (рекомендация ревьюера P4)."""
        rc = 0
        f1 = rep["is_1c"]["f1"]
        racc = rep["route_class_accuracy"]
        if args.min_f1 is not None and f1 is not None and f1 < args.min_f1:
            print(f"REGRESSION: is_1c F1={f1} < --min-f1={args.min_f1}", file=sys.stderr)
            rc = 1
        if args.min_route_acc is not None and racc is not None and racc < args.min_route_acc:
            print(
                f"REGRESSION: route_class_accuracy={racc} < --min-route-acc={args.min_route_acc}",
                file=sys.stderr,
            )
            rc = 1
        return rc

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return _regression_rc()

    m = rep["is_1c"]
    print("=" * 60)
    print(f"1С-ДЕТЕКТОР — EVAL ({args.split}, n={rep['n']})")
    print("=" * 60)
    print(
        f"is_1c   P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}"
        f"   (tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']})"
    )
    print(f"route_class accuracy: {rep['route_class_accuracy']:.3f}")
    for c in _CLASSES:
        pc = rep["per_class"][c]
        print(f"   {c:9s} acc={pc['acc']} (n={pc['n']})")
    print("confidence mean by class:", rep["confidence_mean_by_class"])
    print("confusion (exp -> pred):")
    for c in _CLASSES:
        print(f"   {c:9s} -> {rep['confusion'][c]}")
    cb = rep["complexity_band"]
    print(
        f"\ncomplexity-band (n={cb['n']}, на confident-строках с GT-меткой): acc={cb['accuracy']}"
    )
    for b in _BANDS:
        pb = cb["per_band"][b]
        print(f"   {b:9s} acc={pb['acc']} (n={pb['n']})")
    if cb["auto_misroutes"]:
        print(f"   ⚠ AUTO-мисроутов (medium/complex → flow=auto): {len(cb['auto_misroutes'])}")
        for mr in cb["auto_misroutes"]:
            print(f"      exp={mr['exp']:8s} | {mr['text']}")
    else:
        print("   ✓ AUTO-мисроутов нет (ни одна medium/complex задача не уходит в auto)")
    if rep["misses"] and args.verbose:
        print(f"\nMisses ({len(rep['misses'])}):")
        for mm in rep["misses"]:
            print(f"   exp={mm['exp']:9s} got={mm['got']:9s} conf={mm['conf']} | {mm['text']}")
    elif rep["misses"]:
        print(f"\nMisses: {len(rep['misses'])} (use -v to list)")
    return _regression_rc()


if __name__ == "__main__":
    raise SystemExit(main())
