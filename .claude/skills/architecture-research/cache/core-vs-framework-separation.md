# Research: Core vs Framework Separation

## Date: 2026-02-12

## Sources

### 1. Monorepo Patterns (Web Search)
- **Mercari multi-product monorepo**: Products vs InHouse layers, dependency enforcement, single version policy
- **Nx agent-aware monorepos**: Boundary enforcement via lint rules, explicit public APIs
- **Key insight**: Separate by lifecycle speed, enforce boundaries explicitly

### 2. Claude Code Portability (Web Search)
- **User-level** `~/.claude/` — personal settings, hooks, skills (apply to ALL projects)
- **Project-level** `.claude/` — project-specific, committed to git
- **Merge behavior**: Hooks from both levels fire in parallel (additive). Skills merge by priority (Enterprise > Personal > Project). Settings cascade (project overrides user)
- **Plugin marketplace** (Dec 2025): Bundles of commands, hooks, skills, MCP tools

### 3. Current Project Inventory (Codebase Analysis)
- **Overall coupling**: 73% framework-specific, 27% generic/reusable
- **Hook protocol** (BaseHook, I/O): 100% generic
- **Triad Factory algorithm**: 90% generic
- **Generic hooks**: root-clutter-guard (85%), bulk-action-guard (75%), ralph_* (60-80%)
- **Domain hooks**: research-task-detector (15% generic), knowledge-cache-reminder (20%)
- **Generic skills**: triad-factory (90%), create-hook (80%), doc-to-skill (60%), task-evaluation (70%)
- **Domain skills**: 1c-doc-research, tech-research, architecture-research, pdf-knowledge (5-10%)
- **settings.json**: 98% framework-specific (absolute paths)
- **CLAUDE.md**: 90% framework-specific
- **MEMORY.md**: 85% framework-specific (already in ~/.claude/projects/)

## Key Findings
1. Claude Code natively supports user-level + project-level merge — no custom tooling needed
2. Hook protocol and Triad Factory are the most reusable Core components
3. Domain hooks need full keyword rewrite for new projects — better to keep project-level
4. Ralph Wiggum system is generic (self-correcting loops) but activator signals are domain-specific
5. MEMORY.md already lives in user-level path (~/.claude/projects/) — natural separation point
