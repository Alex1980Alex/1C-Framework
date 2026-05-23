"""Pre-Work hook dispatcher (ADR-D1).

Запускает N prework workers ПАРАЛЛЕЛЬНО через asyncio.create_subprocess_exec +
asyncio.gather(return_exceptions=True). Merge результатов через
prework_aggregator. Single entry point вместо N отдельных UPS hooks
(per ADR-D1 §17.1).

Design:
- Each worker = standalone Python script в .claude/hooks/prework-*.py
- Worker reads stdin JSON, writes stdout JSON {label, items, score}
- Per-worker timeout enforced via asyncio.wait_for
- Failure isolation: worker crash → empty result, dispatcher продолжает
- Total wall-time ≈ max(worker latencies) NOT sum

References:
- ADR-D1: roadmap 260523 §17.1
- Cache: architecture-research/cache/roadmap-260523-3-decisions-2026.md
- Bench: asyncio.gather 28ms vs ThreadPool 45ms (SuperFastPython)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parent.parent
PYTHON_EXE = sys.executable

# Worker registry: (script_name, timeout_seconds, label)
# Add new prework hooks here. Order не matters (parallel execution).
WORKERS: list[tuple[str, float, str]] = [
    ("prework-architecture.py", 1.0, "ARCH"),
    # Future P1 additions:
    # ("prework-similar-code.py", 1.0, "CODE"),
    # ("prework-github-bp.py", 4.0, "GH"),
    # ("prework-stackoverflow.py", 1.0, "SO"),
]


async def _run_worker(script: str, timeout: float, label: str, payload: str) -> dict[str, Any]:
    """Run single prework worker subprocess. Returns {label, items, error?}."""
    script_path = HOOKS_DIR / script
    if not script_path.exists():
        return {"label": label, "items": [], "error": f"script not found: {script}"}
    try:
        proc = await asyncio.create_subprocess_exec(
            PYTHON_EXE,
            str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(
            proc.communicate(input=payload.encode("utf-8")),
            timeout=timeout,
        )
        if proc.returncode != 0:
            return {"label": label, "items": [], "error": f"exit {proc.returncode}"}
        try:
            data = json.loads(stdout.decode("utf-8", errors="replace") or "{}")
            return {
                "label": label,
                "items": data.get("items", []),
                "error": None,
            }
        except json.JSONDecodeError as exc:
            return {"label": label, "items": [], "error": f"bad json: {exc}"}
    except asyncio.TimeoutError:
        return {"label": label, "items": [], "error": f"timeout {timeout}s"}
    except (OSError, ValueError) as exc:
        return {"label": label, "items": [], "error": f"{type(exc).__name__}: {exc}"}


async def dispatch_all(prompt: str) -> list[dict[str, Any]]:
    """Run all registered prework workers в parallel. Returns list of results."""
    payload = json.dumps({"prompt": prompt}, ensure_ascii=False)
    tasks = [_run_worker(script, timeout, label, payload) for script, timeout, label in WORKERS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, BaseException):
            out.append({"label": "?", "items": [], "error": str(r)})
        else:
            out.append(r)
    return out


def main() -> int:
    """UPS hook entry point. Reads stdin → dispatch → stdout JSON."""
    # UTF-8 reconfigure (Windows cp1251 mitigation)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    # Read stdin payload
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    prompt = payload.get("prompt", "")
    if not prompt or len(prompt.strip()) < 10:
        # Skip too-short prompts (no signal to extract)
        sys.exit(0)

    # Skip slash-commands (already routed)
    if prompt.strip().startswith("/"):
        sys.exit(0)

    # Dispatch in parallel
    try:
        results = asyncio.run(dispatch_all(prompt))
    except Exception as exc:
        # Graceful: dispatcher crash → nothing injected
        print(json.dumps({"error": f"dispatcher crash: {exc}"}, ensure_ascii=False))
        sys.exit(0)

    # Aggregate + emit systemMessage
    try:
        from prework_aggregator import build_system_message
        msg = build_system_message(results)
    except ImportError:
        # Fallback: dump raw results
        msg = json.dumps({"prework_results": results}, ensure_ascii=False)

    if msg:
        # systemMessage format expected by Claude Code hooks
        print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    # Add hooks dir + shared dir to sys.path для import prework_aggregator
    sys.path.insert(0, str(HOOKS_DIR))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
