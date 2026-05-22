#!/usr/bin/env python3
"""Hook: post-task-push-pr  (P0+P1+P2 batch, roadmap 40_PR_AUTOMATION/40.4)

Event:    PostToolUse
Matcher:  TaskUpdate
Purpose:  Automate the task → branch → push → PR → review → merge loop.

Features (env-gated, all opt-in; `AUTO_PR_ENABLED=1` is master switch):

  Activation
    AUTO_PR_ENABLED                "1" to activate hook (default off)
    AUTO_PR_REQUIRE_LABEL          gate: only fire if task has this label
                                   (in metadata.labels or `[label]` in subject)
    AUTO_PR_BASE                   base branch (default "master")
    AUTO_PR_MIN_COMMITS            min commits since base/start_sha (default 3)

  Pre-push
    AUTO_PR_NO_TESTS               "1" to skip pre-push test
    AUTO_PR_TEST_CMD               override test command
                                   (default: `pre-commit run --all-files`)
    AUTO_PR_AUTO_REBASE            "1" to rebase HEAD onto remote/base if stale

  PR
    AUTO_PR_REVIEWERS              comma-separated reviewer logins (fallback if
                                   CODEOWNERS finds none)
    AUTO_PR_AUTO_MERGE             "1" to `gh pr merge --squash` after create
    AUTO_PR_WAIT_FOR_CHECKS        "1" to poll `gh pr checks` before merge
    AUTO_PR_CHECKS_TIMEOUT         seconds to wait for checks (default 300)

  Notifications  (SMTP, see shared/pr_notifier.py)
    AUTO_PR_SMTP_HOST, AUTO_PR_NOTIFY_TO  required for email alerts

  Branch model (P3.2)
    AUTO_PR_CHERRY_PICK            "1" — create branch from origin/base and
                                   cherry-pick start_sha..HEAD onto it.
                                   Gives a clean per-task diff; falls back
                                   to the default branch-at-HEAD model on
                                   cherry-pick conflict.

  Safety
    AUTO_PR_DRY_RUN                "1" — all checks run, but no push / PR / merge

Status:
  - in_progress events record `start_sha` for per-task scope tracking (P2.1).
  - completed events create branch+PR if scope ≥ min_commits.
  - Existing PR detection (P0.3): reuses open PR via comment.
  - Cross-PR deps (P2.5): blockedBy tasks → labels `blocked-by:#N`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

from shared import pr_helpers as pr  # noqa: E402
from shared import pr_notifier as notify  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "post-task-push-pr-state.json"
DEFAULT_TEST_CMD = "pre-commit run --all-files"


# --- state I/O ---------------------------------------------------------


def _load_state() -> dict:
    import json

    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    import json

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


# --- pre-push tests ----------------------------------------------------


def _run_pre_push_tests() -> tuple[bool, str]:
    """Run AUTO_PR_TEST_CMD (defaults to pre-commit run --all-files).

    P0.4 — default switched from pytest to pre-commit (full quality gate).
    Returns (ok, message). Skipped via AUTO_PR_NO_TESTS=1.
    """
    if pr.env_flag("AUTO_PR_NO_TESTS"):
        return True, "tests skipped (AUTO_PR_NO_TESTS=1)"
    cmd_str = pr.env_str("AUTO_PR_TEST_CMD") or DEFAULT_TEST_CMD
    try:
        cmd_argv = shlex.split(cmd_str, posix=False)
    except ValueError as exc:
        return False, f"AUTO_PR_TEST_CMD parse error: {exc}"
    if not cmd_argv:
        return False, "AUTO_PR_TEST_CMD empty after tokenization"
    try:
        r = subprocess.run(
            cmd_argv,
            capture_output=True,
            text=True,
            timeout=120,
            shell=False,
            check=False,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            return True, f"tests passed (`{cmd_argv[0]}`)"
        tail = (r.stdout + r.stderr)[-500:].replace("\n", " | ")
        return False, f"tests failed (exit={r.returncode}): {tail}"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"test run error: {type(exc).__name__}: {exc}"


# --- PR body composition -----------------------------------------------


def _compose_pr_body(
    *,
    task_id: str,
    subject: str,
    branch: str,
    base: str,
    ahead: int,
    head_sha: str,
    start_sha: str | None,
    tests_msg: str,
    blocked_by_prs: list[str],
    extra: dict | None = None,
) -> str:
    extra = extra or {}
    scope_line = f"`{start_sha}..{head_sha}`" if start_sha else f"`{base}..{head_sha}`"
    blockers_line = ", ".join(blocked_by_prs) if blocked_by_prs else "_none_"

    return (
        f"## Summary\n"
        f"Auto-created from `TaskUpdate(status=completed)` for task **#{task_id}**.\n"
        f"\n"
        f"- **Subject:** {subject or '_(none)_'}\n"
        f"- **Branch:** `{branch}`\n"
        f"- **Base:** `{base}`\n"
        f"- **Scope:** {scope_line} ({ahead} commit{'s' if ahead != 1 else ''})\n"
        f"- **Pre-push gate:** {tests_msg}\n"
        f"- **Blocked-by:** {blockers_line}\n"
        f"\n"
        f"## Test plan\n"
        f"- [ ] Pre-push gate green (`pre-commit run --all-files`)\n"
        f"- [ ] CI checks green\n"
        f"- [ ] Manual smoke if change touches user-facing flow\n"
        f"\n"
        f"## Notes\n"
        f"Hook: `.claude/hooks/post-task-push-pr.py`. "
        f"Roadmap: `40_PR_AUTOMATION/40.4`. Disable via `AUTO_PR_ENABLED=0`.\n"
        + (
            ""
            if not extra
            else "\n<details><summary>Internal</summary>\n\n```\n"
            + "\n".join(f"{k}: {v}" for k, v in extra.items())
            + "\n```\n</details>\n"
        )
    )


# --- main hook ---------------------------------------------------------


class PostTaskPushPR(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "PostToolUse":
            return None
        if inp.tool_name != "TaskUpdate":
            return None
        if not pr.env_flag("AUTO_PR_ENABLED"):
            return None

        ti = inp.tool_input or {}
        status = ti.get("status")
        task_id = str(ti.get("taskId") or "unknown")

        # ---- P2.1: in_progress → record start_sha and exit silently ----
        if status == "in_progress":
            state = _load_state()
            entry = state.setdefault("processed", {}).setdefault(task_id, {})
            if not entry.get("start_sha"):
                start = pr.head_sha(cwd=PROJECT_ROOT)
                if start:
                    entry["start_sha"] = start
                    entry["in_progress_ts"] = datetime.now().isoformat(timespec="seconds")
                    entry["blockedBy"] = list(
                        ti.get("addBlockedBy") or (ti.get("metadata") or {}).get("blockedBy") or []
                    )
                    _save_state(state)
            return None

        if status != "completed":
            return None

        # ---- P0.1: label gating ----
        required = pr.env_str("AUTO_PR_REQUIRE_LABEL")
        if required:
            ok, why = pr.task_meets_label_requirement(
                ti,
                inp.tool_result if isinstance(inp.tool_result, dict) else None,
                required,
            )
            if not ok:
                return HookOutput().system_message(
                    f"[POST-TASK-PUSH-PR] Task #{task_id}: skipped — {why}. "
                    f"Set label `{required}` to enable auto-PR for this task."
                )

        base = pr.env_str("AUTO_PR_BASE", "master")
        min_commits = pr.safe_int(pr.env_str("AUTO_PR_MIN_COMMITS"), 3)
        dry_run = pr.env_flag("AUTO_PR_DRY_RUN")

        if not pr.branch_exists_local(base, cwd=PROJECT_ROOT):
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR] Skipped: base branch `{base}` not found. "
                f"Set `AUTO_PR_BASE` to an existing local branch."
            )

        # ---- subject extraction (best effort) ----
        subject = ""
        result = inp.tool_result
        if isinstance(result, dict):
            subject = str(result.get("subject", ""))
        if not subject:
            subject = str(ti.get("subject", ""))

        state = _load_state()
        processed = state.setdefault("processed", {})
        entry = processed.get(task_id) or {}
        start_sha = entry.get("start_sha")

        # ---- P2.1: scope range ----
        head_short = pr.head_sha(cwd=PROJECT_ROOT)
        head_full = pr.head_sha(cwd=PROJECT_ROOT, short=False)
        if start_sha:
            ahead = pr.commits_ahead(start_sha, cwd=PROJECT_ROOT)
            scope_base = start_sha
            scope_note = f"per-task scope `{start_sha[:12]}..HEAD`"
        else:
            ahead = pr.commits_ahead(base, cwd=PROJECT_ROOT)
            scope_base = base
            scope_note = f"full range `{base}..HEAD`"

        if ahead < min_commits:
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR] Task #{task_id} completed but "
                f"{ahead} commit(s) in {scope_note} < threshold "
                f"AUTO_PR_MIN_COMMITS={min_commits}. Skipping push/PR."
            )

        # ---- idempotency ----
        if entry.get("head_sha") == head_short and entry.get("pr_url"):
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR] Task #{task_id} already processed at "
                f"HEAD={head_short} → {entry['pr_url']}. Skipping (idempotent)."
            )

        if not pr.gh_available():
            return HookOutput().system_message(
                "[POST-TASK-PUSH-PR] Skipped: `gh` CLI not in PATH. "
                "Install GitHub CLI or unset `AUTO_PR_ENABLED`."
            )

        # ---- P1.3: stale-base detection / opt-in rebase ----
        behind, _, drift_msg = pr.base_drift_status(base, cwd=PROJECT_ROOT)
        rebase_note = ""
        if behind > 0:
            if pr.env_flag("AUTO_PR_AUTO_REBASE") and not dry_run:
                ok, rmsg = pr.auto_rebase_safe(base, cwd=PROJECT_ROOT)
                rebase_note = f"auto-rebased onto origin/{base}: {rmsg}"
                if not ok:
                    return HookOutput().system_message(
                        f"[POST-TASK-PUSH-PR] Task #{task_id}: "
                        f"rebase onto origin/{base} failed ({rmsg}). "
                        f"Skipping PR creation."
                    )
                head_short = pr.head_sha(cwd=PROJECT_ROOT)
                head_full = pr.head_sha(cwd=PROJECT_ROOT, short=False)
            else:
                rebase_note = (
                    f"WARNING: HEAD is {behind} commit(s) behind origin/{base}. "
                    f"Set `AUTO_PR_AUTO_REBASE=1` for auto-rebase."
                )

        # ---- pre-push tests ----
        tests_ok, tests_msg = _run_pre_push_tests()
        if not tests_ok:
            notify.notify_checks_failed(task_id, "", tests_msg)
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR] Task #{task_id}: pre-push gate FAILED. " f"{tests_msg}"
            )

        slug = pr.slugify(subject or f"task-{task_id}")
        branch = f"task/{task_id}-{slug}"

        # ---- DRY-RUN exit ----
        if dry_run:
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR][DRY-RUN] Task #{task_id} OK\n"
                f"- Planned branch: `{branch}`\n"
                f"- Scope: {scope_note} ({ahead} commits)\n"
                f"- Pre-push gate: {tests_msg}\n"
                f"- Drift: {rebase_note or 'in sync'}\n"
                f"- Would push + create PR + "
                f"{'merge' if pr.env_flag('AUTO_PR_AUTO_MERGE') else 'leave open'}\n"
                f"Disable dry-run: `AUTO_PR_DRY_RUN=0`."
            )

        # ---- P3.2: cherry-pick model OR default branch-at-HEAD ----
        branch_mode = "head-ref"
        cherry_note = ""
        if pr.env_flag("AUTO_PR_CHERRY_PICK") and start_sha:
            ok_cp, cp_msg = pr.cherry_pick_range_to_branch(
                start_sha, head_full, branch, base, cwd=PROJECT_ROOT
            )
            if ok_cp:
                branch_mode = "cherry-pick"
                cherry_note = f"cherry-pick: {cp_msg}"
            else:
                cherry_note = (
                    f"cherry-pick failed → fallback to branch-at-HEAD ({cp_msg})"
                )
        if branch_mode == "head-ref":
            code, _, err = pr.run_git("branch", "-f", branch, "HEAD", cwd=PROJECT_ROOT)
            if code != 0:
                return HookOutput().system_message(
                    f"[POST-TASK-PUSH-PR] Task #{task_id}: branch ref failed: {err[:200]}"
                )

        # ---- P0.2: push with conflict-aware retry ----
        push_ok, push_mode, push_msg = pr.push_branch_safe(branch, cwd=PROJECT_ROOT, timeout=90)
        if not push_ok:
            notify.notify_pr_failed(task_id, "push", push_msg)
            return HookOutput().system_message(
                f"[POST-TASK-PUSH-PR] Task #{task_id}: push failed " f"({push_mode}): {push_msg}"
            )

        # ---- P0.3: detect existing PR ----
        existing = pr.gh_pr_list_for_branch(branch, cwd=PROJECT_ROOT)
        open_pr = next((p for p in existing if (p.get("state") or "").upper() == "OPEN"), None)

        # ---- P2.5: resolve blocked-by PR numbers ----
        blocked_task_ids = entry.get("blockedBy", []) or list(
            ti.get("addBlockedBy") or (ti.get("metadata") or {}).get("blockedBy") or []
        )
        blocked_pr_refs: list[str] = []
        blocked_labels: list[str] = []
        for bid in blocked_task_ids:
            bentry = processed.get(str(bid)) or {}
            burl = bentry.get("pr_url")
            if burl:
                m = burl.rsplit("/", 1)[-1]
                if m.isdigit():
                    blocked_pr_refs.append(f"#{m}")
                    blocked_labels.append(f"blocked-by:#{m}")

        title = f"[Task #{task_id}] {subject or 'auto'}"[:80]
        body = _compose_pr_body(
            task_id=task_id,
            subject=subject,
            branch=branch,
            base=base,
            ahead=ahead,
            head_sha=head_short,
            start_sha=start_sha[:12] if start_sha else None,
            tests_msg=tests_msg,
            blocked_by_prs=blocked_pr_refs,
            extra={
                "push_mode": push_mode,
                "drift": rebase_note or "in sync",
                "scope_base": (start_sha or base)[:12],
                "head_full": head_full,
            },
        )

        if open_pr:
            pr_url = open_pr.get("url") or ""
            comment = (
                f"Auto-updated to `{head_short}` "
                f"({ahead} commits in {scope_note}).\n\n"
                f"Pre-push gate: {tests_msg}"
            )
            ok_c, cmsg = pr.gh_pr_comment(pr_url, comment, cwd=PROJECT_ROOT)
            pr_action = f"updated existing PR ({cmsg})"
        else:
            ok_c, pr_url = pr.gh_pr_create(branch, base, title, body, cwd=PROJECT_ROOT)
            if not ok_c:
                notify.notify_pr_failed(task_id, "pr_create", pr_url)
                return HookOutput().system_message(
                    f"[POST-TASK-PUSH-PR] Task #{task_id}: PR create failed: "
                    f"{pr_url}. Branch pushed; create PR manually."
                )
            pr_action = "PR created"

        # ---- P2.3: reviewer assignment ----
        reviewer_note = ""
        reviewers = _resolve_reviewers(scope_base)
        if reviewers and pr_url:
            ok_r, rmsg = pr.gh_pr_add_reviewers(pr_url, reviewers, cwd=PROJECT_ROOT)
            reviewer_note = f"reviewers: {','.join(reviewers)} ({'ok' if ok_r else rmsg})"

        # ---- P2.5: add blocked-by labels ----
        if blocked_labels and pr_url:
            pr.gh_pr_add_labels(pr_url, blocked_labels, cwd=PROJECT_ROOT)

        # ---- P1.2: wait for checks before merge (queue-lite) ----
        merge_note = ""
        if pr_url and pr.env_flag("AUTO_PR_AUTO_MERGE"):
            wait_timeout = pr.safe_int(pr.env_str("AUTO_PR_CHECKS_TIMEOUT"), 300)
            if pr.env_flag("AUTO_PR_WAIT_FOR_CHECKS"):
                ok_w, wmsg = pr.gh_pr_wait_checks(
                    pr_url, cwd=PROJECT_ROOT, max_seconds=wait_timeout
                )
                if not ok_w:
                    notify.notify_checks_failed(task_id, pr_url, wmsg)
                    merge_note = f"\n- checks: {wmsg} — merge SKIPPED"
                    pr_action += " (merge skipped: checks)"
                    open_pr = True  # don't merge
            if not merge_note:
                ok_m, mmsg = pr.gh_pr_merge(pr_url, cwd=PROJECT_ROOT)
                merge_note = f"\n- auto-merge: {'OK' if ok_m else 'FAIL'} — {mmsg}"
                if ok_m:
                    notify.notify_pr_merged(task_id, pr_url)

        # ---- record state ----
        processed[task_id] = {
            **(entry or {}),
            "head_sha": head_short,
            "branch": branch,
            "pr_url": pr_url,
            "completed_ts": datetime.now().isoformat(timespec="seconds"),
            "blockedBy": blocked_task_ids,
        }
        _save_state(state)

        # ---- email notification (created / merged handled above) ----
        if pr_action.startswith("PR created") and pr_url:
            notify.notify_pr_created(task_id, subject, branch, pr_url)

        msg = (
            f"[POST-TASK-PUSH-PR] Task #{task_id} OK\n"
            f"- {pr_action}: {pr_url or '(local-only)'}\n"
            f"- branch: `{branch}` ({ahead} commits in {scope_note}, mode={branch_mode})\n"
            f"- push: {push_mode}"
            + (f"\n- {cherry_note}" if cherry_note else "")
            + (f"\n- {reviewer_note}" if reviewer_note else "")
            + (f"\n- drift: {rebase_note}" if rebase_note else "")
            + merge_note
        )
        return HookOutput().system_message(msg)


# --- P2.3: reviewer resolution -----------------------------------------


def _resolve_reviewers(scope_base: str) -> list[str]:
    """CODEOWNERS first, AUTO_PR_REVIEWERS fallback."""
    paths = pr.changed_paths(scope_base, cwd=PROJECT_ROOT)
    co = pr.codeowners_for_paths(paths, repo_root=PROJECT_ROOT) if paths else []
    if co:
        return co
    fallback = pr.env_str("AUTO_PR_REVIEWERS")
    if not fallback:
        return []
    return [r.strip().lstrip("@") for r in fallback.split(",") if r.strip()]


if __name__ == "__main__":
    PostTaskPushPR().run()
