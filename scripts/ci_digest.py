#!/usr/bin/env python3
"""CI digest — markdown summary of last 24h CI activity."""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL = PROJECT_ROOT / ".claude" / "cache" / "ci-failures.jsonl"
REPO = "Alex1980Alex/1C-Framework"


def _gh(*args: str) -> tuple[int, str]:
    r = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return r.returncode, r.stdout


def _parse_since(s: str) -> timedelta:
    m = re.match(r"(\d+)([hdwm])", s.lower())
    if not m:
        return timedelta(hours=24)
    n, unit = int(m.group(1)), m.group(2)
    return {
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
        "w": timedelta(weeks=n),
        "m": timedelta(days=30 * n),
    }[unit]


def _load_failures(since: datetime) -> list[dict]:
    if not JSONL.exists():
        return []
    out = []
    for ln in JSONL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if e.get("event_type"):
            continue  # skip generic events (notifications/pr-reviews) — only CI failures
        try:
            ts = datetime.fromisoformat((e.get("ts") or "").replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts >= since:
            out.append(e)
    return out


def _gh_json(*args: str) -> list:
    rc, out = _gh(*args)
    if rc != 0 or not out.strip():
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def _section_failures(failures: list[dict]) -> str:
    if not failures:
        return "## CI Failures\n\nNo failures in window.\n"
    by_hash = collections.Counter(e.get("error_hash", "?") for e in failures)
    lines = [f"## CI Failures ({len(failures)} total, {len(by_hash)} unique)", ""]
    for h, count in by_hash.most_common(10):
        sample = next((e for e in failures if e.get("error_hash") == h), {})
        err = (sample.get("error_first_line") or "")[:90]
        lines.append(f"- **[{count}x]** `{h}` — {err}")
    return "\n".join(lines) + "\n"


def _section_open_prs() -> str:
    prs = _gh_json(
        "pr", "list", "--state", "open", "--limit", "20", "--json", "number,title,statusCheckRollup"
    )
    if not prs:
        return "## Open PRs\n\nNo open PRs.\n"
    # Skip noisy gates (pre-existing red or auto-review bot). "Claude Code Review"
    # is the bot workflow; loose "claude" match would skip legitimate claude-* gates.
    skip_re = re.compile(r"YAxUnit|BSL Static|BDD Tests|Claude Code Review|claude\[bot\]", re.I)
    lines = [f"## Open PRs ({len(prs)})", ""]
    for p in prs:
        rollup = p.get("statusCheckRollup") or []
        fails = sum(
            1
            for c in rollup
            if c.get("conclusion") == "FAILURE" and not skip_re.search(c.get("name", ""))
        )
        title = (p.get("title") or "")[:50]
        lines.append(f"- PR#{p['number']} **{title}** — {fails} failing gate(s)")
    return "\n".join(lines) + "\n"


def _section_merged(since_iso: str) -> str:
    prs = _gh_json(
        "pr",
        "list",
        "--state",
        "merged",
        "--search",
        f"merged:>={since_iso}",
        "--limit",
        "30",
        "--json",
        "number,title,mergedAt",
    )
    if not prs:
        return "## Recently Merged\n\nNo merged PRs in window.\n"
    lines = [f"## Recently Merged ({len(prs)} PRs)", ""]
    for p in prs:
        title = (p.get("title") or "")[:60]
        when = (p.get("mergedAt") or "")[:10]
        lines.append(f"- PR#{p['number']} {title} ({when})")
    return "\n".join(lines) + "\n"


def _section_auto_issues() -> str:
    issues = _gh_json(
        "issue",
        "list",
        "--label",
        "ci-failure,automated",
        "--state",
        "open",
        "--json",
        "number,title,createdAt",
    )
    if not issues:
        return "## Auto-Issues\n\nNo auto-issues open.\n"
    lines = [f"## Auto-Issues ({len(issues)} open)", ""]
    for i in issues:
        title = (i.get("title") or "")[:80]
        when = (i.get("createdAt") or "")[:10]
        lines.append(f"- #{i['number']} {title} (created {when})")
    return "\n".join(lines) + "\n"


def _section_notifications() -> str:
    notifs = _gh_json(
        "api",
        "notifications",
        "--jq",
        "[.[] | {subject: .subject.title, type: .subject.type, reason}]",
    )
    if not notifs:
        return "## GitHub Notifications\n\nNo unread.\n"
    by_reason = collections.Counter(n.get("reason", "?") for n in notifs)
    lines = [f"## GitHub Notifications ({len(notifs)} unread)", ""]
    for reason, count in by_reason.most_common():
        lines.append(f"- **{reason}**: {count}")
    lines.append("")
    lines.append("### Recent subjects (top 5):")
    for n in notifs[:5]:
        lines.append(f"- [{n.get('type', '?')}] {(n.get('subject') or '')[:80]}")
    return "\n".join(lines) + "\n"


def generate_digest(since_hours: int) -> str:
    since = datetime.now(UTC) - timedelta(hours=since_hours)
    since_iso = since.strftime("%Y-%m-%d")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        f"# CI Digest — {now}",
        "",
        f"Window: last {since_hours}h since {since_iso}",
        "",
        _section_failures(_load_failures(since)),
        _section_open_prs(),
        _section_merged(since_iso),
        _section_auto_issues(),
        _section_notifications(),
    ]
    return "\n".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--since", default="24h", help="Lookback window (e.g. 24h, 7d)")
    p.add_argument("--save", help="Optional output file (also prints to stdout)")
    args = p.parse_args()
    hours = int(_parse_since(args.since).total_seconds() // 3600)
    digest = generate_digest(hours)
    print(digest)
    if args.save:
        out = Path(args.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(digest, encoding="utf-8")
        print(f"\nSaved: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
