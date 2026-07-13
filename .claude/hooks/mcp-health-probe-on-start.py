#!/usr/bin/env python3
"""
Hook: mcp-health-probe-on-start
Event: SessionStart
Matcher: (none)
Purpose: Проактивный health-check зависимостей MCP-серверов (roadmap 260713 P1.2, B7).
         Инлайн-прогон scripts/probe_mcp_health.py (Qdrant/TEI HTTP + ключевые SQLite):
         быстрый когда всё up (~<300мс), баннер ТОЛЬКО при down (иначе молчит).
         Закрывает пробел «MCP health_check-tools никто не вызывает автоматически» —
         вместо самих tools (их исполняет клиент, серверы тяжёлые) пробим их deps.

Timeout: 10s (4 пробы × таймаут 1.5с; худший случай ~6с при down HTTP + SQLite-локах).
Exit: всегда 0 (informational). Opt-out: MCP_HEALTH_PROBE_DISABLE=1.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS = PROJECT_ROOT / "scripts"


class McpHealthProbe(BaseHook):
    HOOK_NAME = "McpHealthProbe"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("MCP_HEALTH_PROBE_DISABLE") == "1":
            return None
        try:
            if str(_SCRIPTS) not in sys.path:
                sys.path.insert(0, str(_SCRIPTS))
            import probe_mcp_health

            summary = probe_mcp_health.run(timeout=1.5)
        except Exception:
            return None  # graceful — health-probe никогда не ломает старт сессии

        down = summary.get("down") or []
        if not down:
            return None  # всё up — тихо (quiet wakeups rare)

        lines = [
            f"[MCP-HEALTH] Недоступны зависимости MCP-серверов ({len(down)}/{summary.get('total')}):"
        ]
        for d in down:
            affects = ", ".join(d.get("affects", []))
            lines.append(f"  🔴 `{d['target']}` ({d.get('endpoint', '')}) — {d.get('error', '')}")
            if affects:
                lines.append(f"      деградируют: {affects}")
        lines.append(
            "  Qdrant/TEI поднимаются в фоне (ensure-docker-qdrant / tei-warmup); "
            "SQLite-БД проверь вручную. История: `data/mcp-health.jsonl`."
        )
        return HookOutput().system_message("\n".join(lines))


if __name__ == "__main__":
    McpHealthProbe().run()
