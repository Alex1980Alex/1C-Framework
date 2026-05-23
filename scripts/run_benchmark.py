#!/usr/bin/env python3
"""CLI for running BSL rename benchmarks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class _StubBackend:
    """Stub backend that returns empty WorkspaceEdit for dry-run testing."""

    def can_handle(self, uri: str) -> bool:
        return uri.lower().endswith((".bsl", ".os"))

    def plan_rename(self, uri: str, line: int, character: int, new_name: str):
        from bsl.semantic_search.refactor.types import WorkspaceEdit

        return WorkspaceEdit()


def _build_backends(names: list[str]) -> dict:
    backends: dict = {}
    for name in names:
        if name == "ast-grep":
            print(f"WARNING: '{name}' backend is stub — returning empty WorkspaceEdit")
            backends[name] = _StubBackend()
        else:
            print(f"ERROR: Unsupported backend '{name}'")
            sys.exit(1)
    return backends


def _append_trend(run_id: str, backends: list[str], results: list, trend_path: Path) -> None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
        ).strip()
    except Exception:
        commit = "unknown"

    total = len(results)
    successes = sum(1 for r in results if r.applied)

    trend_path.parent.mkdir(parents=True, exist_ok=True)
    if not trend_path.exists():
        trend_path.write_text(
            "| Run ID | Date | Commit | Backends | Success | Total |\n"
            "|--------|------|--------|----------|---------|-------|\n",
            encoding="utf-8",
        )

    date_str = datetime.now().strftime("%Y-%m-%d")
    row = f"| {run_id} | {date_str} | {commit} | {','.join(backends)} | {successes} | {total} |\n"
    with trend_path.open("a", encoding="utf-8") as f:
        f.write(row)
    print(f"Appended trend row to {trend_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run BSL rename benchmarks")
    ap.add_argument("--tasks", type=Path, default=Path("docs/roadmap/benchmark/tasks.json"))
    ap.add_argument("--backends", type=str, default="ast-grep")
    ap.add_argument("--run-id", type=str, required=True)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--categories", type=str, default=None)
    ap.add_argument("--task-id", type=str, default=None)
    ap.add_argument("--append-trend", action="store_true")
    args = ap.parse_args()

    output = args.output or Path(f"data/benchmark-run-{args.run_id}")
    backend_names = [b.strip() for b in args.backends.split(",")]
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    task_ids = [args.task_id] if args.task_id else None

    sys.path.insert(0, str(REPO_ROOT / "src"))
    sys.path.insert(0, str(REPO_ROOT / "docs" / "roadmap"))
    from benchmark.runner import BenchmarkRunner

    backends = _build_backends(backend_names)
    runner = BenchmarkRunner(
        repo_root=REPO_ROOT,
        tasks_path=args.tasks,
        output_dir=output,
    )
    results = runner.run(
        backends=backends,
        run_id=args.run_id,
        categories=categories,
        task_ids=task_ids,
    )

    total = len(results)
    successes = sum(1 for r in results if r.applied)
    print("\n=== Benchmark Summary ===")
    print(f"Run ID:    {args.run_id}")
    print(f"Total:     {total}")
    print(f"Successes: {successes}")
    print(f"Failures:  {total - successes}")

    if args.append_trend:
        _append_trend(
            args.run_id,
            backend_names,
            results,
            REPO_ROOT / "docs" / "roadmap" / "benchmark" / "trend.md",
        )


if __name__ == "__main__":
    main()
