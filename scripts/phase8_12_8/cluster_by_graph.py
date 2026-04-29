"""Phase 8.12.8 Step 2: cluster filtered chunks via call-graph WCC.

TODO: load call_graph from same source as reindex_bsl_qwen3.py
("Context enrichment ON: 975 objects"), build NetworkX graph,
compute weakly_connected_components, output clusters.jsonl with
{cluster_id, members[chunk_id], summary, size}.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402,F401

if __name__ == "__main__":
    raise NotImplementedError("Phase 8.12.8 Step 2 — TODO")
