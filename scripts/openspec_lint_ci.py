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
    return [p for p in CHANGES_ROOT.iterdir()
            if p.is_dir() and p.name != "archive"]


def check_change_structure(change_dir: Path) -> ChangeReport:
    rep = ChangeReport(name=change_dir.name)
    for fname in ("proposal.md", "tasks.md", ".openspec.yaml"):
        if not (change_dir / fname).exists():
            rep.errors.append(f"missing {fname}")
