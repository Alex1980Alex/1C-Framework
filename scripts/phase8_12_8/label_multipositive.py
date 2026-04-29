"""Phase 8.12.8 Step 4: multi-positive labeling + KL-div validation.

TODO: для каждой query из queries_pilot.jsonl:
- primary positive = anchor_chunk_id (graded=3)
- secondary positives = call_graph 1-hop callers ∪ callees (graded=2)
- module siblings of secondary (graded=1)
- KL-divergence: cosine sim distribution (query↔positive) vs noise
  baseline (query↔random chunk). Target KL < KL_DIV_THRESHOLD.
- Output golden_set.jsonl: {query, anchor_chunk_id, primary_positive,
  secondary_positives[], graded{chunk_id: int}}.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402,F401

if __name__ == "__main__":
    raise NotImplementedError("Phase 8.12.8 Step 4 — TODO")
