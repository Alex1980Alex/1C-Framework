---
confidence: 0.3
related:
- '[[_index]]'
status: draft
tags:
- reference
- hooks
- automation
title: Hooks Reference
unified_id: 019e1e30-10a7-7c47-9b31-7f95bc84cda4
---

Reference index for all Claude Code hooks in `.claude/hooks/`. Canonical enumeration lives in skill `hooks-skills-mcp-triad` SKILL.md (table grouped by event: PreToolUse, PostToolUse, Stop, UserPromptSubmit, SessionStart).

## Hook events

- PreToolUse: validate before tool execution
- PostToolUse: react after tool success
- Stop: enforcer chain on conversation end
- UserPromptSubmit: classify/route prompts

**Status: stub.** Expand with per-hook contract specs.
