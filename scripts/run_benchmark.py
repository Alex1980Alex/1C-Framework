#!/usr/bin/env python3
"""CLI for running BSL rename benchmarks."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _ast_grep_binary() -> str:
    if sys.platform == "win32":
        npm_bin = Path.home() / "AppData" / "Roaming" / "npm" / "ast-grep.cmd"
        if npm_bin.exists():
            return str(npm_bin)
    return shutil.which("ast-grep") or "ast-grep"


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "docs" / "roadmap"))

from benchmark.runner import BenchmarkRunner

from src.bsl.semantic_search.refactor.backends.ast_grep_runner import SubprocessAstGrepRunner


def _build_multilspy_backend(repo_root: Path):
    from src.bsl.semantic_search.refactor.backends.multilspy_backend import MultilspyBackend
    from src.bsl.semantic_search.refactor.backends.real_bsl_client import create_bsl_client

    # BSL LS expects workspace root to be the 1C Configuration dir
    # (Configuration.xml present). src/bsl/ holds our test configuration.
    bsl_root = repo_root / "src" / "bsl"
    bsl_files = list(bsl_root.rglob("*.bsl"))
    print(f"[multilspy] preloading {len(bsl_files)} .bsl files...")
    client = create_bsl_client(
        workspace_root=bsl_root,
        preload=bsl_files,
        populate_wait_secs=2.0,
        start_timeout=120.0,
    )
    print("[multilspy] preload complete, client ready")

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
    parser = argparse.ArgumentParser(description="Run BSL rename benchmark")
    parser.add_argument(
        "--backends",
        nargs="+",
        choices=["ast-grep", "multilspy"],
        default=["ast-grep"],
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--append-trend", action="store_true")
    args = parser.parse_args()

    run_id = args.run_id or f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    tasks_path = REPO_ROOT / "docs" / "roadmap" / "benchmark" / "tasks.json"
    output_dir = REPO_ROOT / "docs" / "roadmap" / "benchmark" / "results"

    if args.append_trend:
        _append_trend(
            args.run_id,
            backend_names,
            results,
            REPO_ROOT / "docs" / "roadmap" / "benchmark" / "trend.md",
        )


if __name__ == "__main__":
    main()
