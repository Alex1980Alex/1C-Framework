#!/usr/bin/env python3
"""Generate benchmark tasks JSON for BSL rename refactoring."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BSL_SRC = REPO_ROOT / "src" / "bsl"
OUTPUT_DIR = REPO_ROOT / "docs" / "roadmap" / "benchmark"

_RE_OLD = r"^-\s*(?:Процедура|Функция|Procedure|Function|Перем|Var)\s+(\w+)\s*\("
_RE_NEW = r"^\+\s*(?:Процедура|Функция|Procedure|Function|Перем|Var)\s+(\w+)\s*\("


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_ENV,  # noqa: F821  # WIP script — see roadmap 260523 §16 (build_benchmark_tasks incomplete)
        encoding="utf-8",
    )
    return result.stdout  # noqa: F821  # WIP — see header


def _extract_renames(diff: str) -> list[dict]:
    results: list[dict] = []
    lines = diff.splitlines()
    i = 0
    while i < len(lines):
        old_m = _RE_OLD.match(lines[i])
        if old_m and i + 1 < len(lines):
            new_m = _RE_NEW.match(lines[i + 1])
            if new_m:
                keyword = lines[i].lstrip("- \t").split()[0]
                cat = CATEGORY_MAP.get(keyword, "CAT-5-edge-case")  # noqa: F821
                results.append(
                    {
                        "old_name": old_m.group(1),
                        "new_name": new_m.group(1),
                        "keyword": keyword,
                        "category": cat,
                    }
                )
                i += 2
                continue
        i += 1
    return results


def find_rename_commits(repo_root: Path, limit: int = 100) -> list[dict]:
    out = _git(
        "log",
        "--diff-filter=M",
        "--format=%H %P",
        "-n",
        str(limit),
        "--",
        "*.bsl",
        cwd=repo_root,
    )
    commits: list[dict] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        sha, parent = parts[0], parts[1]
        diff = _git("diff", "-U0", parent, sha, "--", "*.bsl", cwd=repo_root)
        renames = _extract_renames(diff)
        if renames:
            file_uri = ""
            for dl in diff.splitlines():
                if dl.startswith("+++ b/"):
                    file_uri = dl[6:]
                    break
            commits.append(
                {
                    "sha": sha,
                    "parent": parent,
                    "renames": renames,
                    "file_uri": file_uri,
                }
            )
    return commits


def build_tasks(repo_root: Path, output: Path, limit: int) -> None:
    commits = find_rename_commits(repo_root, limit)
    tasks: list[dict] = []
    n = 0
    for commit in commits:
        for rn in commit["renames"]:
            n += 1
            tasks.append(
                {
                    "id": f"T{n:02d}",
                    "category": rn["category"],
                    "commit_sha": commit["sha"],
                    "parent_sha": commit["parent"],
                    "old_name": rn["old_name"],
                    "new_name": rn["new_name"],
                    "file_uri": commit.get("file_uri", ""),
                    "line": 0,
                    "character": 0,
                    "expected_files_affected": 1,
                    "expected_edits": 1,
                    "expected_files": [],
                    "notes": f"Auto-detected: {rn['old_name']} -> {rn['new_name']} ({rn['keyword']})",
                }
            )
    payload = {
        "version": 1,
        "created_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),  # noqa: UP017,F821
        "source_repo": str(repo_root),
        "tasks": tasks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(tasks)} candidate tasks to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build benchmark tasks for BSL rename refactoring")
    parser.add_argument("--auto", action="store_true", help="Scan git history for rename commits")
    parser.add_argument("--write", action="store_true", help="Write output to file")
    parser.add_argument("--limit", type=int, default=40, help="Max commits (auto mode)")
    args = parser.parse_args()

    if args.auto:
        tasks = _build_auto_tasks(args.limit)  # noqa: F821
        output_name = "tasks-auto.json"
    else:
        tasks = _build_curated_tasks()  # noqa: F821
        output_name = "tasks.json"

    data = {
        "version": 2,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "source_repo": str(REPO_ROOT),
        "tasks": tasks,
    }

    output_str = json.dumps(data, indent=2, ensure_ascii=False)

    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / output_name
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Wrote {len(tasks)} tasks to {out_path}", file=sys.stderr)
    else:
        print(output_str)


if __name__ == "__main__":
    main()
