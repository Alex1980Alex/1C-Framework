#!/usr/bin/env python3
"""Mirror the .claude/skills/ catalog into the Qdrant skill_library collection.

Roadmap 260612 P0.1/P0.2 (Skill System Full Verification): the incremental
skills-harvester diffs against its own state file, so it never sees points that
predate it — ghosts of deleted skills (e.g. `1c-mcp-toolkit`) survive in the
collection and keep surfacing in [MEMORY CONTEXT]. This script reconciles the
collection against the catalog itself:

  - prunes ghost points (skill dir gone / archived) — snapshot taken first;
  - upserts drifted (missing) and changed skills (content_hash mismatch,
    incl. legacy points without content_hash) under the §26 write-contract
    (payload content_hash + record_ingest -> memory-ingestion.log);
  - resyncs the incremental harvester's state file.

Usage:
    python scripts/reindex_skill_library.py            # dry-run: print the plan
    python scripts/reindex_skill_library.py --apply    # reconcile for real
    python scripts/reindex_skill_library.py --apply --no-snapshot

Registered in the maintenance cadence (scripts/memory_maintenance.py,
job `reindex_skill_library`, apply-only) — drift catalog<->library converges
to 0 on every cadence run (acceptance criterion A5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Import the harvester core as a top-level module (NOT via the `shared` package:
# src/shared would collide with .claude/hooks/shared, see
# [[feedback-hook-src-shared-collision]]).
_SHARED_DIR = PROJECT_ROOT / ".claude" / "hooks" / "shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

import skills_harvest


def main() -> int:
    ap = argparse.ArgumentParser(description="Mirror skills catalog -> Qdrant skill_library")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run plan)")
    ap.add_argument(
        "--no-snapshot",
        action="store_true",
        help="skip the pre-prune collection snapshot (snapshots are kept by Qdrant on disk)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    stats = skills_harvest.mirror_skill_library(apply=args.apply, snapshot=not args.no_snapshot)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[reindex_skill_library] {mode}")
        print(f"  catalog skills : {stats['catalog']}")
        print(f"  library points : {stats['library']}")
        print(f"  ghosts (prune) : {len(stats['ghosts'])} {stats['ghosts'] or ''}")
        print(f"  to upsert      : {len(stats['to_upsert'])}")
        print(f"  unchanged      : {stats['unchanged']}")
        if args.apply:
            print(
                f"  upserted={stats['upserted']} pruned={stats['pruned']} "
                f"errors={stats['errors']} snapshot={stats['snapshot']}"
            )

    # Honest failure: partial errors -> non-zero so the cadence job shows it.
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
