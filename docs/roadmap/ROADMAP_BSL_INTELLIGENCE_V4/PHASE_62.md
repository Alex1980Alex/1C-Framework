# Phase 62: 1C Object Knowledge Graph

**Priority:** MEDIUM | **Effort:** 4-6 days | **Depends on:** -- | **Effect:** Context

**Goal:** Metadata object graph — links between catalogs, documents, registers, subsystems.

---

## Problem Statement

Claude knows 1C platform API but not the project structure:
- Which catalogs exist and their attributes?
- Which documents create movements in which registers?
- Which subsystems group which objects?
- How are objects related (document -> register -> catalog)?

---

## Tasks

### Task 62.1: Metadata Extraction

#### 62.1.1 Source: Configuration XML Files
- Parse `.xml` files from configuration export
- Extract: object type, name, attributes, table parts
- Handle: synonyms (Russian display names), comments

#### 62.1.2 Source: mdclasses (Optional)
- Java library from github.com/1c-syntax
- More reliable parsing than raw XML
- Alternative: call as subprocess or via API

#### 62.1.3 Source: BSL Code Analysis (Phase 59)
- Module-to-object mapping from folder structure
- Call analysis: which modules reference which objects
- Query analysis: FROM/JOIN clauses identify used objects

#### 62.1.4 Source: Folder Structure
- `Catalogs/Vehicles/` -> Catalog "Vehicles"
- `Documents/Invoice/` -> Document "Invoice"
- `InformationRegisters/Prices/` -> InformationRegister "Prices"
- `CommonModules/CommonModule1/` -> CommonModule "CommonModule1"

### Task 62.2: Knowledge Graph Schema

#### 62.2.1 Node Types
- **MetadataObject**: Catalog, Document, InformationRegister, AccumulationRegister, etc.
- **Attribute**: object attributes (requisites)
- **TablePart**: tabular sections
- **Subsystem**: configuration subsystems
- **CommonModule**: shared code modules
- **Enum**: enumerations

#### 62.2.2 Edge Types
- `HAS_ATTRIBUTE`: Object -> Attribute
- `HAS_TABLE_PART`: Object -> TablePart
- `BELONGS_TO_SUBSYSTEM`: Object -> Subsystem
- `CREATES_MOVEMENTS`: Document -> Register
- `REFERENCES`: Attribute -> Object (type reference)
- `USES_MODULE`: Object -> CommonModule
- `DEPENDS_ON`: Object -> Object (via code analysis)

#### 62.2.3 Storage: SQLite Graph
```sql
CREATE TABLE objects (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,       -- Catalog, Document, Register, etc.
    name TEXT NOT NULL,
    synonym TEXT,             -- Russian display name
    comment TEXT,
    subsystem TEXT
);

CREATE TABLE attributes (
    id TEXT PRIMARY KEY,
    object_id TEXT REFERENCES objects(id),
    name TEXT NOT NULL,
    type TEXT,                -- String, Number, reference type
    synonym TEXT,
    is_required BOOLEAN
);

CREATE TABLE table_parts (
    id TEXT PRIMARY KEY,
    object_id TEXT REFERENCES objects(id),
    name TEXT NOT NULL,
    synonym TEXT
);

CREATE TABLE relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    metadata TEXT              -- JSON with extra info
);
```

### Task 62.3: Graph Builder

#### 62.3.1 XML Parser
- Walk configuration export directory
- Parse each object's XML definition
- Build nodes and edges

#### 62.3.2 Code-Based Relations
- Merge relations discovered from BSL code (Phase 59/61)
- Add `DEPENDS_ON` edges from call graph
- Add `QUERIES` edges from SQL analysis

#### 62.3.3 Incremental Update
- Track file modification times
- Only reparse changed objects
- Update graph incrementally

### Task 62.4: MCP Tools

#### 62.4.1 bsl_objects(type)
- Input: object type (Catalog, Document, Register, etc.)
- Output: list of objects with name, synonym, subsystem
- Options: filter by subsystem

#### 62.4.2 bsl_object_info(name)
- Input: object name
- Output: full info — attributes, table parts, movements, related modules
- Includes: type references in attributes

#### 62.4.3 bsl_related(name)
- Input: object name
- Output: related objects (references, movements, dependencies)
- Options: depth, relation_type filter

#### 62.4.4 bsl_subsystem(name)
- Input: subsystem name
- Output: all objects in subsystem with types
- Nested subsystems support

---

## Deliverables

- [ ] `src/bsl/knowledge_graph/xml_parser.py` — configuration XML parser
- [ ] `src/bsl/knowledge_graph/graph_builder.py` — graph construction
- [ ] `src/bsl/knowledge_graph/graph_db.py` — SQLite graph storage + queries
- [ ] `src/bsl/knowledge_graph/models.py` — MetadataObject, Attribute, Relation models
- [ ] `src/bsl/mcp_server/tools/object_info.py` — MCP tools
- [ ] `data/bsl_knowledge_graph.db` — populated graph
- [ ] Unit tests

---

## Acceptance Criteria

1. All metadata objects from configuration parsed and stored
2. Attribute type references resolved to target objects
3. Document-Register movement links detected
4. Subsystem hierarchy preserved
5. MCP tools return correct results
6. Graph queryable in <10ms
