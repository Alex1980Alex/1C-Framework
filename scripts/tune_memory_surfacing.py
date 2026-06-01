#!/usr/bin/env python3
"""Section 25 B1+B2 -- offline sweep + gated promotion for memory surfacing params.

Closes the self-tuning loop (roadmap 260601 section 5) on top of the B0 golden-set
harness:

  B1  sweep    -- grid-search tunable params on the *train* split (AutoRAG-style
                  offline sweep), rank configs by a composite of NDCG@k + hit-rate
                  (NDCG included deliberately: research warns recall/hit alone is
                  misleading in RRF pipelines). Dry-run: writes the winning config
                  to data/memory/golden/sweep_result.json, never touches the hook.

  B2  promote  -- validate the swept winner against the *held-out* split (the split
                  NOT used to pick it). Promote to data/memory/surfacing_tuning.json
                  ONLY when the target metric improves by >= --min-improvement AND no
                  guard metric regresses. Dry-run by default; writes only with --apply
                  or MEMORY_AUTOTUNE_APPLY=1. Snapshots the prior config for rollback
                  and audits the decision to the confidence-lifecycle log.

      rollback -- restore the previous config snapshot (auto-rollback path: Part A
                  analyzer flags degradation on the next window -> run this).

The hook (memory-first-hook.py::_load_surfacing_tuning) reads surfacing_tuning.json
at import, clamped to its own clamp_ranges, so a promotion can never push the hook
outside safe bounds. Fully reversible: delete the file -> hardcoded defaults.

Usage:
  python scripts/tune_memory_surfacing.py sweep --split train --top 5
  python scripts/tune_memory_surfacing.py promote               # dry-run
  python scripts/tune_memory_surfacing.py promote --apply
  python scripts/tune_memory_surfacing.py rollback --apply
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HARNESS = PROJECT_ROOT / "scripts" / "memory_golden_harness.py"
TUNING_FILE = PROJECT_ROOT / "data" / "memory" / "surfacing_tuning.json"
PREV_FILE = PROJECT_ROOT / "data" / "memory" / "surfacing_tuning.prev.json"
SWEEP_RESULT = PROJECT_ROOT / "data" / "memory" / "golden" / "sweep_result.json"

# Default sweep grid (modest -- golden-set is small, avoid overfitting). experience /
# conversation arms are empty collections so their weights are held fixed.
GRID = {
    "skill": [0.3, 0.5, 0.7, 0.9],
    "pattern_dense": [0.3, 0.5, 0.7],
    "pattern_lexical": [0.5, 0.7, 0.9],
    "min_surface_conf": [0.15, 0.25],
    "conf_floor": [0.30],
    "rrf_k": [60],
}

# No-regression epsilon: a candidate may dip a guard metric by at most this much.
REGRESSION_EPS = 0.01


def _load_harness():
    spec = importlib.util.spec_from_file_location("memory_golden_harness", HARNESS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load_harness()


def target_score(report: dict[str, Any], alpha: float = 0.5) -> float:
    """Composite objective: alpha*NDCG@k + (1-alpha)*hit_rate (roadmap section 3 note)."""
    return round(alpha * report["ndcg_at_k"] + (1.0 - alpha) * report["hit_rate"], 4)


def _clamp_ranges() -> dict[str, Any]:
    try:
        data = json.loads(TUNING_FILE.read_text(encoding="utf-8"))
        return data.get("clamp_ranges", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def clamp_config(config: dict[str, Any], ranges: dict[str, Any]) -> dict[str, Any]:
    """Clamp a config to the tuning file's clamp_ranges (defence in depth vs the hook)."""
    def _c(value: float, key: str) -> float:
        rng = ranges.get(key)
        if isinstance(rng, list) and len(rng) == 2:
            return max(rng[0], min(rng[1], value))
        return value

    out = json.loads(json.dumps(config))
    out["min_surface_conf"] = _c(out["min_surface_conf"], "min_surface_conf")
    out["conf_floor"] = _c(out["conf_floor"], "conf_floor")
    for arm, w in out["surface_rrf_weights"].items():
        out["surface_rrf_weights"][arm] = _c(w, "rrf_weight")
    return out


def build_grid(base_weights: dict[str, Any]) -> list[dict[str, Any]]:
    """Cartesian product of GRID -> list of full config dicts (weights merged onto base)."""
    configs: list[dict[str, Any]] = []
    combos = itertools.product(
        GRID["skill"], GRID["pattern_dense"], GRID["pattern_lexical"],
        GRID["min_surface_conf"], GRID["conf_floor"], GRID["rrf_k"],
    )
    for skill, p_dense, p_lex, min_conf, floor, k in combos:
        weights = dict(base_weights)
        weights["skill"] = skill
        weights["pattern_dense"] = p_dense
        weights["pattern_lexical"] = p_lex
        configs.append(
            {
                "surface_rrf_weights": weights,
                "min_surface_conf": min_conf,
                "conf_floor": floor,
                "rrf_k": k,
            }
        )
    return configs


def sweep(
    golden: list[dict[str, Any]],
    captures: dict[str, Any],
    k: int,
    alpha: float,
) -> list[dict[str, Any]]:
    """Evaluate every grid config; return entries sorted by target score desc."""
    base = H.DEFAULT_CONFIG["surface_rrf_weights"]
    results: list[dict[str, Any]] = []
    for config in build_grid(base):
        report = H.evaluate_config(golden, captures, config, k=k)
        results.append(
            {
                "config": config,
                "score": target_score(report, alpha),
                "metrics": {m: report[m] for m in
                            ("hit_rate", "precision_at_k", "recall_at_k", "ndcg_at_k", "mrr")},
            }
        )
    results.sort(key=lambda r: -r["score"])
    return results


def write_tuning(config: dict[str, Any], note: str) -> None:
    """Persist a config to surfacing_tuning.json, preserving clamp_ranges + bumping version."""
    try:
        prior = json.loads(TUNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        prior = {}
    out = {
        "_comment": "Roadmap section 25 -- managed by tune_memory_surfacing.py (B2 gated promotion). "
        "Reversible: delete this file to restore hook defaults. Hook clamps to clamp_ranges.",
        "version": int(prior.get("version", 1)) + 1,
        "updated": note,
        "managed_by": "tune_memory_surfacing.py",
        "surface_rrf_weights": config["surface_rrf_weights"],
        "min_surface_conf": config["min_surface_conf"],
        "conf_floor": config["conf_floor"],
        "surface_cache_ttl_seconds": prior.get("surface_cache_ttl_seconds", 300),
        "rrf_k": config["rrf_k"],
        "clamp_ranges": prior.get("clamp_ranges", {}),
    }
    TUNING_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def _audit(event: str, **fields: Any) -> None:
    """Best-effort audit to the confidence-lifecycle log (shared with section 22/24)."""
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.vector_memory.lifecycle_log import log_event

        log_event(event, **fields)
    except Exception:
        pass


def _no_regression(best: dict[str, Any], cur: dict[str, Any]) -> bool:
    for metric in ("hit_rate", "ndcg_at_k"):
        if best[metric] < cur[metric] - REGRESSION_EPS:
            return False
    return True


def cmd_sweep(args: argparse.Namespace) -> int:
    golden = H.load_golden(split=args.split)
    captures = H.load_captures()
    if not golden or not captures:
        print("Need golden-set + captures (run: memory_golden_harness.py capture).", file=sys.stderr)
        return 1
    ranked = sweep(golden, captures, args.k, args.alpha)
    current = H.load_tuning_config()
    cur_report = H.evaluate_config(golden, captures, current, k=args.k)
    cur_score = target_score(cur_report, args.alpha)

    print(f"# Sweep (split={args.split}, n={len(golden)}, k={args.k}, alpha={args.alpha})")
    print(f"current config score={cur_score} {cur_report and {m: cur_report[m] for m in ('hit_rate','ndcg_at_k')}}")
    print(f"grid size: {len(ranked)} configs\n")
    for i, r in enumerate(ranked[: args.top], start=1):
        w = r["config"]["surface_rrf_weights"]
        print(f"{i}. score={r['score']} hit={r['metrics']['hit_rate']} ndcg={r['metrics']['ndcg_at_k']} "
              f"| skill={w['skill']} dense={w['pattern_dense']} lex={w['pattern_lexical']} "
              f"min_conf={r['config']['min_surface_conf']} k={r['config']['rrf_k']}")

    best = ranked[0]
    SWEEP_RESULT.parent.mkdir(parents=True, exist_ok=True)
    SWEEP_RESULT.write_text(
        json.dumps(
            {"split": args.split, "k": args.k, "alpha": args.alpha,
             "current_score": cur_score, "best": best},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    delta = round(best["score"] - cur_score, 4)
    print(f"\nbest score={best['score']} (current={cur_score}, delta={delta:+}) -> {SWEEP_RESULT.name} (dry-run)")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    if not SWEEP_RESULT.exists():
        print("No sweep_result.json -- run 'sweep' first.", file=sys.stderr)
        return 1
    sweep_data = json.loads(SWEEP_RESULT.read_text(encoding="utf-8"))
    best_config = sweep_data["best"]["config"]

    golden = H.load_golden(split=args.eval_split)
    captures = H.load_captures()
    if not golden or not captures:
        print("Need golden-set + captures for the eval split.", file=sys.stderr)
        return 1
    current = H.load_tuning_config()
    cur = H.evaluate_config(golden, captures, current, k=args.k)
    best = H.evaluate_config(golden, captures, best_config, k=args.k)
    cur_t = target_score(cur, args.alpha)
    best_t = target_score(best, args.alpha)
    improvement = round(best_t - cur_t, 4)
    no_reg = _no_regression(best, cur)
    gate_ok = improvement >= args.min_improvement and no_reg

    apply = args.apply or os.environ.get("MEMORY_AUTOTUNE_APPLY") == "1"

    print(f"# Promote (validation split={args.eval_split}, k={args.k})")
    print(f"current: target={cur_t} hit={cur['hit_rate']} ndcg={cur['ndcg_at_k']}")
    print(f"best:    target={best_t} hit={best['hit_rate']} ndcg={best['ndcg_at_k']}")
    print(f"improvement={improvement:+} (need >= {args.min_improvement}), no_regression={no_reg}")
    print(f"gate {'PASS' if gate_ok else 'FAIL'}; mode={'APPLY' if apply else 'DRY-RUN'}")

    if not gate_ok:
        _audit("surfacing_tune_skip", improvement=improvement, no_regression=no_reg,
               eval_split=args.eval_split, applied=False)
        print("-> not promoting (gate failed).")
        return 0
    if not apply:
        _audit("surfacing_tune_dryrun", improvement=improvement,
               eval_split=args.eval_split, applied=False)
        print("-> gate passed; dry-run (use --apply or MEMORY_AUTOTUNE_APPLY=1 to write).")
        return 0

    # Snapshot current for rollback, then write.
    if TUNING_FILE.exists():
        PREV_FILE.write_text(TUNING_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    clamped = clamp_config(best_config, _clamp_ranges())
    write_tuning(clamped, note=f"B2 promotion improvement={improvement:+} split={args.eval_split}")
    _audit("surfacing_tune_apply", improvement=improvement, eval_split=args.eval_split,
           applied=True, new_weights=clamped["surface_rrf_weights"],
           min_surface_conf=clamped["min_surface_conf"], rrf_k=clamped["rrf_k"])
    print(f"-> PROMOTED. Snapshot: {PREV_FILE.name}. Hook picks it up on next import.")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    if not PREV_FILE.exists():
        print("No snapshot (surfacing_tuning.prev.json) to roll back to.", file=sys.stderr)
        return 1
    if not (args.apply or os.environ.get("MEMORY_AUTOTUNE_APPLY") == "1"):
        print("Dry-run: would restore surfacing_tuning.json from snapshot (use --apply).")
        return 0
    TUNING_FILE.write_text(PREV_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    _audit("surfacing_tune_rollback", applied=True)
    print(f"-> ROLLED BACK surfacing_tuning.json from {PREV_FILE.name}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="section 25 B1/B2 surfacing self-tuning")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sw = sub.add_parser("sweep", help="grid-search on a split (dry-run)")
    sw.add_argument("--split", default="train")
    sw.add_argument("--k", type=int, default=5)
    sw.add_argument("--alpha", type=float, default=0.5, help="weight of NDCG vs hit in objective")
    sw.add_argument("--top", type=int, default=5)

    pr = sub.add_parser("promote", help="gated promotion validated on held-out split")
    pr.add_argument("--eval-split", default="heldout")
    pr.add_argument("--k", type=int, default=5)
    pr.add_argument("--alpha", type=float, default=0.5)
    pr.add_argument("--min-improvement", type=float, default=0.02)
    pr.add_argument("--apply", action="store_true")

    rb = sub.add_parser("rollback", help="restore the previous config snapshot")
    rb.add_argument("--apply", action="store_true")

    args = ap.parse_args()
    if args.cmd == "sweep":
        return cmd_sweep(args)
    if args.cmd == "promote":
        return cmd_promote(args)
    if args.cmd == "rollback":
        return cmd_rollback(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
