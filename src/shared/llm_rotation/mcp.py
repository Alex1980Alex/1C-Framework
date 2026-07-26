"""
LLM Rotation MCP Server — 7 tools for multi-provider LLM access.

Tools: llm_complete, llm_complete_batch, llm_get_stats, llm_reset_provider,
llm_test_providers, llm_list_providers, llm_route_explain.

Migrated from D:\\1C-Enterprise_Framework\\shared\\llm_rotation_mcp.py
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llm-rotation-mcp")

# Per-call лог (2026-07-26): llm-rotation был ЕДИНСТВЕННЫМ активным сервером без
# второго источника истины (N-P2.2 обвязал memory-*/skill-learning, этот пропущен) —
# клиентский обрыв 60с был серверу невидим. Паттерн 1c-stdio-лаунчера: scripts-dir
# на path, bare import, fail-soft заглушка.
try:
    _SCRIPTS = str(Path(__file__).resolve().parents[3] / "scripts")
    if _SCRIPTS not in sys.path:
        sys.path.append(_SCRIPTS)
    from mcp_call_log import log_mcp_call as _log_call
except Exception:  # pragma: no cover — лог опционален, сервис важнее

    def _log_call(*_a, **_k) -> None:
        return None


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
                    "model": {
                        "type": "string",
                        "description": (
                            "Specific model (optional). Tiers available: 'haiku' | 'sonnet' "
                            "| 'opus' (opus is explicit-only: reachable ONLY by naming it "
                            "here, never via auto-fallback — pick it by task difficulty). "
                            "STRICT TIER MATCH: only a provider "
                            "that declares this model runs it — others are skipped, and if "
                            "nobody declares it the call FAILS instead of silently using "
                            "another model. Omit to let each provider use its own tier. "
                            "Use llm_route_explain to see the resulting route."
                        ),
                    },
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
                    "timeout": {
                        "type": "integer",
                        "description": (
                            "Request timeout in seconds. Auto by max_tokens tier: 90s (≤1024), "
                            "120s (≤3000), 240s (above)."
                        ),
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="llm_complete_batch",
            description=(
                "Send N prompts to LLM in PARALLEL using the same rotation/fallback as "
                "llm_complete. Use for batch generation (drafts, summaries, extraction) — "
                "one call instead of N sequential ones. A single prompt's failure is returned "
                "in its own slot and does NOT abort the batch. Note: claude-cli providers spawn "
                "a full Claude Code process per call, so their concurrency is capped separately "
                "by LLM_ROTATION_BATCH_CLI_CONCURRENCY."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Prompts to send; results are index-aligned with this list",
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional system prompt, shared across all prompts",
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Explicit tier 'haiku' | 'sonnet' | 'opus'; opus only on explicit "
                            "request, never via auto-fallback. STRICT tier match — only a "
                            "provider that declares the model executes it, otherwise the call "
                            "fails rather than silently swapping model. Applied to all prompts."
                        ),
                    },
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
                        "description": "Max tokens to generate per prompt",
                        "default": 2048,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Per-prompt timeout in seconds (auto by max_tokens tier)",
                    },
                    "concurrency": {
                        "type": "integer",
                        "description": (
                            "Override parallelism; claude-cli calls are still clamped "
                            "separately to protect commit memory"
                        ),
                    },
                },
                "required": ["prompts"],
            },
        ),
        Tool(
            name="llm_get_stats",
            description=(
                "Get statistics for all LLM providers: status, requests, errors, response times."
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
        Tool(
            name="llm_route_explain",
            description=(
                "Explain routing WITHOUT calling any LLM: attempt order, per-provider "
                "status/circuit-breaker, effective model, skip reasons (no key / cooldown / "
                "model incompatible), budget. Use to answer 'which model will I get and why'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model to check routing for (alias or full name, optional)",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    started = time.monotonic()

    def _done(ok: bool, error_type: str | None = None, **extra) -> None:
        # **extra (2026-07-26, находка ревьюера Р3): у `error_type` в этом стоке нет
        # читателя — единственный потребитель (scripts/tool_llm_judge.py) смотрит только
        # `ok`, поэтому батч «9 из 10 упало» читался бы как успех. Плоские счётчики
        # batch_total/batch_failed машиночитаемы и переживают отсутствие читателя.
        _log_call(
            "llm-rotation",
            name,
            ok=ok,
            ms=(time.monotonic() - started) * 1000.0,
            error_type=error_type,
            **extra,
        )

    try:
        service = _get_service()

        if name == "llm_route_explain":
            explained = service.explain_route(model=arguments.get("model"))
            _done(True)
            return [
                TextContent(type="text", text=json.dumps(explained, ensure_ascii=False, indent=1))
            ]

        if name == "llm_complete":
            result = await service.complete(
                prompt=arguments["prompt"],
                system_prompt=arguments.get("system_prompt"),
                model=arguments.get("model"),
                preferred_provider=arguments.get("preferred_provider"),
                temperature=arguments.get("temperature", 0.7),
                max_tokens=arguments.get("max_tokens", 2048),
                timeout=arguments.get("timeout"),
            )
            _done(True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False, indent=2),
                )
            ]

        if name == "llm_complete_batch":
            prompts = arguments.get("prompts")
            # Валидация на границе: пустой/неоднородный вход должен получить внятный
            # отказ здесь, а не невнятный обрыв внутри asyncio.gather.
            if not isinstance(prompts, list) or not prompts:
                raise ValueError(
                    "llm_complete_batch: 'prompts' must be a non-empty list of strings"
                )
            if not all(isinstance(p, str) for p in prompts):
                raise ValueError("llm_complete_batch: all items in 'prompts' must be strings")

            raw_results = await service.batch_complete(
                prompts,
                system_prompt=arguments.get("system_prompt"),
                model=arguments.get("model"),
                preferred_provider=arguments.get("preferred_provider"),
                temperature=arguments.get("temperature", 0.7),
                max_tokens=arguments.get("max_tokens", 2048),
                timeout=arguments.get("timeout"),
                concurrency=arguments.get("concurrency"),
                return_exceptions=True,
            )

            results = []
            ok_count = 0
            failed_count = 0
            for i, item in enumerate(raw_results):
                if isinstance(item, BaseException):
                    failed_count += 1
                    results.append(
                        {
                            "index": i,
                            "ok": False,
                            "error_type": type(item).__name__,
                            "error": str(item)[:500],
                        }
                    )
                else:
                    ok_count += 1
                    # Служебные ключи ПОСЛЕ спреда: иначе одно новое поле в результате
                    # провайдера тихо затрёт выравнивание по индексу и признак успеха.
                    results.append({**item, "index": i, "ok": True})

            payload = {
                "total": len(raw_results),
                "ok": ok_count,
                "failed": failed_count,
                "results": results,
            }
            # Текст собираем ДО _done: иначе падение сериализации дало бы вторую запись
            # на тот же вызов из внешнего except (двойной лог одного tool_call).
            text = json.dumps(payload, ensure_ascii=False, indent=2)

            # Честная телеметрия: частичный провал ≠ полный провал ≠ чистый успех.
            counts = {"batch_total": len(raw_results), "batch_failed": failed_count}
            if failed_count == 0:
                _done(True, **counts)
            elif ok_count == 0:
                _done(False, "all_failed", **counts)
            else:
                _done(True, "partial_failure", **counts)

            return [TextContent(type="text", text=text)]

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
                if pname.startswith("_") or "status" not in info:
                    continue
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
            _done(True)
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "llm_reset_provider":
            provider = arguments.get("provider", "")
            success = service.reset_provider(provider)
            if success:
                msg = f"Provider '{provider}' reset to HEALTHY"
            else:
                msg = f"Provider '{provider}' not found"
            _done(True)
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
                    results.append(f"✅ {state.config.name}: OK ({result['response_time']}s)")
                except Exception as e:
                    results.append(f"❌ {state.config.name}: {str(e)[:100]}")
            if not results:
                results.append("No providers available. Check API keys.")
            _done(True)
            return [TextContent(type="text", text="\n".join(results))]

        elif name == "llm_list_providers":
            import os

            lines = ["# Configured Providers\n"]
            for pname, state in service._providers.items():
                cfg = state.config
                has_key = bool(os.environ.get(cfg.api_key_env, "")) if cfg.requires_key else True
                # explicit_only виден в листинге: иначе провайдер выглядит как участник
                # авто-ротации, хотя доступен только по явному model= своего тира.
                tier_note = " — ТОЛЬКО по явному model=" if cfg.explicit_only else ""
                lines.append(
                    f"**{pname}** (priority {cfg.priority}){tier_note}\n"
                    f"  URL: {cfg.base_url}\n"
                    f"  Model: {cfg.default_model}\n"
                    f"  Format: {cfg.format} | Key: {'✅' if has_key else '❌'}\n"
                    f"  Limits: RPM={cfg.rate_limit_rpm or '∞'}, Daily={cfg.daily_limit or '∞'}\n"
                )
            _done(True)
            return [TextContent(type="text", text="\n".join(lines))]

        _done(False, "unknown_tool")
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        _done(False, type(e).__name__)
        # Структурный конверт (2026-07-26): голая строка "Error: ..." для клиента
        # неотличима от успешного текста; JSON с ok:false машиночитаем.
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"ok": False, "tool": name, "error": str(e)[:500]}, ensure_ascii=False
                ),
            )
        ]


async def main():
    logger.info("Starting LLM Rotation MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
