"""Debug Docker MCP Gateway integration"""
import asyncio
import logging
import sys

# Настраиваем логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s',
    stream=sys.stdout
)

# Добавляем src в path
sys.path.insert(0, 'src')

from registry import Registry
from loader import ServerLoader

async def test():
    print("=" * 60)
    print("Docker MCP Gateway Integration Test")
    print("=" * 60)

    registry = Registry()
    loader = ServerLoader(registry)

    # Проверяем конфиг brave
    brave_config = registry.get_server_config('brave')
    print(f'\n[1] brave config:')
    print(f'    type={brave_config.type}')
    print(f'    docker_image={brave_config.docker_image}')
    print(f'    docker_server={brave_config.docker_server}')

    # Проверяем конфиг gateway
    gateway_config = registry.get_server_config('docker-mcp-gateway')
    print(f'\n[2] docker-mcp-gateway config:')
    print(f'    type={gateway_config.type}')
    print(f'    command={gateway_config.command}')
    print(f'    args={gateway_config.args}')

    # Пробуем запустить brave server
    print('\n[3] Starting brave server (this will start Docker MCP Gateway)...')
    try:
        server = await loader.get_server('brave')
        if server:
            print(f'    SUCCESS: server={server.name}, is_proxy={server.is_proxy}')
            print(f'    tools={server.tools}')
        else:
            print('    FAILED: server is None')
    except Exception as e:
        print(f'    ERROR: {e}')
        import traceback
        traceback.print_exc()

    # Проверяем gateway singleton
    print(f'\n[4] Gateway singleton:')
    print(f'    _gateway_instance={ServerLoader._gateway_instance}')
    print(f'    _gateway_tools_cache={len(ServerLoader._gateway_tools_cache)} tools')

    # Shutdown
    await loader.shutdown_all()

if __name__ == '__main__':
    asyncio.run(test())
