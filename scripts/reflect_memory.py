#!/usr/bin/env python3
"""§26 P2 D2.1 — reflection CLI.

Consolidate repeated episodic facts in data/memory_ai.db into semantic
learned_patterns (1 pattern per same-topic cluster), with DERIVES_FROM links
to the source episodes. Dry-run by default — prints a reviewable plan; pass
--apply to embed + upsert + link.

Usage:
  python scripts/reflect_memory.py                      # dry-run plan
  python scripts/reflect_memory.py --apply
  python scripts/reflect_memory.py --min-cluster 2 --theta 1.5 --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "hooks"))

from shared.reflection import (
    DEFAULT_CAP,
    DEFAULT_MIN_CLUSTER,
    DEFAULT_SIM_THRESHOLD,
    make_link_fn,
    reflect,
)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Reflect episodic facts into semantic patterns (§26 P2 D2.1)"
    )
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    # Defaults come from the module. The maintenance cadence runs this CLI, so a
    # hardcoded copy here silently overrides any change made in reflection.py.
    ap.add_argument(
        "--min-cluster",
        type=int,
        default=DEFAULT_MIN_CLUSTER,
        help="min cluster size to consolidate",
    )
    ap.add_argument(
        "--sim", type=float, default=DEFAULT_SIM_THRESHOLD, help="Jaccard token-overlap threshold"
    )
    ap.add_argument(
        "--theta", type=float, default=None, help="alt trigger: summed importance >= theta"
    )
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP, help="max patterns created per run")
    return ap


def main() -> int:
    # Cyrillic pattern names → avoid UnicodeEncodeError aborting the summary on a
    # cp1251 console (esp. after --apply already wrote patterns). [[feedback-windows-hook-stdout-cp1251]]
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    args = _build_parser().parse_args()

    link_fn = make_link_fn() if args.apply else None
    stats = reflect(
        min_cluster=args.min_cluster,
        sim_threshold=args.sim,
        importance_theta=args.theta,
        cap=args.cap,
        dry_run=not args.apply,
        link_fn=link_fn,
    )

    print(
        f"# reflection (apply={args.apply}, min_cluster={args.min_cluster}, sim={args.sim}, theta={args.theta})"
    )
    print(
        f"clusters_found={stats['clusters_found']} clusters_triggered={stats['clusters_triggered']} "
        f"created={stats['created']} skipped_dup={stats['skipped_dup']} "
        f"skipped_cap={stats['skipped_cap']} errors={stats['errors']}"
    )
    for name in stats.get("items", []):
        print(f"  {'WOULD CONSOLIDATE' if not args.apply else 'CONSOLIDATED'}: {name}")
    if not args.apply:
        print("\n-> dry-run; re-run with --apply to write patterns + DERIVES_FROM links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
