---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8bb-7c6e-be07-0b4fc828f86e
---

# 2.11 Task Master

**Где используется:** `.claude/hooks/shared/task_master.py`
**Как работает:** Управляет mandatory tasks в `.claude/cache/hook-todos.json`: add_task → update_task_metadata →
complete_task_by_hook. Используется auto-git-save и другими хуками.
