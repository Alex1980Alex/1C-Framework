#!/usr/bin/env python3
"""
Hook: tei-warmup-on-start
Event: SessionStart
Purpose:
  - Spawn a detached TEI keep-alive daemon (scripts/tei_keepalive.py) so the embedding
    path stays warm. Eliminates cold-start jitter (TEI cold ~400-600ms vs warm ~80ms)
    that pushed memory-first-hook / prework_dispatcher over their UPS timeout.
  - The daemon is single-instance (heartbeat lockfile) and bounded-lifetime, so repeated
    SessionStarts never stack duplicate daemons and it can't become a permanent orphan.
  - Detached subprocess — never blocks session bootstrap.
Timeout: 5s (hook itself; daemon runs in background).
Opt-out: env TEI_KEEPALIVE_DISABLE=1 → skip (also makes the daemon a no-op).
Graceful degradation: missing script/venv/TEI down → silent skip.
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "tei_keepalive.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


class TeiWarmupOnStart(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("TEI_KEEPALIVE_DISABLE") == "1":
            return None
        if not SCRIPT_PATH.exists() or not VENV_PYTHON.exists():
            return None

        try:
            subprocess.Popen(
                [str(VENV_PYTHON), str(SCRIPT_PATH)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(PROJECT_ROOT),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
                    if sys.platform == "win32"
                    else 0
                ),
            )
        except (OSError, ValueError):
            return None

        return HookOutput().system_message(
            "[TEI-WARMUP] keep-alive daemon spawned (bg) — embedder hot for memory-first-hook"
        )


if __name__ == "__main__":
    TeiWarmupOnStart().run()
