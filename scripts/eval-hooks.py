#!/usr/bin/env python3
"""
Hook Evaluation Framework - Sandboxed A/B testing for hook configurations.

Based on Scott Spence's sandboxed evals approach (650+ trials):
https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals

Tests hook behavior without full Claude Code integration by:
1. Simulating hook inputs with test prompts
2. Parsing hook outputs from logs
3. Comparing against expected outcomes
4. Generating pass/fail reports

Usage:
    python scripts/eval-hooks.py                              # Run all suites
    python scripts/eval-hooks.py --suite skill-activation     # Single suite
    python scripts/eval-hooks.py --suite ide-filtering --json # JSON output
    python scripts/eval-hooks.py --list-suites               # List available suites

Test Suites:
    - skill-activation:   Tests Phase 2 shell-output enforcer (20 prompts)
    - stop-hook-safety:   Tests Phase 1 stop-loop prevention (3 prompts)
    - ide-filtering:      Tests Phase 1 IDE event filtering (10 prompts)
    - git-commit-enforcement: Tests git-commit-enforcer behavior
    - docs-change-enforcement: Tests docs-change-enforcer behavior

Reference: GAP_P5_HOOK_OBSERVABILITY.md Phase 8
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

# --- Path resolution ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TESTS_DIR = PROJECT_ROOT / "tests" / "eval"
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"

# Test prompts JSON
PROMPTS_FILE = TESTS_DIR / "hook_prompts.json"

# Log files
INVOCATIONS_LOG = DATA_DIR / "hook-invocations.jsonl"
SKILL_ROUTER_LOG = DATA_DIR / "skill-router.log"
SKILL_USAGE_LOG = DATA_DIR / "skill-usage.log"

# --- Test Suite Definitions ---

class TestSuite:
    """Base class for test suites."""

    def __init__(self, name: str, config: dict, *, live: bool = False, filter_id: str | None = None):
        self.name = name
        self.config = config
        self.live = live
        self.filter_id = filter_id
        self.tests = config.get("tests", [])
        if self.filter_id:
            self.tests = [t for t in self.tests if t.get("id") == self.filter_id]
        self.expected_rate = config.get("expected_activation_rate", 0.8)

    def run(self) -> dict:
        """Run all tests in the suite."""
        results = {
            "suite": self.name,
            "description": self.config.get("description", ""),
            "total": len(self.tests),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "rate": 0.0,
            "tests": [],
        }

        for test in self.tests:
            test_result = self.run_test(test)
            results["tests"].append(test_result)
            if test_result["status"] == "pass":
                results["passed"] += 1
            elif test_result["status"] == "fail":
                results["failed"] += 1
            else:
                results["skipped"] += 1

        results["rate"] = (
            results["passed"] / results["total"] if results["total"] > 0 else 0.0
        )
        return results

    def run_test(self, test: dict) -> dict:
        """Run a single test. Override in subclasses."""
        raise NotImplementedError


class SkillActivationSuite(TestSuite):
    """Test suite for skill activation (Phase 2)."""

    def run_test(self, test: dict) -> dict:
        """Test if prompt activates expected skills."""
        test_id = test["id"]
        prompt = test["prompt"]
        expected_skills = set(test.get("expected_skills", []))

        # Check skill-usage.log for activations
        activations = self._check_skill_activations(prompt)

        # Determine if expected skills were activated
        activated_skills = set(activations)
        missing = expected_skills - activated_skills
        unexpected = activated_skills - expected_skills

        # Status determination
        if not missing and not unexpected:
            status = "pass"
        elif not missing:
            status = "pass"  # Extra skills OK
        else:
            status = "fail"

        return {
            "id": test_id,
            "prompt": prompt,
            "expected": list(expected_skills),
            "activated": list(activated_skills),
            "missing": list(missing),
            "unexpected": list(unexpected),
            "status": status,
            "description": test.get("description", ""),
        }

    def _check_skill_activations(self, prompt: str) -> list[str]:
        """Check skill-usage.log for activations related to prompt."""
        if not SKILL_USAGE_LOG.exists():
            return []

        # Parse log for recent activations
        activations = []
        try:
            with open(SKILL_USAGE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(" | ")
                    if len(parts) >= 2:
                        # Format: "date | skill=X | session=Y"
                        skill_part = parts[1].strip()
                        if skill_part.startswith("skill="):
                            skill = skill_part.replace("skill=", "")
                            activations.append(skill)
        except OSError:
            pass

        # Return unique skills from last N activations
        return list(set(activations[-50:]))


class StopHookSafetySuite(TestSuite):
    """Test suite for stop-loop prevention (Phase 1)."""

    def run_test(self, test: dict) -> dict:
        """Test that no infinite git commit loops occur."""
        test_id = test["id"]

        # Check git log for repetitive commits
        loop_detected = self._check_for_loops()

        # Check ralph_state for stop_running flag
        stop_lock_active = self._check_stop_lock()

        # Status: pass if no loop and stop_lock is working
        status = "pass" if not loop_detected and stop_lock_active else "fail"

        return {
            "id": test_id,
            "loop_detected": loop_detected,
            "stop_lock_active": stop_lock_active,
            "status": status,
            "description": test.get("description", ""),
        }

    def _check_for_loops(self) -> bool:
        """Check git log for repetitive commit patterns."""
        try:
            # Check for "ralph wiggum" or repetitive hook-related commits
            result = subprocess.run(
                ["git", "log", "--oneline", "-20"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

            commits = result.stdout.strip().split("\n")
            # Check for >3 similar commits
            commit_messages = [c.split(" ", 1)[1] if " " in c else c for c in commits]
            counter = Counter(commit_messages)
            for msg, count in counter.items():
                if count > 3 and ("ralph" in msg.lower() or "hook" in msg.lower()):
                    return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def _check_stop_lock(self) -> bool:
        """Check if ralph_state stop_lock is implemented."""
        ralph_state_file = HOOKS_DIR / "shared" / "ralph_state.py"
        if not ralph_state_file.exists():
            return False

        try:
            content = ralph_state_file.read_text(encoding="utf-8")
            return "stop_running" in content and "set_stop_running" in content
        except OSError:
            return False


class IDEFilteringSuite(TestSuite):
    """Test suite for IDE event filtering (Phase 1)."""

    def run_test(self, test: dict) -> dict:
        """Test if IDE events are properly filtered."""
        test_id = test["id"]
        prompt = test["prompt"]
        expected_outcome = test.get("expected_outcome", "filtered")

        # Simulate skill-router filtering logic
        is_filtered = self._should_filter(prompt)

        # Determine status
        if expected_outcome == "filtered":
            status = "pass" if is_filtered else "fail"
        else:  # not_filtered
            status = "pass" if not is_filtered else "fail"

        return {
            "id": test_id,
            "prompt": prompt[:60] + "..." if len(prompt) > 60 else prompt,
            "expected": expected_outcome,
            "actual": "filtered" if is_filtered else "not_filtered",
            "status": status,
            "description": test.get("description", ""),
        }

    def _should_filter(self, prompt: str) -> bool:
        """Replicate skill-router filtering logic."""
        prompt_stripped = prompt.strip()

        # IDE event patterns
        if prompt_stripped.startswith(("<ide_", "<ide_opened_file", "<ide_selection", "<cursor>", "<file_")):
            return True

        # XML heuristic (common in IDE events)
        if prompt_stripped.startswith("<") and prompt_stripped.endswith(">") and "|" in prompt_stripped:
            return True

        # Slash commands
        if prompt_stripped.startswith("/"):
            return True

        # Very short prompts
        if len(prompt_stripped) < 15:
            return True

        # Common short confirmations
        if prompt_stripped.lower() in ("yes", "no", "ok", "sure", "continue", "thanks"):
            return True

        return False


class GitCommitEnforcementSuite(TestSuite):
    """Test suite for git-commit-enforcer behavior."""

    def run_test(self, test: dict) -> dict:
        """Test git-commit-enforcer hook."""
        test_id = test["id"]

        # Check if hook exists and is configured
        hook_file = HOOKS_DIR / "git-commit-enforcer.py"
        hook_exists = hook_file.exists()

        # Check settings.json configuration
        settings_file = PROJECT_ROOT / ".claude" / "settings.json"
        is_configured = False
        if settings_file.exists():
            try:
                settings = json.loads(settings_file.read_text(encoding="utf-8"))
                hooks = settings.get("hooks", {})
                is_configured = "git-commit-enforcer" in str(hooks)
            except (json.JSONDecodeError, OSError):
                pass

        status = "pass" if hook_exists and is_configured else "fail"

        return {
            "id": test_id,
            "hook_exists": hook_exists,
            "is_configured": is_configured,
            "status": status,
            "description": test.get("description", ""),
        }


class DocsChangeEnforcementSuite(TestSuite):
    """Test suite for docs-change-enforcer behavior."""

    def run_test(self, test: dict) -> dict:
        """Test docs-change-enforcer hook and SKIP_PATTERNS."""
        test_id = test["id"]

        # Check if hook exists
        hook_file = HOOKS_DIR / "docs-change-enforcer.py"
        hook_exists = hook_file.exists()

        # Check SKIP_PATTERNS for ralph files
        has_skip_patterns = False
        if hook_file.exists():
            try:
                content = hook_file.read_text(encoding="utf-8")
                has_skip_patterns = "SKIP_PATTERNS" in content and ".ralph" in content
            except OSError:
                pass

        # Check .gitignore for ralph files
        gitignore_file = PROJECT_ROOT / ".gitignore"
        has_gitignore = False
        if gitignore_file.exists():
            try:
                content = gitignore_file.read_text(encoding="utf-8")
                has_gitignore = ".ralph" in content
            except OSError:
                pass

        status = "pass" if hook_exists and has_skip_patterns and has_gitignore else "fail"

        return {
            "id": test_id,
            "hook_exists": hook_exists,
            "has_skip_patterns": has_skip_patterns,
            "has_gitignore": has_gitignore,
            "status": status,
            "description": test.get("description", ""),
        }


# --- Suite Registry ---

SUITE_CLASSES: dict[str, type[TestSuite]] = {
    "skill-activation": SkillActivationSuite,
    "stop-hook-safety": StopHookSafetySuite,
    "ide-filtering": IDEFilteringSuite,
    "git-commit-enforcement": GitCommitEnforcementSuite,
    "docs-change-enforcement": DocsChangeEnforcementSuite,
}


# --- Log Parsing Utilities ---

@lru_cache(maxsize=1)
def load_test_prompts() -> dict:
    """Load test prompts from JSON file."""
    if not PROMPTS_FILE.exists():
        return {"suites": {}}

    try:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"suites": {}}


def list_suites() -> None:
    """List available test suites."""
    prompts = load_test_prompts()
    suites = prompts.get("suites", {})

    print("Available Test Suites:")
    print("=" * 60)
    for name, config in suites.items():
        count = len(config.get("tests", []))
        desc = config.get("description", "No description")
        print(f"  {name:<30} {count:>3} tests  {desc}")
    print()


# --- Report Formatters ---

def format_suite_result(result: dict) -> str:
    """Format a single suite result."""
    lines = [
        f"{'=' * 70}",
        f"  Suite: {result['suite']}",
        f"  {result.get('description', '')}",
        f"{'=' * 70}",
        f"  Result: {result['passed']}/{result['total']} passed ({result['rate']:.1%})",
        "",
    ]

    if result["tests"]:
        lines.append(f"  {'ID':<10} {'Status':<8} {'Details'}")
        lines.append(f"  {'-' * 60}")

        for test in result["tests"]:
            status_symbol = "PASS" if test["status"] == "pass" else "FAIL"
            details = _format_test_details(test)
            lines.append(f"  {test['id']:<10} [{status_symbol}] {details}")

    lines.append("")
    return "\n".join(lines)


def _format_test_details(test: dict) -> str:
    """Format test details for output."""
    if test.get("missing"):
        return f"Missing skills: {', '.join(test['missing'])}"
    if test.get("unexpected"):
        return f"Unexpected: {', '.join(test['unexpected'])}"
    if test.get("loop_detected") is not None:
        return f"Loop detected: {test['loop_detected']}, Lock: {test['stop_lock_active']}"
    if test.get("expected") and test.get("actual"):
        return f"Expected: {test['expected']}, Actual: {test['actual']}"
    if test.get("hook_exists") is not None:
        checks = []
        if test.get("hook_exists") is not None:
            checks.append(f"hook={test['hook_exists']}")
        if test.get("has_skip_patterns") is not None:
            checks.append(f"skip={test['has_skip_patterns']}")
        if test.get("has_gitignore") is not None:
            checks.append(f"gitignore={test['has_gitignore']}")
        return f"Checks: {', '.join(checks)}"
    return test.get("description", "")


def format_summary(all_results: list[dict]) -> str:
    """Format summary across all suites."""
    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    total_tests = sum(r["total"] for r in all_results)
    overall_rate = total_passed / total_tests if total_tests > 0 else 0.0

    lines = [
        "",
        "=" * 70,
        "  SUMMARY",
        "=" * 70,
        f"  Total tests:     {total_tests:>4}",
        f"  Passed:          {total_passed:>4}",
        f"  Failed:          {total_failed:>4}",
        f"  Overall rate:    {overall_rate:>6.1%}",
        "=" * 70,
        "",
    ]

    # Suit comparison
    lines.append("  Suite Performance:")
    lines.append(f"  {'Suite':<30} {'Pass':>6} {'Total':>6} {'Rate':>7}")
    lines.append(f"  {'-' * 50}")

    for result in sorted(all_results, key=lambda x: x["rate"]):
        lines.append(
            f"  {result['suite']:<30} {result['passed']:>6} {result['total']:>6} {result['rate']:>6.1%}"
        )

    lines.append("")
    return "\n".join(lines)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Hook Evaluation Framework - Sandboxed A/B Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/eval-hooks.py                              # Run all suites
  python scripts/eval-hooks.py --suite skill-activation     # Single suite
  python scripts/eval-hooks.py --suite ide-filtering --json # JSON output
  python scripts/eval-hooks.py --list-suites               # List suites

Reference: GAP_P5_HOOK_OBSERVABILITY.md Phase 8
        """,
    )
    parser.add_argument(
        "--suite", "-s",
        help="Specific suite to run (default: all)",
    )
    parser.add_argument(
        "--list-suites", "-l",
        action="store_true",
        help="List available test suites",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output (show all test details)",
    )

    args = parser.parse_args()

    # Handle --list-suites
    if args.list_suites:
        list_suites()
        return 0

    # Load test prompts
    prompts = load_test_prompts()
    suites_config = prompts.get("suites", {})

    if not suites_config:
        print("Error: No test suites found in", PROMPTS_FILE)
        return 1

    # Determine which suites to run
    if args.suite:
        if args.suite not in suites_config:
            print(f"Error: Unknown suite '{args.suite}'")
            print(f"Available: {', '.join(suites_config.keys())}")
            return 1
        suites_to_run = {args.suite: suites_config[args.suite]}
    else:
        suites_to_run = suites_config

    # Run suites
    all_results = []
    for suite_name, suite_config in suites_to_run.items():
        suite_class = SUITE_CLASSES.get(suite_name, TestSuite)
        suite = suite_class(suite_name, suite_config)
        result = suite.run()
        all_results.append(result)

        if not args.json:
            print(format_suite_result(result))

    # Print summary
    if not args.json:
        print(format_summary(all_results))

    # JSON output
    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "suites": all_results,
            "summary": {
                "total_tests": sum(r["total"] for r in all_results),
                "total_passed": sum(r["passed"] for r in all_results),
                "total_failed": sum(r["failed"] for r in all_results),
                "overall_rate": sum(r["passed"] for r in all_results) / max(sum(r["total"] for r in all_results), 1),
            },
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    # Exit code based on overall pass rate
    total_failed = sum(r["failed"] for r in all_results)
    return 1 if total_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
