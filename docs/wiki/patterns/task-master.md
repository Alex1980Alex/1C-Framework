---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.11 Task Master

**Где используется:** `.claude/hooks/shared/task_master.py`
**Как работает:** Управляет mandatory tasks в `.claude/cache/hook-todos.json`: add_task → update_task_metadata → complete_task_by_hook. Используется auto-git-save и другими хуками.
