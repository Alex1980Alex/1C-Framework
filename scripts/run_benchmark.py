#!/usr/bin/env python3
"""Run the BSL rename benchmark with configurable backends."""
from __future__ import annotations

import argparse
import os
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

from src.bsl.semantic_search.refactor.backends.ast_grep_backend import AstGrepBackend
from src.bsl.semantic_search.refactor.backends.ast_grep_runner import SubprocessAstGrepRunner

from benchmark.runner import BenchmarkRunner


def _build_multilspy_backend(repo_root: Path):
    from src.bsl.semantic_search.refactor.backends.real_bsl_client import create_bsl_client
    from src.bsl.semantic_search.refactor.backends.multilspy_backend import MultilspyBackend

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

    def _factory():
        return client

    return MultilspyBackend(client_factory=_factory), client


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

    backends: dict[str, object] = {}
    clients_to_stop: list[object] = []

    try:
        for name in args.backends:
            if name == "ast-grep":
                sgconfig = REPO_ROOT / "tools" / "bsl-ls" / "sgconfig.yml"
                if not sgconfig.exists():
                    print(f"ERROR: sgconfig.yml not found at {sgconfig}", file=sys.stderr)
                    sys.exit(1)
                runner_impl = SubprocessAstGrepRunner(
                    binary=_ast_grep_binary(),
                    config_path=sgconfig,
                )
                from src.bsl.semantic_search.refactor.backends.factory import (
                    build_ast_grep_backend,
                )
                from src.bsl.semantic_search.refactor.classifier import (
                    RoutingMatrix,
                )

                RoutingMatrix.load()
                backends["ast-grep"] = build_ast_grep_backend(
                    runner=runner_impl,
                    workspace_root=REPO_ROOT / "src" / "bsl",
                    project_root=REPO_ROOT,
                )
            elif name == "multilspy":
                backend, client = _build_multilspy_backend(REPO_ROOT)
                backends["multilspy"] = backend
                clients_to_stop.append(client)

        benchmark = BenchmarkRunner(REPO_ROOT, tasks_path, output_dir)
        results = benchmark.run(backends=backends, run_id=run_id)

        success = sum(1 for r in results if r.edits_match_expected)
        total = len(results)
        pct = success / total * 100 if total else 0
        print(f"\nResults: {success}/{total} match expected ({pct:.0f}%)")
        print(f"Report: {output_dir / f'{run_id}_report.md'}")
        print(f"CSV: {output_dir / f'{run_id}_report.csv'}")

        if args.append_trend:
            trend_path = REPO_ROOT / "docs" / "roadmap" / "benchmark" / "trend.md"
            today = datetime.now().strftime("%Y-%m-%d")
            backends_str = ",".join(args.backends)
            if len(args.backends) > 1:
                notes = "full-1 benchmark (multilspy + ast-grep)"
            elif args.backends == ["multilspy"]:
                notes = "multilspy only"
            else:
                notes = "ast-grep only"
            row = (
                f"| {run_id} | {today} | HEAD | {backends_str} "
                f"| {success}/{total} | {total} | {notes} |\n"
            )
            with open(trend_path, "a", encoding="utf-8") as f:
                f.write(row)

        sys.exit(0 if pct >= 90 else 1)
    finally:
        for c in clients_to_stop:
            c.stop()


if __name__ == "__main__":
    main()
