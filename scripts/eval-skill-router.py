#!/usr/bin/env python3
"""
Offline evaluation script for skill-router.
Reads ground truth, runs each prompt through skill-router, computes precision/recall/F1.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH = PROJECT_DIR / "data" / "skill-router-ground-truth.jsonl"
ROUTER_SCRIPT = PROJECT_DIR / ".claude" / "hooks" / "skill-router.py"
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

_SKILL_RE = re.compile(r"Skill\('([^']+)'\)")

def run_router(prompt):
    input_data = json.dumps({"prompt": prompt}, ensure_ascii=False)
    try:
        result = subprocess.run(
            [str(PYTHON), str(ROUTER_SCRIPT)],
            input=input_data, capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_DIR),
            env={**os.environ, "SESSION_STATE_PATH": str(PROJECT_DIR / "data" / "eval-temp"), "PYTHONIOENCODING": "utf-8"},
            encoding="utf-8", errors="replace",
        )
        stdout = result.stdout.strip()
        if not stdout:
            return {"bundles": [], "skills": []}
        bundles, skills = [], []
        for line in stdout.split("\n"):
            if line.startswith("[SKILL-ROUTER] Bundles:"):
                raw = line.replace("[SKILL-ROUTER] Bundles:", "").strip()
                bundles = [b.strip() for b in raw.split(",") if b.strip()]
            found = _SKILL_RE.findall(line)
            if found:
                skills.extend(found)
        return {"bundles": bundles, "skills": skills}
    except Exception as e:
        return {"bundles": [], "skills": [], "error": str(e)}

def compute_metrics(expected, predicted):
    es, ps = set(expected), set(predicted)
    if not es and not ps:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    if not es:
        return {"precision": 0.0 if ps else 1.0, "recall": 1.0, "f1": 0.0 if ps else 1.0, "tp": 0, "fp": len(ps), "fn": 0}
    if not ps:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(es)}
    tp = len(es & ps)
    fp = len(ps - es)
    fn = len(es - ps)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2*p*r / (p+r) if (p+r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}

def main():
    parser = argparse.ArgumentParser(description="Evaluate skill-router accuracy")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ground-truth", type=str, default=str(GROUND_TRUTH))
    parser.add_argument("--save-fp", action="store_true", help="Save FP/FN details to data/skill-router-fp.jsonl")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        print(f"ERROR: Ground truth not found: {gt_path}")
        sys.exit(1)

    samples = []
    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} ground truth samples", file=sys.stderr)
    print(f"Router: {ROUTER_SCRIPT}", file=sys.stderr)
    print(file=sys.stderr)

    eval_state_dir = PROJECT_DIR / "data" / "eval-temp"
    eval_state_dir.mkdir(parents=True, exist_ok=True)
    state_file = eval_state_dir / "session-skills.json"
    if state_file.exists():
        state_file.unlink()

    skill_all, bundle_all = [], []
    intent_results = defaultdict(lambda: {"correct": 0, "total": 0})
    fps_list, fns_list = [], []

    for i, sample in enumerate(samples):
        prompt = sample["prompt"]
        exp_skills = sample.get("expected_skills", [])
        exp_bundles = sample.get("expected_bundles", [])
        intent = sample.get("intent", "action")
        if state_file.exists():
            state_file.unlink()

        result = run_router(prompt)
        pred_skills = result.get("skills", [])
        pred_bundles = result.get("bundles", [])

        sm = compute_metrics(exp_skills, pred_skills)
        bm = compute_metrics(exp_bundles, pred_bundles)
        skill_all.append(sm)
        bundle_all.append(bm)

        if intent in ("informational", "system"):
            ok = len(pred_skills) == 0
        else:
            ok = sm["f1"] > 0 or (not exp_skills and not pred_skills)
        intent_results[intent]["total"] += 1
        if ok:
            intent_results[intent]["correct"] += 1

        if sm["fp"] > 0:
            fps_list.append({"prompt": prompt[:60], "fp_skills": list(set(pred_skills) - set(exp_skills))})
        if sm["fn"] > 0:
            fns_list.append({"prompt": prompt[:60], "fn_skills": list(set(exp_skills) - set(pred_skills))})

        if args.verbose:
            status = "OK" if sm["f1"] == 1.0 or (not exp_skills and not pred_skills) else "MISS"
            print(f"  [{i+1:3d}] {status:4s} | P={sm['precision']:.2f} R={sm['recall']:.2f} F1={sm['f1']:.2f} | {prompt[:50]}", file=sys.stderr)

    def avg(ml, k):
        v = [m[k] for m in ml]
        return sum(v)/len(v) if v else 0.0

    report = {
        "total_samples": len(samples),
        "skill_metrics": {
            "precision": round(avg(skill_all, "precision"), 4),
            "recall": round(avg(skill_all, "recall"), 4),
            "f1": round(avg(skill_all, "f1"), 4),
            "total_tp": sum(m["tp"] for m in skill_all),
            "total_fp": sum(m["fp"] for m in skill_all),
            "total_fn": sum(m["fn"] for m in skill_all),
        },
        "bundle_metrics": {
            "precision": round(avg(bundle_all, "precision"), 4),
            "recall": round(avg(bundle_all, "recall"), 4),
            "f1": round(avg(bundle_all, "f1"), 4),
        },
        "intent_accuracy": {
            intent: {"accuracy": round(r["correct"]/r["total"], 4) if r["total"]>0 else 0, "correct": r["correct"], "total": r["total"]}
            for intent, r in intent_results.items()
        },
        "fp_count": len(fps_list), "fn_count": len(fns_list),
        "top_fps": fps_list[:5], "top_fns": fns_list[:5],
    }

    # Save FP/FN tracking file
    if args.save_fp and (fps_list or fns_list):
        fp_path = PROJECT_DIR / "data" / "skill-router-fp.jsonl"
        with open(fp_path, "w", encoding="utf-8") as f:
            ts = datetime.now().isoformat()
            for fp in fps_list:
                entry = {"ts": ts, "type": "fp", "prompt": fp["prompt"], "extra_skills": fp["fp_skills"]}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            for fn in fns_list:
                entry = {"ts": ts, "type": "fn", "prompt": fn["prompt"], "missed_skills": fn["fn_skills"]}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"Saved {len(fps_list)} FP + {len(fns_list)} FN to {fp_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("SKILL ROUTER EVALUATION REPORT")
        print("=" * 60)
        sm = report["skill_metrics"]
        bm = report["bundle_metrics"]
        print(f"\nSkill Metrics (avg over {len(samples)} samples):")
        print(f"  Precision: {sm['precision']:.4f}")
        print(f"  Recall:    {sm['recall']:.4f}")
        print(f"  F1:        {sm['f1']:.4f}")
        print(f"  TP={sm['total_tp']} FP={sm['total_fp']} FN={sm['total_fn']}")
        print(f"\nBundle Metrics:")
        print(f"  Precision: {bm['precision']:.4f}")
        print(f"  Recall:    {bm['recall']:.4f}")
        print(f"  F1:        {bm['f1']:.4f}")
        print(f"\nIntent Accuracy:")
        for intent, data in report["intent_accuracy"].items():
            print(f"  {intent:15s}: {data['accuracy']*100:.0f}% ({data['correct']}/{data['total']})")
        if fps_list:
            print(f"\nTop False Positives ({len(fps_list)}):")
            for fp in fps_list[:5]:
                print(f"  {fp['prompt']} -> extra: {fp['fp_skills']}")
        if fns_list:
            print(f"\nTop False Negatives ({len(fns_list)}):")
            for fn in fns_list[:5]:
                print(f"  {fn['prompt']} -> missed: {fn['fn_skills']}")
    try:
        if state_file.exists(): state_file.unlink()
        eval_state_dir.rmdir()
    except Exception: pass

if __name__ == "__main__":
    main()
