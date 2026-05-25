#!/usr/bin/env python3
"""Semi-automated CodeQL alert triage for py/empty-except (§20 P2).

Loads all open py/empty-except alerts via gh CLI, classifies each by path
prefix into a category, and applies category-specific dismiss reason.

Categories (in priority order — first match wins):
- vendored: tools/serena, tools/bsl-ls, tools/1c-docs-rag, tools/ast-grep-mcp,
  infra/pipeline (3rd-party serena agents)
- tests: tests/, *_test.py, test_*.py
- intentional: best-effort hook/cache/metric/log reads — graceful degradation
  by design (fail-soft pattern)
- review: anything else — requires manual triage

Output:
- Default: dry-run report (counts per category + sample paths)
- --apply: actually invoke `gh api -X PATCH` for each
- --rule R: target different CodeQL rule (default py/empty-except)
- --include-review: also dismiss `review` category (caution!)

Per roadmap 260523 §20.3 P2 item.

Usage:
    python scripts/triage_codeql_alerts.py             # dry-run
    python scripts/triage_codeql_alerts.py --apply     # actually dismiss
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict

REPO = "Alex1980Alex/1C-Framework"
DEFAULT_RULE = "py/empty-except"

# (priority order matters — first matching pattern wins)
CATEGORIES: list[tuple[str, list[str], str, str]] = [
    (
        "vendored",
        [
            "tools/serena/",
            "tools/bsl-ls/",
            "tools/1c-docs-rag/",
            "tools/ast-grep-mcp/",
            "infra/pipeline/",
        ],
        "Vendored 3rd-party code (serena LSP / bsl-ls / 1c-docs-rag / ast-grep-mcp / serena pipeline agents). Not maintained as primary code; bare except patterns inherited from upstream.",
        "won't fix",
    ),
    (
        "tests",
        ["tests/", "/test_", "_test.py"],
        "Test file — bare except commonly used for cleanup/teardown best-effort, false positive for production analysis.",
        "used in tests",
    ),
    (
        "intentional",
        [
            ".claude/hooks/",
            "infra/lazy-mcp/",
            "scripts/_progress",
            "scripts/analyzers/",
            "scripts/hook-",
            "scripts/measure-",
            "scripts/skill-",
            "scripts/eval-",
            "src/memory/infrastructure/",
            "src/pdf_framework/observability/",
            "src/shared/llm_rotation/",
        ],
        "Intentional graceful degradation: best-effort metric/cache/log read. Fail-soft pattern by design — partial failures must not block hook chain or background pipeline.",
        "won't fix",
    ),
]

REVIEW_REASON = (
    "Production-code site requires manual review — may need typed exception or explicit logger.debug()."
)


def fetch_alerts(rule: str) -> list[dict]:
    """Fetch all open alerts matching rule via gh CLI."""
    out = subprocess.run(
        [
            "gh", "api", "-X", "GET", f"repos/{REPO}/code-scanning/alerts",
            "-f", "state=open", "--paginate",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        print(f"ERROR fetching alerts: {out.stderr[:500]}", file=sys.stderr)
        sys.exit(2)
    data = json.loads(out.stdout)
    return [a for a in data if a.get("rule", {}).get("id") == rule]


def classify(path: str) -> str:
    """Return category name for path. Priority order: first match wins."""
    p = path.replace("\\", "/")
    for cat, prefixes, _reason, _dismiss in CATEGORIES:
        for prefix in prefixes:
            if prefix in p:
                return cat
    return "review"


def dismiss(alert_number: int, reason: str, comment: str) -> bool:
    """Invoke gh api PATCH to dismiss one alert. True on success."""
    result = subprocess.run(
        [
            "gh", "api", "-X", "PATCH",
            f"repos/{REPO}/code-scanning/alerts/{alert_number}",
            "-f", "state=dismissed",
            "-f", f"dismissed_reason={reason}",
            "-f", f"dismissed_comment={comment}",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", default=DEFAULT_RULE,
                        help=f"CodeQL rule id (default: {DEFAULT_RULE})")
    parser.add_argument("--apply", action="store_true",
                        help="Actually dismiss alerts (default: dry-run)")
    parser.add_argument("--include-review", action="store_true",
                        help="Also dismiss `review` category as won't-fix")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit total dismissals (0=no limit)")
    args = parser.parse_args()

    alerts = fetch_alerts(args.rule)
    print(f"Found {len(alerts)} open alerts for rule={args.rule}\n")

    by_cat: dict[str, list[tuple[int, str]]] = defaultdict(list)
    cat_meta: dict[str, tuple[str, str]] = {}
    for cat, _prefixes, comment, reason in CATEGORIES:
        cat_meta[cat] = (comment, reason)
    cat_meta["review"] = (REVIEW_REASON, "won't fix")

    for a in alerts:
        loc = a["most_recent_instance"]["location"]
        path = loc["path"]
        cat = classify(path)
        by_cat[cat].append((a["number"], f"{path}:{loc['start_line']}"))

    print("Distribution:")
    for cat in ["vendored", "tests", "intentional", "review"]:
        items = by_cat.get(cat, [])
        print(f"  {cat:12} {len(items):>4} alerts")
        for num, location in items[:3]:
            print(f"    sample: #{num} {location}")
        if len(items) > 3:
            print(f"    ... +{len(items) - 3} more")
    print()

    if not args.apply:
        print("(dry-run — pass --apply to actually dismiss)")
        return 0

    target_cats = ["vendored", "tests", "intentional"]
    if args.include_review:
        target_cats.append("review")

    total_dismissed = 0
    failed: list[int] = []
    for cat in target_cats:
        items = by_cat.get(cat, [])
        comment, reason = cat_meta[cat]
        print(f"\nDismissing {cat} ({len(items)} alerts)...")
        for num, location in items:
            if args.limit and total_dismissed >= args.limit:
                print(f"  (limit {args.limit} reached)")
                break
            ok = dismiss(num, reason, comment)
            total_dismissed += 1
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] #{num} {location}")
            if not ok:
                failed.append(num)
        if args.limit and total_dismissed >= args.limit:
            break

    print(f"\nDone: {total_dismissed} dismissed, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
