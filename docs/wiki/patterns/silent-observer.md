---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b9-7159-87d1-6558eac10d50
---

# 2.7 Silent Observer

**Где используется:** `.claude/hooks/task-protocol-observer.py`
**Как работает:** PostToolUse хук молча обновляет состояние в SessionState после каждого вызова инструмента (TaskCreate → decomposed, Skill → skill_checked, llm_complete → delegated).
