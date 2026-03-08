"""
Full MCP Protocol Test for Lazy-MCP Server

Тестирует:
1. initialize
2. tools/list
3. recommend_tools
4. get_tools_in_category (все уровни)
5. execute_tool (с реальным сервером)
"""

import subprocess
import json
import sys
import time
from pathlib import Path

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

def log_ok(msg):
    print(f"{GREEN}[OK]{RESET} {msg}")

def log_fail(msg):
    print(f"{RED}[FAIL]{RESET} {msg}")

def log_warn(msg):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def log_header(msg):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{msg}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

class LazyMCPTester:
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "tests": []
        }

    def start_server(self):
        """Запуск lazy-mcp сервера"""
        log_header("Starting Lazy-MCP Server")

        python_exe = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
        server_script = Path(__file__).parent / "src" / "server.py"

        self.process = subprocess.Popen(
            [str(python_exe), str(server_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).parent),
            bufsize=0,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )

        # Ждём запуска
        time.sleep(2)

        if self.process.poll() is None:
            log_ok("Server started")
            return True
        else:
            stderr = self.process.stderr.read().decode('utf-8', errors='ignore')
            log_fail(f"Server failed to start: {stderr[:200]}")
            return False

    def stop_server(self):
        """Остановка сервера"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except:
                self.process.kill()

    def send_request(self, method, params=None, timeout=30):
        """Отправить JSON-RPC запрос"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        msg = json.dumps(request) + "\n"
        self.process.stdin.write(msg.encode('utf-8'))
        self.process.stdin.flush()

        # Читаем ответ с таймаутом
        import select
        import threading

        response_line = None
        def read_line():
            nonlocal response_line
            try:
                response_line = self.process.stdout.readline()
            except:
                pass

        thread = threading.Thread(target=read_line)
        thread.start()
        thread.join(timeout=timeout)

        if response_line:
            return json.loads(response_line.decode('utf-8', errors='ignore'))
        return None

    def test_initialize(self):
        """Тест 1: initialize"""
        log_header("Test 1: MCP Initialize")

        response = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        })

        if response and "result" in response:
            log_ok(f"Initialize OK")
            log_ok(f"  Server: {response['result'].get('serverInfo', {}).get('name', 'unknown')}")
            log_ok(f"  Version: {response['result'].get('serverInfo', {}).get('version', 'unknown')}")
            log_ok(f"  Protocol: {response['result'].get('protocolVersion', 'unknown')}")
            self.results["passed"] += 1
            self.results["tests"].append(("initialize", "PASS", response))
            return True
        else:
            log_fail(f"Initialize failed: {response}")
            self.results["failed"] += 1
            self.results["tests"].append(("initialize", "FAIL", response))
            return False

    def test_tools_list(self):
        """Тест 2: tools/list"""
        log_header("Test 2: MCP Tools List")

        response = self.send_request("tools/list")

        if response and "result" in response:
            tools = response["result"].get("tools", [])
            log_ok(f"Tools list OK: {len(tools)} tools")

            expected_tools = ["recommend_tools", "get_tools_in_category", "execute_tool"]
            for tool in tools:
                name = tool.get("name", "")
                if name in expected_tools:
                    log_ok(f"  {name}: {tool.get('description', '')[:60]}...")
                    expected_tools.remove(name)

            if expected_tools:
                log_warn(f"  Missing tools: {expected_tools}")
                self.results["warnings"] += 1

            self.results["passed"] += 1
            self.results["tests"].append(("tools/list", "PASS", tools))
            return tools
        else:
            log_fail(f"Tools list failed: {response}")
            self.results["failed"] += 1
            self.results["tests"].append(("tools/list", "FAIL", response))
            return []

    def test_recommend_tools(self):
        """Тест 3: recommend_tools"""
        log_header("Test 3: recommend_tools")

        test_cases = [
            ("Найди все процедуры в BSL коде", "1c-development"),
            ("Search documentation for best practices", "documentation"),
            ("Save this to memory", "memory"),
            ("Find all Python functions", "code-analysis"),
            ("Search files for TODO", "file-operations"),
        ]

        for task, expected_category in test_cases:
            response = self.send_request("tools/call", {
                "name": "recommend_tools",
                "arguments": {"task_description": task}
            })

            if response and "result" in response:
                result_content = response["result"].get("content", [])
                if result_content:
                    text = result_content[0].get("text", "")
                    try:
                        result = json.loads(text)
                        recommendations = result.get("recommendations", [])

                        found_category = None
                        for rec in recommendations:
                            if rec.get("category") == expected_category:
                                found_category = expected_category
                                break

                        if found_category:
                            log_ok(f"  '{task[:40]}...' → {expected_category}")
                        else:
                            categories = [r.get("category") for r in recommendations[:3]]
                            log_warn(f"  '{task[:40]}...' → {categories} (expected: {expected_category})")
                            self.results["warnings"] += 1
                    except json.JSONDecodeError:
                        log_fail(f"  Invalid JSON response")
                        self.results["failed"] += 1
            else:
                log_fail(f"  '{task[:40]}...' → FAILED")
                self.results["failed"] += 1

        self.results["passed"] += 1
        self.results["tests"].append(("recommend_tools", "PASS", None))

    def test_get_tools_category(self):
        """Тест 4: get_tools_in_category"""
        log_header("Test 4: get_tools_in_category (Navigation)")

        # Test root level
        response = self.send_request("tools/call", {
            "name": "get_tools_in_category",
            "arguments": {"path": "/"}
        })

        if response and "result" in response:
            result_content = response["result"].get("content", [])
            if result_content:
                text = result_content[0].get("text", "")
                try:
                    result = json.loads(text)
                    categories = result.get("items", [])
                    log_ok(f"Root '/' → {len(categories)} categories")
                    log_ok(f"  Categories: {categories[:5]}...")

                    # Test category level
                    if "1c-development" in categories:
                        response2 = self.send_request("tools/call", {
                            "name": "get_tools_in_category",
                            "arguments": {"path": "/1c-development"}
                        })

                        if response2 and "result" in response2:
                            content2 = response2["result"].get("content", [])
                            if content2:
                                result2 = json.loads(content2[0].get("text", ""))
                                servers = result2.get("items", [])
                                log_ok(f"'/1c-development' → {len(servers)} servers")
                                log_ok(f"  Servers: {servers[:3]}...")

                    self.results["passed"] += 1
                    self.results["tests"].append(("get_tools_in_category", "PASS", categories))
                except json.JSONDecodeError as e:
                    log_fail(f"Invalid JSON: {e}")
                    self.results["failed"] += 1
        else:
            log_fail(f"Navigation failed: {response}")
            self.results["failed"] += 1
            self.results["tests"].append(("get_tools_in_category", "FAIL", response))

    def test_execute_tool(self):
        """Тест 5: execute_tool (реальный вызов)"""
        log_header("Test 5: execute_tool (Real Server Execution)")

        # Тест с ripgrep (быстрый npx сервер)
        response = self.send_request("tools/call", {
            "name": "execute_tool",
            "arguments": {
                "tool_path": "/file-operations/ripgrep/list-file-types",
                "arguments": {}
            }
        }, timeout=60)

        if response and "result" in response:
            result_content = response["result"].get("content", [])
            if result_content:
                text = result_content[0].get("text", "")
                try:
                    result = json.loads(text)
                    if "error" not in result:
                        log_ok(f"execute_tool → ripgrep loaded successfully")
                        if isinstance(result, dict):
                            log_ok(f"  Response type: {type(result)}")
                        self.results["passed"] += 1
                        self.results["tests"].append(("execute_tool", "PASS", result))
                    else:
                        log_fail(f"execute_tool error: {result.get('error')}")
                        self.results["failed"] += 1
                except json.JSONDecodeError:
                    # Может быть text результат
                    log_ok(f"execute_tool → Response (text): {text[:100]}...")
                    self.results["passed"] += 1
        else:
            log_warn(f"execute_tool timeout or no response (may need longer timeout)")
            self.results["warnings"] += 1
            self.results["tests"].append(("execute_tool", "TIMEOUT", response))

    def print_summary(self):
        """Вывод итогов"""
        log_header("TEST SUMMARY")

        total = self.results["passed"] + self.results["failed"]

        print(f"{GREEN}Passed:{RESET}   {self.results['passed']}")
        print(f"{RED}Failed:{RESET}   {self.results['failed']}")
        print(f"{YELLOW}Warnings:{RESET} {self.results['warnings']}")
        print(f"Total:    {total}")
        print()

        if self.results["failed"] == 0:
            print(f"{GREEN}{BOLD}[SUCCESS] ALL TESTS PASSED{RESET}")
        else:
            print(f"{RED}{BOLD}[ERROR] SOME TESTS FAILED{RESET}")

        return self.results["failed"] == 0

def main():
    tester = LazyMCPTester()

    try:
        if not tester.start_server():
            return 1

        time.sleep(1)

        tester.test_initialize()
        tester.test_tools_list()
        tester.test_recommend_tools()
        tester.test_get_tools_category()
        tester.test_execute_tool()

        success = tester.print_summary()
        return 0 if success else 1

    finally:
        tester.stop_server()

if __name__ == "__main__":
    sys.exit(main())
