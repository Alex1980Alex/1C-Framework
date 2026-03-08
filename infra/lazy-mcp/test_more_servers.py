"""Test more servers including ast-grep-mcp"""
import subprocess
import json
import time
import threading
from pathlib import Path

def main():
    python_exe = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    server_script = Path(__file__).parent / "src" / "server.py"

    print("Starting lazy-mcp server...")
    proc = subprocess.Popen(
        [str(python_exe), str(server_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(Path(__file__).parent),
        bufsize=0,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )

    time.sleep(2)

    def send(method, params=None, req_id=1, timeout=60):
        request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        msg = json.dumps(request) + "\n"
        proc.stdin.write(msg.encode('utf-8'))
        proc.stdin.flush()

        response_line = [None]
        def read():
            try:
                response_line[0] = proc.stdout.readline()
            except:
                pass

        t = threading.Thread(target=read)
        t.start()
        t.join(timeout=timeout)

        if response_line[0]:
            decoded = response_line[0].decode('utf-8', errors='ignore').strip()
            return json.loads(decoded) if decoded else None
        return None

    # Initialize
    resp = send("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }, 1)
    print(f"Initialize: {'OK' if resp and 'result' in resp else 'FAIL'}")

    # More tests
    tests = [
        # AST-grep (critical 1C tool)
        ("ast-grep-mcp", "/1c-development/ast-grep-mcp/ast_grep", {
            "pattern": "Процедура $NAME",
            "language": "bsl",
            "path": "D:/1C-Enterprise_Framework/src"
        }, 90),
        
        # Sequential thinking
        ("sequential-thinking", "/reasoning/sequential-thinking/sequentialThinking", {
            "thought": "Test",
            "nextThoughtNeeded": False
        }, 60),
        
        # Brave search
        ("brave-search", "/web/brave/brave_web_search", {
            "query": "test"
        }, 60),
    ]

    results = []
    req_id = 2

    for name, tool_path, args, timeout in tests:
        print(f"\n{'='*60}")
        print(f"Test: {name}")
        print(f"Path: {tool_path}")
        print(f"{'='*60}")

        resp = send("tools/call", {
            "name": "execute_tool",
            "arguments": {
                "tool_path": tool_path,
                "arguments": args
            }
        }, req_id, timeout=timeout)
        req_id += 1

        status = "UNKNOWN"
        detail = ""

        if resp:
            if "result" in resp:
                content = resp["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    try:
                        parsed = json.loads(text)
                        if "error" in parsed:
                            status = "ERROR"
                            detail = str(parsed["error"])[:150]
                        else:
                            status = "OK"
                            detail = text[:150]
                    except:
                        status = "OK"
                        detail = text[:150]
                else:
                    status = "OK (empty)"
            elif "error" in resp:
                status = "ERROR"
                detail = str(resp["error"])[:150]
        else:
            status = "TIMEOUT"

        safe_detail = ''.join(c if ord(c) < 128 else '?' for c in detail)
        print(f"Status: {status}")
        if safe_detail:
            print(f"Detail: {safe_detail}...")

        results.append((name, status))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    for name, status in results:
        icon = "[OK]" if status.startswith("OK") else "[FAIL]"
        print(f"  {icon} {name}: {status}")
        if status.startswith("OK"):
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()

if __name__ == "__main__":
    main()
