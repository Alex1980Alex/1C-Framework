---
confidence: 0.3
related:
- '[[_index]]'
- '[[overview]]'
status: draft
tags:
- 1c
- bsl
- integration
title: BSL Integration
unified_id: 019e1e30-10a8-7b56-9b33-9abba2cfc457
---

Integration points between the Python PDF framework and 1С:Предприятие BSL (`src/bsl/`). Canonical reference in
`CLAUDE.md` BSL Development section.

## Components

- `src/bsl/semantic_search/`: vector search over BSL code
- `src/bsl/mcp_server/`: MCP server for BSL queries
- `tools/auto-documenter/`: Node.js BSL doc generator
- `tools/bsl-debug-server/`: Python RDBG wrapper (1c-debug, 1c-debug-hmr)

**Status: stub.** Expand with embedding-pipeline diagram + MCP tool list.
