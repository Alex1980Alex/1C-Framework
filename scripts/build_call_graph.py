#!/usr/bin/env python3
"""
BSL Call Graph Builder — Phase 61

Parse all BSL files and build the call graph SQLite database.

Usage:
    python scripts/build_call_graph.py --project path/to/1c/project
    python scripts/build_call_graph.py --project path --clear
"""

import argparse
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bsl.parser import BSLASTParser
from src.bsl.call_graph.store import CallGraphStore

SKIP_PATTERNS = ["node_modules", "bin/", "build/"]
DEFAULT_DB = PROJECT_ROOT / "cache" / "bsl_call_graph.db"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build BSL call graph")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--clear", action="store_true", help="Clear existing graph")
    args = ap.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    t0 = time.time()
    parser = BSLASTParser()
    store = CallGraphStore(args.db)

    if args.clear:
        store.clear()
        print("Cleared existing call graph")

    bsl_files = sorted(
        f for f in project.rglob("*.bsl")
        if not any(p in str(f).replace("\\", "/") for p in SKIP_PATTERNS)
    )
    print(f"Found {len(bsl_files)} BSL files")

    errors = 0
    for i, fp in enumerate(bsl_files, 1):
        try:
            module = parser.parse_file(str(fp))
            store.add_module(module)
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"[ERROR] {fp.name}: {e}")

        if i % 200 == 0:
            print(f"[{i}/{len(bsl_files)}] processed...")

    elapsed = time.time() - t0
    stats = store.stats()

    print(f"\n{'='*50}")
    print("CALL GRAPH BUILD COMPLETE")
    print(f"{'='*50}")
    print(f"  Files:      {len(bsl_files)}")
    print(f"  Symbols:    {stats['symbols']}")
    print(f"  Calls:      {stats['calls']}")
    print(f"  Modules:    {stats['modules']}")
    print(f"  Exports:    {stats['exports']}")
    print(f"  By type:    {stats['by_type']}")
    print(f"  By call:    {stats['by_call_type']}")
    print(f"  Errors:     {errors}")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  DB:         {args.db}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
