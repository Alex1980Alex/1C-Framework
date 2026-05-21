#!/usr/bin/env python3
"""
Hook: post-indexing-analyzer
Event: Stop
Matcher: (none)
Purpose: After indexing/graph-build scripts finish, automatically generate a
         deep analysis report. Detects new ``run_end`` entries in
         ``data/indexing-progress.jsonl`` since last fire, and spawns
         ``scripts/analyze_run.py`` (detached) for each new run_id.

Timeout: 30s
Exit codes: always 0 (informational; never blocks Stop)
Pattern: Enforcer (informational variant — system_message only, no block).

State:
  .claude/cache/post-indexing-analyzer-state.json
    {
      "processed_run_ids": ["...", ...],   # FIFO, capped at 500
      "first_seen": "<iso>",                # cold-start marker
      "last_fire": "<iso>"
    }

Cold start: on first invocation (no state file), seed the state with ALL
``run_end`` run_ids currently in the JSONL tail without analyzing them,
then emit a friendly init message. Otherwise old runs would dump a flood
of reports on first activation.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROGRESS_JSONL = PROJECT_ROOT / "data" / "indexing-progress.jsonl"
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "post-indexing-analyzer-state.json"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
ANALYZER_SCRIPT = PROJECT_ROOT / "scripts" / "analyze_run.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

TAIL_BYTES = 512 * 1024
MAX_PROCESSED = 500
MAX_FIRE_PER_INVOCATION = 5


def _read_jsonl_tail(path: Path, max_bytes: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _spawn_analyzer(run_id: str) -> bool:
    """Fire-and-forget detached subprocess. Returns True on launch success."""
    if not PYTHON_EXE.exists() or not ANALYZER_SCRIPT.exists():
        return False
    cmd = [
        str(PYTHON_EXE),
        str(ANALYZER_SCRIPT),
        "--mode",
        "indexing",
        "--run-id",
        run_id,
        "--json-only",
    ]
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS (0x00000008) | CREATE_NO_WINDOW (0x08000000)
        creationflags = 0x00000008 | 0x08000000
    try:
        log_path = REPORTS_DIR / "_analyzer.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            # Child inherits its own duplicated FD; release the parent's copy.
            log_fh.close()
        return True
    except OSError:
        return False


class PostIndexingAnalyzer(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None

        entries = _read_jsonl_tail(PROGRESS_JSONL, TAIL_BYTES)
        if not entries:
            return None

        run_ends = [e for e in entries if e.get("category") == "run_end" and e.get("run_id")]
        if not run_ends:
            return None

        state = _load_state()
        processed: list[str] = list(state.get("processed_run_ids") or [])
        processed_set = set(processed)

        # Cold-start: no prior state → seed with current run_ids, do not analyze.
        if not state:
            seed_ids = [e["run_id"] for e in run_ends]
            state = {
                "processed_run_ids": seed_ids[-MAX_PROCESSED:],
                "first_seen": datetime.now().isoformat(timespec="seconds"),
                "last_fire": datetime.now().isoformat(timespec="seconds"),
            }
            _save_state(state)
            return HookOutput().system_message(  # type: ignore[no-untyped-call]
                f"[POST-INDEXING-ANALYZER] Init: seeded {len(seed_ids)} existing run_ids "
                f"({PROGRESS_JSONL.name}). Future indexing/graph runs will auto-generate "
                f"reports in data/reports/."
            )

        new_run_ends = [e for e in run_ends if e["run_id"] not in processed_set]
        if not new_run_ends:
            return None

        new_run_ends = new_run_ends[-MAX_FIRE_PER_INVOCATION:]

        launched: list[str] = []
        failed: list[str] = []
        for end in new_run_ends:
            run_id = end["run_id"]
            ok = _spawn_analyzer(run_id)
            if ok:
                launched.append(run_id)
            else:
                failed.append(run_id)
            processed.append(run_id)

        if len(processed) > MAX_PROCESSED:
            processed = processed[-MAX_PROCESSED:]
        state["processed_run_ids"] = processed
        state["last_fire"] = datetime.now().isoformat(timespec="seconds")
        _save_state(state)

        if not launched and not failed:
            return None

        # Concise message — per CLAUDE.md "end-of-turn summary" rule
        bits: list[str] = []
        for end in new_run_ends:
            script = end.get("script", "?")
            collection = end.get("collection") or end.get("project") or "?"
            run_id = end["run_id"]
            mark = "OK" if run_id in launched else "FAIL"
            bits.append(f"  - [{mark}] `{script}` -> `{collection}` (run_id={run_id})")
        summary = (
            f"[POST-INDEXING-ANALYZER] Запущен анализ {len(launched)} нового(-ых) ран(-ов). "
            f"Отчёты появятся в `data/reports/indexing/` через ~10-30с. "
            f"Открыть последний: `data/reports/indexing/_latest_<collection>.md`.\n"
            + "\n".join(bits)
        )
        if failed:
            summary += (
                f"\nFAIL причина: python.exe или analyze_run.py не найдены ({len(failed)} run_ids)."
            )
        return HookOutput().system_message(summary)  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    PostIndexingAnalyzer().run()  # type: ignore[no-untyped-call]
