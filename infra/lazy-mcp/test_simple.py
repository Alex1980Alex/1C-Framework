"""Simple test for lazy-mcp tools/call"""

import subprocess
import json
import sys
import time
from pathlib import Path

def main():
    python_exe = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    server_script = Path(__file__).parent / "src" / "server.py"

    print("Starting server...")
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
    print("Server started, sending requests...")

    def send(method, params=None, req_id=1):
        request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        msg = json.dumps(request) + "\n"
        print(f"\n>>> SEND: {method}")
        proc.stdin.write(msg.encode('utf-8'))
        proc.stdin.flush()

        # Read with timeout
        import threading
        response_line = [None]
        def read():
            try:
                response_line[0] = proc.stdout.readline()
            except Exception as e:
                print(f"Read error: {e}")

        t = threading.Thread(target=read)
        t.start()
        t.join(timeout=30)

        if response_line[0]:
            decoded = response_line[0].decode('utf-8', errors='ignore').strip()
            print(f"<<< RECV: {decoded[:500]}...")
            return json.loads(decoded) if decoded else None
        else:
            print("<<< RECV: TIMEOUT/EMPTY")
            return None

    # Test 1: Initialize
    resp = send("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }, 1)
    print(f"Initialize: {'OK' if resp and 'result' in resp else 'FAIL'}")

    # Test 2: tools/list
    resp = send("tools/list", {}, 2)
    if resp and 'result' in resp:
        tools = resp['result'].get('tools', [])
        print(f"Tools: {len(tools)} found - {[t['name'] for t in tools]}")
    else:
        print("Tools: FAIL")

    # Test 3: get_tools_in_category (simple)
    print("\n=== Testing get_tools_in_category ===")
    resp = send("tools/call", {
        "name": "get_tools_in_category",
        "arguments": {"path": "/"}
    }, 3)
    if resp:
        if 'result' in resp:
            print(f"get_tools_in_category: OK")
            content = resp['result'].get('content', [])
            if content:
                print(f"Content: {content[0].get('text', '')[:300]}...")
        elif 'error' in resp:
            print(f"Error: {resp['error']}")
    else:
        print("get_tools_in_category: TIMEOUT")

    # Test 4: recommend_tools
    print("\n=== Testing recommend_tools ===")
    resp = send("tools/call", {
        "name": "recommend_tools",
        "arguments": {"task_description": "search files"}
    }, 4)
    if resp:
        if 'result' in resp:
            print(f"recommend_tools: OK")
            content = resp['result'].get('content', [])
            if content:
                print(f"Content: {content[0].get('text', '')[:500]}...")
        elif 'error' in resp:
            print(f"Error: {resp['error']}")
    else:
        print("recommend_tools: TIMEOUT")

    # Test 5: execute_tool with ripgrep
    print("\n=== Testing execute_tool (ripgrep list-file-types) ===")
    resp = send("tools/call", {
        "name": "execute_tool",
        "arguments": {
            "tool_path": "/file-operations/ripgrep/list-file-types",
            "arguments": {}
        }
    }, 5)
    if resp:
        if 'result' in resp:
            print(f"execute_tool: OK")
            content = resp['result'].get('content', [])
            if content:
                print(f"Content: {content[0].get('text', '')[:500]}...")
        elif 'error' in resp:
            print(f"Error: {resp['error']}")
    else:
        print("execute_tool: TIMEOUT")

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
