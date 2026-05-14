---
confidence: 0.3
related:
- '[[_index]]'
- '[[overview]]'
status: draft
tags:
- architecture
- automation
- triad
title: Hooks + Skills + MCP Triad
unified_id: 019e1e30-10a7-7de2-ab96-bb7c1755b1aa
---

Three-layer automation architecture: Hooks (event-driven), Skills (knowledge),
MCP (capability). See skill `hooks-skills-mcp-triad` for the canonical reference.

## Layers

- **Hooks** (`.claude/hooks/`): PreToolUse / PostToolUse / Stop / UserPromptSubmit / SessionStart enforcers.
- **Skills** (`.claude/skills/`): domain knowledge + workflows.
- **MCP servers**: external capabilities (1c-debug-hmr, bsl-semantic-search, etc.).

**Status: stub.** Expand with sequence diagrams (event flow, enforcement chains) and table of all 30+ registered hooks.
