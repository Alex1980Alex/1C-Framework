# memory-protocol-stop — Планирование

## Запрос
Сделать обязательный memory-цикл (гл.27, doc 43.4) принудительным через хук — «как с pipeline-protocol».

## Решение
Stop-энфорсер `memory-protocol-stop.py` (паттерн Enforcer). Hard condition-based block + opt-out
(`MEMORY_PROTOCOL_DISABLE=1`) — точно как pipeline-protocol-stop.

## Критичные находки (до реализации)
1. `hook-invocations.jsonl` логирует ХУКИ, не MCP-вызовы (0 `mcp__`-строк) → детект памяти **по транскрипту**
   (фактические tool_use, как roadmap-progress-enforcer), НЕ по raw-тексту (имена инструментов есть в прозе/доках).
2. 1C-сигнал по title пайплайна: **строго `startswith("1С-задача (")`** — реальные 1С-пайплайны от моста =
   `f"1С-задача ({command}): {slug}"`. Loose `startswith("1С-задача")` ложно ловил бы framework-пайплайн
   «1С-задача из чата: классификатор…» (поймано до прогона).
