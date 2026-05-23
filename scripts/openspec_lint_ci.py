#!/usr/bin/env python3
"""openspec_lint_ci.py — CI-friendly линтер OpenSpec change'ей.

Используется в .github/workflows/openspec.yml и .pre-commit-config.yaml.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHANGES_ROOT = Path("openspec/changes")
JIRA_RE = re.compile(r"(GKSTCPLK-\d{3,5})", re.IGNORECASE)
REPORT_PATH = Path("openspec-lint-report.md")


@dataclass
class ChangeReport:
    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def list_active_changes() -> list[Path]:
    if not CHANGES_ROOT.exists():
        return []
    return [p for p in CHANGES_ROOT.iterdir() if p.is_dir() and p.name != "archive"]


def check_change_structure(change_dir: Path) -> ChangeReport:
    rep = ChangeReport(name=change_dir.name)
    for fname in ("proposal.md", "tasks.md", ".openspec.yaml"):
        if not (change_dir / fname).exists():
            rep.errors.append(f"missing {fname}")
    if not (change_dir / "design.md").exists():
        rep.warnings.append("missing design.md (recommended)")
    specs_dir = change_dir / "specs"
    if not specs_dir.exists() or not any(specs_dir.iterdir()):
        rep.warnings.append("missing specs/<capability>/spec.md (recommended)")
    proposal = change_dir / "proposal.md"
    if proposal.exists():
        text = proposal.read_text(encoding="utf-8", errors="replace")
        for sec in ("## Summary", "## Motivation", "## Impact"):
            if sec not in text:
                rep.warnings.append(f"proposal.md missing section: {sec}")
    return rep


def _git_run(args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args], capture_output=True, text=True, check=True
        )
        return out.stdout
    except subprocess.CalledProcessError:
        return ""


def changed_files(base: str, head: str) -> list[str]:
    out = _git_run(["diff", "--name-only", f"{base}..{head}"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def commit_messages(base: str, head: str) -> str:
    return _git_run(["log", "--format=%B", f"{base}..{head}"])


def _change_mentions(change_dir: Path, jira: str) -> bool:
    for fname in (".openspec.yaml", "proposal.md", "tasks.md"):
        p = change_dir / fname
        if not p.exists():
            continue
        body = p.read_text(encoding="utf-8", errors="replace").lower()
        if jira.lower() in body:
            return True
    return False


def coverage_check(base: str, head: str) -> tuple[list[str], list[str]]:
    files = changed_files(base, head)
    if not any("ИБTransportManagementDevelop/Конфигурация/src/" in f for f in files):
        return [], []
    jiras = {j.upper() for j in JIRA_RE.findall(commit_messages(base, head))}
    if not jiras:
        return [], []
    active = list_active_changes()
    no_change, with_change = [], []
    for jira in sorted(jiras):
        matched = any(_change_mentions(ch, jira) for ch in active)
        (with_change if matched else no_change).append(jira)
    return no_change, with_change


def render_report(structural, missing, ok_list) -> str:
    lines = ["# OpenSpec lint report", ""]
    for r in structural:
        st = "OK" if r.ok else "FAIL"
        lines.append(f"### [{st}] `{r.name}`")
        for e in r.errors:
            lines.append(f"- error: {e}")
        for w in r.warnings:
            lines.append(f"- warn: {w}")
        lines.append("")
    if missing or ok_list:
        lines.append("## PR ↔ change coverage\n")
        for j in ok_list:
            lines.append(f"- OK: {j} (active change found)")
        for j in missing:
            lines.append(f"- WARN: {j} (no active change in openspec/changes/)")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("structural", "coverage", "all"), default="structural")
    ap.add_argument("--base")
    ap.add_argument("--head")
    ap.add_argument("--fail-on-error", action="store_true")
    ap.add_argument("--warn-only", action="store_true")
    args = ap.parse_args()

    structural: list[ChangeReport] = []
    coverage_missing: list[str] = []
    coverage_ok: list[str] = []

    if args.mode in ("structural", "all"):
        structural = [check_change_structure(c) for c in list_active_changes()]
    if args.mode in ("coverage", "all") and args.base and args.head:
        coverage_missing, coverage_ok = coverage_check(args.base, args.head)

    report = render_report(structural, coverage_missing, coverage_ok)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)

    has_errors = any(not r.ok for r in structural)
    if args.warn_only:
        return 0
    return 1 if (args.fail_on_error and has_errors) else 0


if __name__ == "__main__":
    sys.exit(main())
