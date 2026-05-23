import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lazy-mcp")


@mcp.tool()
def ping() -> str:
    """Ping lazy-mcp"""
    return "pong"


if __name__ == "__main__":
    mcp.run(transport="stdio")
