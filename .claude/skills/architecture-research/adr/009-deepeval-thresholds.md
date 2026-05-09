# ADR-009: DeepEval CI Gating Thresholds

> **Status:** proposed (placeholder — locked in via measurement after v2.0 corpus ready)
> **Date:** 2026-05-09
> **Roadmap:** [260509_ROADMAP_CONSOLIDATED_BACKLOG.md §3.9](../../../../docs/roadmap/260509_ROADMAP_CONSOLIDATED_BACKLOG.md)

## Context

§3.9 требует numerical SLA для качества generated answers, complementary к NDCG retrieval gate из §2.1. Без quality gate model-version updates, prompt changes, или RAG-pipeline refactors могут незаметно деградировать answer quality.

DeepEval (https://github.com/confident-ai/deepeval) — open-source LLM eval framework который предоставляет:
- **FaithfulnessMetric** — answer grounded в retrieval_context (no fabrication)
- **HallucinationMetric** — fabricated facts beyond context (lower is better)
- **AnswerRelevancyMetric** — answer addresses user query (semantic match)
- **ContextualRelevancyMetric** — retrieval context relevant к query

Metrics используют LLM-judge (по умолчанию GPT-4) для оценки.

## Decision

**Initial thresholds (v1, до measurement):**

| Metric | Threshold | Direction |
|---|---|---|
| Faithfulness | ≥ 0.7 | higher better |
| Hallucination | ≤ 0.1 | lower better |

**Активация:** quality gate включается только когда:
1. `deepeval` package установлен (`pip install -e ".[eval]"`).
2. `data/eval/golden_v1.json` имеет ≥ 50 items с непустыми `expected_chunk_ids`.

До этого — только schema gate (3 unit tests, всегда runs в CI).

**Future calibration:**
- После первого CI run с реальным dataset: измерить baseline через `evaluate(cases, [FaithfulnessMetric()])` без assertion.
- Зафиксировать baseline в `data/eval/baselines/deepeval_v1.json`.
- Установить threshold = `baseline - 0.05` (5% buffer для noise).
- Pereoценить ежеквартально; raise threshold by 2-3% при стабильных runs.

## Rationale

**Why 0.7 / 0.1 (initial)?**

- **Faithfulness 0.7**: ниже 0.7 considered "weak grounding" по DeepEval docs (https://docs.confident-ai.com/docs/metrics-faithfulness). Production RAG systems обычно targeting 0.8+, но 0.7 — conservative starting point чтобы не блокировать infrastructure landing.
- **Hallucination 0.1**: 10% fabrication rate is upper bound для acceptable RAG. Below 0.05 — tight goal для production; 0.1 — landing-friendly.

**Why placeholder thresholds, не fixed?**

Без measured baseline на real corpus + real RAG pipeline нельзя предсказать distribution. ADR-008 (Qwen3 late chunking) была ассерчена ровно так же: initial thresholds из docs → CI baseline measurement → adjusted ADR.

**Why две метрики, не четыре?**

DeepEval предоставляет 10+ metrics. Запуск всех = expensive (LLM judge per metric per case). Faithfulness + Hallucination — minimum viable pair: Faithfulness ловит "answer NOT grounded", Hallucination ловит "answer ADDS fabrication". Остальные (AnswerRelevancy, ContextualRelevancy, ContextualPrecision/Recall) — следующие итерации.

## Consequences

**Pros:**
- Quantitative SLA для answer quality, complementary к retrieval NDCG.
- Catches model-version regressions (e.g., Claude 4.7 → 4.8 prompt drift).
- Standardised framework — DeepEval имеет CI integration cookbook.

**Cons:**
- LLM judge cost: каждый CI run = N items × 2 metrics × LLM call ($0.01-0.05/case с GPT-4o-mini). 50 items × 2 = ~$1-5/CI run. Mitigation: запускать только на nightly, не на каждый PR.
- LLM judge subjectivity: thresholds могут drift между LLM versions. Mitigation: pin judge model version в DeepEval config.
- Schema-only gate **не ловит quality regressions** до v2.0 dataset — текущее значение infrastructure preparation, не активная защита.

## Implementation

- [`tests/eval/test_deepeval.py`](../../../../tests/eval/test_deepeval.py) — schema gate (3 unit tests) + quality gate (2 integration tests, gated на deepeval install + dataset size).
- [`pyproject.toml`](../../../../pyproject.toml) — `[eval]` extra с `deepeval>=0.20`.
- [`.github/workflows/ci.yml`](../../../../.github/workflows/ci.yml) — step "DeepEval gate (schema validation)" в `test-unit` job.
- Threshold константы: `FAITHFULNESS_THRESHOLD = 0.7`, `HALLUCINATION_THRESHOLD = 0.1` в test_deepeval.py.

## Related

- ADR-008: Qwen3 late chunking — calibration pattern (initial → CI baseline → locked).
- §2.1 Smoke gate (NDCG retrieval) — sibling quality gate, same skip-when-not-ready pattern.
- `data/eval/CHANGELOG.md` — golden_v1 expansion plan (v2.0 = 100 items с ground truth активирует quality gate).

## Status timeline

- 2026-05-09 — proposed (initial thresholds + infrastructure landing).
- TBD — accepted (после v2.0 dataset + first calibrated CI run).
