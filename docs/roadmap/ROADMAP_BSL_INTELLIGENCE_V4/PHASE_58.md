# Phase 58: BSL Eval Dataset and Baseline

**Priority:** CRITICAL | **Effort:** 1-2 days | **Depends on:** -- | **Effect:** Measurement

**Goal:** Create eval dataset, establish baseline. Without this, cannot measure any improvement.

---

## Problem Statement

No evaluation dataset exists for BSL code search. Impossible to:
- Measure current search quality
- Compare approaches (FTS5 vs vector vs hybrid)
- Validate improvements from Phases 59-67
- Detect regressions

---

## Tasks

### Task 58.1: Create Eval Dataset (100 pairs)

Create 100 `(query, expected_modules)` pairs across 4 categories:

#### 58.1.1 Functionality Search (~25 pairs)
- "document posting handler" -> specific modules
- "form opening event" -> modules with OnOpen/OnCreate
- "scheduled job handler" -> specific modules
- "print form generation" -> modules with print logic

#### 58.1.2 API Search (~25 pairs)
- "FindByCode catalog" -> modules calling CatalogManager.FindByCode()
- "BeginTransaction" -> modules with transaction blocks
- "Query with temp tables" -> modules using INTO keyword
- "ValueTable sorting" -> modules with ValueTable.Sort()

#### 58.1.3 Business Logic Search (~25 pairs)
- "vehicle blocking" -> relevant business modules
- "price calculation" -> pricing logic modules
- "document status change" -> status management modules
- "access rights check" -> permission validation modules

#### 58.1.4 Pattern Search (~25 pairs)
- "temp table in query" -> modules with INTO in query text
- "try-catch error handling" -> modules with Try/Except blocks
- "recursive procedure call" -> modules with self-references
- "external data source connection" -> modules with connection logic

### Task 58.2: Auto-Evaluation Script

Create `scripts/eval_bsl_search.py`:

#### 58.2.1 Metrics Implementation
- **Recall@5** — fraction of relevant results in top 5
- **Recall@10** — fraction of relevant results in top 10
- **MRR** (Mean Reciprocal Rank) — 1/rank of first relevant result
- **nDCG** (normalized Discounted Cumulative Gain) — position-weighted relevance

#### 58.2.2 Test Runner
- Load eval dataset from JSON/YAML
- Run each query against search backend
- Collect results, compute metrics
- Output summary table + per-query details

#### 58.2.3 Report Generation
- Markdown report with metrics table
- Per-category breakdown
- Failure analysis (queries with 0 recall)
- Comparison mode (before/after)

### Task 58.3: Baseline Measurement

Run eval against current search backends:

#### 58.3.1 FTS5 Baseline
- Run all 100 queries against SQLite FTS5
- Record recall@5, recall@10, MRR, nDCG

#### 58.3.2 Qdrant nomic Baseline
- Run all 100 queries against Qdrant (nomic-embed-text 768d)
- Record same metrics

#### 58.3.3 Baseline Report
- Generate comparison table
- Identify weakest categories
- Set concrete improvement targets

---

## Expected Baseline

| Metric | FTS5 | Qdrant nomic | Target (v4) |
|--------|------|-------------|-------------|
| Recall@5 | ~0.30 | ~0.45 | >0.80 |
| Recall@10 | ~0.45 | ~0.60 | >0.90 |
| MRR | ~0.25 | ~0.35 | >0.70 |

---

## Deliverables

- [ ] `data/eval/bsl_eval_dataset.json` — 100 query-result pairs
- [ ] `scripts/eval_bsl_search.py` — evaluation runner
- [ ] `docs/analysis/bsl_baseline_report.md` — baseline metrics report

---

## Acceptance Criteria

1. Dataset has >= 100 pairs across 4 categories
2. All 4 metrics implemented and tested
3. Baseline numbers recorded for FTS5 and Qdrant
4. Report generated with per-category breakdown
