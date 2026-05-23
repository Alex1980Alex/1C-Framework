# ADR-008: DSPy Migration Verdict — Self-RAG Nodes

**Status:** Accepted (verdict PASS, 2026-04-21; lifecycle reaffirmed 2026-05-15 via roadmap 260509 §2.1)
**Date:** 2026-04-21 (eval) / 2026-05-15 (status update)
**Context:** Hermes Phase 2.1 + roadmap [260509 §2.1](../roadmap/260509_ROADMAP_CONSOLIDATED_BACKLOG.md#21-p0--adr-008-verdict--safe-smoke-gate-260423-c1)

## Decision

Migrate 3 Self-RAG nodes (grader, rewriter, hallucination_checker) from pure LangChain to DSPy signatures with fallback chain: `cheap_llm → DSPy → LangChain`.

## Evaluation

Benchmark: 50-query eval set (20 grounded, 15 partial, 15 hallucination-prone) across 3 domains (pdf, 1c, general).

Источник данных: [`data/eval/hermes/report.md`](../../data/eval/hermes/report.md) (50-entry eval set, 2026-04-21).

| Metric | Baseline (LangChain) | Candidate (DSPy) | Delta | Verdict |
|--------|---------------------|-------------------|-------|---------|
| Grader accuracy | 0.9200 | 0.9400 | **+0.0200** | PASS |
| Grader binary F1 | 0.9583 | 0.9691 | +0.0107 | PASS |
| Grader latency p50 (s) | 1.2939 | 1.3637 | +0.0699 | within budget |
| Grader latency p95 (s) | 15.3221 | 17.6501 | +2.3280 | within budget |
| Hallucination accuracy | 1.0000 | 0.9667 | -0.0333 | PASS (within 5%) |
| Hallucination latency p50 (s) | 1.8584 | 2.4541 | +0.5957 | within budget |
| Hallucination latency p95 (s) | 19.3761 | 12.7317 | **-6.6445** | improvement |

> 5% regression threshold → ROLLBACK
>
> **Verdict: PASS** — no >5% regression. Grader accuracy +2pp, hallucination latency p95 improved on 6.6s. См. полный report c CI bounds в `data/eval/hermes/report.md`.

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
