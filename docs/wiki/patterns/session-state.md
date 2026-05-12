---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b9-7fdf-9c3f-e0671cf313d9
---

# 2.2 SessionState

**Где используется:** `.claude/hooks/shared/session_state.py`
**Как работает:** Singleton-файл `session-skills.json` координирует состояние между 15+ хуками. Хуки читают/пишут активные навыки, флаги делегирования и фазы task protocol.
