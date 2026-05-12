---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b2-7dc4-b01d-d2296f7e9696
---

# 2.1 BaseHook Protocol

**Где используется:** все хуки в `.claude/hooks/`
**Ключевые классы:** `BaseHook`, `HookInput`, `HookOutput`, `HookEvent`
**Как работает:** Каждый хук читает JSON из stdin (`HookInput`), обрабатывает и пишет JSON в stdout (`HookOutput`). При ошибке — graceful degradation (sys.exit(0)). Кодировка строго UTF-8.
