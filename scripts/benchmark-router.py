#!/usr/bin/env python3
"""Benchmark script for skill-router with/without Layer C (TF-IDF).

Runs ground truth through the router and measures precision/recall/F1
with ablation modes: A only, A+B, A+B+C, C only.

Usage:
    python scripts/benchmark-router.py
    python scripts/benchmark-router.py --ablation
    python scripts/benchmark-router.py --verbose
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
GROUND_TRUTH = PROJECT_DIR / "data" / "skill-router-ground-truth.jsonl"
ROUTER_SCRIPT = PROJECT_DIR / ".claude" / "hooks" / "skill-router.py"
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

import re
_SKILL_RE = re.compile(r"Skill\('([^']+)'\)")
_BUNDLE_RE = re.compile(r"\[SKILL-ROUTER\] Bundles: (.+)")


def run_router(prompt: str, env_extra: dict | None = None) -> dict:
    """Run skill-router.py with given prompt, return parsed output."""
    input_data = json.dumps({"prompt": prompt}, ensure_ascii=False)
    env = {
        **os.environ,
        "SESSION_STATE_PATH": str(PROJECT_DIR / "data" / "bench-temp"),
        "PYTHONIOENCODING": "utf-8",
    }
    if env_extra:
        env.update(env_extra)

    try:
        t0 = time.perf_counter()
        result = subprocess.run(
            [str(PYTHON), str(ROUTER_SCRIPT)],
            input=input_data, capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_DIR), env=env,
            encoding="utf-8", errors="replace",
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        stdout = result.stdout.strip()
        if not stdout:
            return {"bundles": [], "skills": [], "latency_ms": latency_ms}

        bundles, skills = [], []
        for line in stdout.split("\n"):
            m = _BUNDLE_RE.search(line)
            if m:
                bundles = [b.strip() for b in m.group(1).split(",") if b.strip()]
            found = _SKILL_RE.findall(line)
            if found:
                skills.extend(found)
        return {"bundles": bundles, "skills": skills, "latency_ms": latency_ms}
    except Exception as e:
        return {"bundles": [], "skills": [], "error": str(e), "latency_ms": 0}


def compute_metrics(expected: list, predicted: list) -> dict:
    """Compute precision, recall, F1 for two lists."""
    es, ps = set(expected), set(predicted)
    if not es and not ps:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not es:
        return {"precision": 0.0 if ps else 1.0, "recall": 1.0, "f1": 0.0 if ps else 1.0}
    if not ps:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0}
    tp = len(es & ps)
    fp = len(ps - es)
    fn = len(es - ps)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1}


def load_ground_truth() -> list[dict]:
    """Load ground truth samples."""
    if not GROUND_TRUTH.exists():
        print(f"ERROR: Ground truth not found: {GROUND_TRUTH}", file=sys.stderr)
        sys.exit(1)
    samples = []
    with open(GROUND_TRUTH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def run_evaluation(samples: list[dict], mode: str = "full", verbose: bool = False) -> dict:
    """Run full evaluation with given mode.

    Modes:
        full: Normal operation (A+B+C if artifacts exist)
        no_tfidf: Disable Layer C (delete artifacts temporarily)
    """
    env_extra = {}
    if mode == "no_tfidf":
        # Tell the router to skip TF-IDF by setting an env var
        env_extra["SKILL_ROUTER_NO_TFIDF"] = "1"

    # Clear session state between runs
    bench_dir = PROJECT_DIR / "data" / "bench-temp"
    bench_dir.mkdir(parents=True, exist_ok=True)
    state_file = bench_dir / "session-skills.json"

    all_metrics = []
    latencies = []

    for i, sample in enumerate(samples):
        prompt = sample["prompt"]
        exp_skills = sample.get("expected_skills", [])
        intent = sample.get("intent", "action")

        # Clear session state
        if state_file.exists():
            state_file.unlink()

        result = run_router(prompt, env_extra)
        pred_skills = result.get("skills", [])
        latency = result.get("latency_ms", 0)
        latencies.append(latency)

        m = compute_metrics(exp_skills, pred_skills)
        all_metrics.append(m)

        if verbose:
            status = "OK" if m["f1"] == 1.0 or (not exp_skills and not pred_skills) else "MISS"
            print(f"  [{i+1:3d}] {status:4s} P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} | {prompt[:50]}")

    # Cleanup
    try:
        if state_file.exists():
            state_file.unlink()
        bench_dir.rmdir()
    except Exception:
        pass

    # Aggregate
    def avg(key):
        vals = [m[key] for m in all_metrics]
        return sum(vals) / len(vals) if vals else 0.0

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)

    return {
        "mode": mode,
        "samples": len(samples),
        "precision": round(avg("precision"), 4),
        "recall": round(avg("recall"), 4),
        "f1": round(avg("f1"), 4),
        "latency_p50": round(latencies_sorted[n // 2], 1) if n else 0,
        "latency_p95": round(latencies_sorted[int(n * 0.95)], 1) if n else 0,
        "latency_p99": round(latencies_sorted[int(n * 0.99)], 1) if n else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark skill-router with/without TF-IDF Layer C")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--ablation", action="store_true", help="Run with and without Layer C")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    samples = load_ground_truth()
    print(f"Loaded {len(samples)} ground truth samples", file=sys.stderr)
    print(f"Router: {ROUTER_SCRIPT}", file=sys.stderr)

    # Check if TF-IDF artifacts exist
    tfidf_dir = PROJECT_DIR / "data" / "route-tfidf"
    has_tfidf = (tfidf_dir / "metadata.json").exists()
    print(f"TF-IDF artifacts: {'FOUND' if has_tfidf else 'NOT FOUND'}", file=sys.stderr)
    print(file=sys.stderr)

    results = {}

    if args.ablation:
        # Run both modes
        print("=== Mode: A+B (no TF-IDF) ===", file=sys.stderr)
        results["no_tfidf"] = run_evaluation(samples, mode="no_tfidf", verbose=args.verbose)

        if has_tfidf:
            print("\n=== Mode: A+B+C (with TF-IDF) ===", file=sys.stderr)
            results["with_tfidf"] = run_evaluation(samples, mode="full", verbose=args.verbose)
        else:
            print("\nSkipping A+B+C mode (no artifacts)", file=sys.stderr)
    else:
        mode = "full" if has_tfidf else "no_tfidf"
        print(f"=== Mode: {'A+B+C' if has_tfidf else 'A+B'} ===", file=sys.stderr)
        results["current"] = run_evaluation(samples, mode=mode, verbose=args.verbose)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 65)
        print("SKILL ROUTER BENCHMARK RESULTS")
        print("=" * 65)

        for label, r in results.items():
            print(f"\n  [{label.upper()}] (mode={r['mode']}, {r['samples']} samples)")
            print(f"    Precision: {r['precision']:.4f}")
            print(f"    Recall:    {r['recall']:.4f}")
            print(f"    F1:        {r['f1']:.4f}")
            print(f"    Latency:   p50={r['latency_p50']:.0f}ms  p95={r['latency_p95']:.0f}ms  p99={r['latency_p99']:.0f}ms")

        if "no_tfidf" in results and "with_tfidf" in results:
            base = results["no_tfidf"]
            enhanced = results["with_tfidf"]
            print(f"\n  DELTA (Layer C effect):")
            print(f"    Precision: {enhanced['precision'] - base['precision']:+.4f}")
            print(f"    Recall:    {enhanced['recall'] - base['recall']:+.4f}")
            print(f"    F1:        {enhanced['f1'] - base['f1']:+.4f}")
            print(f"    Latency:   p50 {enhanced['latency_p50'] - base['latency_p50']:+.0f}ms")


if __name__ == "__main__":
    main()
