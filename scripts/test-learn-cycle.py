#!/usr/bin/env python3
"""End-to-end tests for LEARN cycle: research_protocol -> pending_learn -> Level F."""
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


# =========================================================================
print("=" * 60)
print("TEST 1: FastAPI code triggers research_protocol")
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
pending = state.get("pending_learn")
test("pending_learn is set", pending is not None)
test("label = FastAPI Framework", pending and pending.get("label") == "FastAPI Framework")
test("domain = tech", pending and pending.get("domain") == "tech")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 2: Level F fires on PostToolUse after pending_learn")
print("=" * 60)

tmp, env = fresh_env()
# Step 1: PRE — set pending_learn
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/routes.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI()",
    }
}, env)
state1 = read_state(tmp)
test("pending_learn set after PRE", state1.get("pending_learn") is not None)

# Step 2: POST — Level F should detect pending_learn
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
test("Level F output contains LEARN", "LEARN" in stdout2, f"stdout={stdout2[:200]}")
test("pending_learn cleared after Level F", state2.get("pending_learn") is None)
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 3: Redis code triggers research_protocol")
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
pending = state.get("pending_learn")
test("pending_learn is set", pending is not None)
test("label = Redis Caching", pending and pending.get("label") == "Redis Caching")
test("domain = tech", pending and pending.get("domain") == "tech")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 4: 1C Metadata triggers research_protocol (1c domain)")
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
pending = state.get("pending_learn")
test("pending_learn is set", pending is not None)
test("domain = 1c", pending and pending.get("domain") == "1c",
     f"got: {pending}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 5: Level A pattern should NOT trigger research_protocol")
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
# protocol.py outputs JSON {"continue": false, "decision": "block"} with exit code 0
blocked = is_json_block(result)
test("Level A blocks (JSON block)", blocked,
     f"exit={result.returncode}, stdout={result.stdout[:200] if result.stdout else 'empty'}")
test("No pending_learn set", pending is None, f"got: {pending}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 6: Short content ignored (< 30 chars)")
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
pending = state.get("pending_learn")
test("No pending_learn for short content", pending is None)
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 7: Pytest pattern triggers research_protocol")
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
pending = state.get("pending_learn")
test("pending_learn is set", pending is not None)
test("label = Pytest Framework", pending and pending.get("label") == "Pytest Framework",
     f"got: {pending}")
shutil.rmtree(tmp, ignore_errors=True)

# =========================================================================
print()
print("=" * 60)
print("TEST 8: Duplicate pending_learn not overwritten")
print("=" * 60)

tmp, env = fresh_env()
# Set first pending_learn (FastAPI)
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/api/app.py",
        "content": "from fastapi import FastAPI, APIRouter\napp = FastAPI(title='test')",
    }
}, env)
state1 = read_state(tmp)
label1 = state1.get("pending_learn", {}).get("label")

# Try to set second pending_learn (Redis) — should NOT overwrite
run_hook({
    "tool_name": "Write",
    "tool_input": {
        "file_path": "D:/1C-Framework/src/cache/r.py",
        "content": "from redis import Redis\nclient = Redis.from_url('redis://localhost')",
    }
}, env)
state2 = read_state(tmp)
label2 = state2.get("pending_learn", {}).get("label")

test("First pending_learn was FastAPI", label1 == "FastAPI Framework", f"got: {label1}")
test("Second write did not overwrite", label2 == "FastAPI Framework", f"got: {label2}")
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
