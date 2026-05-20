#!/usr/bin/env python3
"""openspec_jira_sync.py — JIRA bridge (skeleton).

Status: SKELETON (v0.1, 2026-05-20). Full impl deferred — см. roadmap §M.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--action", choices=("push", "pull", "status"),
                    default="status")
    ap.add_argument("--change-id", help="OpenSpec change id")
    args = ap.parse_args()

    base = os.environ.get("JIRA_BASE_URL")
    token = os.environ.get("JIRA_TOKEN")
    if not base or not token:
        print("[SKELETON] JIRA_BASE_URL/JIRA_TOKEN env-vars не заданы.",
              file=sys.stderr)
        return 1
    print(f"[SKELETON] action={args.action} change={args.change_id} jira={base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
