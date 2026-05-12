---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b3-7209-b594-21bbc7176a5e
---

# 2.10 Circuit Breaker

**Где используется:** `.claude/hooks/shared/circuit_breaker.py`
**Как работает:** Три состояния: CLOSED → OPEN (при 5 ошибках) → HALF_OPEN (через 300s) → CLOSED (при 2 успехах). Декоратор `@with_circuit_breaker("hook-name")` оборачивает хуки.
