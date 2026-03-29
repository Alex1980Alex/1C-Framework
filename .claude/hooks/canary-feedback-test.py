#!/usr/bin/env python3
"""
CANARY: Test additionalContext and exit codes for PostToolUse.
DELETE after testing.

Tests 3 feedback mechanisms:
1. stdout JSON with additionalContext (Grep trigger)
2. stdout JSON with systemMessage (Glob trigger)
3. stderr + exit 2 (Read trigger on specific file)
"""
import sys
import json

def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    tool = data.get("tool_name", "")

    # Test 1: additionalContext on Grep
    if tool == "Grep":
        result = {"additionalContext": "FEEDBACK_TEST_AC_7x8y9z: additionalContext works if you see this"}
        sys.stdout.buffer.write(json.dumps(result).encode("utf-8"))
        sys.exit(0)

    # Test 2: systemMessage on Glob
    if tool == "Glob":
        result = {"systemMessage": "FEEDBACK_TEST_SM_4a5b6c: systemMessage works if you see this"}
        sys.stdout.buffer.write(json.dumps(result).encode("utf-8"))
        sys.exit(0)

    # Test 3: stderr + exit 2 on TaskList
    if tool == "TaskList":
        sys.stderr.buffer.write(b"FEEDBACK_TEST_E2_1d2e3f: stderr+exit2 works if you see this")
        sys.exit(2)

    # Default: pass through silently
    sys.exit(0)

if __name__ == "__main__":
    main()
