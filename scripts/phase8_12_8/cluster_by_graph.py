"""Phase 8.12.8 Step 2: cluster filtered chunks via call-graph WCC."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "cache" / "bsl_call_graph.db"


def build_graph(db_path: Path) -> nx.Graph:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    G = nx.Graph()
    idx: dict[tuple[str, str], list[str]] = defaultdict(list)

    cursor.execute("SELECT id, name, module_path FROM symbols")
    for sym_id, name, module_path in cursor.fetchall():
        module_path = module_path or ""
        G.add_node(sym_id, name=name, module_path=module_path)
        idx[(name, module_path)].append(sym_id)
        idx[(name, "")].append(sym_id)

    cursor.execute("SELECT caller_id, callee_name, callee_module FROM calls")
    for caller_id, callee_name, callee_module in cursor.fetchall():
        callee_module = callee_module or ""
        callee_ids = idx.get((callee_name, callee_module), []) or idx.get((callee_name, ""), [])
        for callee_id in callee_ids:
            if callee_id != caller_id:
                G.add_edge(caller_id, callee_id)

    conn.close()
    return G


def cluster_summary(G: nx.Graph, members: list[str]) -> dict:
    module_paths = [G.nodes[m].get("module_path", "") for m in members]
    return {
        "unique_modules": len(set(module_paths)),
        "top_modules": sorted(set(module_paths))[:3],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=config.CLUSTERS)
    parser.add_argument("--min-size", type=int, default=3)
    parser.add_argument("--max-size", type=int, default=200)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Error: DB not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    print(f"[1/3] Loading graph from {args.db}")
    G = build_graph(args.db)
    print(f"      nodes={G.number_of_nodes()} edges={G.number_of_edges()}")

    print("[2/3] Computing connected components")
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    print(f"      total components: {len(components)}")
    print(f"      top-5 sizes: {[len(c) for c in components[:5]]}")

    print(f"[3/3] Filtering [{args.min_size}, {args.max_size}] + writing")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(args.output, "w", encoding="utf-8") as f:
        for cid, comp in enumerate(components):
            if args.min_size <= len(comp) <= args.max_size:
                members = sorted(comp)
                f.write(
                    json.dumps(
                        {
                            "cluster_id": cid,
                            "size": len(comp),
                            "members": members,
                            "summary": cluster_summary(G, members),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1

    print(f"Done: {written} clusters -> {args.output}")


if __name__ == "__main__":
    main()
