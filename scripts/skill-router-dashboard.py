#!/usr/bin/env python3
"""
Skill Router Dashboard — CLI visualization of routing metrics.
# -*- coding: utf-8 -*-

Reads from:
  - data/skill-accuracy.jsonl (recommend/activate events)
  - data/skill-router-ground-truth.jsonl (labeled prompts)
  - data/skill-router.log (routing log)

Outputs:
  - Activation rate trend
  - Precision/Recall/F1 from ground truth eval
  - Bundle frequency heatmap
  - Top false positives/negatives
  - Intent accuracy breakdown

Usage:
  python scripts/skill-router-dashboard.py
  python scripts/skill-router-dashboard.py --json
  python scripts/skill-router-dashboard.py --period 7  # last 7 days
"""

import argparse
import io
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows console encoding for Cyrillic
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

PROJECT_DIR = Path(__file__).resolve().parent.parent
ACCURACY_LOG = PROJECT_DIR / "data" / "skill-accuracy.jsonl"
ROUTER_LOG = PROJECT_DIR / "data" / "skill-router.log"
GROUND_TRUTH = PROJECT_DIR / "data" / "skill-router-ground-truth.jsonl"
EVAL_SCRIPT = PROJECT_DIR / "scripts" / "eval-skill-router.py"


def load_accuracy_events(days: int = 0) -> list[dict]:
    """Load events from skill-accuracy.jsonl, optionally filtered by days."""
    events = []
    if not ACCURACY_LOG.exists():
        return events
    cutoff = (datetime.now() - timedelta(days=days)).isoformat() if days > 0 else ""
    with open(ACCURACY_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if cutoff and event.get("ts", "") < cutoff:
                    continue
                events.append(event)
            except json.JSONDecodeError:
                continue
    return events


def compute_activation_rate(events: list[dict]) -> dict:
    """Compute activation rate from recommend/activate events."""
    recommends = [e for e in events if e.get("type") == "recommend"]
    activates = [e for e in events if e.get("type") == "activate"]

    prompt_ids_recommended = set()
    prompt_ids_activated = set()
    for e in recommends:
        pid = e.get("prompt_id")
        if pid:
            prompt_ids_recommended.add(pid)
    for e in activates:
        pid = e.get("prompt_id")
        if pid:
            prompt_ids_activated.add(pid)

    total_recommends = len(recommends)
    total_activates = len(activates)
    unique_recommended = len(prompt_ids_recommended)
    unique_activated = len(prompt_ids_activated & prompt_ids_recommended)

    rate = (unique_activated / unique_recommended * 100) if unique_recommended > 0 else 0

    return {
        "total_recommend_events": total_recommends,
        "total_activate_events": total_activates,
        "unique_prompts_recommended": unique_recommended,
        "unique_prompts_activated": unique_activated,
        "activation_rate_pct": round(rate, 1),
    }


def compute_skill_frequency(events: list[dict]) -> dict[str, int]:
    """Count how often each skill is recommended."""
    counter: Counter = Counter()
    for e in events:
        if e.get("type") == "recommend":
            for skill in e.get("skills", []):
                counter[skill] += 1
    return dict(counter.most_common(20))


def compute_daily_trend(events: list[dict], days: int = 14) -> list[dict]:
    """Compute daily activation rate for trend analysis."""
    cutoff = datetime.now() - timedelta(days=days)
    daily: dict[str, dict] = defaultdict(lambda: {"recommended": set(), "activated": set()})

    for e in events:
        ts = e.get("ts", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        if dt < cutoff:
            continue
        day = dt.strftime("%Y-%m-%d")
        pid = e.get("prompt_id")
        if not pid:
            continue
        if e.get("type") == "recommend":
            daily[day]["recommended"].add(pid)
        elif e.get("type") == "activate":
            daily[day]["activated"].add(pid)

    trend = []
    for day in sorted(daily.keys()):
        d = daily[day]
        rec = len(d["recommended"])
        act = len(d["activated"] & d["recommended"])
        rate = (act / rec * 100) if rec > 0 else 0
        trend.append({"date": day, "recommended": rec, "activated": act, "rate_pct": round(rate, 1)})
    return trend


def run_eval() -> dict | None:
    """Run eval-skill-router.py and capture JSON output."""
    if not EVAL_SCRIPT.exists():
        return None
    python = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    try:
        result = subprocess.run(
            [str(python), str(EVAL_SCRIPT), "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=str(PROJECT_DIR),
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return None


def render_bar(value: float, max_val: float = 100, width: int = 30) -> str:
    """Render a simple ASCII bar chart."""
    filled = int(value / max_val * width) if max_val > 0 else 0
    filled = min(filled, width)
    return f"[{'#' * filled}{'.' * (width - filled)}]"


def print_dashboard(args):
    """Print the full dashboard to stdout."""
    events = load_accuracy_events(days=args.period)

    print("=" * 70)
    print("  SKILL ROUTER DASHBOARD")
    print(f"  Period: {'all time' if args.period == 0 else f'last {args.period} days'}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # --- Activation Rate ---
    ar = compute_activation_rate(events)
    print(f"\n{'ACTIVATION RATE':=^70}")
    print(f"  Recommend events: {ar['total_recommend_events']}")
    print(f"  Activate events:  {ar['total_activate_events']}")
    print(f"  Unique prompts recommended: {ar['unique_prompts_recommended']}")
    print(f"  Unique prompts activated:   {ar['unique_prompts_activated']}")
    rate = ar["activation_rate_pct"]
    status = "OK" if rate >= 70 else ("WARN" if rate >= 40 else "CRIT")
    print(f"  Activation rate: {rate:.1f}% {render_bar(rate)} [{status}]")

    # --- Daily Trend ---
    trend = compute_daily_trend(events, days=14)
    if trend:
        print(f"\n{'DAILY TREND (last 14 days)':=^70}")
        for day in trend[-10:]:
            bar = render_bar(day["rate_pct"])
            print(f"  {day['date']}  {day['rate_pct']:5.1f}% {bar}  ({day['activated']}/{day['recommended']})")

    # --- Skill Frequency ---
    freq = compute_skill_frequency(events)
    if freq:
        print(f"\n{'TOP RECOMMENDED SKILLS':=^70}")
        max_count = max(freq.values()) if freq else 1
        for skill, count in list(freq.items())[:15]:
            bar = render_bar(count, max_count, 25)
            print(f"  {skill:40s} {count:4d} {bar}")

    # --- Eval Results ---
    print(f"\n{'GROUND TRUTH EVALUATION':=^70}")
    eval_result = run_eval()
    if eval_result:
        sm = eval_result.get("skill_metrics", {})
        bm = eval_result.get("bundle_metrics", {})
        print(f"  Samples: {eval_result.get('total_samples', '?')}")
        print(f"  Skill  - P: {sm.get('precision', 0):.4f}  R: {sm.get('recall', 0):.4f}  F1: {sm.get('f1', 0):.4f}")
        print(f"  Bundle - P: {bm.get('precision', 0):.4f}  R: {bm.get('recall', 0):.4f}  F1: {bm.get('f1', 0):.4f}")
        print(f"  TP={sm.get('total_tp', 0)}  FP={sm.get('total_fp', 0)}  FN={sm.get('total_fn', 0)}")

        # Intent accuracy
        intent_acc = eval_result.get("intent_accuracy", {})
        if intent_acc:
            print(f"\n  Intent Accuracy:")
            for intent, data in intent_acc.items():
                acc = data.get("accuracy", 0) * 100
                print(f"    {intent:15s}: {acc:5.1f}% ({data.get('correct', 0)}/{data.get('total', 0)})")

        # FP/FN analysis
        fp_count = eval_result.get("fp_count", 0)
        fn_count = eval_result.get("fn_count", 0)
        if fp_count > 0 or fn_count > 0:
            print(f"\n{'ERROR ANALYSIS':=^70}")
            print(f"  False Positives: {fp_count}")
            for fp in eval_result.get("top_fps", [])[:5]:
                print(f"    {fp.get('prompt', '')[:50]} -> extra: {fp.get('fp_skills', [])}")
            print(f"  False Negatives: {fn_count}")
            for fn in eval_result.get("top_fns", [])[:5]:
                print(f"    {fn.get('prompt', '')[:50]} -> missed: {fn.get('fn_skills', [])}")
    else:
        print("  (eval script not available or failed)")

    # --- Bundle count ---
    config_path = PROJECT_DIR / ".claude" / "skills" / "skill-router-config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            bundle_count = len(config.get("bundles", {}))
            print(f"\n{'CONFIG STATS':=^70}")
            print(f"  Config version: {config.get('version', '?')}")
            print(f"  Total bundles: {bundle_count}")
            print(f"  Min score: {config.get('min_score', '?')}")
            print(f"  Max bundles per match: {config.get('max_bundles', '?')}")
            total_kw = sum(
                len(b.get("keywords", [])) + len(b.get("weighted_keywords", {}))
                for b in config.get("bundles", {}).values()
            )
            print(f"  Total keywords: {total_kw}")
        except Exception:
            pass

    print("\n" + "=" * 70)


def print_json(args):
    """Print dashboard data as JSON."""
    events = load_accuracy_events(days=args.period)
    data = {
        "generated_at": datetime.now().isoformat(),
        "period_days": args.period,
        "activation_rate": compute_activation_rate(events),
        "daily_trend": compute_daily_trend(events, days=14),
        "skill_frequency": compute_skill_frequency(events),
    }
    eval_result = run_eval()
    if eval_result:
        data["eval"] = eval_result
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Skill Router Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--period", type=int, default=0, help="Filter to last N days (0=all)")
    args = parser.parse_args()

    if args.json:
        print_json(args)
    else:
        print_dashboard(args)


if __name__ == "__main__":
    main()
