#!/usr/bin/env python3
"""Orphan task/* branch cleanup — local + remote.

Roadmap: 40_PR_AUTOMATION/40.4 P2.4.

Dry-run by default. Pass --apply to actually delete.

Local: deletes `task/*` branches whose tip is reachable from base (or
origin/base) AND last commit is older than --stale-days (default 30).

Remote: deletes origin `task/*` branches whose PR is MERGED or CLOSED.
Skips if PR is OPEN or absent (possibly WIP).

CLI:
  python scripts/cleanup_orphan_branches.py [--apply] [--stale-days N]
                                            [--base BR] [--no-remote]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "hooks"))

from shared import pr_helpers as pr


def _list_refs(prefix: str) -> list[str]:
    code, out, _ = pr.run_git("for-each-ref", "--format=%(refname:short)", prefix, cwd=PROJECT_ROOT)
    if code != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def list_local_task_branches() -> list[str]:
    return _list_refs("refs/heads/task/")


def list_remote_task_branches() -> list[str]:
    return [b.removeprefix("origin/") for b in _list_refs("refs/remotes/origin/task/")]


def branch_age_days(branch: str) -> int:
    code, out, _ = pr.run_git("log", "-1", "--format=%ct", branch, cwd=PROJECT_ROOT)
    if code != 0 or not out.strip():
        return 0
    try:
        ts = datetime.fromtimestamp(int(out.strip()))
    except (ValueError, OSError):
        return 0
    return (datetime.now() - ts).days


def cleanup_local(*, base: str, stale_days: int, apply: bool) -> list[str]:
    actions: list[str] = []
    ref = base if pr.branch_exists_local(base, cwd=PROJECT_ROOT) else f"origin/{base}"
    for br in list_local_task_branches():
        if not pr.is_ancestor(br, ref, cwd=PROJECT_ROOT):
            continue  # not merged → skip silently
        age = branch_age_days(br)
        if age < stale_days:
            actions.append(f"keep local {br} (merged but only {age}d old)")
            continue
        verb = "DELETE" if apply else "WOULD DELETE"
        actions.append(f"{verb} local {br} (merged, {age}d)")
        if apply:
            pr.run_git("branch", "-D", br, cwd=PROJECT_ROOT)
    return actions


def cleanup_remote(*, apply: bool) -> list[str]:
    if not pr.gh_available():
        return ["skip remote — gh CLI not available"]
    actions: list[str] = []
    for br in list_remote_task_branches():
        prs = pr.gh_pr_list_for_branch(br, cwd=PROJECT_ROOT)
        if not prs:
            actions.append(f"keep remote {br} (no PR, possibly WIP)")
            continue
        states = {(p.get("state") or "").upper() for p in prs}
        if "OPEN" in states:
            actions.append(f"keep remote {br} (open PR)")
            continue
        if states & {"MERGED", "CLOSED"}:
            verb = "DELETE" if apply else "WOULD DELETE"
            actions.append(f"{verb} remote {br} (PR state={sorted(states)})")
            if apply:
                pr.gh_pr_delete_branch(br, cwd=PROJECT_ROOT)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--base", default=os.environ.get("AUTO_PR_BASE", "master"))
    parser.add_argument("--no-remote", action="store_true")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    ts = datetime.now().isoformat(timespec="seconds")
    print(f"[orphan-cleanup] {mode} · base={args.base} · stale-days={args.stale_days} · {ts}")
    print()

    print("Local branches:")
    local_actions = cleanup_local(base=args.base, stale_days=args.stale_days, apply=args.apply)
    for line in local_actions or ["(none)"]:
        print(f"  - {line}")
    print()

    if not args.no_remote:
        print("Remote branches:")
        for line in cleanup_remote(apply=args.apply) or ["(none)"]:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
