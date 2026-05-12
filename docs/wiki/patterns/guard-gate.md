---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b5-7be2-81fd-28a8034035cd
---

# 2.6 Guard Gate

**Где используется:** `.claude/hooks/z-ai-write-guard.py`, `.claude/hooks/approval-gate.py`
**Как работает:** PreToolUse хуки перехватывают операции записи и блокируют при нарушении политик. `z-ai-write-guard` требует Z.AI делегирование для >15 строк кода. `approval-gate` требует одобренный OpenSpec.
