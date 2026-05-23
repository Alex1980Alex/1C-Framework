#!/usr/bin/env python3
"""PR automation dashboard — daily roll-up from hook-invocations.jsonl.

Roadmap: 40_PR_AUTOMATION/40.4 P1.5.

Reads `data/hook-invocations.jsonl` filtered to PostTaskPushPR entries plus
state from `.claude/cache/post-task-push-pr-state.json`, emits a markdown
report with daily counts, top errors and stale open PRs.

CLI:
  python scripts/pr_automation_dashboard.py [--days N] [--out PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "post-task-push-pr-state.json"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "pr_automation"
HOOK_NAME = "PostTaskPushPR"


def _parse_jsonl(days: int) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=days)
    out: list[dict] = []
    try:
        with LOG_FILE.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("hook") != HOOK_NAME:
                    continue
                try:
                    ts = datetime.fromisoformat(e.get("ts", ""))
                except ValueError:
                    continue
                # Tolerate legacy naive timestamps from pre-UTC state-file
                # writers: normalize to aware UTC before comparing with cutoff.
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts < cutoff:
                    continue
                e["_ts"] = ts
                out.append(e)
    except OSError:
        return []
    return out


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _classify(entry: dict) -> str:
    o = entry.get("outcome")
    if o == "error":
        return "error"
    if o == "block":
        return "block"
    return "ok"


def _safe_median(values: list[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def build_report(days: int) -> dict:
    entries = _parse_jsonl(days)
    state = _load_state().get("processed", {})
    today = datetime.now(UTC).date().isoformat()

    prs_tracked = sum(1 for v in state.values() if v.get("pr_url"))
    prs_today = sum(1 for v in state.values() if str(v.get("completed_ts", "")).startswith(today))

    buckets: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        buckets[e["_ts"].date().isoformat()].append(e)

    daily: list[dict] = []
    error_reasons: Counter = Counter()
    all_ms: list[int] = []
    for day in sorted(buckets):
        items = buckets[day]
        d = {"day": day, "total": len(items), "ok": 0, "error": 0, "block": 0}
        ms_list: list[int] = []
        for it in items:
            d[_classify(it)] += 1
            ms = int(it.get("elapsed_ms") or 0)
            ms_list.append(ms)
            all_ms.append(ms)
            if it.get("error"):
                error_reasons[str(it["error"])[:120]] += 1
        d["median_ms"] = _safe_median(ms_list)
        daily.append(d)

    stale_cut = datetime.now(UTC) - timedelta(days=7)
    stale: list[dict] = []
    for tid, v in state.items():
        url = v.get("pr_url")
        ts_str = v.get("completed_ts")
        if not (url and ts_str):
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        # Legacy naive timestamps → assume UTC (matches today's writers).
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < stale_cut:
            stale.append(
                {
                    "task_id": tid,
                    "pr_url": url,
                    "completed_ts": ts_str,
                    "branch": v.get("branch", ""),
                }
            )

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "window_days": days,
        "total_invocations": len(entries),
        "total_prs_tracked": prs_tracked,
        "prs_completed_today": prs_today,
        "median_elapsed_ms_all": _safe_median(all_ms),
        "daily": daily,
        "top_errors": error_reasons.most_common(5),
        "stale_prs_over_7d": stale,
    }


def render_markdown(r: dict) -> str:
    lines = [
        "# PR Automation — Dashboard",
        "",
        f"_Generated: {r['generated_at']} · window: last {r['window_days']}d_",
        "",
        "## Summary",
        "",
        f"- **Invocations** (window): {r['total_invocations']}",
        f"- **PRs tracked** (lifetime): {r['total_prs_tracked']}",
        f"- **PRs completed today**: {r['prs_completed_today']}",
        f"- **Median elapsed ms** (window): {r['median_elapsed_ms_all']:.0f}",
        "",
        "## Daily breakdown",
        "",
        "| Day | Total | OK | Error | Block | Median ms |",
        "|-----|-------|-----|-------|-------|-----------|",
    ]
    if r["daily"]:
        for d in r["daily"]:
            lines.append(
                f"| {d['day']} | {d['total']} | {d['ok']} | "
                f"{d['error']} | {d['block']} | {d['median_ms']:.0f} |"
            )
    else:
        lines.append("| _(no entries in window)_ | | | | | |")
    lines += ["", "## Top failure reasons", ""]
    if r["top_errors"]:
        for reason, count in r["top_errors"]:
            lines.append(f"- ×{count} — `{reason}`")
    else:
        lines.append("- _none_")
    lines += ["", "## Stale open PRs (>7 days since completion)", ""]
    if r["stale_prs_over_7d"]:
        for s in r["stale_prs_over_7d"]:
            lines.append(
                f"- Task #{s['task_id']} — {s['pr_url']} "
                f"(since {s['completed_ts']}, branch `{s['branch']}`)"
            )
    else:
        lines.append("- _none_")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    # Windows cp1251 console kills `×`/`—`. Reconfigure to UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="PR automation dashboard")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report(args.days)
    md = render_markdown(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        if args.json:
            args.out.with_suffix(".json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
    else:
        sys.stdout.write(md)

    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "_latest.md").write_text(md, encoding="utf-8")
        if args.json or args.out:
            (REPORT_DIR / "_latest.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        dated = REPORT_DIR / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.md"
        if not dated.exists():
            dated.write_text(md, encoding="utf-8")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
