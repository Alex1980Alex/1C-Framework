#!/usr/bin/env python3
"""
Test Runner: Execute All Tests for Code Skill Enforcer

Runs all test suites:
1. Unit Tests (15 tests)
2. Integration Tests (6 flows)
3. E2E Scenarios (3 scenarios)

Usage:
    python run-all-tests.py
    python -m pytest run-all-tests.py -v

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

import sys
import subprocess
from pathlib import Path

# Test directory
_TESTS_DIR = Path(__file__).parent


def run_test_file(test_file: str, name: str) -> bool:
    """Run a single test file."""
    test_path = _TESTS_DIR / test_file

    if not test_path.exists():
        print(f"[FAIL] Test file not found: {test_path}")
        return False

    print(f"\n{'=' * 60}")
    print(f"Running: {name}")
    print(f"File: {test_file}")
    print('=' * 60)

    result = subprocess.run(
        [sys.executable, str(test_path)],
        cwd=str(test_path.parent),
        capture_output=False
    )

    return result.returncode == 0


def main():
    """Run all test suites."""
    print("\n" + "=" * 60)
    print("CODE SKILL ENFORCER - TEST SUITE")
    print("=" * 60)

    results = {
        "Unit Tests": run_test_file("test_code_skill_enforcer.py", "Unit Tests"),
        "Integration Tests": run_test_file("test_integration.py", "Integration Tests"),
        "E2E Scenarios": run_test_file("test_e2e.py", "E2E Scenarios"),
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)

    for name, passed in results.items():
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        print(f"{status}: {name}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
    else:
        print("⚠️ SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
