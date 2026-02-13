"""Ralph Wiggum Stop Hook for Claude Code.

When Claude tries to stop, this hook checks:
1. If RALPH_ACTIVE flag file exists — we're in a Ralph loop, apply full logic
2. If not in Ralph loop — always allow stop (don't interfere with normal sessions)

Exit codes:
  0 = allow stop
  2 = block stop (continue working)
"""
import json
import os
import sys

# Configuration
MAX_ITERATIONS = 15
COMPLETION_MARKERS = ["RALPH_DONE", "TASK_COMPLETE_OK", "ALL_DONE"]

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
ITERATION_FILE = os.path.join(HOOK_DIR, ".ralph_wiggum_count")
ACTIVE_FILE = os.path.join(HOOK_DIR, ".ralph_active")

# Incomplete work signals (case-insensitive)
INCOMPLETE_SIGNALS = [
    "todo",
    "fixme",
    "need to",
    "will implement",
    "next step",
    "pending",
    "will continue",
]

# Signals that the task is truly complete
COMPLETION_SIGNALS = [
    "all criteria met",
    "task completed",
    "all tests pass",
]


def is_ralph_active() -> bool:
    """Check if we're inside a Ralph Wiggum loop."""
    return os.path.exists(ACTIVE_FILE)


def get_iteration_count() -> int:
    try:
        with open(ITERATION_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def set_iteration_count(count: int) -> None:
    os.makedirs(HOOK_DIR, exist_ok=True)
    with open(ITERATION_FILE, "w") as f:
        f.write(str(count))


def main():
    # If NOT in a Ralph loop — always allow stop, don't interfere
    if not is_ralph_active():
        sys.exit(0)

    # Read hook input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        input_data = {}

    # Increment iteration counter
    count = get_iteration_count() + 1
    set_iteration_count(count)

    # Safety: hard limit
    if count >= MAX_ITERATIONS:
        set_iteration_count(0)
        try:
            os.remove(ACTIVE_FILE)
        except OSError:
            pass
        sys.exit(0)

    # Gather text to analyze
    transcript = input_data.get("transcript", "")
    reason = input_data.get("reason", "")
    combined = f"{transcript} {reason}".lower()

    # Check 1: Completion marker → allow stop
    for marker in COMPLETION_MARKERS:
        if marker.lower() in combined:
            set_iteration_count(0)
            try:
                os.remove(ACTIVE_FILE)
            except OSError:
                pass
            sys.exit(0)

    # Check 2: Strong completion signals (2+) → allow stop
    completion_score = sum(1 for s in COMPLETION_SIGNALS if s in combined)
    if completion_score >= 2:
        set_iteration_count(0)
        try:
            os.remove(ACTIVE_FILE)
        except OSError:
            pass
        sys.exit(0)

    # Check 3: Incomplete signals → block stop
    incomplete_found = [s for s in INCOMPLETE_SIGNALS if s in combined]
    if incomplete_found:
        msg = (
            f"Incomplete tasks found (iteration {count}/{MAX_ITERATIONS}). "
            f"Signals: {', '.join(incomplete_found[:3])}. "
            "Continue working. When ALL criteria are met, include marker: RALPH_DONE"
        )
        print(json.dumps({"decision": "block", "reason": msg}))
        sys.exit(2)

    # Check 4: Early iterations without clear completion → block
    if count <= 3:
        msg = (
            f"Iteration {count}/{MAX_ITERATIONS}. "
            "Task may not be fully complete. Check all completion criteria. "
            "If done, include marker: RALPH_DONE"
        )
        print(json.dumps({"decision": "block", "reason": msg}))
        sys.exit(2)

    # Later iterations with no signals → allow stop
    sys.exit(0)


if __name__ == "__main__":
    main()
