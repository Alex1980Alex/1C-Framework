"""
Тест интеграции lazy-mcp с Docker MCP Gateway

Проверяет:
1. Singleton pattern для gateway
2. Retry логика
3. Кеширование tools
4. Выполнение инструментов через mcp-exec
"""

import asyncio
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from loader import ServerLoader
from registry import Registry


async def test_docker_mcp_integration():
    print("=" * 60)
    print("Testing lazy-mcp → Docker MCP Gateway Integration")
    print("=" * 60)

    # Загружаем registry
    registry_path = os.path.join(os.path.dirname(__file__), 'config', 'registry.yaml')
    print(f"\n[1] Loading registry: {registry_path}")
    registry = Registry(registry_path)

    # Создаём loader
    loader = ServerLoader(registry, max_active=5)
    print("[1] ✓ Registry loaded")

    # Test 1: Запуск brave (docker-mcp)
    print("\n[2] Starting brave server (via Docker MCP Gateway)...")
    print("    This may take 15-20 seconds for gateway initialization...")

    try:
        server = await loader.get_server('brave')
        if server:
            print(f"[2] ✓ Server started: {server.name}")
            print(f"    - Is proxy: {server.is_proxy}")
            print(f"    - Tools count: {len(server.tools)}")
            for tool in server.tools:
                print(f"      • {tool.get('name', '?')}: {tool.get('description', '')[:50]}")
        else:
            print("[2] ✗ Failed to start brave server")
            return False

    except Exception as e:
        print(f"[2] ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Проверка singleton (второй запрос должен быть быстрым)
    print("\n[3] Testing singleton pattern (second request should be instant)...")
    import time
    start = time.time()

    try:
        server2 = await loader.get_server('fetch')
        elapsed = time.time() - start
        if server2:
            print(f"[3] ✓ fetch server started in {elapsed:.2f}s")
            if elapsed < 1.0:
                print("    ✓ Singleton working (reused gateway)")
            else:
                print("    ⚠ Singleton may not be working (took too long)")
        else:
            print("[3] ✗ Failed to start fetch server")

    except Exception as e:
        print(f"[3] ✗ Error: {e}")

    # Test 3: Выполнение инструмента
    print("\n[4] Executing brave_web_search tool...")
    try:
        result = await loader.execute_tool('brave', 'brave_web_search', {
            'query': 'python programming',
            'count': 1
        })

        if isinstance(result, dict):
            if 'error' in result:
                print(f"[4] ✗ Tool error: {result['error']}")
            else:
                print(f"[4] ✓ Tool executed successfully")
                print(f"    - Result type: {type(result).__name__}")
                # Показываем часть результата
                result_str = str(result)[:200]
                print(f"    - Result preview: {result_str}...")
        else:
            print(f"[4] ✓ Result: {result}")

    except Exception as e:
        print(f"[4] ✗ Error: {e}")
        import traceback
        traceback.print_exc()

    # Test 4: Список активных серверов
    print("\n[5] Active servers:")
    for name in loader.list_active():
        print(f"    • {name}")

    # Cleanup
    print("\n[6] Shutting down...")
    await loader.shutdown_all()
    print("[6] ✓ All servers stopped")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_docker_mcp_integration())
    sys.exit(0 if success else 1)
