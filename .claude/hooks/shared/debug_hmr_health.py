"""Shared helper: probe 1c-debug-hmr readiness via the smoke-test script.

Both `implement-1c-task-preflight.py` and `analyze-1c-task-preflight.py` need
the same answer: "is 1c-debug-hmr reachable, and what pipeline mode is the
environment in?". This helper centralizes the probe to keep the two hooks in
sync — change the probe protocol here and both hooks pick it up.

Roadmap: docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md §5.1
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _HOOKS_DIR.parent.parent
SMOKE_TEST_SCRIPT = PROJECT_ROOT / "scripts" / "smoke_test_implement_1c_task.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

DEFAULT_TIMEOUT = 25  # seconds; matches existing implement-1c-task-preflight budget


@dataclass
class DebugHmrProbeResult:
    """Outcome of the probe.

    Attributes mirror the smoke-test --json shape that hooks consume.
    """

    ok: bool = False
    mode: str = "unknown"
    exit_code: int = -1
    debug_hmr_ready: bool = False
    failed_handshakes: list = field(default_factory=list)
    error: str | None = None


def probe_debug_hmr_ready(timeout: int = DEFAULT_TIMEOUT) -> DebugHmrProbeResult:
    """Run smoke_test_implement_1c_task.py --json, extract debug-hmr readiness.

    Returns a DebugHmrProbeResult. On any error (missing script, timeout, JSON
    decode failure, spawn error) returns ok=False with error populated — hooks
    decide whether to surface as warning or skip.
    """
    if not SMOKE_TEST_SCRIPT.exists():
        return DebugHmrProbeResult(
            error=f"smoke-test script missing: {SMOKE_TEST_SCRIPT.relative_to(PROJECT_ROOT)}"
        )

    python = str(PYTHON_EXE) if PYTHON_EXE.exists() else sys.executable

    try:
        proc = subprocess.run(
            [python, str(SMOKE_TEST_SCRIPT), "--json"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return DebugHmrProbeResult(error=f"smoke-test timed out after {timeout}s")
    except Exception as exc:
        return DebugHmrProbeResult(error=f"{type(exc).__name__}: {exc}")

    try:
        data = json.loads(proc.stdout) if proc.stdout else None
    except (json.JSONDecodeError, ValueError) as exc:
        return DebugHmrProbeResult(
            exit_code=proc.returncode,
            error=f"json decode: {exc}",
        )

    if not data:
        return DebugHmrProbeResult(
            exit_code=proc.returncode,
            error="empty smoke-test output",
        )

    mcp_health = data.get("mcp_health") or {}
    return DebugHmrProbeResult(
        ok=True,
        mode=data.get("mode", "unknown"),
        exit_code=proc.returncode,
        debug_hmr_ready=bool(mcp_health.get("debug_hmr")),
        failed_handshakes=_extract_failed_handshakes(data),
    )


def _extract_failed_handshakes(data: dict) -> list:
    """Pick names + details of handshakes that failed."""
    out = []
    for h in data.get("handshakes") or []:
        if not h.get("ok"):
            name = h.get("name", "?")
            detail = h.get("detail", "")
            out.append(f"{name} ({detail})" if detail else name)
    return out
