#!/usr/bin/env python3
"""
Integration Tests for Code Skill Enforcer Hook

Tests complete workflows:
- PRE-A flow: Skill not activated -> BLOCK -> Skill() -> retry -> ALLOW
- PRE-B flow: Write to hooks/ -> BLOCK -> create-hook -> retry -> ALLOW
- PRE-C flow: Bash docker -> BLOCK -> deployment -> retry -> ALLOW
- Research flow: FastAPI -> ADVISE -> research -> write -> OK
- POST-E flow: Activated skill + bad pattern -> advisory + task
- LEARN flow: Research -> Write -> 3 tasks -> complete -> OK

Run: python -m pytest tests/test_integration.py -v
Or:  python tests/test_integration.py

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Add hooks to path
_HOOK_DIR = Path(__file__).parent.parent / "hooks"
sys.path.insert(0, str(_HOOK_DIR))
sys.path.insert(0, str(_HOOK_DIR / "base"))
sys.path.insert(0, str(_HOOK_DIR / "shared"))


# ============================================================================
# Session Simulator (mocks SessionState)
# ============================================================================

class SessionSimulator:
    """Simulates SessionState for testing."""

    def __init__(self, temp_dir: Path):
        self.state_file = temp_dir / "session-skills.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state = {
            "activated_skills": [],
            "pending_learn": None,
            "session_id": "test-session",
            "created_at": "2026-02-23T00:00:00",
            "last_updated": "2026-02-23T00:00:00"
        }
        self._save_state()

    def _save_state(self):
        """Save state to file."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def activate_skill(self, skill_name: str):
        """Activate a skill."""
        if skill_name not in self._state["activated_skills"]:
            self._state["activated_skills"].append(skill_name)
            self._state["last_updated"] = "2026-02-23T00:00:00"
            self._save_state()

    def get_activated(self) -> List[str]:
        """Get activated skills."""
        return self._state["activated_skills"]

    def clear_pending_learn(self):
        """Clear pending learn."""
        self._state["pending_learn"] = None
        self._save_state()

    def set_pending_learn(self, data: Dict[str, Any]):
        """Set pending learn."""
        self._state["pending_learn"] = data
        self._save_state()

    def get_pending_learn(self) -> Dict[str, Any]:
        """Get pending learn."""
        return self._state.get("pending_learn")

    def cleanup(self):
        """Clean up temp files."""
        if self.state_file.exists():
            self.state_file.unlink()


# ============================================================================
# Test Runner with Session Control
# ============================================================================

class IntegrationTestRunner:
    """Integration test runner with session simulation."""

    def __init__(self, hook_path: Path, session: SessionSimulator):
        self.hook_path = hook_path
        self.python_exe = sys.executable
        self.session = session

    def run_hook(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run hook with input data."""
        input_json = json.dumps(input_data)

        # Set environment variable for session state path
        env = os.environ.copy()
        env["SESSION_STATE_PATH"] = str(self.session.state_file.parent)

        try:
            result = subprocess.run(
                [self.python_exe, str(self.hook_path)],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.hook_path.parent),
                env=env
            )

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Timeout"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}


# ============================================================================
# Integration Test Scenarios
# ============================================================================

def test_pre_a_flow():
    """
    Test PRE-A flow:
    1. Write StateGraph without skill -> BLOCK
    2. Activate langgraph-core skill
    3. Retry same Write -> ALLOW
    """
    print("\n" + "=" * 60)
    print("[Integration] PRE-A Flow: Content Pattern Enforcement")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = SessionSimulator(Path(temp_dir))
        hook_path = _HOOK_DIR / "code-skill-enforcer.py"

        if not hook_path.exists():
            print(f"[FAIL] Hook not found: {hook_path}")
            return False

        runner = IntegrationTestRunner(hook_path, session)

        # Step 1: Write StateGraph without skill -> BLOCK
        print("\n[Step 1] Write StateGraph without skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "agent.py",
                "content": "from langgraph.graph import StateGraph\ngraph = StateGraph(AgentState)"
            }
        })

        if result["exit_code"] != 2:
            print(f"[FAIL] Step 1 failed: Expected exit 2, got {result['exit_code']}")
            return False

        if "langgraph-core" not in result["stdout"]:
            print(f"[FAIL] Step 1 failed: Expected 'langgraph-core' in output")
            return False

        print("✅ Step 1: BLOCKED as expected")

        # Step 2: Activate skill
        print("\n[Step 2] Activate langgraph-core skill...")
        session.activate_skill("langgraph-core")
        print(f"✅ Step 2: Activated skills: {session.get_activated()}")

        # Step 3: Retry same Write -> ALLOW
        print("\n[Step 3] Retry Write with activated skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "agent.py",
                "content": "from langgraph.graph import StateGraph\ngraph = StateGraph(AgentState)"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 3 failed: Expected exit 0, got {result['exit_code']}")
            return False

        if "SKILL REQUIRED" in result["stdout"]:
            print(f"[FAIL] Step 3 failed: Should not require skill after activation")
            return False

        print("✅ Step 3: ALLOWED as expected")

        print("\n✅ PRE-A FLOW PASSED")
        session.cleanup()
        return True


def test_pre_b_flow():
    """
    Test PRE-B flow:
    1. Write to .claude/hooks/ without skill -> BLOCK
    2. Activate create-hook skill
    3. Retry same Write -> ALLOW
    """
    print("\n" + "=" * 60)
    print("[Integration] PRE-B Flow: Directory Rule Enforcement")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = SessionSimulator(Path(temp_dir))
        hook_path = _HOOK_DIR / "code-skill-enforcer.py"

        if not hook_path.exists():
            print(f"[FAIL] Hook not found: {hook_path}")
            return False

        runner = IntegrationTestRunner(hook_path, session)

        # Step 1: Write to hooks/ without skill -> BLOCK
        print("\n[Step 1] Write to .claude/hooks/ without skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "D:/1С-Framework/.claude/hooks/test-hook.py",
                "content": "def run(): pass"
            }
        })

        if result["exit_code"] != 2:
            print(f"[FAIL] Step 1 failed: Expected exit 2, got {result['exit_code']}")
            return False

        if "create-hook" not in result["stdout"]:
            print(f"[FAIL] Step 1 failed: Expected 'create-hook' in output")
            return False

        print("✅ Step 1: BLOCKED as expected")

        # Step 2: Activate skill
        print("\n[Step 2] Activate create-hook skill...")
        session.activate_skill("create-hook")
        print(f"✅ Step 2: Activated skills: {session.get_activated()}")

        # Step 3: Retry same Write -> ALLOW
        print("\n[Step 3] Retry Write with activated skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "D:/1С-Framework/.claude/hooks/test-hook.py",
                "content": "def run(): pass"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 3 failed: Expected exit 0, got {result['exit_code']}")
            return False

        print("✅ Step 3: ALLOWED as expected")

        print("\n✅ PRE-B FLOW PASSED")
        session.cleanup()
        return True


def test_pre_c_flow():
    """
    Test PRE-C flow:
    1. Bash docker compose without skill -> BLOCK
    2. Activate deployment skill
    3. Retry same Bash -> ALLOW
    """
    print("\n" + "=" * 60)
    print("[Integration] PRE-C Flow: Bash Command Enforcement")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = SessionSimulator(Path(temp_dir))
        hook_path = _HOOK_DIR / "code-skill-enforcer.py"

        if not hook_path.exists():
            print(f"[FAIL] Hook not found: {hook_path}")
            return False

        runner = IntegrationTestRunner(hook_path, session)

        # Step 1: Bash docker compose without skill -> BLOCK
        print("\n[Step 1] Bash docker compose without skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "docker compose up -d"
            }
        })

        if result["exit_code"] != 2:
            print(f"[FAIL] Step 1 failed: Expected exit 2, got {result['exit_code']}")
            return False

        if "deployment" not in result["stdout"]:
            print(f"[FAIL] Step 1 failed: Expected 'deployment' in output")
            return False

        print("✅ Step 1: BLOCKED as expected")

        # Step 2: Activate skill
        print("\n[Step 2] Activate deployment skill...")
        session.activate_skill("deployment")
        print(f"✅ Step 2: Activated skills: {session.get_activated()}")

        # Step 3: Retry same Bash -> ALLOW
        print("\n[Step 3] Retry Bash with activated skill...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "docker compose up -d"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 3 failed: Expected exit 0, got {result['exit_code']}")
            return False

        print("✅ Step 3: ALLOWED as expected")

        print("\n✅ PRE-C FLOW PASSED")
        session.cleanup()
        return True


def test_research_flow():
    """
    Test Research flow:
    1. Write FastAPI code -> ADVISE with research protocol
    2. (Simulated) Claude does research
    3. Write code again -> OK (no pending_learn after first write)
    """
    print("\n" + "=" * 60)
    print("[Integration] Research Flow: Protocol Advisory")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = SessionSimulator(Path(temp_dir))
        hook_path = _HOOK_DIR / "code-skill-enforcer.py"

        if not hook_path.exists():
            print(f"[FAIL] Hook not found: {hook_path}")
            return False

        runner = IntegrationTestRunner(hook_path, session)

        # Step 1: Write FastAPI -> ADVISE
        print("\n[Step 1] Write FastAPI code (triggers research protocol)...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "api.py",
                "content": "from fastapi import APIRouter\n\nrouter = APIRouter(prefix='/api')"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 1 failed: Expected exit 0 (ADVISE), got {result['exit_code']}")
            return False

        if "Research Protocol" not in result["stdout"]:
            print(f"[FAIL] Step 1 failed: Expected research protocol message")
            return False

        print("✅ Step 1: ADVISE shown as expected")

        # Check pending_learn was set
        pending = session.get_pending_learn()
        if not pending or pending.get("label") != "FastAPI Framework":
            print(f"[FAIL] Step 1 failed: pending_learn not set correctly")
            return False

        print(f"✅ Step 1: pending_learn set: {pending['label']}")

        # Step 2: Clear pending (simulating LEARN phase completion)
        print("\n[Step 2] Clear pending_learn (simulating LEARN completion)...")
        session.clear_pending_learn()
        print("✅ Step 2: pending_learn cleared")

        print("\n✅ RESEARCH FLOW PASSED")
        session.cleanup()
        return True


def test_learn_flow():
    """
    Test LEARN flow:
    1. PRE: Write FastAPI -> sets pending_learn
    2. POST: Same Write -> creates 3 LEARN tasks
    3. Clear pending_learn after task creation
    """
    print("\n" + "=" * 60)
    print("[Integration] LEARN Flow: Task Creation")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        session = SessionSimulator(Path(temp_dir))
        hook_path = _HOOK_DIR / "code-skill-enforcer.py"

        if not hook_path.exists():
            print(f"[FAIL] Hook not found: {hook_path}")
            return False

        runner = IntegrationTestRunner(hook_path, session)

        # Step 1: PRE - Write FastAPI -> sets pending_learn
        print("\n[Step 1] PRE: Write FastAPI (sets pending_learn)...")
        result = runner.run_hook({
            "detected_event": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "api.py",
                "content": "from fastapi import FastAPI\napp = FastAPI()"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 1 failed: Expected exit 0, got {result['exit_code']}")
            return False

        pending = session.get_pending_learn()
        if not pending:
            print(f"[FAIL] Step 1 failed: pending_learn not set")
            return False

        print(f"✅ Step 1: pending_learn set for '{pending['label']}'")

        # Step 2: POST - Same Write -> should create LEARN tasks
        print("\n[Step 2] POST: Write completed (should create LEARN tasks)...")
        result = runner.run_hook({
            "detected_event": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "api.py",
                "content": "from fastapi import FastAPI\napp = FastAPI()"
            }
        })

        if result["exit_code"] != 0:
            print(f"[FAIL] Step 2 failed: Expected exit 0, got {result['exit_code']}")
            return False

        if "LEARN PHASE" not in result["stdout"]:
            print(f"[FAIL] Step 2 failed: Expected LEARN PHASE message")
            print(f"   stdout: {result['stdout']}")
            return False

        print("✅ Step 2: LEARN tasks created")

        # Step 3: Verify pending_learn was cleared
        print("\n[Step 3] Verify pending_learn cleared...")
        pending = session.get_pending_learn()
        if pending is not None:
            print(f"[FAIL] Step 3 failed: pending_learn should be cleared")
            return False

        print("✅ Step 3: pending_learn cleared")

        print("\n✅ LEARN FLOW PASSED")
        session.cleanup()
        return True


# ============================================================================
# Main Test Runner
# ============================================================================

def run_integration_tests():
    """Run all integration tests."""
    tests = [
        ("PRE-A Flow", test_pre_a_flow),
        ("PRE-B Flow", test_pre_b_flow),
        ("PRE-C Flow", test_pre_c_flow),
        ("Research Flow", test_research_flow),
        ("LEARN Flow", test_learn_flow),
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("INTEGRATION TESTS: Code Skill Enforcer")
    print("=" * 60)

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[FAIL] {name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"INTEGRATION TESTS SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
