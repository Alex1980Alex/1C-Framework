#!/usr/bin/env python3
"""Train-only A2-weight optimizer for skill-router (roadmap 260613 B5).

Greedy coordinate descent over ``config["a2_signals"]`` weights, scored on the
**TRAIN split ONLY** (``eval-skill-router.py --split train``), then measured
honestly on **TEST** once. Candidate weights are injected via a temp config +
``SKILL_ROUTER_CONFIG`` env — the production config is never touched unless
``--apply``.

Why train-only: tuning on the full/test set is exactly the F1-contamination this
roadmap removes (260613). The honest held-out number is TEST, scored AFTER tuning.
Anti-overfit guardrail (B6): warns if the train→test gap exceeds the threshold.
Reproducible (B7): deterministic coordinate order, logs gt_hash + grid.

Prerequisite: A7 (representative gate — quarantine promoted). Tuning on the
designed-only subset would just overfit the easy cases.

Usage:
    python scripts/tune_skill_router.py                  # dry-run: report best vs baseline
    python scripts/tune_skill_router.py --coords literal # tune one coord (fast smoke)
    python scripts/tune_skill_router.py --apply          # write best a2_signals into config
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT_ROOT / ".claude" / "skills" / "skill-router-config.json"
EVAL = PROJECT_ROOT / "scripts" / "eval-skill-router.py"
GT = PROJECT_ROOT / "data" / "skill-router-ground-truth.jsonl"
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

# Coordinate → candidate values (small, interpretable ranges; A2 is a thin layer).
COORD_GRID: dict[str, list[int]] = {
    "literal": [3, 4, 5, 6],  # literal_name_weight
    "bsl": [2, 3, 4, 5],  # bsl_signal_weights["bsl-dev"]
    "conn": [2, 3, 4],  # conn_str_weights["research-1c"]
}
DEFAULT_A2 = {
    "bsl_signal_weights": {"bsl-dev": 3, "research-1c": 1},
    "conn_str_weights": {"research-1c": 3},
    "literal_name_weight": 4,
    "literal_name_min_len": 6,
}


# --- pure helpers (unit-tested) ---------------------------------------------


def set_coord(a2: dict, coord: str, value: int) -> dict:
    """Return a deep copy of `a2` with one coordinate set to `value`."""
    out = copy.deepcopy(a2)
    if coord == "literal":
        out["literal_name_weight"] = value
    elif coord == "bsl":
        out.setdefault("bsl_signal_weights", {})["bsl-dev"] = value
    elif coord == "conn":
        out.setdefault("conn_str_weights", {})["research-1c"] = value
    else:
        raise ValueError(f"unknown coord {coord!r}")
    return out


def _total_weight(a2: dict) -> int:
    return (
        int(a2.get("literal_name_weight", 0))
        + int(a2.get("bsl_signal_weights", {}).get("bsl-dev", 0))
        + int(a2.get("conn_str_weights", {}).get("research-1c", 0))
    )


def select_best(cands: list[dict]) -> dict:
    """Pick max train_f1; tie-break by SMALLER total weight (Occam — avoid inflating
    weights for no gain), then higher silence_accuracy. None train_f1 sorts last."""
    return max(
        cands,
        key=lambda r: (
            r["train_f1"] if r["train_f1"] is not None else -1.0,
            -_total_weight(r["a2"]),
            r.get("silence") if r.get("silence") is not None else -1.0,
        ),
    )


def is_overfit(train_f1: float | None, test_f1: float | None, threshold: float = 0.10) -> bool:
    """B6 guardrail: train→test gap beyond threshold flags overfit."""
    if train_f1 is None or test_f1 is None:
        return False
    return (train_f1 - test_f1) > threshold


# --- eval runner (subprocess + config injection) ----------------------------


def run_eval(a2: dict, split: str, timeout: float = 600.0) -> dict | None:
    """Inject `a2` into a temp config, run eval --split, return honest metrics.

    Uses SKILL_ROUTER_CONFIG env so the router (spawned by eval as a subprocess)
    picks up the candidate weights. Never touches the production config."""
    try:
        base = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[tune] cannot read base config: {exc}", file=sys.stderr)
        return None
    base["a2_signals"] = {**base.get("a2_signals", {}), **a2}
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="router-cfg-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(base, fh, ensure_ascii=False)
        env = {**os.environ, "SKILL_ROUTER_CONFIG": tmp_path, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run(
            [str(PYTHON), str(EVAL), "--split", split, "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        rep = json.loads(r.stdout)
        hm = rep.get("honest_metrics", {})
        return {
            "action_f1": hm.get("action_f1"),
            "silence": hm.get("silence_accuracy"),
            "n_action": hm.get("n_action"),
        }
    except Exception as exc:
        print(f"[tune] eval failed (split={split}): {exc}", file=sys.stderr)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _seed_a2() -> dict:
    """Start from the production config's a2_signals (fallback to DEFAULT_A2)."""
    seed = copy.deepcopy(DEFAULT_A2)
    try:
        cfg_a2 = json.loads(CONFIG.read_text(encoding="utf-8")).get("a2_signals", {})
        for k in (
            "bsl_signal_weights",
            "conn_str_weights",
            "literal_name_weight",
            "literal_name_min_len",
        ):
            if k in cfg_a2:
                seed[k] = cfg_a2[k]
    except (OSError, json.JSONDecodeError):
        pass
    return seed


def main() -> int:
    ap = argparse.ArgumentParser(description="Train-only A2-weight optimizer (260613 B5)")
    ap.add_argument("--coords", default="literal,bsl", help="comma list: literal,bsl,conn")
    ap.add_argument("--gap-threshold", type=float, default=0.10, help="B6 overfit warn gap")
    ap.add_argument("--apply", action="store_true", help="write best a2_signals into config")
    args = ap.parse_args()

    coords = [c.strip() for c in args.coords.split(",") if c.strip() in COORD_GRID]
    if not coords:
        print(
            f"[tune] no valid coords in {args.coords!r} (allowed: {list(COORD_GRID)})",
            file=sys.stderr,
        )
        return 2

    gt_hash = hashlib.sha1(GT.read_bytes()).hexdigest()[:12] if GT.exists() else "no-gt"
    print(f"[tune] gt_hash={gt_hash} coords={coords} (train-only greedy)", file=sys.stderr)

    seed = _seed_a2()
    base = run_eval(seed, "train")
    if not base or base["action_f1"] is None:
        print("[tune] baseline train eval failed — aborting", file=sys.stderr)
        return 1
    best = {"a2": seed, "train_f1": base["action_f1"], "silence": base["silence"]}
    print(f"[tune] baseline train action_f1={best['train_f1']}", file=sys.stderr)

    for coord in coords:
        cands = [best]  # keep current best in the running
        for val in COORD_GRID[coord]:
            cand_a2 = set_coord(best["a2"], coord, val)
            if cand_a2 == best["a2"]:
                continue
            m = run_eval(cand_a2, "train")
            f1 = m["action_f1"] if m else None
            print(f"[tune]   {coord}={val} -> train action_f1={f1}", file=sys.stderr)
            cands.append({"a2": cand_a2, "train_f1": f1, "silence": m["silence"] if m else None})
        best = select_best(cands)
        print(f"[tune] coord {coord} best -> {best['train_f1']} {best['a2']}", file=sys.stderr)

    # Honest held-out: measure best + baseline on TEST (scored once, after tuning).
    best_test = run_eval(best["a2"], "test")
    base_test = run_eval(seed, "test")
    best_test_f1 = best_test["action_f1"] if best_test else None
    base_test_f1 = base_test["action_f1"] if base_test else None
    overfit = is_overfit(best["train_f1"], best_test_f1, args.gap_threshold)

    report = {
        "gt_hash": gt_hash,
        "coords": coords,
        "baseline": {"a2": seed, "train_f1": base["action_f1"], "test_f1": base_test_f1},
        "best": {"a2": best["a2"], "train_f1": best["train_f1"], "test_f1": best_test_f1},
        "train_gain": (
            round(best["train_f1"] - base["action_f1"], 4)
            if best["train_f1"] is not None and base["action_f1"] is not None
            else None
        ),
        "overfit_warn": overfit,
    }
    out = sys.stdout.buffer
    out.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    out.flush()

    if overfit:
        print(
            f"[tune] WARN B6: train {best['train_f1']} >> test {best_test_f1} "
            f"(gap > {args.gap_threshold}) — possible overfit, prefer baseline",
            file=sys.stderr,
        )

    if args.apply:
        if report["train_gain"] and report["train_gain"] > 0 and not overfit:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
            cfg.setdefault("a2_signals", {}).update(best["a2"])
            tmp = CONFIG.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, CONFIG)
            print(f"[tune] APPLIED best a2_signals to {CONFIG.name}", file=sys.stderr)
        else:
            print("[tune] --apply skipped: no train gain or overfit warn", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
