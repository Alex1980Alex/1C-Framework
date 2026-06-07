#!/usr/bin/env python3
"""Cross-store sync CLI — MIRRORS links + conflict resolution (§26 P3, D3.2+D3.3).

Reuses the D3.1 scanners (``scripts/cross_store_index.run_scan``) to find facts
duplicated across stores, then:
  - **D3.2** picks a canonical store per duplicate via ``ConflictResolver``
    (SOURCE_PRIORITY) and writes a conflict-resolution audit;
  - **D3.3** materialises ``MIRRORS`` edges (mirror --MIRRORS--> canonical) in the
    link_registry so the duplicate relationship is persisted, not re-derived.

READ-ONLY by default (dry-run; builds a report only). ``--apply`` creates the
``MIRRORS`` links — **idempotent** (skips an edge that already exists) and
**reversible** (links are tagged ``created_by="cross-store-sync"``; deleting them
restores the prior state). Fail-soft: a down store is skipped, never aborts.

Usage:
  python scripts/cross_store_sync.py            # dry-run plan + report
  python scripts/cross_store_sync.py --apply    # create MIRRORS links
  python scripts/cross_store_sync.py --no-report
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.orchestrator.cross_store_index import build_index, find_cross_store_dups
from memory.orchestrator.cross_store_sync import (
    build_sync_plan,
    render_sync_report,
    summarize_plan,
)
from memory.orchestrator.link_registry import LinkRegistry, LinkType
from scripts.cross_store_index import run_scan

REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"


def apply_links(plan: dict[str, Any], registry: LinkRegistry) -> dict[str, int]:
    """Create the planned MIRRORS links (idempotent). Returns create/skip/error counts."""
    created = existing = errors = 0
    for ml in plan["links"]:
        try:
            if registry.find_link(ml.mirror_uid, ml.canonical_uid, LinkType.MIRRORS) is not None:
                existing += 1
                continue
            registry.create_link(
                source_id=ml.mirror_uid,
                target_id=ml.canonical_uid,
                link_type=LinkType.MIRRORS,
                strength=1.0,
                created_by="cross-store-sync",
                metadata={"content_hash": ml.content_hash, "via": "cross_store_sync_D3.3"},
            )
            created += 1
        except Exception:  # fail-soft per-link (e.g. self-link, race) — never abort the batch
            errors += 1
    return {"created": created, "existing": existing, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="cross-store sync: MIRRORS links + conflict resolution (§26 P3)"
    )
    ap.add_argument("--apply", action="store_true", help="create MIRRORS links (default: dry-run)")
    ap.add_argument("--no-report", action="store_true", help="do not write report file")
    ap.add_argument("--stamp", default=None, help="override timestamp (tests)")
    args = ap.parse_args()

    records, errors = run_scan()
    dups = find_cross_store_dups(build_index(records))
    plan = build_sync_plan(dups)
    summary = summarize_plan(plan)
    stamp = args.stamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    applied_stats: dict[str, int] | None = None
    if args.apply:
        applied_stats = apply_links(plan, LinkRegistry())

    if not args.no_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = render_sync_report(
            plan, summary, stamp, applied=bool(args.apply), store_errors=errors
        )
        (REPORTS_DIR / f"cross_store_sync_{stamp}.md").write_text(report, encoding="utf-8")
        sidecar = {
            "summary": summary,
            "store_errors": errors,
            "applied": applied_stats,
            "conflicts": plan["conflicts"],
            "links": [
                {
                    "mirror": lk.mirror_uid,
                    "canonical": lk.canonical_uid,
                    "content_hash": lk.content_hash,
                }
                for lk in plan["links"]
            ],
        }
        (REPORTS_DIR / f"cross_store_sync_{stamp}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ASCII-safe stdout (details live in the UTF-8 report).
    print("# cross-store sync (MIRRORS + conflict resolution)")
    print(
        f"mirror_links={summary['mirror_links']} conflict_groups={summary['conflict_groups']} "
        f"skipped={summary['skipped_groups']} canonical_by_store={summary['canonical_by_store']}"
    )
    if applied_stats is not None:
        print(f"applied: {applied_stats}")
    else:
        print("dry-run; re-run with --apply to create MIRRORS links.")
    if errors:
        print(f"skipped stores (fail-soft): {errors}")
    if not args.no_report:
        print(f"report: data/reports/memory/cross_store_sync_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
