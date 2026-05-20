#!/usr/bin/env python3
"""smoke_test_openspec.py — preflight для OpenSpec workflow."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("openspec")
REQUIRED_TOP = ("AGENTS.md", "project.md", "config.yaml")
REQUIRED_DIRS = ("changes", "profiles")
REQUIRED_CHANGE_FILES = ("proposal.md", "tasks.md", ".openspec.yaml")


def check_top() -> list[str]:
    issues: list[str] = []
    if not ROOT.exists():
        return ["openspec/ root missing — run openspec init or create manually"]
    for fname in REQUIRED_TOP:
        if not (ROOT / fname).exists():
            issues.append(f"openspec/{fname} missing")
    for dname in REQUIRED_DIRS:
        if not (ROOT / dname).is_dir():
            issues.append(f"openspec/{dname}/ missing")
    return issues


def check_changes() -> tuple[list[str], list[str]]:
    issues: list[str] = []
    found: list[str] = []
    changes_dir = ROOT / "changes"
    if not changes_dir.exists():
        return ["openspec/changes/ missing"], []
    for ch in changes_dir.iterdir():
        if not ch.is_dir() or ch.name == "archive":
            continue
        found.append(ch.name)
        for fname in REQUIRED_CHANGE_FILES:
            if not (ch / fname).exists():
                issues.append(f"{ch.name}/{fname} missing")
    return issues, found


def check_lint() -> tuple[int, str]:
    try:
        out = subprocess.run(
            [sys.executable, "scripts/openspec_lint_ci.py", "--mode",
             "structural"], capture_output=True, text=True, timeout=30)
        return out.returncode, out.stdout[-200:]
    except Exception as e:
        return 2, f"lint failed: {e}"
