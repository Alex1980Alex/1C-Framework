"""Test Docker MCP Gateway with LSP-style Content-Length header"""
import subprocess
import json
import time
import sys
import threading

print("Testing Docker MCP Gateway with LSP protocol...")
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

# Ждём для инициализации
print("Waiting 10 seconds for full gateway initialization...")
time.sleep(10)

# Проверяем что процесс жив
if process.poll() is not None:
    stderr = process.stderr.read().decode('utf-8', errors='ignore')
    print(f"ERROR: Process died!")
    print(f"stderr: {stderr}")
    sys.exit(1)

print("Process is alive")

# Формируем LSP-style сообщение с Content-Length header
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

content = json.dumps(init_request)
# Попробуем оба варианта: с header и без

# Вариант 1: С Content-Length header (LSP protocol)
print("\n--- Test 1: With Content-Length header ---")
message_with_header = f"Content-Length: {len(content)}\r\n\r\n{content}"
print(f"Sending: {message_with_header[:100]}...")
process.stdin.write(message_with_header.encode('utf-8'))
process.stdin.flush()

# Читаем ответ
response = None
def read_response():
    global response
    try:
        # Сначала читаем header
        header = b""
        while True:
            byte = process.stdout.read(1)
            if not byte:
                break
            header += byte
            if header.endswith(b"\r\n\r\n"):
                break
            if len(header) > 1000:  # Timeout protection
                break

        # Парсим Content-Length если есть
        header_str = header.decode('utf-8', errors='ignore')
        if "Content-Length:" in header_str:
            for line in header_str.split('\r\n'):
                if line.startswith("Content-Length:"):
                    length = int(line.split(":")[1].strip())
                    content_bytes = process.stdout.read(length)
                    response = content_bytes.decode('utf-8', errors='ignore')
                    return

        # Или просто читаем строку (JSON-RPC без header)
        line = header + process.stdout.readline()
        response = line.decode('utf-8', errors='ignore').strip()
    except Exception as e:
        response = f"ERROR: {e}"

thread = threading.Thread(target=read_response)
thread.start()
thread.join(timeout=15)

if thread.is_alive():
    print("TIMEOUT: No response in 15 seconds")
else:
    print(f"Response: {response}")
    if response and not response.startswith("ERROR"):
        try:
            data = json.loads(response)
            print(f"Parsed JSON: {json.dumps(data, indent=2)[:500]}")
        except:
            print("Could not parse as JSON")

# Cleanup
process.kill()
print("\nDone.")
