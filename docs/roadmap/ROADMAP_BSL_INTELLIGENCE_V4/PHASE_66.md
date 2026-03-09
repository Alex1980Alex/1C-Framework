# Phase 66: BSL Coding Assistant

**Priority:** HIGH | **Effort:** 3-5 days | **Depends on:** Phases 59, 61, 62 | **Effect:** Code quality

**Goal:** Improve BSL code generation via project context.

---

## Problem Statement

Claude knows 1C platform API but lacks project-specific context when writing BSL code:
- Doesn't know existing similar procedures (may duplicate code)
- Doesn't know project coding conventions
- Doesn't know which objects/modules are available
- Doesn't know dependencies and call patterns

---

## Tasks

### Task 66.1: Auto-Context Hook

UserPromptSubmit hook that detects BSL coding requests and auto-fetches relevant context.

#### 66.1.1 Detection
- Triggers on: "напиши процедуру", "создай функцию", "реализуй", "добавь обработку"
- Also triggers on: file mentions ending in `.bsl`, explicit 1C/BSL keywords
- Does NOT trigger on: search queries, analysis questions

#### 66.1.2 Context Fetching
On trigger, automatically fetch and inject into system message:

**a) Similar Procedures**
- Search index for procedures similar to the request
- Top-3 most similar procedures with full body
- Purpose: Claude sees existing patterns and avoids duplication

**b) Related Objects**
- From knowledge graph (Phase 62): objects mentioned in the request
- Attributes, table parts, types
- Purpose: Claude knows exact field names and types

**c) Module Dependencies**
- If editing existing module: its current call graph (Phase 61)
- Imported modules, exported procedures
- Purpose: Claude knows what's available to call

**d) Module Template**
- If creating new module: template based on module type
- Header comments, standard regions, compilation directives
- Purpose: consistent structure

#### 66.1.3 Context Format
```
## Project Context (auto-fetched)

### Similar Existing Procedures
1. CommonModule.DocProcessing.HandlePosting() — [full body]
2. CommonModule.DocProcessing.ValidateDocument() — [full body]

### Related Objects
- Document.Invoice: Number, Date, Counterparty (CatalogRef.Counterparties), Products (TablePart)
- Catalog.Products: Code, Description, Price (Number), Unit (CatalogRef.Units)

### Available Dependencies
- CommonModule.ProductCalculation: CalcTotal(), CalcDiscount(), CalcTax()
- CommonModule.CommonFunctions: FormatDate(), FormatCurrency()

### Module Structure
Current module has 12 procedures, region "EventHandlers" with 3 handlers.
```

### Task 66.2: Code Style Extractor

#### 66.2.1 Convention Detection
Analyze existing codebase to extract:
- Naming conventions (Hungarian notation? PascalCase?)
- Comment style (// vs //)
- Error handling patterns (Try/Except usage)
- Variable naming patterns
- Region organization

#### 66.2.2 Style Rules File
- Generate `data/bsl_code_style.json` from analysis
- Rules: naming, structure, patterns, anti-patterns
- Inject into context when writing new code

#### 66.2.3 Style Validation (Optional)
- Post-generation check: does new code match style?
- Warn on violations, suggest fixes

### Task 66.3: Template Generator

#### 66.3.1 Module Templates
Templates by module type:
- **CommonModule**: standard regions, export functions
- **ObjectModule**: event handlers, posting, filling
- **FormModule**: OnCreateAtServer, command handlers
- **ManagerModule**: constructor patterns
- **RecordSetModule**: register writing patterns

#### 66.3.2 Procedure Templates
Templates by procedure type:
- **Event handler**: standard signature, cancel parameter
- **Query function**: query builder pattern, parameters
- **Validation**: check pattern, error messages
- **Print form**: spreadsheet builder pattern

#### 66.3.3 Template Selection
- Auto-select template based on request context
- Allow manual override via parameter

---

## Deliverables

- [ ] `.claude/hooks/bsl-auto-context.py` — UserPromptSubmit hook
- [ ] `src/bsl/assistant/context_builder.py` — context fetching and formatting
- [ ] `src/bsl/assistant/style_extractor.py` — code style analysis
- [ ] `src/bsl/assistant/template_generator.py` — module/procedure templates
- [ ] `data/bsl_code_style.json` — extracted style rules
- [ ] `data/bsl_templates/` — template files by type

---

## Acceptance Criteria

1. Auto-context hook triggers on BSL coding requests
2. Context includes: similar procedures, related objects, dependencies
3. Code style rules extracted from 50+ BSL files
4. Templates available for 5+ module types
5. Generated code follows detected project conventions
6. No noticeable latency increase (<500ms for context fetching)
