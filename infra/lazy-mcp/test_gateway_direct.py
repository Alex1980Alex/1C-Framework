"""Test Docker MCP Gateway directly"""
import subprocess
import json
import time
import sys

print("Testing Docker MCP Gateway directly...")
print("=" * 60)

# Запускаем gateway
cmd = ["docker", "mcp", "gateway", "run", "--transport", "stdio", "--enable-all-servers"]
print(f"Command: {' '.join(cmd)}")

process = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0
)

print(f"Process started, PID: {process.pid}")

# Ждём немного для инициализации
print("Waiting 5 seconds for gateway to initialize...")
time.sleep(5)

# Проверяем что процесс жив
if process.poll() is not None:
    stderr = process.stderr.read().decode('utf-8', errors='ignore')
    print(f"ERROR: Process died immediately!")
    print(f"stderr: {stderr}")
    sys.exit(1)

print("Process is alive, sending initialize request...")

# Отправляем initialize request
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

message = json.dumps(init_request) + "\n"
print(f"Sending: {message.strip()}")
process.stdin.write(message.encode('utf-8'))
process.stdin.flush()

# Пытаемся прочитать ответ (с timeout)
print("Reading response (30 sec timeout)...")
import select
import threading

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
thread.join(timeout=30)

if thread.is_alive():
    print("TIMEOUT: No response in 30 seconds")
    # Проверяем stderr
    import os
    os.set_blocking(process.stderr.fileno(), False)
    try:
        stderr = process.stderr.read()
        if stderr:
            print(f"stderr: {stderr.decode('utf-8', errors='ignore')}")
    except:
        pass
else:
    print(f"Response: {response}")
    if response:
        try:
            data = json.loads(response)
            print(f"Parsed: {json.dumps(data, indent=2)}")
        except:
            pass

# Cleanup
process.kill()
print("\nDone.")
