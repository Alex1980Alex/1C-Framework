"""Skeleton for synthetic golden dataset expansion (roadmap 260509 §2.2 v2.0).

Generates additional items for `data/eval/golden_v1.json` by sampling chunks
from the indexed `pdf_documents` Qdrant collection and synthesizing questions
via DSPy.

NOT YET FUNCTIONAL — requires:
  - `pip install dspy-ai`
  - LLM credentials (ANTHROPIC_API_KEY or OPENAI_API_KEY)
  - Indexed `pdf_documents` collection

Currently exits with an instructive error if invoked. Kept in repo as the
scaffold for the v2.0 expansion task.

Usage (when functional):
    python scripts/gen_golden_dataset.py --count 30 --difficulty medium

Roadmap reference: docs/roadmap/260509_ROADMAP_CONSOLIDATED_BACKLOG.md §2.2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATASET_PATH = Path("data/eval/golden_v1.json")
SCHEMA_KEYS = {
    "id",
    "query",
    "expected_chunk_ids",
    "expected_keywords",
    "expected_answer_summary",
    "difficulty",
    "category",
    "domain",
}


def _check_prerequisites() -> list[str]:
    """Return list of missing prerequisites (empty list = ready to run)."""
    missing: list[str] = []
    try:
        import dspy
    except ImportError:
        missing.append("`dspy-ai` not installed (run: pip install dspy-ai)")
    try:
        import qdrant_client
    except ImportError:
        missing.append("`qdrant-client` not installed (install via `[qdrant]` extra)")
    return missing


def _load_existing_dataset() -> dict:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"{DATASET_PATH} not found — run from repo root")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _next_id(existing: dict) -> int:
    items = existing.get("items", [])
    nums = []
    for item in items:
        ident = item.get("id", "")
        if ident.startswith("gv1-"):
            try:
                nums.append(int(ident.split("-")[1]))
            except (ValueError, IndexError):
                continue
    return max(nums, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10, help="Items to synthesize")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="medium")
    parser.add_argument("--collection", default="pdf_documents", help="Qdrant collection")
    parser.add_argument("--dry-run", action="store_true", help="Validate prerequisites only")
    args = parser.parse_args()

    missing = _check_prerequisites()
    if missing:
        print("ERROR: missing prerequisites for synthetic generation:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(file=sys.stderr)
        print(
            "This script is a scaffold. Install deps + provide LLM creds to run.", file=sys.stderr
        )
        return 2

    if args.dry_run:
        existing = _load_existing_dataset()
        print(f"Dataset loaded: {len(existing.get('items', []))} items")
        print(f"Next id would be: gv1-{_next_id(existing):03d}")
        print("OK — prerequisites satisfied")
        return 0

    print("ERROR: synthetic generation logic not yet implemented.", file=sys.stderr)
    print("       This file is a scaffold pending DSPy.Synthesize integration.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
