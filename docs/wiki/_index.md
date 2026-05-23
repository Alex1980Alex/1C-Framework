---
confidence: 1.0
related:
- '[[overview]]'
- '[[triad-architecture]]'
- '[[PATTERNS]]'
status: active
tags:
- wiki
- index
- map
unified_id: 019e1e30-d82a-79e7-8f03-c9264380ac20
---

# Framework Wiki Map

Navigation index for the PDF Vector & Graph Framework knowledge base.

## Architecture Docs

| Document | Topic | Key Links |
|----------|-------|-----------|
| [[overview]] | Architecture layers, search strategies, data flows | All below |
| [[triad-architecture]] | Hooks + Skills + MCP integration pattern | [[hooks-reference]], [[skills-reference]] |
| [[ralph-wiggum]] | Autonomous loop + self-correction system | [[overview]] |
| [[hooks-reference]] | All 13 hooks: events, matchers, logic | [[skills-reference]], [[triad-architecture]] |
| [[skills-reference]] | All skills: triggers, workflows, cache | [[hooks-reference]], [[triad-architecture]] |
| [[PATTERNS]] | 15 arch + 13 automation patterns | [[overview]], [[bsl-integration]] |
| [[bsl-integration]] | BSL/1C development integration | [[PATTERNS]], [[overview]] |
| [[core-framework-separation]] | Integration structure (hooks + skills layout) | [[triad-architecture]] |
| [[SCHEMA]] | Wiki naming rules, frontmatter, promotion lifecycle | [[_index]], [[log]] |
| [[log]] | Chronology of promotions and session summaries | [[_index]], [[SCHEMA]] |

## Wiki Pages

| Section | Path | Description |
|---------|------|-------------|
| Drafts | `docs/wiki/drafts/` | Work-in-progress pages (auto-indexed by memory-first-hook) |
| Patterns | `docs/wiki/patterns/` | Extracted architectural and automation patterns |

## Memory System

| Layer | Storage | Weight |
|-------|---------|--------|
| SQLite | `data/memory_ai.db` | 0.30 |
| Qdrant | 3 collections (skill, experience, conversation) | 0.35 |
| .md files | `~/.claude/projects/.../memory/` | 0.15 |
| Wiki drafts | `docs/wiki/drafts/` | 0.20 |

## MCP Servers

| Server | Tool Prefix | Status |
|--------|-------------|--------|
| 1c-mcp-crud | `mcp__1c-mcp-crud__*` | Active |
| pdf-vector-graph | `mcp__pdf-vector-graph__*` | Active |
| bsl-semantic-search | `mcp__bsl-semantic-search__*` | Active |
| obsidian-mcp | `mcp__obsidian-mcp__*` | Disabled (needs Obsidian app) |

## Quick Links

- [[overview]] — start here
- [[PATTERNS]] — design patterns catalog
- [[triad-architecture]] — the core integration pattern
