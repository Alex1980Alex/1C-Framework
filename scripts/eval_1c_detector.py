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
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH = PROJECT_DIR / "data" / "1c-detector-ground-truth.json"
BRIDGE = PROJECT_DIR / ".claude" / "hooks" / "shared" / "pipeline_1c_bridge.py"

_CLASSES = ("none", "ask", "confident")


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
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def evaluate(rows: list[dict]) -> dict:
    bridge = load_bridge()
    tp = fp = fn = tn = 0
    cls_tot = {c: 0 for c in _CLASSES}
    cls_ok = {c: 0 for c in _CLASSES}
    confusion = {c: {d: 0 for d in _CLASSES} for c in _CLASSES}
    conf_by_class: dict[str, list[float]] = {c: [] for c in _CLASSES}
    misses = []
    for s in rows:
        text = s["text"]
        exp_1c = bool(s["is_1c"])
        exp_cls = s["route_class"]
        r = bridge.route_1c_task(text)
        pred_1c = bool(r.get("is_1c"))
        pred_cls = route_class_of(r.get("flow", "none"))
        conf = r.get("confidence")
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
            misses.append({"text": text[:60], "exp": exp_cls, "got": pred_cls,
                           "conf": conf, "is_1c": pred_1c})
        if isinstance(conf, (int, float)):
            conf_by_class[exp_cls].append(float(conf))

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "n": len(rows),
        "is_1c": prf(tp, fp, fn) | {"tn": tn},
        "route_class_accuracy": round(
            sum(cls_ok.values()) / len(rows), 4) if rows else None,
        "per_class": {
            c: {"acc": round(cls_ok[c] / cls_tot[c], 4) if cls_tot[c] else None,
                "n": cls_tot[c]}
            for c in _CLASSES
        },
        "confusion": confusion,
        "confidence_mean_by_class": {c: mean(conf_by_class[c]) for c in _CLASSES},
        "misses": misses,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eval 1С-detector (is_1c + route_class)")
    ap.add_argument("--ground-truth", default=str(GROUND_TRUTH))
    ap.add_argument("--split", choices=["train", "test", "all"], default="all")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args(argv)

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

    rep = evaluate(rows)
    rep["split"] = args.split

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    m = rep["is_1c"]
    print("=" * 60)
    print(f"1С-ДЕТЕКТОР — EVAL ({args.split}, n={rep['n']})")
    print("=" * 60)
    print(f"is_1c   P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}"
          f"   (tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']})")
    print(f"route_class accuracy: {rep['route_class_accuracy']:.3f}")
    for c in _CLASSES:
        pc = rep["per_class"][c]
        print(f"   {c:9s} acc={pc['acc']} (n={pc['n']})")
    print("confidence mean by class:", rep["confidence_mean_by_class"])
    print("confusion (exp -> pred):")
    for c in _CLASSES:
        print(f"   {c:9s} -> {rep['confusion'][c]}")
    if rep["misses"] and args.verbose:
        print(f"\nMisses ({len(rep['misses'])}):")
        for mm in rep["misses"]:
            print(f"   exp={mm['exp']:9s} got={mm['got']:9s} conf={mm['conf']} | {mm['text']}")
    elif rep["misses"]:
        print(f"\nMisses: {len(rep['misses'])} (use -v to list)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
