"""Test Docker MCP Gateway - find available servers"""
import subprocess
import json
import time
import threading

print("Testing Docker MCP Gateway - Finding available servers...")
print("=" * 60)

# Запускаем gateway БЕЗ серверов, только с dynamic tools
cmd = [
    "docker", "mcp", "gateway", "run",
    "--transport", "stdio",
    "--enable-all-servers",  # Включаем dynamic tools
    "--verbose"
]
print(f"Command: {' '.join(cmd)}")

process = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0
)

print(f"Process started, PID: {process.pid}")

# Поток для чтения stderr
stderr_lines = []
def read_stderr():
    while True:
        line = process.stderr.readline()
        if not line:
            break
        stderr_lines.append(line.decode('utf-8', errors='ignore').strip())

stderr_thread = threading.Thread(target=read_stderr, daemon=True)
stderr_thread.start()

# Ждём инициализации
print("\nWaiting 15 seconds for initialization...")
time.sleep(15)

if process.poll() is not None:
    print(f"ERROR: Process died!")
    for line in stderr_lines[-20:]:
        print(f"  {line}")
    exit(1)

print("Sending initialize...")

# Initialize
init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}
process.stdin.write((json.dumps(init_request) + "\n").encode('utf-8'))
process.stdin.flush()

# Read response
line = process.stdout.readline().decode('utf-8').strip()
print(f"Initialize response: {line[:200]}...")

# Get tools list
print("\nGetting tools list...")
tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
process.stdin.write((json.dumps(tools_request) + "\n").encode('utf-8'))
process.stdin.flush()

# Read tools response
response = None
def read_response():
    global response
    response = process.stdout.readline().decode('utf-8').strip()

thread = threading.Thread(target=read_response)
thread.start()
thread.join(timeout=10)

if response:
    try:
        data = json.loads(response)
        tools = data.get('result', {}).get('tools', [])
        print(f"\nFound {len(tools)} tools:")
        for tool in tools[:30]:  # Первые 30
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:60]}")

        # Ищем mcp-find
        mcp_find = [t for t in tools if 'find' in t.get('name', '').lower()]
        if mcp_find:
            print(f"\n[mcp-find tool found]: {mcp_find[0]['name']}")

            # Используем mcp-find для поиска brave
            print("\nSearching for 'brave' servers...")
            find_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": mcp_find[0]['name'],
                    "arguments": {"query": "brave"}
                }
            }
            process.stdin.write((json.dumps(find_request) + "\n").encode('utf-8'))
            process.stdin.flush()

            find_response = process.stdout.readline().decode('utf-8').strip()
            print(f"mcp-find response: {find_response[:500]}")

    except Exception as e:
        print(f"Error parsing: {e}")
        print(f"Raw: {response[:500]}")
else:
    print("No response from tools/list")

# Cleanup
process.kill()
print("\nDone.")
