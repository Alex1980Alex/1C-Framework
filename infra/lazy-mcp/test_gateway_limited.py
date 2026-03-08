"""Test Docker MCP Gateway with limited servers"""
import subprocess
import json
import time
import sys
import threading

print("Testing Docker MCP Gateway with LIMITED servers...")
print("=" * 60)

# Запускаем gateway с КОНКРЕТНЫМИ серверами вместо --enable-all-servers
cmd = [
    "docker", "mcp", "gateway", "run",
    "--transport", "stdio",
    "--servers=brave-search",  # Только brave
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
        if len(stderr_lines) <= 20:
            print(f"[stderr] {stderr_lines[-1]}")

stderr_thread = threading.Thread(target=read_stderr, daemon=True)
stderr_thread.start()

# Ждём для инициализации (меньше серверов = быстрее)
print("\nWaiting 8 seconds for initialization...")
time.sleep(8)

# Проверяем что процесс жив
if process.poll() is not None:
    print(f"ERROR: Process died! Exit code: {process.poll()}")
    time.sleep(1)  # Даём время stderr закончить
    print(f"stderr collected: {len(stderr_lines)} lines")
    for line in stderr_lines[-10:]:
        print(f"  {line}")
    sys.exit(1)

print("Process is alive, sending initialize request...")

# JSON-RPC запрос (простой формат - без Content-Length)
init_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}

content = json.dumps(init_request) + "\n"
print(f"Sending: {content.strip()}")
process.stdin.write(content.encode('utf-8'))
process.stdin.flush()

# Читаем ответ
response = None
def read_response():
    global response
    try:
        line = process.stdout.readline()
        response = line.decode('utf-8', errors='ignore').strip()
    except Exception as e:
        response = f"ERROR: {e}"

thread = threading.Thread(target=read_response)
thread.start()
thread.join(timeout=20)

if thread.is_alive():
    print("TIMEOUT: No response in 20 seconds")
    print(f"\nstderr collected ({len(stderr_lines)} lines):")
    for line in stderr_lines[-15:]:
        print(f"  {line}")
else:
    print(f"Response: {response}")
    if response and not response.startswith("ERROR") and response:
        try:
            data = json.loads(response)
            print(f"SUCCESS! Parsed JSON:")
            print(json.dumps(data, indent=2)[:1000])
        except Exception as e:
            print(f"Could not parse as JSON: {e}")

# Cleanup
process.kill()
print("\nDone.")
