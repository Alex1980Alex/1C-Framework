---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.5 Multi-Level Enforcement

**Где используется:** `.claude/hooks/code-skill-enforcer.py`
**Как работает:** 6 уровней проверки: B (directory rules) → A (content patterns) → A.1 (research protocol) → C (bash commands) → D (research cache) → E (post-verification) → F (LEARN phase). Блокирует Write/Edit без активации нужного скилла.
