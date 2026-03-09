# Phase 59: AST-based BSL Indexing

**Priority:** CRITICAL | **Effort:** 3-5 days | **Depends on:** -- | **Effect:** +44% recall

**Goal:** Parse BSL -> index by symbols (procedure, function), not by files.

---

## Problem Statement

Current indexing treats entire BSL files as single chunks:

```
File: CommonModule.DocumentProcessing.bsl (500 lines, 15 procedures)
  -> One chunk in index -> one embedding -> loss of individual procedure semantics
```

This means:
- Embedding averages semantics of 15 unrelated procedures
- Search returns whole file instead of specific procedure
- Impossible to find specific function by its logic

---

## Target State

```
File: CommonModule.DocumentProcessing.bsl
  -> Procedure HandlePosting() -> separate embedding + metadata
  -> Function GetMovements() -> separate embedding + metadata
  -> ...15 symbols -> 15 embeddings with context
```

---

## Tasks

### Task 59.1: BSL AST Parser (Python)

#### 59.1.1 Parser Core
- Regex-based parser (MVP, sufficient for symbol extraction)
- Support both English and Russian BSL keywords
- Handle: procedures, functions, params, module variables, compilation directives

```python
PROCEDURE_RE = r"(?:^|\n)\s*(Procedure|Function|Процедура|Функция)\s+(\w+)\s*\(([^)]*)\)(?:\s+Export|\s+Экспорт)?"
END_RE = r"(?:^|\n)\s*(EndProcedure|EndFunction|КонецПроцедуры|КонецФункции)"
VAR_RE = r"(?:^|\n)\s*(Var|Перем)\s+(\w+)"
CALL_RE = r"(\w+)\.(\w+)\s*\("
```

#### 59.1.2 Symbol Extraction
- Extract symbol name, type (Procedure/Function), line range
- Detect Export flag
- Parse parameter list (name, default value, ByVal)
- Extract compilation directives (&AtServer, &AtClient, etc.)

#### 59.1.3 Call Extraction
- Direct calls: `ModuleName.MethodName()`
- Global context calls: `CatalogManager.FindByCode()`
- Query references: `FROM Catalog.Vehicles`, `JOIN Document.Invoice`
- Event subscriptions: `OnPosting`, `BeforeWrite`, `OnCreateAtServer`

#### 59.1.4 Comment/Doc Extraction
- Extract comment block before procedure (// comment lines)
- Extract inline comments
- Detect region markers (#Region / #EndRegion)

### Task 59.2: Symbol-Level Chunking

#### 59.2.1 Chunk Structure
Each symbol becomes a separate chunk with:
- **content**: full procedure/function body
- **metadata.name**: symbol name (e.g., `HandlePosting`)
- **metadata.type**: `Procedure` | `Function`
- **metadata.is_export**: boolean
- **metadata.params**: parameter list as string
- **metadata.module_path**: relative file path
- **metadata.module_type**: `CommonModule` | `ObjectModule` | `FormModule` | etc.
- **metadata.subsystem**: detected subsystem name
- **metadata.line_start**: first line number
- **metadata.line_end**: last line number
- **metadata.compilation_directive**: `&AtServer` | `&AtClient` | etc.

#### 59.2.2 Context Enrichment
- Prepend first 3 lines of procedure + comment before it
- Include module-level variables referenced in the procedure
- Include region name if procedure is inside a #Region

#### 59.2.3 Module-Level Chunk
- Create one "module summary" chunk per file
- Contains: module path, type, list of exported symbols, module variables
- Lower weight in search, used for context

### Task 59.3: Update Indexing Pipeline

#### 59.3.1 CLI Flag
- Add `--ast` mode to `smart_index_bsl.py`
- Default: current file-level indexing (backward compatible)
- `--ast`: new symbol-level indexing

#### 59.3.2 Qdrant Integration
- Store symbol chunks in existing `bsl_code_v2` collection (or new `bsl_code_v3`)
- Payload fields: all metadata from 59.2.1
- Filter support: by module_type, is_export, compilation_directive

#### 59.3.3 FTS5 Integration
- Update SQLite FTS5 index with symbol-level entries
- Multi-column: symbol_name (10x weight), body (1x weight), module_path (5x weight)

#### 59.3.4 Incremental Reindex
- Track file modification timestamps
- Only reparse changed files
- Update/delete symbols from changed files, add new ones

---

## Technology Options

| Approach | Pros | Cons |
|----------|------|------|
| ANTLR4 (Java) from bsl-parser | Full parser, 100% coverage | Requires Java |
| Regex-based (Python) | Simple, fast, sufficient | Can't parse complex constructs |
| Tree-sitter BSL grammar | Incremental, fast | DOES NOT EXIST - create from scratch |
| BSL Language Server API | Has LSP, symbols, diagnostics | Heavy (JVM), slow startup |

**Decision:** Start with regex-based parser, migrate to ANTLR4 if needed.

---

## Expected Effect

| Metric | Before (file-level) | After (symbol-level) | Improvement |
|--------|---------------------|---------------------|-------------|
| Recall@5 | ~0.45 | ~0.65 | +44% |
| Recall@10 | ~0.60 | ~0.80 | +33% |
| Chunks per file | 1 | ~10-15 | Granularity |
| Total chunks | ~2,004 | ~15,000-20,000 | Volume |

---

## Deliverables

- [ ] `src/bsl/parser/bsl_ast_parser.py` — regex-based BSL parser
- [ ] `src/bsl/parser/bsl_chunker.py` — symbol-level chunking
- [ ] `src/bsl/parser/models.py` — BSLSymbol, BSLModule data models
- [ ] Updated `smart_index_bsl.py` with `--ast` flag
- [ ] Unit tests for parser (10+ BSL files coverage)

---

## Acceptance Criteria

1. Parser extracts procedures/functions from 95%+ of BSL files without errors
2. Each symbol has correct metadata (name, type, params, export, line range)
3. Calls extracted with caller/callee information
4. `--ast` mode indexes to both Qdrant and FTS5
5. Eval dataset (Phase 58) shows measurable recall improvement
