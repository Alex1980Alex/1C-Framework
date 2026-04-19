---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.1 BaseHook Protocol

**Где используется:** все хуки в `.claude/hooks/`
**Ключевые классы:** `BaseHook`, `HookInput`, `HookOutput`, `HookEvent`
**Как работает:** Каждый хук читает JSON из stdin (`HookInput`), обрабатывает и пишет JSON в stdout (`HookOutput`). При ошибке — graceful degradation (sys.exit(0)). Кодировка строго UTF-8.
