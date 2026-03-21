#!/usr/bin/env python3
"""Evaluate analysis scorer against human-scored ground truth.

Usage:
    python scripts/eval-analysis-scorer.py [--json]
"""

import json
import sys
from pathlib import Path

# Import scorer functions from sibling script
_scorer_path = Path(__file__).parent / "score-analysis-report.py"
_scorer_ns: dict = {}
exec(_scorer_path.read_text(encoding="utf-8"), _scorer_ns)
parse_report = _scorer_ns["parse_report"]
compute_score = _scorer_ns["compute_score"]


def pearsonr(x: list, y: list) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    sx = sum((xi - mx) ** 2 for xi in x) ** 0.5
    sy = sum((yi - my) ** 2 for yi in y) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / (sx * sy)


def gap_types(gaps: list) -> set:
    return {g.get("type", "?") for g in gaps}


def main():
    json_output = "--json" in sys.argv
    base = Path(__file__).parent.parent
    ds_path = base / "data" / "eval" / "1c-analysis" / "eval_dataset.json"

    if not ds_path.exists():
        print(f"Error: {ds_path} not found", file=sys.stderr)
        sys.exit(1)

    dataset = json.loads(ds_path.read_text(encoding="utf-8"))
    results = []
    auto_scores, human_scores = [], []
    all_auto_types, all_exp_types = [], []

    for entry in dataset:
        eid = entry["id"]
        human = entry["human_scores"]["overall"]
        exp_gaps = entry.get("expected_gaps", [])
        rpath = base / entry["report_path"]

        if not rpath.exists():
            results.append({"id": eid, "auto": None, "human": human,
                            "delta": None, "auto_gaps": 0, "exp_gaps": len(exp_gaps),
                            "error": "file not found"})
            continue

        text = rpath.read_text(encoding="utf-8")
        parsed = parse_report(text)
        score = compute_score(parsed)
        auto = score["total"]
        a_gaps = score["gaps"]
        delta = auto - human

        results.append({"id": eid, "auto": auto, "human": human,
                        "delta": delta, "auto_gaps": len(a_gaps), "exp_gaps": len(exp_gaps),
                        "error": None})
        auto_scores.append(auto)
        human_scores.append(human)
        all_auto_types.append(gap_types(a_gaps))
        all_exp_types.append(gap_types(exp_gaps))

    # Gap metrics
    tp = fp = fn = 0
    for at, et in zip(all_auto_types, all_exp_types):
        tp += len(at & et)
        fp += len(at - et)
        fn += len(et - at)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    n = len(auto_scores)
    mae = sum(abs(r["delta"]) for r in results if r["delta"] is not None) / n if n else 0
    corr = pearsonr(auto_scores, human_scores)

    summary = {"n": n, "mae": round(mae, 1), "pearson_r": round(corr, 4),
               "gap_precision": round(prec, 3), "gap_recall": round(rec, 3),
               "gap_f1": round(f1, 3)}

    if json_output:
        print(json.dumps({"results": results, "summary": summary}, indent=2, ensure_ascii=False))
        return

    # Table
    print(f"{'ID':<18} {'Auto':>5} {'Human':>6} {'Delta':>6} {'G(A)':>5} {'G(E)':>5}")
    print("-" * 52)
    for r in results:
        a = f"{r['auto']}" if r["auto"] is not None else "N/A"
        d = f"{r['delta']:+d}" if r["delta"] is not None else "N/A"
        print(f"{r['id']:<18} {a:>5} {r['human']:>6} {d:>6} {r['auto_gaps']:>5} {r['exp_gaps']:>5}")

    # Summary
    print(f"\n{'='*52}")
    print(f"  Reports:       {n}")
    print(f"  MAE:           {mae:.1f}  (target < 10)")
    print(f"  Pearson R:     {corr:.4f}  (target > 0.8)")
    print(f"  Gap Precision: {prec:.1%}  ")
    print(f"  Gap Recall:    {rec:.1%}  ")
    print(f"  Gap F1:        {f1:.1%}  (target > 0.7)")
    print(f"{'='*52}")

    # Verdict
    ok_mae = mae < 10
    ok_corr = corr > 0.8
    ok_f1 = f1 > 0.7
    status = "PASS" if (ok_mae and ok_corr and ok_f1) else "NEEDS CALIBRATION"
    print(f"\n  Verdict: {status}")
    if not ok_mae:
        print(f"    MAE {mae:.1f} > 10 — scorer diverges from human judgement")
    if not ok_corr:
        print(f"    Pearson {corr:.4f} < 0.8 — weak correlation")
    if not ok_f1:
        print(f"    Gap F1 {f1:.1%} < 70% — gap detection inaccurate")


if __name__ == "__main__":
    main()
