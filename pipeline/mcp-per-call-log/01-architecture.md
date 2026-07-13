# 01 Планирование — P2.3 per-call лог MCP-серверов (roadmap 260713 / B9)

## Цель
Внутренний per-call лог у двух критичных MCP-серверов (memory-orchestrator, 1c-mcp-crud) —
второй источник истины, переживающий падение stdio-транспорта ДО Claude Code Post-хука.
Пишет `{ts, server, tool, ok, ms, error_type}` → `.claude/cache/mcp-<server>-calls.jsonl`.

## Критичные файлы
- `scripts/mcp_call_log.py` (новый shared helper, stdlib-only)
- `src/memory/orchestrator/memory_orchestrator.py` (обёртка call_tool)
- `scripts/mcp_1c_stdio_launcher.py` (монки-патч OneCClient.call_tool)

## Инварианты
Fail-soft (никогда не роняет сервер), metadata-only, opt-out `MCP_CALL_LOG_DISABLE=1`, ротация 2MB.
