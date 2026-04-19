---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.6 Guard Gate

**Где используется:** `.claude/hooks/z-ai-write-guard.py`, `.claude/hooks/approval-gate.py`
**Как работает:** PreToolUse хуки перехватывают операции записи и блокируют при нарушении политик. `z-ai-write-guard` требует Z.AI делегирование для >15 строк кода. `approval-gate` требует одобренный OpenSpec.
