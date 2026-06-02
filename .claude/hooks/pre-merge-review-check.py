#!/usr/bin/env python3
"""
Hook: pre-merge-review-check
Event: PreToolUse:Bash
Purpose: Block `gh pr merge N` if PR has unresolved HIGH/MEDIUM bot review comments.

Override: env GH_MERGE_REVIEW_OVERRIDE=1 (set in same Bash invocation if user
explicitly authorizes merge despite findings, e.g. "merge it" override).

Detects severity via gemini-code-assist markers (high/medium/low icons +
"![high]"/"![medium]" prefix in body) and explicit "## Severity: HIGH" patterns.
Timeout: 6s (allows gh api roundtrip + parse).
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

GH_TIMEOUT_S = 4

MERGE_RE = re.compile(r"\bgh\s+pr\s+merge\b", re.I)
MERGE_NUM_RE = re.compile(r"\bgh\s+pr\s+merge\s+(?:https://[^\s]+/pull/)?(\d+)", re.I)
HIGH_RE = re.compile(r"!\[high\]|## Severity:\s*HIGH\b|severity:\s*high\b|priority:\s*high\b", re.I)
MEDIUM_RE = re.compile(
    r"!\[medium\]|## Severity:\s*MEDIUM\b|severity:\s*medium\b|priority:\s*medium\b", re.I
)


def _extract_pr_number(cmd: str) -> int | None:
    m = MERGE_NUM_RE.search(cmd)
    if m:
        return int(m.group(1))
    if not MERGE_RE.search(cmd):
        return None
    # Fallback: `gh pr merge` без args или с branch name → current branch PR
    try:
        r = subprocess.run(
            ["gh", "pr", "view", "--json", "number"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout).get("number")
    except (json.JSONDecodeError, AttributeError):
        return None


def _gh_api(endpoint: str) -> list:
    try:
        r = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    if r.returncode != 0 or not r.stdout.strip():
        return []
    try:
        data = json.loads(r.stdout)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _classify_comment(body: str) -> str:
    if HIGH_RE.search(body):
        return "high"
    if MEDIUM_RE.search(body):
        return "medium"
    return "low"


def _is_bot(login: str) -> bool:
    return login.endswith("[bot]") or "code-assist" in login.lower()


def _current_repo() -> tuple[str, str] | None:
    """Return (owner, name) from current gh repo context, or None."""
    try:
        r = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        d = json.loads(r.stdout)
        owner = (d.get("owner") or {}).get("login")
        name = d.get("name")
        return (owner, name) if owner and name else None
    except (json.JSONDecodeError, AttributeError):
        return None


def _fetch_resolved_dbids(pr: int) -> set[int]:
    """GraphQL: returns databaseIds of comments whose review thread is resolved OR outdated."""
    repo = _current_repo()
    if not repo:
        return set()
    owner, name = repo
    q = (
        f'query {{ repository(owner: "{owner}", name: "{name}") '
        f"{{ pullRequest(number: {pr}) "
        "{ reviewThreads(first: 100) { nodes { isResolved isOutdated "
        "comments(first: 100) { nodes { databaseId } } } } } } }"
    )
    try:
        r = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={q}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_S,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()
    if r.returncode != 0 or not r.stdout.strip():
        return set()
    try:
        threads = (
            json.loads(r.stdout)
            .get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
            .get("nodes", [])
        )
    except (json.JSONDecodeError, AttributeError):
        return set()
    resolved = set()
    for t in threads:
        if not isinstance(t, dict):
            continue
        if not (t.get("isResolved") or t.get("isOutdated")):
            continue
        for c in (t.get("comments") or {}).get("nodes", []) or []:
            dbid = c.get("databaseId") if isinstance(c, dict) else None
            if isinstance(dbid, int):
                resolved.add(dbid)
    return resolved


def _check_pr_reviews(pr: int) -> dict:
    """Fetch review comments + reviews, classify by severity, return summary."""
    comments = _gh_api(f"repos/{{owner}}/{{repo}}/pulls/{pr}/comments")
    reviews = _gh_api(f"repos/{{owner}}/{{repo}}/pulls/{pr}/reviews")
    resolved_ids = _fetch_resolved_dbids(pr)
    high, medium, samples = 0, 0, []
    for c in comments + reviews:
        if not isinstance(c, dict):
            continue
        # Skip resolved or outdated threads (GraphQL authoritative). Fallback for
        # entries lacking databaseId (e.g. PR reviews): line/position None heuristic.
        if c.get("id") in resolved_ids or c.get("databaseId") in resolved_ids:
            continue
        if c.get("path") and (c.get("line") is None or c.get("position") is None):
            continue
        user = (c.get("user") or {}).get("login", "")
        if not _is_bot(user):
            continue
        body = c.get("body") or ""
        sev = _classify_comment(body)
        if sev == "high":
            high += 1
        elif sev == "medium":
            medium += 1
        else:
            continue
        if len(samples) < 3:
            path = c.get("path", "")
            samples.append(f"{sev.upper()} {user} {path}: {body[:120]}")
    return {"high": high, "medium": medium, "samples": samples}


class PreMergeReviewCheck(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("GH_MERGE_REVIEW_OVERRIDE") == "1":
            return None
        tool_input = inp.tool_input or {}
        cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        if not cmd:
            return None
        pr = _extract_pr_number(cmd)
        if pr is None:
            return None
        summary = _check_pr_reviews(pr)
        if summary["high"] == 0 and summary["medium"] == 0:
            return None
        msg_lines = [
            f"[PRE-MERGE-REVIEW] PR #{pr} has unresolved bot reviews:",
            f"  HIGH: {summary['high']}  MEDIUM: {summary['medium']}",
            "",
            "Samples:",
        ]
        for s in summary["samples"]:
            msg_lines.append(f"  - {s}")
        msg_lines.append("")
        msg_lines.append(
            "Action: review and apply fixes BEFORE merge. "
            "Override with env GH_MERGE_REVIEW_OVERRIDE=1 if intentional."
        )
        return HookOutput().block("\n".join(msg_lines))


if __name__ == "__main__":
    PreMergeReviewCheck().run()
