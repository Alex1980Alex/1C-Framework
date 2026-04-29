"""Phase 8.12.8 — direct sync Z.AI completion (no asyncio loop reuse issues)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

ZAI_BASE = "https://api.z.ai/api/anthropic"
ZAI_MODEL = "glm-5.1"


def llm_complete(prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
    """Direct Z.AI Anthropic-compatible call. Sync, no asyncio."""
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY not set in env")
    r = httpx.post(
        f"{ZAI_BASE}/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": ZAI_MODEL, "max_tokens": max_tokens, "temperature": temperature,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120.0,
    )
    r.raise_for_status()
    data = r.json()
    blocks = data.get("content", [])
    for b in blocks:
        if b.get("type") == "text":
            return b.get("text", "").strip()
    return ""
