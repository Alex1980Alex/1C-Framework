# Phase 61: BSL Call Graph and Dependency Analysis

**Priority:** HIGH | **Effort:** 5-7 days | **Depends on:** Phase 59 | **Effect:** New capability

**Goal:** Build call graph between modules for impact analysis and navigation.

---

## What This Enables

- "Which modules call BlockVehicle()?" -> exact answer in <10ms
- "If I change catalog Vehicles, what breaks?" -> impact graph
- Dead code detection -> unused exported procedures
- Navigation by dependencies instead of files

---

## Tasks

### Task 61.1: Call Extraction from AST

Extension of Phase 59 parser to extract call relationships:

#### 61.1.1 Direct Calls
- Pattern: `ModuleName.MethodName(args)`
- Extract: caller symbol, callee module, callee method, line number
- Handle aliased modules (local variables assigned from global)

#### 61.1.2 Global Context Calls
- Pattern: `CatalogManager.FindByCode()`, `Documents.Invoice.CreateDocument()`
- Map to 1C platform API objects
- Distinguish platform API calls from user module calls

#### 61.1.3 Query References
- Parse query text literals (`Query.Text = "..."`)
- Extract: `FROM Catalog.Vehicles`, `JOIN Document.Invoice`
- Map to metadata objects

#### 61.1.4 Event Subscriptions
- Detect event handler patterns: `OnPosting`, `BeforeWrite`, `OnCreateAtServer`
- Map to event types and object types
- Link form event handlers to their forms

### Task 61.2: SQLite Graph Storage

#### 61.2.1 Schema

```sql
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,           -- module_path:symbol_name
    name TEXT NOT NULL,
    type TEXT NOT NULL,            -- Procedure | Function
    module_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    is_export BOOLEAN,
    params TEXT,                   -- JSON array of param names
    doc_comment TEXT,
    compilation_directive TEXT     -- &AtServer, &AtClient, etc.
);

CREATE TABLE calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_id TEXT REFERENCES symbols(id),
    callee_name TEXT NOT NULL,     -- method name
    callee_module TEXT,            -- module name (NULL for local calls)
    line_number INTEGER,
    call_type TEXT                 -- direct | global_context | query | event
);

CREATE TABLE module_metadata (
    path TEXT PRIMARY KEY,
    module_type TEXT,              -- CommonModule | ObjectModule | FormModule | etc.
    subsystem TEXT,
    object_type TEXT,              -- Catalog | Document | Register | etc.
    object_name TEXT
);
```

#### 61.2.2 Indexes
- `symbols(module_path)` — find all symbols in module
- `symbols(name, is_export)` — find exported symbols by name
- `calls(caller_id)` — outgoing calls from symbol
- `calls(callee_name, callee_module)` — incoming calls to symbol
- `module_metadata(subsystem)` — modules by subsystem

#### 61.2.3 Database Location
- `data/bsl_call_graph.db` — SQLite database
- Versioned: track schema version for migrations

### Task 61.3: Graph Query API

#### 61.3.1 Call Graph Queries
- `get_callers(module, method)` — who calls this method?
- `get_callees(module, method)` — what does this method call?
- `get_call_chain(module, method, depth)` — transitive call chain
- `get_call_count(module, method)` — how many callers?

#### 61.3.2 Impact Analysis
- `impact_analysis(module, method)` — all affected modules if this changes
- `impact_analysis_object(object_type, object_name)` — affected modules for metadata object change
- Depth-limited BFS traversal
- Return: list of (module, method, distance, path)

#### 61.3.3 Dead Code Detection
- `find_dead_code()` — exported procedures never called from outside
- `find_unused_variables()` — module variables never referenced
- `find_orphan_modules()` — modules with no incoming/outgoing calls
- Filters: exclude test modules, exclude event handlers (they're called by platform)

#### 61.3.4 Dependency Statistics
- `module_coupling(module)` — afferent + efferent coupling
- `most_called_symbols(top_n)` — hottest procedures
- `most_dependent_modules(top_n)` — highest coupling
- `subsystem_dependencies()` — inter-subsystem call matrix

### Task 61.4: MCP Tools

#### 61.4.1 bsl_call_graph
- Input: module name, method name
- Output: callers and callees with line numbers
- Options: direction (in/out/both), depth

#### 61.4.2 bsl_impact_analysis
- Input: module name, method name (or object type + name)
- Output: affected modules sorted by distance
- Options: max_depth, include_queries

#### 61.4.3 bsl_dead_code
- Input: optional scope (subsystem, module_type)
- Output: list of unused exported procedures
- Options: exclude_patterns (event handlers, tests)

#### 61.4.4 bsl_dependencies
- Input: module name
- Output: dependency graph (imports, exports, coupling metrics)
- Options: format (list, mermaid)

### Task 61.5: Visualization (Optional)

#### 61.5.1 Mermaid Diagrams
- Generate Mermaid flowchart from call graph
- Limit: top-N nodes by PageRank
- Color by module type

#### 61.5.2 Statistics Dashboard
- Total symbols, calls, modules
- Top-10 most called procedures
- Top-10 highest coupling modules
- Dead code percentage

---

## Inspiration

- codebase-memory-mcp (github.com/DeusData) — 64 langs, tree-sitter, Louvain clustering
- code-graph-mcp (github.com/entrepeneur4lyf) — PageRank, ast-grep
- Axon (github.com/harshkedia177) — graph + embeddings + communities

---

## Deliverables

- [ ] `src/bsl/graph/call_extractor.py` — call extraction from parsed AST
- [ ] `src/bsl/graph/graph_db.py` — SQLite graph storage + queries
- [ ] `src/bsl/graph/impact_analyzer.py` — impact analysis engine
- [ ] `src/bsl/graph/dead_code_detector.py` — dead code detection
- [ ] `src/bsl/mcp_server/tools/call_graph.py` — MCP tool
- [ ] `src/bsl/mcp_server/tools/impact_analysis.py` — MCP tool
- [ ] `src/bsl/mcp_server/tools/dead_code.py` — MCP tool
- [ ] `data/bsl_call_graph.db` — populated graph database
- [ ] Unit tests for all query types

---

## Acceptance Criteria

1. Call graph populated for all 2,004 BSL files
2. `get_callers()` returns results in <10ms
3. `impact_analysis()` returns results in <100ms
4. Dead code detector finds real unused procedures
5. MCP tools accessible from Claude Code
6. No false positives on event handlers (excluded from dead code)
