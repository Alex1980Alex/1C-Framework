---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.10 Circuit Breaker

**Где используется:** `.claude/hooks/shared/circuit_breaker.py`
**Как работает:** Три состояния: CLOSED → OPEN (при 5 ошибках) → HALF_OPEN (через 300s) → CLOSED (при 2 успехах). Декоратор `@with_circuit_breaker("hook-name")` оборачивает хуки.
