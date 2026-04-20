# ADR-008: DSPy Migration Verdict — Self-RAG Nodes

**Status:** Pending eval results
**Date:** 2026-04-21
**Context:** Hermes Phase 2.1

## Decision

Migrate 3 Self-RAG nodes (grader, rewriter, hallucination_checker) from pure LangChain to DSPy signatures with fallback chain: `cheap_llm → DSPy → LangChain`.

## Evaluation

Benchmark: 50-query eval set (20 grounded, 15 partial, 15 hallucination-prone) across 3 domains (pdf, 1c, general).

| Metric | Baseline (LangChain) | Candidate (DSPy) | Delta | Verdict |
|--------|---------------------|-------------------|-------|---------|
| Grader accuracy | _pending_ | _pending_ | — | — |
| Grader binary F1 | _pending_ | _pending_ | — | — |
| Hallucination accuracy | _pending_ | _pending_ | — | — |
| Hallucination grounded F1 | _pending_ | _pending_ | — | — |
| Grader latency p50 | _pending_ | _pending_ | — | — |

> 5% regression threshold → ROLLBACK

## Rollback Plan

If ROLLBACK verdict:

1. Revert node files to LangChain-only paths:
   - `src/pdf_framework/agents/rag/nodes/grader.py`
   - `src/pdf_framework/agents/rag/nodes/rewriter.py`
   - `src/pdf_framework/agents/rag/nodes/hallucination_checker.py`
2. Remove DSPy signature imports from `src/pdf_framework/prompts/signatures.py`
3. Remove `is_dspy_available()` gate functions
4. Keep `is_cheap_llm_enabled()` path (independent optimization)
5. Run `python scripts/eval_hermes_phase2.py --baseline langchain` to confirm baseline restored

## Run Commands

```bash
# Baseline
python scripts/eval_hermes_phase2.py --baseline langchain --output-dir data/eval/hermes

# Candidate
python scripts/eval_hermes_phase2.py --candidate dspy --output-dir data/eval/hermes

# Report
python scripts/eval_hermes_phase2.py --report data/eval/hermes/report.md

# Smoke gate (pre-commit)
python scripts/eval_hermes_phase2.py --smoke
```
