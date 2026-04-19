---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.8 Error Classifier

**Где используется:** `.claude/hooks/posttooluse-bash-errors.py`
**Как работает:** Классифицирует ошибки bash-команд по типам (pytest_failure, git_conflict, pip_error) и возвращает `hookSpecificOutput` с рекомендацией.
