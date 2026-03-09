#!/usr/bin/env python3
"""
BSL Search Evaluation Runner - Phase 58

Runs evaluation queries against BSL search infrastructure (Qdrant + FTS5)
and produces a baseline metrics report.

Usage:
    python scripts/eval_bsl_search.py [--output docs/analysis/bsl_baseline_report.md]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.bsl.evaluation.metrics import (
    EvalResult,
    aggregate_results,
    evaluate_single,
    format_report,
)


def load_dataset(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_qdrant_client = None
_embed_model = None


def _get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient as QC
        _qdrant_client = QC(host="localhost", port=6333, timeout=10)
    return _qdrant_client


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)
    return _embed_model


def _extract_module_name(file_path: str) -> str:
    """Extract module name from file_path for matching."""
    fp = file_path.replace("\\", "/")
    # Extract filename without extension
    name = os.path.basename(fp).replace(".bsl", "")
    # Also try to extract parent object name
    parts = fp.split("/")
    # Pattern: .../ObjectName/Ext/ModuleType.bsl
    for i, p in enumerate(parts):
        if p == "Ext" and i > 0:
            return f"{parts[i-1]}.{name}"
    return name


def search_qdrant(query: str, limit: int = 10) -> List[str]:
    """Search Qdrant bsl_code_v2 collection via qdrant-client."""
    try:
        client = _get_qdrant()
        model = _get_embed_model()
        embedding = model.encode(f"search_query: {query}").tolist()
        results = client.search(collection_name="bsl_code_v2", query_vector=embedding, limit=limit)
        names = []
        for r in results:
            payload = r.payload or {}
            fp = payload.get("file_path", "")
            if fp:
                names.append(_extract_module_name(fp))
        return names
    except Exception as e:
        print(f"  [qdrant error: {e}]")
        return []


def search_fts5(query: str, limit: int = 10) -> List[str]:
    """Search FTS5 SQLite index for BSL code."""
    try:
        import sqlite3
        db_path = os.path.join(PROJECT_ROOT, "cache", "docs-mcp", "hybrid_search.db")
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            # Escape query for FTS5: wrap each word in quotes
            words = query.split()
            fts_query = " ".join(f'"{w}"' for w in words if w)
            cursor.execute(
                "SELECT d.title, rank FROM documents_fts fts "
                "JOIN documents d ON d.rowid = fts.rowid "
                "WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts_query, limit),
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows if row[0]]
        except sqlite3.OperationalError:
            # Fallback: single phrase match
            cursor.execute(
                "SELECT title, rank FROM documents_fts WHERE documents_fts MATCH ? ORDER BY rank LIMIT ?",
                (f'"{query}"', limit),
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows if row[0]]
        finally:
            conn.close()
    except Exception as e:
        print(f"  [fts5 error: {e}]")
        return []


def search_combined(query: str, limit: int = 10) -> List[str]:
    """Combined search: Qdrant + FTS5, deduplicated."""
    qdrant_results = search_qdrant(query, limit)
    fts_results = search_fts5(query, limit)
    seen = set()
    combined = []
    for name in qdrant_results + fts_results:
        if name not in seen:
            seen.add(name)
            combined.append(name)
    return combined[:limit]


def run_evaluation(dataset_path, search_fn=None, search_mode="combined"):
    if search_fn is None:
        search_fn = {"qdrant": search_qdrant, "fts5": search_fts5, "combined": search_combined}.get(search_mode, search_combined)
    dataset = load_dataset(dataset_path)
    queries = dataset["queries"]
    print(f"Running evaluation: {len(queries)} queries, mode={search_mode}")
    print("=" * 60)
    results = []
    start_time = time.time()
    for i, query_data in enumerate(queries):
        qid = query_data["query_id"]
        query = query_data["query"]
        category = query_data["category"]
        expected = query_data["expected_results"]
        retrieved = search_fn(query)
        result = evaluate_single(qid, query, category, retrieved, expected)
        results.append(result)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(queries)} queries...")
    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f}s ({elapsed / len(queries):.2f}s/query)")
    summary = aggregate_results(results)
    summary["search_mode"] = search_mode
    summary["elapsed_seconds"] = round(elapsed, 1)
    summary["avg_latency_ms"] = round(elapsed * 1000 / len(queries), 0)
    return summary


def main():
    parser = argparse.ArgumentParser(description="BSL Search Evaluation Runner")
    parser.add_argument("--dataset", default=os.path.join(PROJECT_ROOT, "data", "eval", "bsl", "bsl_eval_dataset.json"))
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "docs", "analysis", "bsl_baseline_report.md"))
    parser.add_argument("--mode", choices=["qdrant", "fts5", "combined"], default="combined")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()
    if not os.path.exists(args.dataset):
        print(f"ERROR: Dataset not found: {args.dataset}")
        sys.exit(1)
    summary = run_evaluation(args.dataset, search_mode=args.mode)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        report = format_report(summary, title=f"BSL Search Baseline ({args.mode})")
        report += "\n## Run Info\n\n"
        report += f"- **Search mode**: {args.mode}\n"
        report += f"- **Total time**: {summary['elapsed_seconds']}s\n"
        report += f"- **Avg latency**: {summary['avg_latency_ms']}ms/query\n"
        report += f"- **Date**: {time.strftime('%Y-%m-%d %H:%M')}\n"
        print(report)
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
