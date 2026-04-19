---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.13 3-Tier Pipeline

**Где используется:** весь lifecycle хуков Claude Code
**Как работает:**
1. `UserPromptSubmit` — роутинг (skill-router, research-task-detector)
2. `PreToolUse` — enforcement (code-skill-enforcer, z-ai-write-guard, approval-gate)
3. `PostToolUse` — observation (task-protocol-observer, delegation-tracker, auto-git-save)
4. `Stop` — финальные проверки (ralph_wiggum_stop, git-commit-enforcer)

---
