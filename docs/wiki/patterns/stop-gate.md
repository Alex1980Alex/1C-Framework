---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.9 Stop Gate

**Где используется:** `.claude/hooks/ralph_wiggum_stop.py`, `.claude/hooks/git-commit-enforcer.py`
**Как работает:** Stop хуки проверяют финальное состояние. `ralph_wiggum_stop` — проверяет критерии завершения автоцикла. `git-commit-enforcer` — требует чистый working tree в watched paths.
