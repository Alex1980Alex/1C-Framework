#!/usr/bin/env python3
"""
Offline evaluation script for skill-router.
Reads ground truth, runs each prompt through skill-router, computes precision/recall/F1.
"""

import argparse
import hashlib
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
_OPTIONAL_RE = re.compile(r"Опционально \(по контексту\): (.+)")
_RECOMMENDED_RE = re.compile(r"Рекомендованные скиллы: (.+)")


def run_router(prompt):
    input_data = json.dumps({"prompt": prompt}, ensure_ascii=False)
    try:
        result = subprocess.run(
            [str(PYTHON), str(ROUTER_SCRIPT)],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_DIR),
            env={
                **os.environ,
                "SESSION_STATE_PATH": str(PROJECT_DIR / "data" / "eval-temp"),
                "PYTHONIOENCODING": "utf-8",
            },
            encoding="utf-8",
            errors="replace",
        )
        stdout = result.stdout.strip()
        if not stdout:
            return {"bundles": [], "skills": []}
        bundles, required_skills, all_skills = [], [], []
        for line in stdout.split("\n"):
            if line.startswith("[SKILL-ROUTER] Bundles:"):
                raw = line.replace("[SKILL-ROUTER] Bundles:", "").strip()
                bundles = [b.strip() for b in raw.split(",") if b.strip()]
            # Capture required skills from Skill('X') calls
            found = _SKILL_RE.findall(line)
            if found:
                required_skills.extend(found)
                all_skills.extend(found)
            # Capture recommended skills line
            m = _RECOMMENDED_RE.search(line)
            if m:
                for s in m.group(1).split(","):
                    s = s.strip()
                    if s and s not in all_skills:
                        all_skills.append(s)
            # Capture optional skills line
            m = _OPTIONAL_RE.search(line)
            if m:
                for s in m.group(1).split(","):
                    s = s.strip()
                    if s and s not in all_skills:
                        all_skills.append(s)
        return {"bundles": bundles, "skills": all_skills, "required_skills": required_skills}
    except Exception as e:
        return {"bundles": [], "skills": [], "error": str(e)}


def compute_metrics(expected, predicted):
    es, ps = set(expected), set(predicted)
    if not es and not ps:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    if not es:
        return {
            "precision": 0.0 if ps else 1.0,
            "recall": 1.0,
            "f1": 0.0 if ps else 1.0,
            "tp": 0,
            "fp": len(ps),
            "fn": 0,
        }
    if not ps:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": len(es)}
    tp = len(es & ps)
    fp = len(ps - es)
    fn = len(es - ps)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def _split_of(prompt, sample):
    """Deterministic train/test split (260613 H1). Honors an explicit per-sample
    `split` field; else hashes the prompt (sha1 % 5 -> ~20% test). Stable across
    runs — NOT Python's salted hash()."""
    s = sample.get("split")
    if s in ("train", "test"):
        return s
    h = int(hashlib.sha1(prompt.encode("utf-8")).hexdigest(), 16)
    return "test" if h % 5 == 0 else "train"


def _action_f1(rows):
    """Macro-F1 over ACTION samples only (expected_skills != []). Excludes the
    silence-credit padding — empty-expected samples that score f1=1.0 just for
    staying silent (260613 F5)."""
    vals = [r["f1"] for r in rows if r["is_action"]]
    return round(sum(vals) / len(vals), 4) if vals else None


def _silence_accuracy(rows):
    """Fraction of empty-expected samples on which the router correctly stayed
    silent. Reported SEPARATELY from action_f1 so the two don't pad each other."""
    vals = [r for r in rows if not r["is_action"]]
    return round(sum(1 for r in vals if r["silent_ok"]) / len(vals), 4) if vals else None


def main():
    parser = argparse.ArgumentParser(description="Evaluate skill-router accuracy")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ground-truth", type=str, default=str(GROUND_TRUTH))
    parser.add_argument(
        "--save-fp", action="store_true", help="Save FP/FN details to data/skill-router-fp.jsonl"
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Persist report to data/reports/skills/skill-router-eval-latest.json"
        " (источник F1 для skill_system_acceptance, roadmap 260612 P4)",
    )
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        print(f"ERROR: Ground truth not found: {gt_path}")
        sys.exit(1)

    samples = []
    with open(gt_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    # 260613 A5: quarantine-кейсы (transcript-router, leakage-кандидаты) исключены
    # из метрик — их метки выведены из вывода роутера (contamination). Остаются в
    # GT-файле для авторской ре-верификации; не влияют на честное число гейта.
    _n_all = len(samples)
    samples = [s for s in samples if s.get("split") != "quarantine"]
    _n_quar = _n_all - len(samples)
    if _n_quar:
        print(f"Excluded {_n_quar} quarantine cases (leakage-suspect)", file=sys.stderr)
    print(f"Loaded {len(samples)} scored ground truth samples", file=sys.stderr)
    print(f"Router: {ROUTER_SCRIPT}", file=sys.stderr)
    print(file=sys.stderr)

    eval_state_dir = PROJECT_DIR / "data" / "eval-temp"
    eval_state_dir.mkdir(parents=True, exist_ok=True)
    state_file = eval_state_dir / "session-skills.json"
    if state_file.exists():
        state_file.unlink()

    skill_all, skill_req_all, bundle_all = [], [], []
    intent_results = defaultdict(lambda: {"correct": 0, "total": 0})
    fps_list, fns_list = [], []
    per_sample = []  # 260613: split + action/silence classification per sample

    for i, sample in enumerate(samples):
        prompt = sample["prompt"]
        exp_skills = sample.get("expected_skills", [])
        exp_bundles = sample.get("expected_bundles", [])
        intent = sample.get("intent", "action")
        if state_file.exists():
            state_file.unlink()

        result = run_router(prompt)
        pred_skills = result.get("skills", [])
        pred_req_skills = result.get("required_skills", [])
        pred_bundles = result.get("bundles", [])

        sm = compute_metrics(exp_skills, pred_skills)
        sm_req = compute_metrics(exp_skills, pred_req_skills)
        bm = compute_metrics(exp_bundles, pred_bundles)
        skill_all.append(sm)
        skill_req_all.append(sm_req)
        bundle_all.append(bm)
        per_sample.append(
            {
                "split": _split_of(prompt, sample),
                "is_action": bool(exp_skills),
                "f1": sm["f1"],
                "silent_ok": len(pred_skills) == 0,
            }
        )

        if intent in ("informational", "system"):
            ok = len(pred_skills) == 0
        else:
            ok = sm["f1"] > 0 or (not exp_skills and not pred_skills)
        intent_results[intent]["total"] += 1
        if ok:
            intent_results[intent]["correct"] += 1

        if sm["fp"] > 0:
            fps_list.append(
                {"prompt": prompt[:60], "fp_skills": list(set(pred_skills) - set(exp_skills))}
            )
        if sm["fn"] > 0:
            fns_list.append(
                {"prompt": prompt[:60], "fn_skills": list(set(exp_skills) - set(pred_skills))}
            )

        if args.verbose:
            status = "OK" if sm["f1"] == 1.0 or (not exp_skills and not pred_skills) else "MISS"
            print(
                f"  [{i + 1:3d}] {status:4s} | P={sm['precision']:.2f} R={sm['recall']:.2f} F1={sm['f1']:.2f} | {prompt[:50]}",
                file=sys.stderr,
            )

    def avg(ml, k):
        v = [m[k] for m in ml]
        return sum(v) / len(v) if v else 0.0

    # 260613 F1/F5 — honest metrics. `skill_metrics.f1` below is the legacy macro-F1
    # over ALL samples (padded by empty-expected samples scoring 1.0 for silence).
    # `action_f1` (POOLED, action samples only) strips that padding and is the number
    # the acceptance gate reads. The train/test split is DIAGNOSTIC only: the router
    # does NOT train on the GT at eval-time (A2 weights are hardcoded offline), so a
    # split says nothing about generalization — it just exposes GT noise/size (tiny
    # test folds invert vs train). A real held-out needs A2 re-derived on `train` only;
    # until then pooled action_f1 is the honest, stable signal.
    honest_metrics = {
        "action_f1": _action_f1(per_sample),
        "silence_accuracy": _silence_accuracy(per_sample),
        "n_action": sum(1 for r in per_sample if r["is_action"]),
        "n_silence": sum(1 for r in per_sample if not r["is_action"]),
        "split_method": "field|sha1mod5",
        "splits": {
            sp: {
                "action_f1": _action_f1([r for r in per_sample if r["split"] == sp]),
                "silence_accuracy": _silence_accuracy(
                    [r for r in per_sample if r["split"] == sp]
                ),
                "n": sum(1 for r in per_sample if r["split"] == sp),
                "n_action": sum(
                    1 for r in per_sample if r["split"] == sp and r["is_action"]
                ),
            }
            for sp in ("train", "test")
        },
    }

    report = {
        "total_samples": len(samples),
        "honest_metrics": honest_metrics,
        "skill_metrics": {
            "precision": round(avg(skill_all, "precision"), 4),
            "recall": round(avg(skill_all, "recall"), 4),
            "f1": round(avg(skill_all, "f1"), 4),
            "total_tp": sum(m["tp"] for m in skill_all),
            "total_fp": sum(m["fp"] for m in skill_all),
            "total_fn": sum(m["fn"] for m in skill_all),
        },
        "skill_required_metrics": {
            "precision": round(avg(skill_req_all, "precision"), 4),
            "recall": round(avg(skill_req_all, "recall"), 4),
            "f1": round(avg(skill_req_all, "f1"), 4),
            "total_tp": sum(m["tp"] for m in skill_req_all),
            "total_fp": sum(m["fp"] for m in skill_req_all),
            "total_fn": sum(m["fn"] for m in skill_req_all),
        },
        "bundle_metrics": {
            "precision": round(avg(bundle_all, "precision"), 4),
            "recall": round(avg(bundle_all, "recall"), 4),
            "f1": round(avg(bundle_all, "f1"), 4),
        },
        "intent_accuracy": {
            intent: {
                "accuracy": round(r["correct"] / r["total"], 4) if r["total"] > 0 else 0,
                "correct": r["correct"],
                "total": r["total"],
            }
            for intent, r in intent_results.items()
        },
        "fp_count": len(fps_list),
        "fn_count": len(fns_list),
        "top_fps": fps_list[:5],
        "top_fns": fns_list[:5],
    }

    if args.save_report:
        report_path = PROJECT_DIR / "data" / "reports" / "skills" / "skill-router-eval-latest.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(
                {"ts": datetime.now().isoformat(), "ground_truth": str(gt_path), **report},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Saved report to {report_path}", file=sys.stderr)

    # Save FP/FN tracking file
    if args.save_fp and (fps_list or fns_list):
        fp_path = PROJECT_DIR / "data" / "skill-router-fp.jsonl"
        with open(fp_path, "w", encoding="utf-8") as f:
            ts = datetime.now().isoformat()
            for fp in fps_list:
                entry = {
                    "ts": ts,
                    "type": "fp",
                    "prompt": fp["prompt"],
                    "extra_skills": fp["fp_skills"],
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            for fn in fns_list:
                entry = {
                    "ts": ts,
                    "type": "fn",
                    "prompt": fn["prompt"],
                    "missed_skills": fn["fn_skills"],
                }
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
        srm = report["skill_required_metrics"]
        print(f"\nSkill Metrics — Required Only (avg over {len(samples)} samples):")
        print(f"  Precision: {srm['precision']:.4f}")
        print(f"  Recall:    {srm['recall']:.4f}")
        print(f"  F1:        {srm['f1']:.4f}")
        print(f"  TP={srm['total_tp']} FP={srm['total_fp']} FN={srm['total_fn']}")
        print("\nSkill Metrics — All (required + optional + affinity):")
        print(f"  Precision: {sm['precision']:.4f}")
        print(f"  Recall:    {sm['recall']:.4f}")
        print(f"  F1:        {sm['f1']:.4f}")
        print(f"  TP={sm['total_tp']} FP={sm['total_fp']} FN={sm['total_fn']}")
        hm = report["honest_metrics"]
        ht, htr = hm["splits"]["test"], hm["splits"]["train"]
        print("\nHonest Metrics (260613 — action-only, no silence-credit padding):")
        print(
            f"  action F1 (pooled): {hm['action_f1']} over {hm['n_action']} action samples"
            "  <- GATE metric"
        )
        print(f"  action F1 (train):  {htr['action_f1']} (n_action={htr['n_action']})")
        print(
            f"  action F1 (test):   {ht['action_f1']} (n_action={ht['n_action']})"
            "  <- diagnostic only (tiny split, noisy)"
        )
        print(
            f"  silence accuracy:  {hm['silence_accuracy']} "
            f"over {hm['n_silence']} empty-expected samples"
        )
        print("\nBundle Metrics:")
        print(f"  Precision: {bm['precision']:.4f}")
        print(f"  Recall:    {bm['recall']:.4f}")
        print(f"  F1:        {bm['f1']:.4f}")
        print("\nIntent Accuracy:")
        for intent, data in report["intent_accuracy"].items():
            print(
                f"  {intent:15s}: {data['accuracy'] * 100:.0f}% ({data['correct']}/{data['total']})"
            )
        if fps_list:
            print(f"\nTop False Positives ({len(fps_list)}):")
            for fp in fps_list[:5]:
                print(f"  {fp['prompt']} -> extra: {fp['fp_skills']}")
        if fns_list:
            print(f"\nTop False Negatives ({len(fns_list)}):")
            for fn in fns_list[:5]:
                print(f"  {fn['prompt']} -> missed: {fn['fn_skills']}")
    try:
        if state_file.exists():
            state_file.unlink()
        eval_state_dir.rmdir()
    except Exception:
        pass


if __name__ == "__main__":
    main()
