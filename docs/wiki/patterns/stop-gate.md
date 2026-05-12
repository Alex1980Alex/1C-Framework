---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8ba-7c41-8348-642e8919c5a2
---

# 2.9 Stop Gate

**Где используется:** `.claude/hooks/ralph_wiggum_stop.py`, `.claude/hooks/git-commit-enforcer.py`
**Как работает:** Stop хуки проверяют финальное состояние. `ralph_wiggum_stop` — проверяет критерии завершения автоцикла. `git-commit-enforcer` — требует чистый working tree в watched paths.
