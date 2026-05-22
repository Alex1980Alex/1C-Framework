"""PR automation helpers — git + gh CLI primitives.

Shared between `post-task-push-pr.py` hook and `scripts/cleanup_orphan_branches.py`
/ `scripts/pr_automation_dashboard.py`. All operations:
- Use shell=False (security).
- Bounded timeout (no indefinite hang).
- Swallow OSError/TimeoutExpired into tuple results (callers branch on bool).

Roadmap reference: 40_PR_AUTOMATION/40.4 (P0+P1+P2 batch).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

# --- generic ------------------------------------------------------------


def safe_int(value: str | int | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip() or default)
    except (ValueError, TypeError):
        return default


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "-", (text or "").lower(), flags=re.UNICODE)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60] or "task"


# --- git ----------------------------------------------------------------


def run_git(
    *args: str,
    cwd: str | Path,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Wrap `git <args>`. Returns (returncode, stdout, stderr) — never raises."""
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd),
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def commits_ahead(base: str, *, cwd: str | Path, head: str = "HEAD") -> int:
    code, out, _ = run_git("rev-list", "--count", f"{base}..{head}", cwd=cwd)
    return safe_int(out, 0) if code == 0 else 0


def head_sha(*, cwd: str | Path, short: bool = True) -> str:
    code, out, _ = run_git("rev-parse", "HEAD", cwd=cwd)
    if code != 0 or not out:
        return ""
    return out[:12] if short else out


def is_ancestor(a: str, b: str, *, cwd: str | Path) -> bool:
    """True if commit `a` is an ancestor of commit `b`."""
    code, _, _ = run_git("merge-base", "--is-ancestor", a, b, cwd=cwd)
    return code == 0


def branch_exists_local(name: str, *, cwd: str | Path) -> bool:
    code, _, _ = run_git("rev-parse", "--verify", "--quiet", name, cwd=cwd)
    return code == 0


def fetch_remote(
    remote: str,
    ref: str | None = None,
    *,
    cwd: str | Path,
    timeout: int = 30,
) -> tuple[bool, str]:
    args = ["fetch", remote]
    if ref:
        args.append(ref)
    code, _, err = run_git(*args, cwd=cwd, timeout=timeout)
    return (code == 0), (err or "ok")


def changed_paths(base: str, *, cwd: str | Path, head: str = "HEAD") -> list[str]:
    """Files changed in base..HEAD. Used for CODEOWNERS lookup."""
    code, out, _ = run_git("diff", "--name-only", f"{base}..{head}", cwd=cwd)
    if code != 0:
        return []
    return [ln for ln in out.splitlines() if ln.strip()]


# --- gh CLI -------------------------------------------------------------


def gh_available() -> bool:
    try:
        r = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            shell=False,
        )
        return r.returncode == 0
    except (FileNotFoundError, OSError):
        return False


def _run_gh(
    *args: str,
    cwd: str | Path,
    timeout: int = 30,
) -> tuple[int, str, str]:
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
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def gh_pr_list_for_branch(branch: str, *, cwd: str | Path) -> list[dict]:
    """Return open + closed/merged PRs for given head branch. Empty on error."""
    code, out, _ = _run_gh(
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "all",
        "--json",
        "number,url,state,title,headRefName",
        cwd=cwd,
    )
    if code != 0 or not out:
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def gh_pr_create(
    branch: str,
    base: str,
    title: str,
    body: str,
    *,
    cwd: str | Path,
    draft: bool = False,
) -> tuple[bool, str]:
    args = [
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
    ]
    if draft:
        args.append("--draft")
    code, out, err = _run_gh(*args, cwd=cwd, timeout=30)
    if code == 0:
        url = out.splitlines()[-1] if out else ""
        return True, url.strip()
    return False, (err or out)[:300]


def gh_pr_comment(pr_url: str, body: str, *, cwd: str | Path) -> tuple[bool, str]:
    code, _, err = _run_gh("pr", "comment", pr_url, "--body", body, cwd=cwd, timeout=20)
    return (code == 0), (err[:200] if err else "ok")


def gh_pr_checks_status(pr_url: str, *, cwd: str | Path) -> str:
    """Return: pending | success | failure | unknown."""
    code, out, _ = _run_gh(
        "pr",
        "checks",
        pr_url,
        "--json",
        "state,conclusion",
        cwd=cwd,
        timeout=15,
    )
    if code != 0 or not out:
        return "unknown"
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return "unknown"
    if not data:
        return "success"  # no checks configured = green
    states = {(c.get("state") or c.get("conclusion") or "").lower() for c in data}
    if states & {"failure", "cancelled", "timed_out", "action_required"}:
        return "failure"
    if states & {"pending", "in_progress", "queued", "waiting", "neutral"}:
        return "pending"
    return "success"


def gh_pr_wait_checks(pr_url: str, *, cwd: str | Path, max_seconds: int = 300) -> tuple[bool, str]:
    """Poll until checks resolve. Returns (success, message). Bounded by max_seconds."""
    start = time.time()
    last = "unknown"
    while time.time() - start < max_seconds:
        last = gh_pr_checks_status(pr_url, cwd=cwd)
        if last == "success":
            return True, f"checks ok ({int(time.time() - start)}s)"
        if last == "failure":
            return False, f"checks failed ({int(time.time() - start)}s)"
        time.sleep(15)
    return False, f"checks still {last} after {max_seconds}s timeout"


def gh_pr_merge(
    pr_url: str, *, cwd: str | Path, squash: bool = True, delete_branch: bool = True
) -> tuple[bool, str]:
    args = ["pr", "merge", pr_url]
    if squash:
        args.append("--squash")
    if delete_branch:
        args.append("--delete-branch")
    code, _, err = _run_gh(*args, cwd=cwd, timeout=30)
    if code == 0:
        return True, "merged"
    return False, (err or "")[:300]


def gh_pr_add_reviewers(
    pr_url: str, reviewers: Sequence[str], *, cwd: str | Path
) -> tuple[bool, str]:
    if not reviewers:
        return True, "no reviewers"
    rev_arg = ",".join(reviewers)
    code, _, err = _run_gh("pr", "edit", pr_url, "--add-reviewer", rev_arg, cwd=cwd, timeout=15)
    return (code == 0), (err[:200] if err else f"added {rev_arg}")


def gh_pr_add_labels(pr_url: str, labels: Sequence[str], *, cwd: str | Path) -> tuple[bool, str]:
    if not labels:
        return True, "no labels"
    code, _, err = _run_gh(
        "pr",
        "edit",
        pr_url,
        "--add-label",
        ",".join(labels),
        cwd=cwd,
        timeout=15,
    )
    return (code == 0), (err[:200] if err else f"labels {labels}")


def gh_pr_delete_branch(branch: str, *, cwd: str | Path) -> tuple[bool, str]:
    """Delete remote branch via git push :branch (works even if PR gone)."""
    code, _, err = run_git("push", "origin", "--delete", branch, cwd=cwd, timeout=30)
    return (code == 0), (err[:200] if err else "deleted")


# --- label / scope detection -------------------------------------------


def task_meets_label_requirement(
    tool_input: dict | None, tool_result: dict | str | None, required_label: str
) -> tuple[bool, str]:
    """P0.1 label-driven activation.

    Strategy:
      - required_label empty/None → always pass (backward compat).
      - else check `tool_input.metadata.labels` (list of str)
        OR `tool_input.subject` / `tool_result.subject` containing `[<label>]`.
    """
    if not required_label:
        return True, "no label requirement"
    label_lower = required_label.lower()
    if isinstance(tool_input, dict):
        meta = tool_input.get("metadata")
        if isinstance(meta, dict):
            labels = meta.get("labels") or []
            if isinstance(labels, list) and any(str(lbl).lower() == label_lower for lbl in labels):
                return True, f"label `{required_label}` in metadata"
        subj = str(tool_input.get("subject") or "")
        if f"[{label_lower}]" in subj.lower():
            return True, "label tag in subject"
    if isinstance(tool_result, dict):
        subj = str(tool_result.get("subject") or "")
        if f"[{label_lower}]" in subj.lower():
            return True, "label tag in result subject"
    return False, f"label `{required_label}` not found"


# --- CODEOWNERS parsing ------------------------------------------------

CODEOWNERS_PATHS = (
    ".github/CODEOWNERS",
    "docs/CODEOWNERS",
    "CODEOWNERS",
)


def _read_codeowners(repo_root: Path) -> list[tuple[str, list[str]]]:
    for rel in CODEOWNERS_PATHS:
        p = repo_root / rel
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            rules: list[tuple[str, list[str]]] = []
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                pattern = parts[0]
                owners = [o.lstrip("@") for o in parts[1:] if o.startswith("@") or "/" in o]
                if owners:
                    rules.append((pattern, owners))
            return rules
    return []


def codeowners_for_paths(paths: Iterable[str], *, repo_root: Path) -> list[str]:
    """Return unique reviewer logins matching changed paths in CODEOWNERS.

    Simple glob matching (gitignore-style). Later rules override earlier ones
    per GitHub semantics, so we scan all rules and merge owners from matches.
    """
    rules = _read_codeowners(repo_root)
    if not rules:
        return []
    matched: dict[str, None] = {}
    for path in paths:
        last_owners: list[str] | None = None
        for pattern, owners in rules:
            pat = pattern
            if pat.startswith("/"):
                pat = pat[1:]
            if pat.endswith("/"):
                pat += "**"
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, "**/" + pat):
                last_owners = owners
        if last_owners:
            for o in last_owners:
                matched.setdefault(o, None)
    return list(matched.keys())


# --- push with conflict detection --------------------------------------

REJECT_HINTS = (
    "Updates were rejected",
    "non-fast-forward",
    "fetch first",
    "tip of your current branch is behind",
)


def push_branch_safe(
    branch: str,
    *,
    cwd: str | Path,
    base_for_ancestor: str | None = None,
    remote: str = "origin",
    timeout: int = 60,
) -> tuple[bool, str, str]:
    """Push with single-retry on stale-rejection.

    Returns (ok, mode, message).
      mode = "ok" | "stale_retry_ok" | "conflict" | "error"

    Strategy:
      1. First push.
      2. If error contains rejection hint → fetch remote branch, check if
         remote tip is ancestor of HEAD (i.e. local has all remote commits
         plus new ones). If yes — actually stale upstream sync issue, retry push.
         Otherwise — true conflict, skip with message.
    """
    code, _, err = run_git("push", "-u", remote, branch, cwd=cwd, timeout=timeout)
    if code == 0:
        return True, "ok", "pushed"
    if not any(h.lower() in err.lower() for h in REJECT_HINTS):
        return False, "error", err[:300]
    # rejection path
    ok, fmsg = fetch_remote(remote, branch, cwd=cwd, timeout=timeout)
    if not ok:
        return False, "conflict", f"fetch failed: {fmsg[:200]}"
    remote_ref = f"{remote}/{branch}"
    if is_ancestor(remote_ref, "HEAD", cwd=cwd):
        # remote is ancestor → simple FF, retry
        code2, _, err2 = run_git("push", "-u", remote, branch, cwd=cwd, timeout=timeout)
        if code2 == 0:
            return True, "stale_retry_ok", "fast-forwarded after fetch"
        return False, "conflict", f"retry failed: {err2[:200]}"
    return (
        False,
        "conflict",
        (f"branch `{branch}` has divergent commits on remote; " "manual review needed"),
    )


# --- stale base check (P1.3) -------------------------------------------


def base_drift_status(
    base: str, *, cwd: str | Path, remote: str = "origin"
) -> tuple[int, int, str]:
    """Return (behind, ahead, msg) — HEAD vs remote/base.

    behind  — commits in remote/base not in HEAD  (we are stale)
    ahead   — commits in HEAD not in remote/base
    """
    ok, _ = fetch_remote(remote, base, cwd=cwd, timeout=30)
    if not ok:
        return 0, 0, "fetch failed"
    code, out, _ = run_git(
        "rev-list", "--left-right", "--count", f"{remote}/{base}...HEAD", cwd=cwd
    )
    if code != 0 or not out:
        return 0, 0, "rev-list failed"
    try:
        behind, ahead = (int(x) for x in out.split())
        return behind, ahead, "ok"
    except ValueError:
        return 0, 0, f"parse error: {out}"


def auto_rebase_safe(base: str, *, cwd: str | Path, remote: str = "origin") -> tuple[bool, str]:
    """Rebase current HEAD onto remote/base. Aborts on conflict.

    Caller must verify they want to rewrite history before calling.
    """
    code, _, err = run_git("rebase", f"{remote}/{base}", cwd=cwd, timeout=60)
    if code == 0:
        return True, "rebased"
    # try abort
    run_git("rebase", "--abort", cwd=cwd, timeout=15)
    return False, f"rebase conflict (aborted): {err[:200]}"


# --- env helper --------------------------------------------------------


def env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip() == "1"


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()
