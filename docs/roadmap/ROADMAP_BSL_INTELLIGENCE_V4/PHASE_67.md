# Phase 67: External Tools Integration

**Priority:** LOW | **Effort:** 2-4 days | **Depends on:** -- | **Effect:** Ecosystem

**Goal:** Integrate external tools to extend BSL code intelligence capabilities.

---

## Integration Candidates

### Task 67.1: claude-hud

#### 67.1.1 Overview
- HUD overlay for Claude Code
- Shows current context, active tools, token usage
- Could display BSL-specific info (current module, call graph)

#### 67.1.2 Integration
- Add BSL panel: current module info, dependencies, related objects
- Show search results inline
- Display code style warnings

### Task 67.2: codebase-memory-mcp

#### 67.2.1 Overview
- github.com/DeusData/codebase-memory-mcp
- 64 language support, tree-sitter parsing, Louvain clustering
- Community detection in code graphs

#### 67.2.2 Integration
- Evaluate BSL support (likely needs custom grammar)
- If supported: use for community detection in call graph
- If not: adapt Louvain clustering algorithm for our call graph (Phase 61)

#### 67.2.3 Value
- Identify module communities (groups of tightly coupled modules)
- Suggest refactoring targets (modules spanning multiple communities)

### Task 67.3: parry

#### 67.3.1 Overview
- Code review and analysis tool
- Static analysis patterns
- Could complement bsl-language-server diagnostics

#### 67.3.2 Integration
- Evaluate BSL support
- If supported: integrate as additional analysis layer
- If not: skip (bsl-language-server covers this)

### Task 67.4: sonar-bsl-plugin

#### 67.4.1 Overview
- github.com/1c-syntax/sonar-bsl-plugin (252 stars)
- SonarQube plugin for BSL
- 100+ code quality rules

#### 67.4.2 Integration Options
- Option A: Run SonarQube server, query API for issues
- Option B: Extract rules, implement as standalone checks
- Option C: Use sonar-bsl-plugin CLI mode (if available)

#### 67.4.3 MCP Tool
- `bsl_quality_check(module)` — run quality rules on module
- Returns: issues with severity, line number, rule description
- Could use existing bsl-language-server diagnostics as alternative

### Task 67.5: bsl-language-server

#### 67.5.1 Overview
- github.com/1c-syntax/bsl-language-server (388 stars)
- Full LSP implementation for BSL
- Diagnostics, formatting, symbol resolution

#### 67.5.2 Current State
- Already partially integrated via Serena LSP
- Consider: direct integration for diagnostics

#### 67.5.3 Enhanced Integration
- Use diagnostics API for code quality checks
- Use symbol resolution for more accurate call graph
- Use formatting for code style normalization

---

## Evaluation Criteria

For each tool, evaluate:

| Criterion | Weight | Description |
|-----------|--------|-------------|
| BSL support | 30% | Does it support BSL natively? |
| Value added | 30% | What does it give beyond our existing tools? |
| Integration effort | 20% | How hard to integrate? |
| Maintenance burden | 20% | Ongoing cost of keeping it working? |

---

## Deliverables

- [ ] Evaluation report for each candidate tool
- [ ] Integration for 2-3 highest-value tools
- [ ] Updated `.mcp/bsl.json` with new servers (if any)
- [ ] Documentation of integrated tools

---

## Acceptance Criteria

1. Each candidate tool evaluated against criteria
2. At least 2 tools integrated (highest value/effort ratio)
3. No conflicts with existing MCP servers
4. Documentation updated with new capabilities
