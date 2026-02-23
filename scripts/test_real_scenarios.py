#!/usr/bin/env python3
"""Real-World Scenario Tests for Code Skill Enforcer.

20 E2E scenarios testing the enforcer via subprocess with realistic inputs.
Each scenario sends real-world code to the hook and validates the response.

Usage:
    python scripts/test_real_scenarios.py           # run all
    python scripts/test_real_scenarios.py --verbose  # show details
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = PROJECT_ROOT / ".claude" / "hooks" / "code-skill-enforcer.py"
PYTHON_EXE = sys.executable


def run_hook(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the hook with input and return result."""
    try:
        start = time.perf_counter()
        result = subprocess.run(
            [PYTHON_EXE, str(HOOK_PATH)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(HOOK_PATH.parent),
        )
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "elapsed_ms": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Timeout", "elapsed_ms": 10000}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "elapsed_ms": 0}


# --- Scenario definitions ---

SCENARIOS = [
    # (name, input_data, expected_exit, expected_in_stdout, level)
    (
        "Write LangGraph StateGraph",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "agent.py", "content": "from langgraph.graph import StateGraph\ngraph = StateGraph(AgentState)"}},
        2, "SKILL REQUIRED", "A content"
    ),
    (
        "Edit QdrantClient",
        {"detected_event": "PreToolUse", "tool_name": "Edit",
         "tool_input": {"file_path": "store.py", "old_string": "x", "new_string": "client = QdrantClient(url='localhost')"}},
        2, "SKILL REQUIRED", "A content"
    ),
    (
        "Write in .claude/hooks/",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "D:/1C-Framework/.claude/hooks/my-hook.py", "content": "class MyHook: pass"}},
        2, "create-hook", "B directory"
    ),
    (
        "Write in .claude/skills/",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "D:/1C-Framework/.claude/skills/new/SKILL.md", "content": "# My Skill\nSome content here for the skill file"}},
        2, "create-skill", "B directory"
    ),
    (
        "Bash docker compose",
        {"detected_event": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "docker compose up -d"}},
        2, "deployment", "C bash"
    ),
    (
        "Bash kubectl apply",
        {"detected_event": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "kubectl apply -f deployment.yaml"}},
        2, "kubernetes", "C bash"
    ),
    (
        "Bash pytest",
        {"detected_event": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "pytest tests/ -v --cov"}},
        2, "testing", "C bash"
    ),
    (
        "Write simple Python",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "test.py", "content": "def hello():\n    print('hello world')\n    return 42"}},
        0, None, "none"
    ),
    (
        "Bash ls -la",
        {"detected_event": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "ls -la"}},
        0, None, "none"
    ),
    (
        "Write FastAPI import",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "api.py", "content": "from fastapi import APIRouter\nrouter = APIRouter(prefix='/api')"}},
        0, "Research Protocol", "D research"
    ),
    (
        "Write 1C query language",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "query.bsl", "content": "Запрос = Новый Запрос;\nЗапрос.Текст = \"ВЫБРАТЬ СУММА(Количество) ИЗ РегистрНакопления\""}},
        2, "SKILL REQUIRED", "A content"
    ),
    (
        "Write 1C document posting",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "posting.bsl", "content": "Процедура ОбработкаПроведения(Отказ, РежимПроведения)\n    Движения.Выполнить();\nКонецПроцедуры"}},
        2, "SKILL REQUIRED", "A content"
    ),
    (
        "Write Dockerfile (M7)",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "Dockerfile", "content": "FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt"}},
        0, "Research Protocol", "D research"
    ),
    (
        "Write @pytest.fixture (M7)",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "conftest.py", "content": "import pytest\n\n@pytest.fixture\ndef db_session():\n    yield session\n    session.close()"}},
        0, "Research Protocol", "D research"
    ),
    (
        "Write GitHub Actions (M7)",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": ".github/workflows/ci.yml", "content": "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest"}},
        2, "ci-cd", "B directory"
    ),
    (
        "Write 1C managed form",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "form.bsl", "content": "Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)\n    Формат(42, \"ЧДЦ=2\");\n    СтрШаблон(\"%1 - %2\", а, б);\nКонецПроцедуры"}},
        2, "SKILL REQUIRED", "A content"
    ),
    (
        "POST WebSearch",
        {"detected_event": "PostToolUse", "tool_name": "WebSearch",
         "tool_input": {"query": "qdrant collection create API"}},
        0, "RESEARCH CACHE", "D cache"
    ),
    (
        "Write enforcer itself (exclude_files)",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "D:/1C-Framework/.claude/hooks/code-skill-enforcer.py",
                        "content": "class CodeSkillEnforcer(BaseHook): pass"}},
        0, None, "exclude_files"
    ),
    (
        "Write < 20 chars",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {"file_path": "test.py", "content": "x = 1"}},
        0, None, "short"
    ),
    (
        "Empty JSON input",
        {"detected_event": "PreToolUse", "tool_name": "Write",
         "tool_input": {}},
        0, None, "graceful"
    ),
]


def run_scenarios(verbose: bool = False) -> tuple:
    """Run all scenarios, return (passed, failed, results)."""
    passed = 0
    failed = 0
    results = []
    latencies = []

    for name, input_data, expected_exit, expected_text, level in SCENARIOS:
        result = run_hook(input_data)
        latencies.append(result["elapsed_ms"])

        exit_ok = result["exit_code"] == expected_exit
        text_ok = True
        if expected_text:
            text_ok = expected_text in result["stdout"]

        success = exit_ok and text_ok
        status = "[PASS]" if success else "[FAIL]"

        if success:
            passed += 1
        else:
            failed += 1

        results.append({
            "name": name,
            "level": level,
            "success": success,
            "exit_code": result["exit_code"],
            "expected_exit": expected_exit,
            "elapsed_ms": round(result["elapsed_ms"], 1),
        })

        if verbose or not success:
            print(f"{status} #{len(results):2d} {name} (level={level})")
            if not exit_ok:
                print(f"       Expected exit {expected_exit}, got {result['exit_code']}")
            if not text_ok:
                print(f"       Expected '{expected_text}' in stdout")
                if verbose:
                    print(f"       stdout: {result['stdout'][:150]}")
            if verbose and success:
                print(f"       exit={result['exit_code']}, {result['elapsed_ms']:.0f}ms")

    return passed, failed, results, latencies


def main():
    parser = argparse.ArgumentParser(description="Real-World Scenario Tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all results")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not HOOK_PATH.exists():
        print(f"[FAIL] Hook not found: {HOOK_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("Real-World Scenarios: Code Skill Enforcer")
    print("=" * 60)

    passed, failed, results, latencies = run_scenarios(args.verbose)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passed}/{len(SCENARIOS)} passed, {failed} failed")
    if latencies:
        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        avg = sum(latencies) / len(latencies)
        print(f"LATENCY: avg={avg:.0f}ms, p95={latencies[p95_idx]:.0f}ms, max={max(latencies):.0f}ms")
    print("=" * 60)

    if args.json:
        output = {
            "passed": passed,
            "failed": failed,
            "total": len(SCENARIOS),
            "scenarios": results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
