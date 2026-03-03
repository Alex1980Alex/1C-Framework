#!/usr/bin/env python3
"""End-to-end tests for LEARN cycle: Level A.1 BLOCK → Skill('learning-loop') → dedup."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

PYTHON = sys.executable
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENFORCER = os.path.join(PROJECT_DIR, ".claude", "hooks", "code-skill-enforcer.py")

passed = 0
failed = 0


def make_env(state_dir):
    return {
        **os.environ,
        "SESSION_STATE_PATH": state_dir,
        "PYTHONIOENCODING": "utf-8",
    }


def run_hook(input_data, env):
    result = subprocess.run(
        [PYTHON, ENFORCER],
        input=json.dumps(input_data, ensure_ascii=False),
        capture_output=True, text=True, timeout=10,
        env=env, encoding="utf-8", errors="replace",
    )
    return result


def read_state(state_dir):
    state_file = os.path.join(state_dir, "session-skills.json")
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")


def fresh_env():
    d = tempfile.mkdtemp(prefix="learn_test_")
    return d, make_env(d)


def is_json_block(result):
    """Check if hook output is a JSON block (protocol.py style)."""
    stdout = result.stdout or ""
    return '"decision": "block"' in stdout or '"continue": false' in stdout


def parse_stdout(result):
    """Parse JSON stdout from hook."""
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}


# =========================================================================
print("=" * 60)
print("TEST 1: FastAPI code triggers BLOCK with learning-loop instruction")
print("=" * 60)

tmp, env = fresh_env()
result = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": (
            "from fastapi import FastAPI, APIRouter, HTTPException\n"
            "app = FastAPI(title='My API')\n"
            "router = APIRouter(prefix='/api/v1')\n"
        ),
    }
}, env)
state = read_state(tmp)
blocked = is_json_block(result)
out = parse_stdout(result)
activated = state.get("activated_skills", [])
test("BLOCK output", blocked,
     f"stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("reason mentions learning-loop", "learning-loop" in out.get("reason", ""),
     f"reason={out.get('reason', '')[:100]}")
test("activated_skills contains learn:fastapi-framework",
     "learn:fastapi-framework" in activated,
     f"activated={activated}")
test("pending_learn is set as backup",
     state.get("pending_learn") is not None)
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 2: Level F advisory after A.1 block (clears pending_learn)")
print("=" * 60)

tmp, env = fresh_env()
# Step 1: PRE — A.1 blocks and sets learn:fastapi-framework + pending_learn
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI()",
    }
}, env)
state1 = read_state(tmp)
test("pending_learn set after PRE block", state1.get("pending_learn") is not None)
test("learn:fastapi-framework in activated",
     "learn:fastapi-framework" in state1.get("activated_skills", []))

# Step 2: POST — Level F should detect pending_learn + learn:X activated → clear
result2 = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": "from fastapi import FastAPI",
    },
    "tool_result": "File written successfully",
}, env)
state2 = read_state(tmp)
test("pending_learn cleared by Level F (learn:X was activated)",
     state2.get("pending_learn") is None,
     f"pending_learn={state2.get('pending_learn')}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 3: Redis code triggers BLOCK")
print("=" * 60)

tmp, env = fresh_env()
result = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/cache/redis_cache.py",
        "content": (
            "import aioredis\n"
            "from redis import Redis\n"
            "class RedisCache:\n"
            "    def __init__(self):\n"
            "        self.client = Redis.from_url('redis://localhost')\n"
        ),
    }
}, env)
state = read_state(tmp)
blocked = is_json_block(result)
activated = state.get("activated_skills", [])
test("BLOCK output", blocked,
     f"stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("activated_skills contains learn:redis-caching",
     "learn:redis-caching" in activated,
     f"activated={activated}")
test("pending_learn label = Redis Caching",
     state.get("pending_learn", {}).get("label") == "Redis Caching")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 4: 1C Metadata triggers BLOCK (1c domain)")
print("=" * 60)

# Content must match research_protocol pattern (Справочник\s+) but NOT
# any Level A pattern (СправочникМенеджер., РегистрыСведений., Новый Структура, etc.)
tmp, env = fresh_env()
bsl_content = (
    # Процедура ОбработкаДанных()
    "\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0430"
    " \u041e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430"
    "\u0414\u0430\u043d\u043d\u044b\u0445()\n"
    # Данные = Справочник Номенклатура
    "    \u0414\u0430\u043d\u043d\u044b\u0435 = "
    "\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a"
    " \u041d\u043e\u043c\u0435\u043d\u043a\u043b\u0430\u0442\u0443\u0440\u0430"
    ";\n"
    # Результат = ПолучитьДанные();
    "    \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 = "
    "\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c"
    "\u0414\u0430\u043d\u043d\u044b\u0435();\n"
    # КонецПроцедуры
    "\u041a\u043e\u043d\u0435\u0446"
    "\u041f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u044b\n"
)
result = run_hook({
    "tool_name": "Edit",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/1c/module.bsl",
        "new_string": bsl_content,
    }
}, env)
state = read_state(tmp)
blocked = is_json_block(result)
out = parse_stdout(result)
test("BLOCK output", blocked,
     f"stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("reason mentions domain 1c",
     "1c" in out.get("reason", "").lower(),
     f"reason={out.get('reason', '')[:100]}")
test("pending_learn domain = 1c",
     state.get("pending_learn", {}).get("domain") == "1c",
     f"got: {state.get('pending_learn')}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 5: Level A pattern blocks FIRST (no A.1 trigger)")
print("=" * 60)

tmp, env = fresh_env()
result = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/agents/new.py",
        "content": (
            "from langgraph.graph import StateGraph\n"
            "builder = StateGraph(dict)\n"
            "builder.add_node('start', lambda x: x)\n"
        ),
    }
}, env)
state = read_state(tmp)
pending = state.get("pending_learn")
# Level A blocks with SKILL REQUIRED, not LEARNING REQUIRED
blocked = is_json_block(result)
out = parse_stdout(result)
test("Level A blocks (JSON block)", blocked,
     f"exit={result.returncode}, stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("Block reason mentions SKILL REQUIRED (Level A, not A.1)",
     "SKILL REQUIRED" in out.get("reason", ""),
     f"reason={out.get('reason', '')[:100]}")
test("No pending_learn set", pending is None, f"got: {pending}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 6: Short content ignored (< 30 chars) — no BLOCK")
print("=" * 60)

tmp, env = fresh_env()
result = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/test.py",
        "content": "import redis",
    }
}, env)
state = read_state(tmp)
blocked = is_json_block(result)
test("No BLOCK for short content", not blocked)
test("No pending_learn for short content", state.get("pending_learn") is None)
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 7: Pytest pattern triggers BLOCK")
print("=" * 60)

tmp, env = fresh_env()
result = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/tests/conftest.py",
        "content": (
            "import pytest\n"
            "@pytest.fixture\n"
            "def client():\n"
            "    from src.api import create_app\n"
            "    app = create_app()\n"
            "    return app.test_client()\n"
        ),
    }
}, env)
state = read_state(tmp)
blocked = is_json_block(result)
out = parse_stdout(result)
test("BLOCK output", blocked,
     f"stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("reason mentions learning-loop", "learning-loop" in out.get("reason", ""),
     f"reason={out.get('reason', '')[:100]}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 8: Dedup — second call with SAME pattern NOT blocked")
print("=" * 60)

tmp, env = fresh_env()
# First call — FastAPI — should BLOCK
result1 = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/app.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI(title='test')",
    }
}, env)
blocked1 = is_json_block(result1)
test("First FastAPI call BLOCKED", blocked1)

# Second call — same FastAPI pattern — should NOT block (dedup)
result2 = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/v2.py",
        "content": "from fastapi import FastAPI\napp = FastAPI(title='v2')",
    }
}, env)
blocked2 = is_json_block(result2)
test("Second FastAPI call NOT blocked (dedup)", not blocked2,
     f"stdout={result2.stdout[:200] if result2.stdout else 'empty'}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 9: Dedup — different pattern still blocks")
print("=" * 60)

tmp, env = fresh_env()
# First call — FastAPI — BLOCK
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/app.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI(title='test')",
    }
}, env)

# Second call — Redis (different pattern) — should still BLOCK
result2 = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/cache/r.py",
        "content": "from redis import Redis\nclient = Redis.from_url('redis://localhost')",
    }
}, env)
blocked2 = is_json_block(result2)
state = read_state(tmp)
activated = state.get("activated_skills", [])
test("Redis BLOCKED (different pattern from FastAPI)", blocked2,
     f"stdout={result2.stdout[:200] if result2.stdout else 'empty'}")
test("Both learn keys in activated_skills",
     "learn:fastapi-framework" in activated and "learn:redis-caching" in activated,
     f"activated={activated}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 10: Level F clears pending_learn when learn:X activated")
print("=" * 60)

tmp, env = fresh_env()
# Step 1: PRE — A.1 blocks, sets pending_learn + learn:fastapi-framework
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI()",
    }
}, env)
state1 = read_state(tmp)
test("pending_learn exists after A.1 block",
     state1.get("pending_learn") is not None)

# Step 2: POST — Level F detects pending_learn, sees learn:X activated → clears
result2 = run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": "from fastapi import FastAPI",
    },
    "tool_result": "File written successfully",
}, env)
state2 = read_state(tmp)
stdout2 = result2.stdout or ""
test("Level F clears pending_learn (learn:X was activated)",
     state2.get("pending_learn") is None,
     f"pending_learn={state2.get('pending_learn')}")
# Level F returns None (skip) when learn:X activated — no system_message
test("No LEARN advisory (already handled by A.1)",
     "LEARN" not in stdout2 or '"systemMessage"' not in stdout2,
     f"stdout={stdout2[:200]}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
total = passed + failed
print(f"RESULTS: {passed} passed, {failed} failed, {total} total")
if failed == 0:
    print("ALL TESTS PASSED")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
