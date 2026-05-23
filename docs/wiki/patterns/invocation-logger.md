---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b6-75ac-91c2-544b823a0589
---

# 2.12 Invocation Logger

**Где используется:** `.claude/hooks/shared/invocation_logger.py`
**Как работает:** Append-only JSONL лог всех вызовов хуков. Каждая запись: timestamp, hook, event, tool, elapsed_ms,
outcome. Ротация при 10MB.
