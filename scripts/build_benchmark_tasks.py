#!/usr/bin/env python3
"""Scan git history for rename-like commits and propose benchmark tasks.

Usage:
    python scripts/build_benchmark_tasks.py [--output tasks.json] [--limit 40]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "PYTHONIOENCODING": "utf-8"}

_KW = r"(?:Процедура|Функция|Procedure|Function|Перем|Var)"
_RE_OLD = re.compile(rf"^-\s*{_KW}\s+(\w+)\s*\(")
_RE_NEW = re.compile(rf"^\+\s*{_KW}\s+(\w+)\s*\(")

CATEGORY_MAP = {"Перем": "CAT-1-local-variable", "Var": "CAT-1-local-variable"}


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=_ENV,
        encoding="utf-8",
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.strip()}")
    return r.stdout


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
                cat = CATEGORY_MAP.get(keyword, "CAT-5-edge-case")
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
        "created_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),  # noqa: UP017
        "source_repo": str(repo_root),
        "tasks": tasks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(tasks)} candidate tasks to {output}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build benchmark tasks from git rename history")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--output", type=Path, default=Path("docs/roadmap/benchmark/tasks-auto.json"))
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()
    build_tasks(args.repo.resolve(), args.output.resolve(), args.limit)


if __name__ == "__main__":
    main()
