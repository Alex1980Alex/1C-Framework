"""CLI entry-point for run analyzers.

Usage:
    python scripts/analyze_run.py --mode indexing --run-id <ID> [--collection <name>] [--verbosity medium|full]
    python scripts/analyze_run.py --mode graph    --source networkx|neo4j|qdrant_graph [...]

Triggered automatically by ``.claude/hooks/post-indexing-analyzer.py`` on
Claude Code Stop event (detects new ``run_end`` entries in
``data/indexing-progress.jsonl``). Also callable manually to re-render
a report for any historical run_id.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from analyzers.graph import GraphAnalyzer  # noqa: E402
from analyzers.indexing import IndexingAnalyzer  # noqa: E402
from analyzers.report_writer import write_report  # noqa: E402

PROGRESS_JSONL = REPO_ROOT / "data" / "indexing-progress.jsonl"
REPORTS_DIR = REPO_ROOT / "data" / "reports"
DEFAULT_BSL_DB = REPO_ROOT / "cache" / "bsl_call_graph.db"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze a completed indexing/graph run.")
    p.add_argument("--mode", required=True, choices=["indexing", "graph"])
    p.add_argument("--run-id", required=False, help="run_id from progress JSONL")
    p.add_argument("--collection", required=False, help="override detected Qdrant collection")
    p.add_argument(
        "--source",
        required=False,
        choices=["sqlite", "neo4j", "qdrant_graph"],
        help="graph source (mode=graph only)",
    )
    p.add_argument("--db-path", default=str(DEFAULT_BSL_DB), help="SQLite call graph DB (mode=graph, source=sqlite)")
    p.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-password", default="bsl-graph-2026")
    p.add_argument("--qdrant-collection", default="graph_embeddings")
    p.add_argument("--verbosity", default="medium", choices=["short", "medium", "full"])
    p.add_argument("--sample-size", type=int, default=200)
    p.add_argument("--qdrant-url", default=None)
    p.add_argument("--progress-jsonl", default=str(PROGRESS_JSONL))
    p.add_argument("--reports-dir", default=str(REPORTS_DIR))
    p.add_argument("--json-only", action="store_true", help="emit JSON summary to stdout instead of paths")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    reports_dir = Path(args.reports_dir)

    if args.mode == "indexing":
        if not args.run_id:
            print("ERROR: --run-id required for --mode=indexing", file=sys.stderr)
            return 2
        analyzer = IndexingAnalyzer(
            run_id=args.run_id,
            progress_jsonl=Path(args.progress_jsonl),
            reports_dir=reports_dir,
            collection=args.collection,
            qdrant_url=args.qdrant_url,
            verbosity=args.verbosity,
            sample_size=args.sample_size,
        )
    else:
        if not args.source:
            print("ERROR: --source required for --mode=graph (sqlite|neo4j|qdrant_graph)", file=sys.stderr)
            return 2
        analyzer = GraphAnalyzer(
            source=args.source,
            run_id=args.run_id,
            progress_jsonl=Path(args.progress_jsonl),
            reports_dir=reports_dir,
            db_path=Path(args.db_path) if args.db_path else None,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
            qdrant_url=args.qdrant_url,
            qdrant_collection=args.qdrant_collection,
            verbosity=args.verbosity,
            sample_size=args.sample_size,
        )

    try:
        spec = analyzer.analyze()
    except Exception as exc:
        print(f"ERROR: analyzer failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    md_path, json_path = write_report(spec, reports_dir)

    if args.json_only:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": spec.mode,
                    "subject": spec.subject,
                    "run_id": spec.run_id,
                    "md": str(md_path),
                    "json": str(json_path),
                    "anomalies": len(spec.anomalies),
                    "summary": spec.summary,
                },
                ensure_ascii=False,
                default=str,
            )
        )
    else:
        print(f"Report: {md_path}")
        print(f"JSON:   {json_path}")
        if spec.anomalies:
            print(f"Anomalies: {len(spec.anomalies)}")
            for a in spec.anomalies:
                print(f"  - {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
