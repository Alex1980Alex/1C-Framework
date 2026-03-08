"""Test Docker MCP in same context as MCP server"""
import asyncio
import sys
import os
import logging

# Setup same as server.py
sys.path.insert(0, 'src')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

from registry import Registry
from loader import ServerLoader

async def test():
    print("=" * 60, file=sys.stderr)
    print("Testing Docker MCP Gateway in MCP server context", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Same initialization as server.py
    from pathlib import Path
    config_path = Path(__file__).parent / "config" / "registry.yaml"

    print(f"Config path: {config_path}", file=sys.stderr)
    print(f"Config exists: {config_path.exists()}", file=sys.stderr)

    registry = Registry(config_path)
    loader = ServerLoader(registry, max_active=5)

    print(f"Loaded {len(registry.servers)} servers", file=sys.stderr)

    # Test brave
    print("\n[1] Testing brave server startup...", file=sys.stderr)
    server = await loader.get_server("brave")

    if server:
        print(f"Server: {server.name}", file=sys.stderr)
        print(f"Is proxy: {server.is_proxy}", file=sys.stderr)
        print(f"Tools: {len(server.tools)}", file=sys.stderr)
        print(f"Process alive: {server.process.poll() is None}", file=sys.stderr)

        # Check gateway
        gateway = loader.active_servers.get("docker-mcp-gateway")
        if gateway:
            print(f"\nGateway tools: {len(gateway.tools)}", file=sys.stderr)
            print(f"Gateway alive: {gateway.process.poll() is None}", file=sys.stderr)

        # Execute tool
        print("\n[2] Executing brave_web_search...", file=sys.stderr)
        result = await loader.execute_tool("brave", "brave_web_search", {
            "query": "test MCP",
            "count": 1
        })

        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
        else:
            print("SUCCESS!", file=sys.stderr)
            print(f"Result type: {type(result)}", file=sys.stderr)
    else:
        print("ERROR: Failed to start brave server", file=sys.stderr)

        # Check if gateway started
        gateway = ServerLoader._gateway_instance
        if gateway:
            print(f"Gateway started but brave failed", file=sys.stderr)
            print(f"Gateway alive: {gateway.process.poll() is None}", file=sys.stderr)
            if gateway.process.poll() is not None:
                stderr = gateway.process.stderr.read().decode('utf-8', errors='ignore')
                print(f"Gateway stderr: {stderr[:500]}", file=sys.stderr)
        else:
            print("Gateway never started", file=sys.stderr)

    await loader.shutdown_all()
    print("\nDone.", file=sys.stderr)

if __name__ == '__main__':
    asyncio.run(test())
