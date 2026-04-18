#!/usr/bin/env python3
"""Run the BSL rename benchmark with ast-grep backend."""
from __future__ import annotations

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

from src.bsl.semantic_search.refactor.backends.ast_grep_backend import AstGrepBackend
from src.bsl.semantic_search.refactor.backends.ast_grep_runner import SubprocessAstGrepRunner


def main() -> None:
    tasks_path = REPO_ROOT / "docs" / "roadmap" / "benchmark" / "tasks.json"
    output_dir = REPO_ROOT / "docs" / "roadmap" / "benchmark" / "results"
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    runner_impl = SubprocessAstGrepRunner(binary=_ast_grep_binary())
    ast_grep_backend = AstGrepBackend(runner=runner_impl, workspace_root=REPO_ROOT / "src" / "bsl")

    benchmark = BenchmarkRunner(REPO_ROOT, tasks_path, output_dir)
    results = benchmark.run(
        backends={"ast-grep": ast_grep_backend},
        run_id=run_id,
    )

    applied = sum(1 for r in results if r.applied)
    total = len(results)
    print(f"\nResults: {applied}/{total} applied ({applied/total*100:.0f}%)")
    print(f"Report: {output_dir / f'{run_id}_report.md'}")
    print(f"CSV: {output_dir / f'{run_id}_report.csv'}")


if __name__ == "__main__":
    main()
