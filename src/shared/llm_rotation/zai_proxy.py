"""
Z.AI Proxy — OpenAI-compatible proxy for Z.AI/Anthropic API.

Translates OpenAI Chat Completion format to Anthropic Messages API.
Supports GLM-5 deep thinking mode and tool streaming.

Migrated from D:\\1C-Enterprise_Framework\\shared\\zai_proxy.py
Adapted: uses project-local config, standalone module.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from aiohttp import ClientSession, ClientTimeout, web
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("zai-proxy")

# Configuration
ZAI_API_KEY = os.getenv("ZAI_API_KEY", os.getenv("LLM_ROTATION_ZAI_API_KEY", ""))
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/anthropic")
ZAI_DEFAULT_MODEL = os.getenv("ZAI_DEFAULT_MODEL", "glm-5")

# GLM-5 limits
GLM_5_MAX_TOKENS = 128_000
GLM_5_CONTEXT_WINDOW = 200_000
GLM_5_DEFAULT_TEMPERATURE = 1.0
GLM_5_THINKING_ENABLED = True


def openai_to_anthropic(openai_request: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI Chat Completion request to Anthropic Messages format."""
    messages = openai_request.get("messages", [])

    # Extract system message
    system_text = ""
    converted_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_text = content
        elif role == "tool":
            converted_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": content,
                }],
            })
        else:
            mapped_role = "assistant" if role == "assistant" else "user"
            converted_messages.append({"role": mapped_role, "content": content})

    anthropic_req: Dict[str, Any] = {
        "model": openai_request.get("model", ZAI_DEFAULT_MODEL),
        "messages": converted_messages,
        "max_tokens": min(
            openai_request.get("max_tokens", 4096),
            GLM_5_MAX_TOKENS,
        ),
    }

    if system_text:
        anthropic_req["system"] = system_text

    # Sampling parameters
    if "temperature" in openai_request:
        anthropic_req["temperature"] = openai_request["temperature"]
    if "top_p" in openai_request:
        anthropic_req["top_p"] = openai_request["top_p"]

    # GLM-5: deep thinking
    if GLM_5_THINKING_ENABLED:
        anthropic_req["thinking"] = {"type": "enabled", "budget_tokens": 10000}

    # Tools
    tools = openai_request.get("tools", [])
    if tools:
        anthropic_tools = []
        for tool in tools:
            fn = tool.get("function", {})
            anthropic_tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object"}),
            })
        anthropic_req["tools"] = anthropic_tools

    return anthropic_req


def anthropic_to_openai(anthropic_response: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Anthropic Messages response to OpenAI Chat Completion format."""
    content_blocks = anthropic_response.get("content", [])
    text_parts = []
    tool_calls = []
    reasoning_content = None

    for block in content_blocks:
        block_type = block.get("type", "")
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        elif block_type == "thinking":
            reasoning_content = block.get("thinking", "")
        elif block_type == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                },
            })

    stop_reason = anthropic_response.get("stop_reason", "end_turn")
    finish_reason = _map_stop_reason(stop_reason)

    message: Dict[str, Any] = {
        "role": "assistant",
        "content": "\n".join(text_parts) if text_parts else None,
    }
    if reasoning_content:
        message["reasoning_content"] = reasoning_content
    if tool_calls:
        message["tool_calls"] = tool_calls
        if not text_parts:
            message["content"] = None

    usage = anthropic_response.get("usage", {})

    return {
        "id": f"chatcmpl-{anthropic_response.get('id', 'unknown')}",
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": anthropic_response.get("model", ZAI_DEFAULT_MODEL),
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    }


def _map_stop_reason(stop_reason: str) -> str:
    """Map Anthropic stop reason to OpenAI finish reason."""
    mapping = {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
        "max_tokens": "length",
    }
    return mapping.get(stop_reason, "stop")


class ZAIProxy:
    """HTTP proxy server translating OpenAI format to Z.AI/Anthropic API."""

    def __init__(self, port: int = 8000):
        self.port = port
        self._session: Optional[ClientSession] = None
        self._stats = {
            "request_count": 0,
            "stream_request_count": 0,
            "thinking_request_count": 0,
            "total_time": 0.0,
        }

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                timeout=ClientTimeout(total=300)
            )
        return self._session

    async def handle_chat(self, request: web.Request) -> web.StreamResponse:
        """POST /v1/chat/completions — main proxy endpoint."""
        openai_req = await request.json()
        stream = openai_req.get("stream", False)

        anthropic_req = openai_to_anthropic(openai_req)

        if stream:
            return await self._handle_stream(request, anthropic_req)
        return await self._handle_normal(anthropic_req)

    async def _handle_normal(self, anthropic_req: Dict[str, Any]) -> web.Response:
        """Non-streaming request."""
        session = await self._get_session()
        headers = {
            "x-api-key": ZAI_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        start = datetime.now()
        async with session.post(
            f"{ZAI_BASE_URL}/v1/messages",
            json=anthropic_req,
            headers=headers,
        ) as resp:
            data = await resp.json()
            status = resp.status

        elapsed = (datetime.now() - start).total_seconds()
        self._stats["request_count"] += 1
        self._stats["total_time"] += elapsed

        if status != 200:
            return web.json_response(data, status=status)

        openai_resp = anthropic_to_openai(data)
        return web.json_response(openai_resp)

    async def _handle_stream(
        self, request: web.Request, anthropic_req: Dict[str, Any]
    ) -> web.StreamResponse:
        """Streaming request with SSE."""
        anthropic_req["stream"] = True

        session = await self._get_session()
        headers = {
            "x-api-key": ZAI_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        await response.prepare(request)

        self._stats["stream_request_count"] += 1

        async with session.post(
            f"{ZAI_BASE_URL}/v1/messages",
            json=anthropic_req,
            headers=headers,
        ) as resp:
            async for line in resp.content:
                decoded = line.decode("utf-8").strip()
                if not decoded or not decoded.startswith("data: "):
                    continue
                data_str = decoded[6:]
                if data_str == "[DONE]":
                    await response.write(b"data: [DONE]\n\n")
                    break
                try:
                    event = json.loads(data_str)
                    chunk = self._convert_stream_chunk(event)
                    if chunk:
                        await response.write(
                            f"data: {json.dumps(chunk)}\n\n".encode()
                        )
                except json.JSONDecodeError:
                    continue

        return response

    def _convert_stream_chunk(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert Anthropic stream event to OpenAI stream chunk."""
        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                return {
                    "object": "chat.completion.chunk",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": delta.get("text", "")},
                        "finish_reason": None,
                    }],
                }
            elif delta_type == "thinking_delta":
                return {
                    "object": "chat.completion.chunk",
                    "choices": [{
                        "index": 0,
                        "delta": {"reasoning_content": delta.get("thinking", "")},
                        "finish_reason": None,
                    }],
                }

        elif event_type == "message_delta":
            stop_reason = event.get("delta", {}).get("stop_reason", "end_turn")
            return {
                "object": "chat.completion.chunk",
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": _map_stop_reason(stop_reason),
                }],
            }

        return None

    async def handle_models(self, _request: web.Request) -> web.Response:
        """GET /v1/models"""
        return web.json_response({
            "object": "list",
            "data": [
                {"id": "glm-5", "object": "model", "owned_by": "zhipu"},
                {"id": "glm-4.6", "object": "model", "owned_by": "zhipu"},
                {"id": "glm-4.5-air", "object": "model", "owned_by": "zhipu"},
            ],
        })

    async def handle_health(self, _request: web.Request) -> web.Response:
        """GET /health"""
        return web.json_response({
            "status": "ok",
            "provider": "z.ai_direct",
            "model": ZAI_DEFAULT_MODEL,
            "version": "2.0",
        })

    async def handle_stats(self, _request: web.Request) -> web.Response:
        """GET /stats"""
        return web.json_response(self._stats)

    async def start(self) -> None:
        """Start the proxy server."""
        app = web.Application()
        app.router.add_post("/v1/chat/completions", self.handle_chat)
        app.router.add_get("/v1/models", self.handle_models)
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/stats", self.handle_stats)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Z.AI proxy started on port {self.port}")

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
