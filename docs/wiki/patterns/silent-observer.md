---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.7 Silent Observer

**Где используется:** `.claude/hooks/task-protocol-observer.py`
**Как работает:** PostToolUse хук молча обновляет состояние в SessionState после каждого вызова инструмента (TaskCreate → decomposed, Skill → skill_checked, llm_complete → delegated).
