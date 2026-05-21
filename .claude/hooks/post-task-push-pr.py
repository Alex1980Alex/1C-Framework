#!/usr/bin/env python3
"""
Hook: post-task-push-pr
Event: PostToolUse
Matcher: TaskUpdate
Purpose: When a task transitions to status="completed", create a per-task
         branch from current HEAD, push it, create a GitHub PR, and
         optionally auto-merge. Closes the task → branch → PR → merge loop.

Trigger flow:
  1. TaskUpdate(status=completed) emitted by Claude or user
  2. Hook reads tool_input.taskId + status, verifies "completed"
  3. Check AUTO_PR_ENABLED env (default "0" — opt-in to avoid noise)
  4. Compute commit range against base branch (default: master)
  5. If commits >= AUTO_PR_MIN_COMMITS:
     a. Run quick sanity tests (pytest -x --timeout=30, skip via NO_TESTS)
     b. Create task/<taskId>-<slug> branch ref at current HEAD
     c. Push branch to origin
     d. gh pr create --base $AUTO_PR_BASE --head task/...
     e. Optional: gh pr merge --squash (if AUTO_PR_AUTO_MERGE=1)
     f. Emit systemMessage with PR URL

Configuration (env vars):
  AUTO_PR_ENABLED        — "1" to enable, anything else disables (default off)
  AUTO_PR_BASE           — base branch (default "master")
  AUTO_PR_MIN_COMMITS    — minimum commits since base to trigger (default 3)
  AUTO_PR_AUTO_MERGE     — "1" to gh pr merge --squash after create (default 0)
  AUTO_PR_NO_TESTS       — "1" to skip pre-push tests (default off, tests run)
  AUTO_PR_TEST_CMD       — override test command (default: pytest -x ...)

Timeout: 90s (includes test run + push + PR create + merge)
Exit codes: always 0 (informational, never blocks task completion)
Pattern: Enforcer (informational variant — system_message only)

Safety:
  - Idempotent: if branch already exists with same commits, skips push/PR
  - Never force-pushes, never resets working tree
  - Stays on current branch (creates task branch as ref, no checkout)
  - Bounded: skips silently if gh CLI / git remote unavailable
"""

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "post-task-push-pr-state.json"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _is_enabled() -> bool:
    return _env("AUTO_PR_ENABLED", "0") == "1"


def _run_git(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "-", text.lower(), flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60] or "task"


def _commits_ahead(base: str) -> int:
    code, out, _ = _run_git("rev-list", "--count", f"{base}..HEAD")
    try:
        return int(out) if code == 0 else 0
    except ValueError:
        return 0


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _run_pre_push_tests() -> tuple[bool, str]:
    """Returns (ok, message). Skipped if AUTO_PR_NO_TESTS=1.

    Security: tokenizes via shlex + uses shell=False to avoid command
    injection. AUTO_PR_TEST_CMD is operator-controlled, but defence-in-depth
    insists on shell-less execution.
    """
    if _env("AUTO_PR_NO_TESTS") == "1":
        return True, "tests skipped (AUTO_PR_NO_TESTS=1)"
    cmd_str = _env("AUTO_PR_TEST_CMD") or (
        ".venv/Scripts/python.exe -m pytest tests/integration/test_analyze_run.py "
        "-q --timeout=30 -x"
    )
    try:
        cmd_argv = shlex.split(cmd_str, posix=False)
    except ValueError as exc:
        return False, f"AUTO_PR_TEST_CMD parse error: {exc}"
    if not cmd_argv:
        return False, "AUTO_PR_TEST_CMD is empty after tokenization"
    try:
        r = subprocess.run(
            cmd_argv,
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            return True, "tests passed"
        tail = (r.stdout + r.stderr)[-400:].replace("\n", " | ")
        return False, f"tests failed (exit={r.returncode}): {tail}"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"test run error: {type(exc).__name__}: {exc}"


def _safe_int(value: str, default: int) -> int:
    """Parse int with fallback — prevents hook crash on malformed env."""
    try:
        return int((value or "").strip() or default)
    except (ValueError, TypeError):
        return default


def _gh_available() -> bool:
    try:
        r = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return r.returncode == 0
    except (FileNotFoundError, OSError):
        return False


def _create_pr(branch: str, base: str, title: str, body: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                base,
                "--head",
                branch,
                "--title",
                title,
                "--body",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            url = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
            return True, url
        return False, (r.stderr or r.stdout).strip()[:300]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _merge_pr(pr_url: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["gh", "pr", "merge", pr_url, "--squash", "--delete-branch"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            return True, "merged + branch deleted"
        return False, (r.stderr or r.stdout).strip()[:300]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


class PostTaskPushPR(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "PostToolUse":
            return None
        if inp.tool_name != "TaskUpdate":
            return None
        if not _is_enabled():
            return None

        ti = inp.tool_input or {}
        if ti.get("status") != "completed":
            return None

        task_id = str(ti.get("taskId") or "unknown")
        # Subject best-effort: TaskUpdate's tool_response is usually a status
        # string like "Updated task #N status", not the task subject. We use
        # taskId in the branch slug if subject can't be recovered.
        subject = ""
        result = inp.tool_result
        if isinstance(result, dict):
            subject = str(result.get("subject", ""))

        base = _env("AUTO_PR_BASE", "master")
        min_commits = _safe_int(_env("AUTO_PR_MIN_COMMITS"), 3)

        # Verify base branch exists locally
        code, _, _ = _run_git("rev-parse", "--verify", base)
        if code != 0:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Skipped: base branch '{base}' not found. "
                f"Set AUTO_PR_BASE to existing branch (e.g. dev-master)."
            )

        ahead = _commits_ahead(base)
        if ahead < min_commits:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id} completed but "
                f"{ahead} commit(s) ahead of {base} < threshold "
                f"AUTO_PR_MIN_COMMITS={min_commits}. Skipping push/PR."
            )

        state = _load_state()
        head_sha = _run_git("rev-parse", "HEAD")[1][:12]
        already = state.get("processed", {}).get(task_id, {}).get("head_sha")
        if already == head_sha:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id} already processed at "
                f"HEAD={head_sha}. Skipping (idempotent)."
            )

        if not _gh_available():
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                "[POST-TASK-PUSH-PR] Skipped: `gh` CLI not in PATH. "
                "Install GitHub CLI or unset AUTO_PR_ENABLED."
            )

        tests_ok, tests_msg = _run_pre_push_tests()
        if not tests_ok:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id}: skipping push, "
                f"pre-push tests FAILED. {tests_msg}"
            )

        slug = _slugify(subject or f"task-{task_id}")
        branch = f"task/{task_id}-{slug}"

        # Create or update branch ref at current HEAD without checkout
        code, _, err = _run_git("branch", "-f", branch, "HEAD")
        if code != 0:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id}: branch creation failed: {err[:200]}"
            )

        code, _, err = _run_git("push", "-u", "origin", branch, timeout=60)
        if code != 0:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id}: push failed: {err[:200]}"
            )

        title = f"[Task #{task_id}] {subject or 'auto'}"[:80]
        body = (
            f"Auto-created from `TaskUpdate(status=completed)` for task **#{task_id}**.\n\n"
            f"- **subject:** {subject or '(none)'}\n"
            f"- **branch:** `{branch}`\n"
            f"- **base:** `{base}`\n"
            f"- **commits ahead:** {ahead}\n"
            f"- **HEAD:** `{head_sha}`\n"
            f"- **pre-push tests:** {tests_msg}\n\n"
            f"Hook: `.claude/hooks/post-task-push-pr.py`. "
            f"Disable via `AUTO_PR_ENABLED=0`."
        )
        ok, pr_url = _create_pr(branch, base, title, body)
        if not ok:
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-TASK-PUSH-PR] Task #{task_id}: PR create failed: {pr_url}. "
                f"Branch `{branch}` pushed; create PR manually."
            )

        merge_note = ""
        if _env("AUTO_PR_AUTO_MERGE") == "1":
            merge_ok, merge_msg = _merge_pr(pr_url)
            merge_note = f"\n- **auto-merge:** {'OK' if merge_ok else 'FAIL'} — {merge_msg}"

        # Record state
        state.setdefault("processed", {})[task_id] = {
            "head_sha": head_sha,
            "branch": branch,
            "pr_url": pr_url,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        _save_state(state)

        return HookOutput().system_message(  # type: ignore[no-untyped-call]
            f"[POST-TASK-PUSH-PR] Task #{task_id} OK\n"
            f"- branch: `{branch}` ({ahead} commits)\n"
            f"- PR: {pr_url}{merge_note}"
        )


if __name__ == "__main__":
    PostTaskPushPR().run()  # type: ignore[no-untyped-call]
