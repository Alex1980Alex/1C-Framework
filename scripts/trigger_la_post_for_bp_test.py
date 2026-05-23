"""Trigger LA posting via 1c-mcp-crud HTTP service for BP fire test.

P1 acceptance validation for roadmap 260508. Posts ТМУТ-000006 to fire
the BP set on ObjectModule line 141 (OnPosting handler). The MCP HTTP
call hangs while target is stopped at BP — main session uses mcp__1c-debug
to inspect stack/vars/eval and then step Continue to resume.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import httpx

URL = "http://localhost/transport/hs/mcp/rpc"
USER = "a.terletskiy@sodrugestvo.ru"
PASSWORD = "Alex80Alex"
DOC_GUID = "326d2e61-4a6f-11f1-a14d-dc567b7507dc"
DOC_TYPE = "ДокументСсылка." "гкс_Лабораторный" "Анализ"
KEY_UID = "УникальныйИден" "тификатор"
KEY_TYPE = "ТипОбъекта"


async def main() -> int:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "post_document",
            "arguments": {
                "object_description": {
                    "_objectRef": True,
                    KEY_UID: DOC_GUID,
                    KEY_TYPE: DOC_TYPE,
                },
                "action": "post",
                "dry_run": False,
            },
        },
    }
    started = time.time()
    print(f"[{started:.0f}] POST {URL} (dry_run=false, BP expected)", flush=True)
    async with httpx.AsyncClient(
        auth=httpx.BasicAuth(USER, PASSWORD),
        timeout=httpx.Timeout(180.0),
    ) as c:
        try:
            r = await c.post(URL, json=payload)
            elapsed = time.time() - started
            print(f"[+{elapsed:.1f}s] HTTP {r.status_code}", flush=True)
            try:
                body = r.json()
            except ValueError:
                body = {"raw": r.text[:500]}
            print(json.dumps(body, ensure_ascii=False, indent=2), flush=True)
            return 0 if r.status_code < 400 else 1
        except httpx.TimeoutException:
            elapsed = time.time() - started
            print(f"[+{elapsed:.1f}s] TIMEOUT (BP probably stuck)", flush=True)
            return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
