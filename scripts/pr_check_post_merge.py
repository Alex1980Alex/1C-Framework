#!/usr/bin/env python3
"""Post-merge CI check + auto-revert.

Roadmap: 40_PR_AUTOMATION/40.4 P3.4.

Iterates over merged PRs recorded in
`.claude/cache/post-task-push-pr-state.json`, queries GitHub for the
post-merge CI status of each PR's merge commit, and (if `--apply`) creates
a revert PR for failing merges. State-file gains `post_merge_status` to
avoid re-checking the same PR.

CLI:
  python scripts/pr_check_post_merge.py
                       [--lookback-hours N]    # default 72
                       [--apply]               # actually revert
                       [--base BRANCH]         # default master
                       [--state-file PATH]     # default repo .claude/cache/...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "hooks"))

from shared import pr_helpers as pr
from shared import pr_notifier as notify

DEFAULT_STATE = PROJECT_ROOT / ".claude" / "cache" / "post-task-push-pr-state.json"


def _gh_json(*args: str, cwd: Path, timeout: int = 30) -> tuple[bool, dict | list]:
    import subprocess

    try:
        r = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd),
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, {}
    if r.returncode != 0 or not r.stdout.strip():
        return False, {}
    try:
        return True, json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, {}


def pr_merge_info(pr_url: str, *, cwd: Path) -> dict | None:
    """Return {merged_at, merge_sha, base} for a merged PR, else None."""
    ok, data = _gh_json(
        "pr",
        "view",
        pr_url,
        "--json",
        "mergedAt,mergeCommit,baseRefName,state",
        cwd=cwd,
    )
    if not ok or not isinstance(data, dict):
        return None
    if data.get("state") != "MERGED" or not data.get("mergedAt"):
        return None
    mc = data.get("mergeCommit") or {}
    return {
        "merged_at": data["mergedAt"],
        "merge_sha": mc.get("oid", ""),
        "base": data.get("baseRefName", ""),
    }


def runs_for_sha(sha: str, *, cwd: Path) -> tuple[str, str]:
    """Return (status, summary) — status: success | failure | pending | none."""
    if not sha:
        return "none", "no merge sha"
    ok, data = _gh_json(
        "run",
        "list",
        "--commit",
        sha,
        "--json",
        "status,conclusion,workflowName,databaseId,url",
        "--limit",
        "20",
        cwd=cwd,
    )
    if not ok:
        return "none", "gh run list failed"
    runs = data if isinstance(data, list) else []
    if not runs:
        return "none", "no workflow runs"
    pending = [r for r in runs if (r.get("status") or "").lower() != "completed"]
    if pending:
        return "pending", f"{len(pending)} run(s) still running"
    failed = [
        r
        for r in runs
        if (r.get("conclusion") or "").lower()
        in {"failure", "cancelled", "timed_out", "action_required"}
    ]
    if failed:
        urls = ", ".join(r.get("url", "?") for r in failed[:3])
        return "failure", f"{len(failed)} failing run(s): {urls}"
    return "success", f"{len(runs)} run(s) green"


def revert_merge_commit(
    merge_sha: str, base: str, original_pr_url: str, *, cwd: Path
) -> tuple[bool, str, str]:
    """Create revert PR for `merge_sha` against `base`. Returns (ok, pr_url, msg).

    Uses git worktree to keep caller's working tree clean.
    """
    ok, _ = pr.fetch_remote("origin", base, cwd=cwd, timeout=60)
    if not ok:
        return False, "", "fetch failed"

    revert_branch = f"auto-revert/{merge_sha[:12]}"
    worktree_dir = Path(tempfile.mkdtemp(prefix="auto-revert-"))

    def _cleanup(rm_branch: bool) -> None:
        pr.run_git("worktree", "remove", "-f", str(worktree_dir), cwd=cwd, timeout=30)
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
        if rm_branch:
            pr.run_git("branch", "-D", revert_branch, cwd=cwd, timeout=15)

    code, _, err = pr.run_git(
        "worktree",
        "add",
        "-f",
        "-B",
        revert_branch,
        str(worktree_dir),
        f"origin/{base}",
        cwd=cwd,
        timeout=60,
    )
    if code != 0:
        _cleanup(rm_branch=False)
        return False, "", f"worktree add: {err[:200]}"

    # `-m 1` reverts to first-parent (the base side). Required for merge commits;
    # harmless flag on squash commits (git falls back to plain revert).
    code, _, err = pr.run_git(
        "revert",
        "--no-edit",
        "-m",
        "1",
        merge_sha,
        cwd=worktree_dir,
        timeout=60,
    )
    if code != 0:
        # try without -m for squash commits
        pr.run_git("revert", "--abort", cwd=worktree_dir, timeout=15)
        code2, _, err2 = pr.run_git("revert", "--no-edit", merge_sha, cwd=worktree_dir, timeout=60)
        if code2 != 0:
            pr.run_git("revert", "--abort", cwd=worktree_dir, timeout=15)
            _cleanup(rm_branch=True)
            return False, "", f"revert conflict: {(err2 or err)[:200]}"

    code, _, err = pr.run_git("push", "-u", "origin", revert_branch, cwd=worktree_dir, timeout=60)
    if code != 0:
        _cleanup(rm_branch=True)
        return False, "", f"push: {err[:200]}"

    title = f"Revert: {merge_sha[:12]} (post-merge CI fail)"[:80]
    body = (
        f"Auto-generated revert of merge `{merge_sha}` after post-merge CI "
        f"failure.\n\n"
        f"- Original PR: {original_pr_url}\n"
        f"- Detected by: `scripts/pr_check_post_merge.py`\n\n"
        f"Manual review required before merging this revert."
    )
    ok_c, new_url = pr.gh_pr_create(revert_branch, base, title, body, cwd=cwd)
    _cleanup(rm_branch=False)
    if not ok_c:
        return False, "", f"pr create: {new_url[:200]}"
    return True, new_url, "revert PR created"


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _within_lookback(merged_at_str: str, hours: int) -> bool:
    try:
        dt = datetime.fromisoformat(merged_at_str.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(UTC) - dt) <= timedelta(hours=hours)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="Post-merge CI check + auto-revert")
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument(
        "--apply", action="store_true", help="actually create revert PRs (default: report only)"
    )
    parser.add_argument("--base", default=os.environ.get("AUTO_PR_BASE", "master"))
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()

    if not pr.gh_available():
        print("[post-merge-check] gh CLI not available — exiting")
        return 0

    state = load_state(args.state_file)
    processed = state.get("processed", {}) or {}
    if not processed:
        print(f"[post-merge-check] no PRs in {args.state_file}")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"[post-merge-check] {mode} · lookback={args.lookback_hours}h "
        f"· base={args.base} · "
        f"{datetime.now().isoformat(timespec='seconds')}"
    )
    print()

    summary = {"checked": 0, "failures": 0, "reverted": 0, "skipped": 0}
    for tid, entry in processed.items():
        pr_url = entry.get("pr_url")
        if not pr_url or entry.get("post_merge_status") in {"success", "reverted"}:
            summary["skipped"] += 1
            continue
        info = pr_merge_info(pr_url, cwd=PROJECT_ROOT)
        if not info:
            summary["skipped"] += 1
            continue
        if not _within_lookback(info["merged_at"], args.lookback_hours):
            summary["skipped"] += 1
            continue
        summary["checked"] += 1

        status, detail = runs_for_sha(info["merge_sha"], cwd=PROJECT_ROOT)
        line = f"  Task #{tid} · {pr_url} · sha={info['merge_sha'][:12]} · {status}"
        if status == "pending":
            print(f"{line} ({detail}) — will recheck later")
            continue
        if status == "success":
            entry["post_merge_status"] = "success"
            entry["post_merge_checked_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            print(f"{line} ({detail})")
            continue
        if status == "none":
            entry["post_merge_status"] = "no_runs"
            print(f"{line} ({detail})")
            continue
        # failure
        summary["failures"] += 1
        print(f"{line} ({detail})")
        if not args.apply:
            print("    -> would create revert PR (use --apply)")
            continue
        ok, new_url, msg = revert_merge_commit(
            info["merge_sha"], info["base"] or args.base, pr_url, cwd=PROJECT_ROOT
        )
        if ok:
            entry["post_merge_status"] = "reverted"
            entry["post_merge_revert_pr"] = new_url
            entry["post_merge_checked_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            summary["reverted"] += 1
            notify.notify_pr_failed(tid, "post_merge_revert", detail, new_url)
            print(f"    -> revert PR: {new_url}")
        else:
            print(f"    -> revert FAILED: {msg}")

    save_state(args.state_file, state)
    print()
    print(
        f"[post-merge-check] summary: checked={summary['checked']} "
        f"failures={summary['failures']} reverted={summary['reverted']} "
        f"skipped={summary['skipped']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
