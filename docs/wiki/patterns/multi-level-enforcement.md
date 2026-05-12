---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b6-7b81-bc1a-62b825de4b2a
---

# 2.5 Multi-Level Enforcement

**Где используется:** `.claude/hooks/code-skill-enforcer.py`
**Как работает:** 6 уровней проверки: B (directory rules) → A (content patterns) → A.1 (research protocol) → C (bash commands) → D (research cache) → E (post-verification) → F (LEARN phase). Блокирует Write/Edit без активации нужного скилла.
