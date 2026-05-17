# ROADMAP: API-Key Required Tasks (DEFERRED)

> **Дата:** 2026-05-17
> **Статус:** ALL DEFERRED — все tasks требуют `ANTHROPIC_API_KEY` (paid Anthropic API access)
> **Master plan:** consolidates Roadmap 260516 Phase 2/4/5 + future paid-API tasks
> **Subscription path не работает:** Phase 2/4 specifically benefit от true HTTP parallelism, который subscription tier (claude-cli) не обеспечивает

## Содержание

- [Why these tasks need API key](#why-these-tasks-need-api-key)
- [Phase 2 — Paid HTTP hot-path для grader/hallucination_checker](#phase-2--paid-http-hot-path)
- [Phase 4 — LiteLLM unified gateway](#phase-4--litellm-unified-gateway)
- [Phase 5 — Eval framework + regression gates](#phase-5--eval-framework--regression-gates)
- [Phase 6 — §3.2 Contextual Retrieval enable](#phase-6--32-contextual-retrieval-enable)
- [Cost estimates](#cost-estimates)
- [Decision tree: когда запустить](#decision-tree-когда-запустить)
- [Acceptance criteria](#acceptance-criteria)
- [Связанные документы](#связанные-документы)

---

## Why these tasks need API key

**Текущее состояние LLM Rotation Service:**
- Default provider: `claude-cli-haiku` (priority 0) — claude-cli subprocess через subscription
- Fallback: `claude-cli-sonnet`, `ollama-local`, `anthropic-sonnet` (silent skip без `ANTHROPIC_API_KEY`)

**Empirical finding (§3 Phase 3 batch implementation, commit `7dd1fbea8`):**
- claude-agent-sdk fundamentally **serializes subprocess spawns** на subscription tier
- `batch_complete()` с concurrency=10 даёт ~1× speedup vs sequential (instead of expected 10×)
- Adaptive concurrency controller built (4 signals: cb_opened, 429, 5xx, slow) но без real parallelism throttle bandwidth неактивен

**Что Phase 2/4 решают (требуют HTTP parallel):**
- True parallelism (10+ concurrent requests via HTTP)
- Sub-second latency для grader/hallucination_checker hot-path
- Response caching через LiteLLM (cache hit rate ~30-50% на repeat queries)

**Phase 5 — нюанс:**
- Eval framework сам по себе НЕ требует API key
- Но cost/quality benchmarks теряют смысл без paid API comparison
- Можно делать partial Phase 5 на subscription tier — limited value

---

## Phase 2 — Paid HTTP hot-path

**Цель:** Switch Self-RAG hot-path components с claude-cli subprocess на HTTP Anthropic API для true parallelism + sub-second latency.

### 2.1 Provider config switch

```python
# src/shared/llm_rotation/service.py DEFAULT_PROVIDERS
# Priority order CHANGES:
# 0. anthropic-sonnet-fast (HTTP, требует API key)
# 1. claude-cli-haiku (subscription fallback)
# 2. ollama-local (offline fallback)
```

Реализуется через env: `ANTHROPIC_API_KEY` + `LLM_ROTATION_PRIMARY_PROVIDER=anthropic-sonnet-fast`.

### 2.2 CheapLLM adapter updates

**Components, переключаемые на paid (Cat 1, high-throughput):**
- `grader` (Self-RAG relevance check, max_tokens=50)
- `hallucination_checker` (max_tokens=100)
- `rewriter` (max_tokens=200)
- `query_expansion` (max_tokens=300)
- `search_classifier` (max_tokens=100)

**Не переключаются (Cat 2, bulk):**
- `entity_extractor` (max_tokens=4096) — слишком дорого через paid API на массовой индексации
- `community_summarizer`, `context_generator` — остаются на subscription

### 2.3 Benchmarks

Compare latency + cost:
- p95 latency: subscription ~5-15s vs paid HTTP ~200-500ms (expected)
- Self-RAG full query: 2-3 LLM calls × latency = total UX time

**Target:** Self-RAG p95 < 3s (currently ~15-30s через subscription).

---

## Phase 4 — LiteLLM unified gateway

**Цель:** Layer LiteLLM поверх current providers для caching + retries + observability.

### 4.1 Setup

```bash
pip install litellm
# Config router в src/shared/llm_rotation/service.py:
# litellm.Router(model_list=[anthropic-fast, claude-cli-haiku, ollama-local])
```

LiteLLM features:
- Response caching (SQLite or Redis backend, 30-50% hit rate expected)
- Automatic retries с exponential backoff (replaces tenacity)
- Cost tracking per provider
- Unified streaming interface

### 4.2 Integration с CheapLLM adapter

Replace existing rotation logic с `litellm.completion()` call → router handles routing.

**Migration risk:** existing 33 integration tests могут break — нужен careful refactor.

### 4.3 Benchmarks

- Cache hit latency: < 10ms vs cold call 500ms-15s
- Cache hit rate на repeat Self-RAG calls: target ≥ 30%
- Cost per query: track via LiteLLM cost API

---

## Phase 5 — Eval framework + regression gates

**Цель:** Automated quality regression detection на CheapLLM component outputs.

### 5.1 Quality criteria expansion

Current `QUALITY_CRITERIA` в [`src/shared/llm_rotation/adapter.py`](../../src/shared/llm_rotation/adapter.py):
- grader: exact_match
- hallucination_checker: exact_match
- rewriter: different_from_input
- entity_extractor: valid_json

**Расширения:**
- Per-component golden test sets (10-30 examples each)
- Semantic similarity threshold (cosine ≥ 0.7 vs expected output)
- Latency budget assertions (per-component p95 cap)

### 5.2 CI integration

```yaml
# .github/workflows/eval.yml (new)
- name: CheapLLM regression gate
  run: python scripts/eval_cheapllm_components.py --strict
  # Fails CI if any component:
  #   - quality drops > 5% vs baseline
  #   - p95 latency > 1.5× baseline
```

### 5.3 Baseline management

- Store baselines в `data/eval/cheapllm_baselines.json` (per-provider)
- Update via `python scripts/eval_cheapllm_components.py --update-baselines`
- Manual review required для baseline updates (PR check)

**Partial Phase 5 без API key:** только subscription-tier (claude-cli) baselines + ollama. Limited value comparison.

---

## Phase 6 — §3.2 Contextual Retrieval enable

**Цель:** Enable Anthropic-style chunk context generation (Phase 50, [`src/pdf_framework/processing/context_generator.py`](../../src/pdf_framework/processing/context_generator.py)) на production collections.

### 6.1 Current state (2026-05-17)

- **Implementation: FULL** — 354 lines с LLM context gen + SQLite cache + batch concurrency + Ralph Wiggum retry
- **Config:** `CONTEXTUAL_RETRIEVAL__ENABLED=False` (default off)
- **Model required:** `claude-haiku-4-5-20251001` via `langchain_anthropic.ChatAnthropic` → требует `ANTHROPIC_API_KEY`
- **Fallback:** `cheap_llm_call` через llm_rotation adapter (subscription tier, claude-cli) — works, но slow

### 6.2 Why deferred

**Cost analysis:**
- Per-chunk: 1 LLM call generates 1-2 sentence context summary
- Subscription tier (claude-cli): ~15s per call serialized → 830 chunks × 15s = **~3.5h wall-clock per indexing run**
- Paid Haiku API: ~500ms per call × $0.001 = $0.83 total per indexing of pdf_documents (830 chunks)
- Re-indexing на каждом auto-reindex trigger → cumulative cost grows

**Cache helps:** SQLite cache `data/context_cache.db` keyed by chunk_id — repeat runs skip already-generated contexts. Only NEW/CHANGED chunks pay LLM cost.

**Expected lift:** +20-35% NDCG@10 per Anthropic 2024 blog (mixed corpus). On highly technical corpus (BSL Cyrillic) impact may be lower.

### 6.3 Execution plan (when unblocked)

1. Set `CONTEXTUAL_RETRIEVAL__ENABLED=true` + ensure `ANTHROPIC_API_KEY` provisioned
2. Re-index test sample (50 chunks, $0.05 cost) → verify cache + retry logic works end-to-end
3. Full re-index pdf_documents (830 chunks, ~$0.85, ~5 min on paid API)
4. NDCG bench via golden_v1 v2.3 (18 grounded PDF queries) vs current dense-only
5. If MIGRATE (lift ≥ +5%): enable globally + re-index framework_code_v1 + wiki_pages_v1
6. Auto-reindex hook: ensure incremental chunks get context (already handled by SQLite cache key)

### 6.4 Acceptance gates

- [ ] Sample (50 chunks) bench shows NDCG@10 lift ≥ +10% vs dense-only
- [ ] Full pdf_documents indexing completes in < 10 min on paid API
- [ ] Cost per re-indexing < $5 (cache hit rate makes incremental cheap)
- [ ] No regression on PDF p95 latency (context only affects index time, not retrieval)

---

## Cost estimates

| Phase | Setup time | Monthly API cost (estimated) |
|---|---|---|
| Phase 2 (hot-path switch) | 4-6h | $20-80/month при ~1000 Self-RAG queries/day |
| Phase 4 (LiteLLM gateway) | 6-10h | $0 additional (uses Phase 2 API) + Redis ~$5/month |
| Phase 5 (eval framework) | 4-8h | $5-15/month для regression tests |
| **Total** | 14-24h eng | **$25-100/month** ongoing |

**Anthropic pricing reference (2026 levels):**
- Haiku 4.5: ~$0.001/1K input + $0.005/1K output
- Sonnet 4.6: ~$0.003/1K input + $0.015/1K output

Self-RAG query average ~2K input + 200 output tokens × 3 LLM calls = ~$0.006-0.06 per query.

---

## Decision tree: когда запустить

```
START
  │
  ├── Q1: Allocated ANTHROPIC_API_KEY budget ≥ $20/month?
  │     ├── NO → DEFER, остаёмся на subscription tier
  │     └── YES → продолжить
  │
  ├── Q2: Self-RAG production traffic > 100 queries/day?
  │     ├── NO → Phase 2 ROI marginal (latency не bottleneck) — DEFER
  │     └── YES → продолжить
  │
  ├── Q3: Существующий subscription tier hit rate limits?
  │     ├── NO → subscription tier работает — DEFER
  │     └── YES → продолжить
  │
  └── EXECUTE: Phase 2 → Phase 4 → Phase 5 sequentially
```

**Текущий статус 2026-05-17:** Q1=NO (no API key budget allocated). Roadmap waits.

---

## Acceptance criteria (overall)

Roadmap считается выполненным когда:

- [ ] `ANTHROPIC_API_KEY` provisioned и budget allocated
- [ ] Phase 2: Self-RAG p95 < 3s (down from current 15-30s)
- [ ] Phase 4: LiteLLM cache hit rate ≥ 30% on repeat queries
- [ ] Phase 5: regression gates active в CI, fail on > 5% quality drop
- [ ] Cost stays within allocated budget

---

## Связанные документы

- [`260516_ROADMAP_LLM_ROTATION_IMPROVEMENTS.md`](260516_ROADMAP_LLM_ROTATION_IMPROVEMENTS.md) — original roadmap (Phase 1+3 closed, Phase 2+4+5 deferred here)
- [Memory: aggressive delegation](../../.claude/projects/C--1--Framework/memory/feedback_delegation_aggressive.md) — текущая стратегия Token Economy
- [Skill: llm-rotation](../../.claude/skills/llm-rotation/SKILL.md) — current providers + adapter implementation
- [Skill: z-ai-delegation](../../.claude/skills/z-ai-delegation/SKILL.md) — delegation protocol

---

## Decision (2026-05-17)

**ALL TASKS DEFERRED.** Triggers для re-evaluation:
1. User allocates `ANTHROPIC_API_KEY` budget ($20-100/month)
2. Self-RAG production traffic grows > 100 queries/day (subscription tier latency becomes UX-blocking)
3. Production user reports actual subscription tier rate-limit issues
4. Cost-benefit analysis shows positive ROI from cache hit rate

Возврат к работе тривиален — все skeletons + plans ready, текущая subscription-tier infrastructure (LLM Rotation Service v1.0) полностью functional как fallback.
