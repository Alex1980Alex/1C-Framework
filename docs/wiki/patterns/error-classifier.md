---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b4-754e-9f79-5ebd35b49f5b
---

# 2.8 Error Classifier

**Где используется:** `.claude/hooks/posttooluse-bash-errors.py`
**Как работает:** Классифицирует ошибки bash-команд по типам (pytest_failure, git_conflict, pip_error) и возвращает `hookSpecificOutput` с рекомендацией.
