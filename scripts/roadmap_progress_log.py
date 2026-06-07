#!/usr/bin/env python3
"""
roadmap_progress_log.py — §18 Progress Log tooling (roadmap 260523 §19 P2+P3).

Two subcommands operating on roadmaps that contain a `## §18 ... Progress Log`
section (reverse-chronological, append-only, dated `### YYYY-MM-DD` entries):

  lint    P2 — validate §18 structure (dated entries, valid calendar dates,
               reverse-chronological order). Optional PR-mode freshness check
               (`--base <ref>`): if a roadmap's §18 changed vs base but NO new
               dated entry was added → fail (append-only log must gain an entry).
               Wired into CI `lint` job. Graceful: missing base ref → structural-only.

  append  P3 — insert a skeleton dated entry at the top of §18 (after the header
               note), so the operator/Claude fills in details. Reduces the risk of
               skipping the §19 manual step.

Pure functions (extract/parse/validate/build) are git-free and unit-tested in
tests/unit/test_roadmap_progress_log.py. The CLI/git layer is a thin wrapper.

Usage:
  python scripts/roadmap_progress_log.py lint [--base origin/master] [--no-freshness] [--json]
  python scripts/roadmap_progress_log.py append --date 2026-05-29 --summary "..." [--pr 99] [--roadmap <file>] [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROADMAP_DIR = PROJECT_ROOT / "docs" / "roadmap"

# §18 section starts at this heading and runs until the next top-level `## §` heading.
# Asymmetry is intentional: the START needs `§18\b` (must NOT match `§180`/`§181`),
# but the END matches ANY `## §N` heading (`§19`, `§20`, even `§180`) — any next
# top-level section terminates §18. Do not "align" these two regexes.
_SECTION_HEADING_RE = re.compile(r"^##\s+§18\b.*$", re.MULTILINE)
_NEXT_SECTION_RE = re.compile(r"^##\s+§", re.MULTILINE)
# Dated entry inside §18: `### 2026-05-29 (optional suffix) — title`
_ENTRY_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\b(.*)$", re.MULTILINE)
# Obsidian-style memory wikilink `[[name]]` / `[[name|alias]]` / `[[name#anchor]]`.
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
# A wikilink worth validating as a MEMORY reference: starts with a memory-entry
# type prefix (feedback/project/reference/user) + `-`/`_` separator. Scoping to this
# convention avoids false-positives from doc syntax examples (`[[overview]]`,
# `[[page-name]]`), code artifacts (`[[Callable[..., Any]`), and concept mentions
# (`[[wikilinks]]`), while still catching real refs AND hyphen/underscore drift
# (e.g. `[[feedback-bsl-...]]` → file is `feedback_bsl_...md`).
_MEMORY_NAME_RE = re.compile(r"^(feedback|project|reference|user)[-_][\w-]+$")
# Default memory store (Claude Code project memory dir). Overridable via --memory-dir.
_DEFAULT_MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--1--Framework" / "memory"
# Tolerate small clock skew between local/CI/commit timezones.
_FUTURE_SKEW_DAYS = 2


# ── pure helpers (git-free, unit-tested) ──────────────────────────────────────


def extract_section_18(text: str) -> str | None:
    """Return the `## §18` block (heading → just before next `## §`), or None."""
    m = _SECTION_HEADING_RE.search(text)
    if not m:
        return None
    nxt = _NEXT_SECTION_RE.search(text, m.end())
    return text[m.start() : nxt.start()] if nxt else text[m.start() :]


def parse_entries(section: str) -> list[tuple[str, str]]:
    """Return [(date_str, heading_tail), ...] for each `### YYYY-MM-DD` entry."""
    return [(m.group(1), m.group(2).strip()) for m in _ENTRY_RE.finditer(section)]


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_structure(section: str, today: date) -> list[str]:
    """Validate §18 structure. Return list of problem strings (empty = OK)."""
    problems: list[str] = []
    entries = parse_entries(section)
    if not entries:
        problems.append("§18 has no dated `### YYYY-MM-DD` entries")
        return problems

    parsed: list[date] = []
    horizon = today + timedelta(days=_FUTURE_SKEW_DAYS)
    for ds, _tail in entries:
        d = _parse_date(ds)
        if d is None:
            problems.append(f"invalid calendar date in entry heading: {ds}")
            continue
        if d > horizon:
            problems.append(f"future-dated entry: {ds} (today={today.isoformat()})")
        parsed.append(d)

    # Reverse-chronological: each entry's date must be <= the previous one's.
    for prev, cur in zip(parsed, parsed[1:]):
        if cur > prev:
            problems.append(
                f"entries not reverse-chronological: {cur.isoformat()} appears below {prev.isoformat()}"
            )
    return problems


def entry_dates(section: str) -> list[str]:
    """Sorted list of entry date strings (for freshness comparison)."""
    return sorted(ds for ds, _ in parse_entries(section))


def entry_headings(section: str) -> list[str]:
    """Full normalized entry headings `YYYY-MM-DD <tail>` (for freshness comparison)."""
    return [f"{ds} {tail}".strip() for ds, tail in parse_entries(section)]


def freshness_problem(base_text: str, head_text: str) -> str | None:
    """Append-only freshness: if §18 changed vs base but no NEW dated entry was
    added, return a problem string; else None. Trivial edits outside §18 don't
    trigger (we compare only the §18 sections).

    Compares full entry HEADINGS (not just dates) so that a genuine prepended
    entry is detected as: all base headings preserved AND at least one extra.
    This catches both an in-place body edit (headings unchanged → FAIL) and a
    date-rename / history rewrite (a base heading disappears → FAIL), which a
    date-multiset comparison would miss (reviewer ae1c7fab finding #1)."""
    base_sec = extract_section_18(base_text)
    head_sec = extract_section_18(head_text)
    if head_sec is None:
        return None  # No §18 in head → not a progress-log roadmap; nothing to enforce.
    if base_sec is None:
        return None  # §18 newly introduced → fine.
    if base_sec == head_sec:
        return None  # §18 unchanged → fine.
    base_h = set(entry_headings(base_sec))
    head_h = entry_headings(head_sec)
    head_set = set(head_h)
    # Fresh ⟺ every base entry still present (no history rewrite) AND ≥1 new heading.
    preserved = base_h <= head_set
    has_new = len(head_set) > len(base_h)
    if preserved and has_new:
        return None
    return (
        "§18 section changed vs base but NO new dated entry was added (or an existing "
        "entry was rewritten) — the Progress Log is append-only (§19). Add a new "
        "`### YYYY-MM-DD — title` entry on top instead of editing history, or revert."
    )


def extract_wikilinks(text: str) -> list[str]:
    """Return unique `[[name]]` targets (alias/anchor stripped), preserving order."""
    seen: dict[str, None] = {}
    for m in _WIKILINK_RE.finditer(text):
        name = m.group(1).strip()
        if name:
            seen.setdefault(name, None)
    return list(seen)


def build_skeleton(d: str, summary: str, pr: str | None = None) -> str:
    """Build a skeleton §18 entry block for the `append` subcommand."""
    pr_line = f" (PR [#{pr}](https://github.com/Alex1980Alex/1C-Framework/pull/{pr}))" if pr else ""
    return (
        f"### {d} — {summary}\n\n"
        f"**Outcome:** _<TODO: что достигнуто>_{pr_line}\n\n"
        "**Landed:**\n"
        "- _<TODO: файлы/изменения>_\n\n"
        "**Gates:** _<TODO: ruff/mypy/pytest/code-verify>_\n\n"
        "**Next priorities:** _<TODO>_\n"
    )


def insert_entry(text: str, skeleton: str) -> str:
    """Insert skeleton at the top of §18 (before the first dated entry, else after heading)."""
    m = _SECTION_HEADING_RE.search(text)
    if not m:
        raise ValueError("no §18 section found")
    sec = extract_section_18(text) or ""
    em = _ENTRY_RE.search(sec)
    if em:
        insert_at = m.start() + em.start()
    else:
        line_end = text.find("\n", m.start())
        insert_at = (line_end + 1) if line_end != -1 else m.end()
    block = skeleton if skeleton.endswith("\n\n") else skeleton.rstrip("\n") + "\n\n"
    return text[:insert_at] + block + text[insert_at:]


# ── git / fs layer ────────────────────────────────────────────────────────────


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def _roadmap_files() -> list[Path]:
    """Roadmaps whose §18 is a heading-based dated Progress Log (≥1 `### YYYY-MM-DD`).

    Deliberately scoped to the 260523 convention. Roadmaps using §18 for a Changelog
    or a table-based (`| Дата | Phase |`) log are NOT this tooling's concern → skipped,
    not failed.
    """
    if not ROADMAP_DIR.exists():
        return []
    out: list[Path] = []
    for p in sorted(ROADMAP_DIR.glob("*.md")):
        sec = extract_section_18(_read(p))
        if sec and parse_entries(sec):
            out.append(p)
    return out


def _git_show(ref: str, rel_path: str) -> str | None:
    """Return file content at `ref:rel_path`, or None if unavailable."""
    try:
        r = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


# ── subcommands ────────────────────────────────────────────────────────────────


def cmd_lint(args: argparse.Namespace) -> int:
    today = date.today() if args.today is None else datetime.strptime(args.today, "%Y-%m-%d").date()
    files = _roadmap_files()
    report: dict[str, list[str]] = {}
    rc = 0

    for p in files:
        rel = p.relative_to(PROJECT_ROOT).as_posix()
        head_text = _read(p)
        section = extract_section_18(head_text)
        problems = validate_structure(section or "", today)

        if not args.no_freshness and args.base:
            base_text = _git_show(args.base, rel)
            if base_text is None:
                problems.append(f"[freshness skipped: base ref '{args.base}' unavailable]")
            else:
                fp = freshness_problem(base_text, head_text)
                if fp:
                    problems.append(fp)

        # "[freshness skipped...]" is advisory, not a failure.
        hard = [x for x in problems if not x.startswith("[freshness skipped")]
        report[rel] = problems
        if hard:
            rc = 1

    if args.json:
        print(json.dumps({"ok": rc == 0, "roadmaps": report}, ensure_ascii=False, indent=2))
    else:
        if not files:
            print("[roadmap-lint] no roadmaps with §18 found — nothing to check")
        for rel, probs in report.items():
            hard = [x for x in probs if not x.startswith("[freshness skipped")]
            print(f"[roadmap-lint] {'FAIL' if hard else 'OK'} {rel}")
            for x in probs:
                print(f"    - {x}")
    return rc


def cmd_append(args: argparse.Namespace) -> int:
    target = Path(args.roadmap) if args.roadmap else None
    if target is None:
        files = _roadmap_files()
        if len(files) != 1:
            print(
                f"[roadmap-append] {len(files)} roadmaps with §18 found — specify --roadmap <file>",
                file=sys.stderr,
            )
            return 2
        target = files[0]
    if not target.exists():
        print(f"[roadmap-append] not found: {target}", file=sys.stderr)
        return 2

    d = args.date or date.today().isoformat()
    if _parse_date(d) is None:
        print(f"[roadmap-append] invalid --date: {d}", file=sys.stderr)
        return 2

    text = _read(target)
    skeleton = build_skeleton(d, args.summary, args.pr)
    try:
        new_text = insert_entry(text, skeleton)
    except ValueError as e:
        print(f"[roadmap-append] {e}", file=sys.stderr)
        return 2

    if args.apply:
        target.write_text(new_text, encoding="utf-8")
        print(f"[roadmap-append] inserted skeleton entry {d} into {target.name}")
    else:
        print("[roadmap-append] DRY-RUN (use --apply to write). Skeleton:\n")
        print(skeleton)
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    """Validate `[[name]]` memory wikilinks across roadmaps against the memory store.

    Advisory by default: the memory dir is local-only (absent in CI) → graceful skip,
    rc 0. `--strict` makes broken links a hard failure (rc 1) for local use.
    """
    mem_dir = Path(args.memory_dir) if args.memory_dir else _DEFAULT_MEMORY_DIR
    if not mem_dir.exists():
        print(f"[roadmap-links] memory dir not found ({mem_dir}) — skipped (advisory)")
        return 0

    files = sorted(ROADMAP_DIR.glob("*.md")) if ROADMAP_DIR.exists() else []
    broken: dict[str, list[str]] = {}
    for p in files:
        rel = p.relative_to(PROJECT_ROOT).as_posix()
        mem_links = [n for n in extract_wikilinks(_read(p)) if _MEMORY_NAME_RE.match(n)]
        bad = [n for n in mem_links if not (mem_dir / f"{n}.md").exists()]
        if bad:
            broken[rel] = bad

    if args.json:
        print(json.dumps({"ok": not broken, "broken": broken}, ensure_ascii=False, indent=2))
    elif not broken:
        print("[roadmap-links] OK — all memory wikilinks resolve")
    else:
        for rel, names in broken.items():
            print(f"[roadmap-links] {rel}: {len(names)} broken `[[...]]`")
            for n in names:
                print(f"    - [[{n}]] → missing {n}.md")

    return 1 if (broken and args.strict) else 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1251 → non-cp1251 chars (→, §, em-dash, `[[...]]`)
    # raise UnicodeEncodeError. Force UTF-8 stdout (project convention).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="§18 Progress Log tooling (roadmap 260523 §19)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("lint", help="validate §18 structure (+ optional PR freshness)")
    lp.add_argument(
        "--base", default="", help="git ref to compare for freshness (e.g. origin/master)"
    )
    lp.add_argument("--no-freshness", action="store_true", help="structural checks only")
    lp.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD, for tests)")
    lp.add_argument("--json", action="store_true")
    lp.set_defaults(func=cmd_lint)

    apnd = sub.add_parser("append", help="insert skeleton dated entry at top of §18")
    apnd.add_argument("--date", default=None, help="entry date YYYY-MM-DD (default: today)")
    apnd.add_argument("--summary", required=True, help="one-line entry title")
    apnd.add_argument("--pr", default=None, help="PR number to link")
    apnd.add_argument(
        "--roadmap", default=None, help="target roadmap file (default: the sole §18 roadmap)"
    )
    apnd.add_argument("--apply", action="store_true", help="write the file (default: dry-run)")
    apnd.set_defaults(func=cmd_append)

    lk = sub.add_parser("links", help="validate [[name]] memory wikilinks (advisory)")
    lk.add_argument(
        "--memory-dir",
        default=None,
        help="memory store dir (default: ~/.claude/projects/C--1--Framework/memory)",
    )
    lk.add_argument("--strict", action="store_true", help="exit 1 on broken links")
    lk.add_argument("--json", action="store_true")
    lk.set_defaults(func=cmd_links)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
