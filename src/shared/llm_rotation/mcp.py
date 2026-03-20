"""
LLM Rotation MCP Server — 5 tools for multi-provider LLM access.

Tools: llm_complete, llm_get_stats, llm_reset_provider, llm_test_providers, llm_list_providers.

Migrated from D:\\1C-Enterprise_Framework\\shared\\llm_rotation_mcp.py
"""

import asyncio
import json
import logging
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llm-rotation-mcp")

app = Server("llm-rotation")

# Lazy-init service
_service = None


def _get_service():
    global _service
    if _service is None:
        from src.shared.llm_rotation.service import LLMRotationService
        _service = LLMRotationService()
    return _service


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="llm_complete",
            description="Send a prompt to LLM with automatic provider rotation and fallback.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The prompt to send"},
                    "system_prompt": {"type": "string", "description": "Optional system prompt"},
                    "model": {"type": "string", "description": "Specific model to use (optional)"},
                    "preferred_provider": {
                        "type": "string",
                        "description": "Preferred provider name (optional)",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature (0.0-2.0)",
                        "default": 0.7,
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens to generate",
                        "default": 2048,
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="llm_get_stats",
            description=(
                "Get statistics for all LLM providers: "
                "status, requests, errors, response times."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="llm_reset_provider",
            description="Reset a specific provider's state to HEALTHY (clear errors and cooldown).",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "description": "Provider name to reset"},
                },
                "required": ["provider"],
            },
        ),
        Tool(
            name="llm_test_providers",
            description="Test all available providers with a simple prompt to check availability.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="llm_list_providers",
            description="List all configured providers with their configuration details.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        service = _get_service()

        if name == "llm_complete":
            result = await service.complete(
                prompt=arguments["prompt"],
                system_prompt=arguments.get("system_prompt"),
                model=arguments.get("model"),
                preferred_provider=arguments.get("preferred_provider"),
                temperature=arguments.get("temperature", 0.7),
                max_tokens=arguments.get("max_tokens", 2048),
            )
            return [TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2),
            )]

        elif name == "llm_get_stats":
            stats = service.get_stats()
            lines = ["# LLM Provider Stats\n"]
            status_icons = {
                "healthy": "🟢",
                "degraded": "🟡",
                "unavailable": "🔴",
                "cooldown": "⏳",
            }
            for pname, info in stats.items():
                icon = status_icons.get(info["status"], "❓")
                lines.append(
                    f"**{icon} {pname}** (priority {info['priority']})\n"
                    f"  Status: {info['status']} | Model: {info['model']}\n"
                    f"  Requests: {info['requests']} | Errors: {info['errors']}\n"
                    f"  Avg time: {info['avg_response_time']}s | Available: {info['available']}"
                )
                if info["last_error"]:
                    lines.append(f"  Last error: {info['last_error']}")
                lines.append("")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "llm_reset_provider":
            provider = arguments.get("provider", "")
            success = service.reset_provider(provider)
            if success:
                msg = f"Provider '{provider}' reset to HEALTHY"
            else:
                msg = f"Provider '{provider}' not found"
            return [TextContent(type="text", text=msg)]

        elif name == "llm_test_providers":
            results = []
            for state in service.get_available_providers():
                try:
                    result = await service.complete(
                        prompt="Say 'OK'",
                        preferred_provider=state.config.name,
                        max_tokens=10,
                    )
                    results.append(
                        f"✅ {state.config.name}: OK ({result['response_time']}s)"
                    )
                except Exception as e:
                    results.append(f"❌ {state.config.name}: {str(e)[:100]}")
            if not results:
                results.append("No providers available. Check API keys.")
            return [TextContent(type="text", text="\n".join(results))]

        elif name == "llm_list_providers":
            import os
            lines = ["# Configured Providers\n"]
            for pname, state in service._providers.items():
                cfg = state.config
                has_key = bool(os.environ.get(cfg.api_key_env, "")) if cfg.requires_key else True
                lines.append(
                    f"**{pname}** (priority {cfg.priority})\n"
                    f"  URL: {cfg.base_url}\n"
                    f"  Model: {cfg.default_model}\n"
                    f"  Format: {cfg.format} | Key: {'✅' if has_key else '❌'}\n"
                    f"  Limits: RPM={cfg.rate_limit_rpm or '∞'}, Daily={cfg.daily_limit or '∞'}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    logger.info("Starting LLM Rotation MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
