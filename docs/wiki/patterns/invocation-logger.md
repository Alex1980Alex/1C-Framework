---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.12 Invocation Logger

**Где используется:** `.claude/hooks/shared/invocation_logger.py`
**Как работает:** Append-only JSONL лог всех вызовов хуков. Каждая запись: timestamp, hook, event, tool, elapsed_ms, outcome. Ротация при 10MB.
