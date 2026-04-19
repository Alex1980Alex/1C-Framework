---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.2 SessionState

**Где используется:** `.claude/hooks/shared/session_state.py`
**Как работает:** Singleton-файл `session-skills.json` координирует состояние между 15+ хуками. Хуки читают/пишут активные навыки, флаги делегирования и фазы task protocol.
