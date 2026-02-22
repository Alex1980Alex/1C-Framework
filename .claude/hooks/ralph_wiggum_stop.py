"""Ralph Wiggum Stop Hook for Claude Code.

When Claude tries to stop, this hook checks:
1. If Ralph is not active — always allow stop (don't interfere)
2. If stale activation (>2h) — auto-deactivate, allow stop
3. If max iterations reached — force deactivate, allow stop
4. If RALPH_DONE marker found — deactivate, allow stop
5. If structured criteria all met — deactivate, allow stop
6. If pending mandatory tasks in hook-todos.json — block stop
7. If incomplete signals found — block stop
8. If early iterations (<=3) — block stop
9. Else — allow stop

Exit codes:
  0 = allow stop
  2 = block stop (continue working)
"""

import json
import os
import sys

# Core path resolution: find base/ and shared/ regardless of hook location
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# Check user-level first, then local
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _THIS_DIR)

COMPLETION_MARKERS = ["RALPH_DONE", "TASK_COMPLETE_OK", "ALL_DONE"]

INCOMPLETE_SIGNALS = [
    "todo",
    "fixme",
    "need to",
    "will implement",
    "next step",
    "pending",
    "will continue",
    "need to register",
    "need to test",
    "need to save",
    "need to update",
]

COMPLETION_SIGNALS = [
    "all criteria met",
    "task completed",
    "all tests pass",
    "все критерии выполнены",
    "задача завершена",
]

# Mandatory hooks whose pending tasks block stop
MANDATORY_HOOKS = {
    "knowledge-cache-reminder-hook",
    "factory-enforcer-hook",
}

# Criteria → transcript signals mapping
CRITERIA_SIGNAL_MAP = {
    "cache saved": ["cache", "saved", "кеш", "сохранен", "cached"],
    "_index.json updated": ["_index.json", "index updated", "индекс обновлен"],
    "settings.json updated": ["settings.json"],
    "MEMORY.md updated": ["memory.md", "memory updated"],
    "test passed": [
        "test pass", "tests pass", "тест пройден", "pass",
        "all tests", "7/7", "verified",
    ],
    "all files created": ["created", "написан", "создан"],
    "tests pass": ["test pass", "tests pass", "verified"],
    "all listed items completed": ["completed", "завершен", "done"],
    "all tasks completed": ["completed", "завершен", "done"],
    "comparison table created": [
        "comparison", "таблица", "matrix", "pros", "cons", "сравнение",
    ],
    "recommendation given": [
        "recommendation", "рекомендация", "выбран", "recommend", "chosen",
    ],
}

def _find_hook_todos():
    """Find hook-todos.json via core_paths or fallback."""
    try:
        from shared.core_paths import get_cache_dir
        return str(get_cache_dir() / "hook-todos.json")
    except ImportError:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "cache", "hook-todos.json"
        )


HOOK_TODOS_PATH = _find_hook_todos()


def _get_pending_mandatory_tasks() -> list[str]:
    """Read hook-todos.json and return pending mandatory task titles."""
    try:
        with open(HOOK_TODOS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        todos = data.get("todos", [])
        return [
            t.get("content", "unknown")
            for t in todos
            if t.get("status") == "pending"
            and t.get("createdBy") in MANDATORY_HOOKS
        ]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def _check_criteria(combined: str, criteria: dict) -> tuple[bool, list[str]]:
    """Check structured criteria against transcript.

    Returns (all_met, unmet_criteria_list).
    """
    completion_criteria = criteria.get("completion_criteria", [])
    if not completion_criteria:
        return True, []

    unmet = []
    for criterion in completion_criteria:
        signals = CRITERIA_SIGNAL_MAP.get(criterion, [criterion.lower()])
        if not any(s in combined for s in signals):
            unmet.append(criterion)

    return len(unmet) == 0, unmet


def _block(count: int, max_iter: int, reason: str) -> None:
    """Block stop with formatted message."""
    msg = f"[RALPH] Iteration {count}/{max_iter}. {reason}"
    print(json.dumps({"decision": "block", "reason": msg}))
    sys.exit(2)


def main():
    from shared.ralph_state import (
        is_active, is_stale, deactivate,
        increment_iteration, get_max_iterations, get_criteria,
        set_stop_running, clear_stop_running,
    )

    # 1. Not active → allow stop
    if not is_active():
        sys.exit(0)

    # Prevent cascade: signal other hooks that stop is running
    set_stop_running()

    # Read hook input
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        input_data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        input_data = {}

    max_iter = get_max_iterations()

    # 2. Stale activation (>2h) → auto-deactivate
    if is_stale():
        deactivate()
        sys.exit(0)

    # 3. Increment iteration, check hard limit
    count = increment_iteration()
    if count >= max_iter:
        deactivate()
        sys.exit(0)

    # Gather text to analyze
    transcript = input_data.get("transcript", "")
    reason = input_data.get("reason", "")
    combined = f"{transcript} {reason}".lower()

    # 4. Completion markers → deactivate, allow stop
    for marker in COMPLETION_MARKERS:
        if marker.lower() in combined:
            deactivate()
            sys.exit(0)

    # 5. Strong completion signals (2+) → allow stop
    completion_score = sum(1 for s in COMPLETION_SIGNALS if s in combined)
    if completion_score >= 2:
        deactivate()
        sys.exit(0)

    # 6. Structured criteria check
    criteria = get_criteria()
    if criteria:
        all_met, unmet = _check_criteria(combined, criteria)
        if all_met:
            deactivate()
            sys.exit(0)

    # 7. Pending mandatory tasks → block
    pending_tasks = _get_pending_mandatory_tasks()
    if pending_tasks:
        tasks_str = "; ".join(pending_tasks[:3])
        unmet_str = ""
        if criteria:
            _, unmet = _check_criteria(combined, criteria)
            if unmet:
                unmet_str = f" Unmet criteria: {', '.join(unmet)}."
        _block(
            count, max_iter,
            f"Pending mandatory tasks: {tasks_str}.{unmet_str} "
            "Continue working. Include RALPH_DONE when all done."
        )

    # 8. Incomplete signals → block
    incomplete_found = [s for s in INCOMPLETE_SIGNALS if s in combined]
    if incomplete_found:
        _block(
            count, max_iter,
            f"Incomplete signals: {', '.join(incomplete_found[:3])}. "
            "Continue working. Include RALPH_DONE when all done."
        )

    # 9. Early iterations without clear completion → block
    if count <= 3:
        unmet_str = ""
        if criteria:
            _, unmet = _check_criteria(combined, criteria)
            if unmet:
                unmet_str = f" Unmet: {', '.join(unmet)}."
        _block(
            count, max_iter,
            f"Task may not be complete.{unmet_str} "
            "Check all criteria. Include RALPH_DONE if done."
        )

    # 10. Later iterations with no signals → allow stop
    sys.exit(0)


if __name__ == "__main__":
    _timer = None
    try:
        from shared.invocation_logger import InvocationTimer
        _timer = InvocationTimer("ralph-wiggum-stop", event="Stop").start()
    except Exception:
        pass

    _exit_code = 0
    try:
        main()
    except SystemExit as e:
        _exit_code = e.code if e.code is not None else 0
    except Exception:
        _exit_code = 0

    # Log invocation based on exit code
    if _timer:
        outcome = "block" if _exit_code == 2 else "allow"
        _timer.log(outcome=outcome)

    # Clean up stop lock
    try:
        from shared.ralph_state import clear_stop_running
        clear_stop_running()
    except Exception:
        pass

    sys.exit(_exit_code)
