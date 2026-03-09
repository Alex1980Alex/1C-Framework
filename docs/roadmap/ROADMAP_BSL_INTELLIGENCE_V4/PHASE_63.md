# Phase 63: Contextual BSL Search

**Priority:** MEDIUM | **Effort:** 2-3 days | **Depends on:** Phases 59, 60, 62 | **Effect:** +15-20% recall

**Goal:** Add module context to each chunk during indexing. +15-20% retrieval quality.

---

## Problem Statement

Current search indexes code in isolation — each procedure/function is embedded without its context:
- Which module does it belong to?
- What subsystem is it part of?
- What objects does it work with?
- What are its dependencies?

Without context, semantically similar but functionally different procedures look the same to the embedding model.

---

## Approach

Based on **Anthropic's Contextual Retrieval** research: prepend a context block to each chunk before embedding.

```
Context: CommonModule "DocumentProcessing", subsystem "Sales",
works with Document.Invoice, Catalog.Products, AccumulationRegister.Sales.
Dependencies: CommonModule.ProductCalculation, CommonModule.TaxCalculation.
This procedure handles document posting and creates register movements.

Procedure HandlePosting(Document, Cancel, PostingMode) Export
    ...
```

---

## Tasks

### Task 63.1: Context Generator

#### 63.1.1 Module Context
- Module type (CommonModule, ObjectModule, FormModule, etc.)
- Parent object (for ObjectModule: Catalog.Vehicles, Document.Invoice)
- Subsystem membership (from Phase 62 knowledge graph)

#### 63.1.2 Dependency Context
- Called modules (from Phase 61 call graph)
- Used objects (from query analysis in Phase 61)
- Event subscriptions (from Phase 59 AST)

#### 63.1.3 Semantic Context
- Auto-generated 1-2 sentence description of what the procedure does
- Option A: Rule-based (from procedure name + params + calls)
- Option B: LLM-generated (batch, cached, one-time cost)

#### 63.1.4 Context Template
```
Context: {module_type} "{module_name}", subsystem "{subsystem}",
works with {object_list}.
Dependencies: {dependency_list}.
{semantic_description}
```

### Task 63.2: Indexing Pipeline Update

#### 63.2.1 Context Injection
- Before embedding, prepend context block to chunk content
- Store original content separately (for display)
- Store context string in metadata (for debugging)

#### 63.2.2 Cache
- Cache generated contexts in SQLite
- Key: module_path + symbol_name
- Invalidate on file change

#### 63.2.3 Batch Processing
- Generate contexts for all symbols
- Embed with context prepended
- Store in Qdrant `bsl_code_v3` collection

### Task 63.3: Search Pipeline Update

#### 63.3.1 Query Context
- Optionally prepend context to search query too
- Test: with and without query context
- Measure impact on eval dataset

#### 63.3.2 Result Display
- Show context in search results (collapsible)
- Highlight matching context elements

---

## Expected Effect

| Metric | Without context | With context | Improvement |
|--------|----------------|--------------|-------------|
| Recall@5 | ~0.70 | ~0.85 | +15-20% |
| Recall@10 | ~0.85 | ~0.95 | +10-12% |
| Cross-module queries | Weak | Strong | Significant |

Cross-module queries benefit most: "how is vehicle blocking implemented?" now matches procedures in modules that work with Catalog.Vehicles even if the word "vehicle" isn't in the procedure body.

---

## Deliverables

- [ ] `src/bsl/search/context_generator.py` — context generation from graph + call data
- [ ] `src/bsl/search/contextual_indexer.py` — indexing with context prepended
- [ ] Context cache in SQLite
- [ ] Updated search pipeline
- [ ] A/B eval report (with/without context)

---

## Acceptance Criteria

1. Every symbol chunk has a context block prepended before embedding
2. Context includes: module info, subsystem, dependencies, objects
3. Context cached and invalidated on file change
4. Eval shows 15%+ improvement on cross-module queries
5. Search results display context information
