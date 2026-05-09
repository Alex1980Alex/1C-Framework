# Eval Datasets Changelog

Tracking versioned curated evaluation datasets for retrieval / RAG / smoke-gate benchmarks.

## golden_v1.json v1.1 — 2026-05-09 (templated expansion)

**Status:** seed expanded (40 items: 10 manual v1.0 + 30 templated). Schema gates ZELENЫ. Quality gates всё ещё skip (требует ≥50 items с populated `expected_chunk_ids`).

**Что добавлено:** 30 queries сконструированных на основе existing chapters framework documentation + CLAUDE.md без LLM (pure templating). Coverage:
- Difficulty: easy 9, medium 17, hard 14
- Domain: rag-framework 17, embeddings 7, infra 11, 1c 5
- Category: factual 14, conceptual 8, procedural 9, analytical 5, comparative 4

**Limitations:** `expected_chunk_ids: []` для всех 40 items — grounding pass требует actual indexed `pdf_documents` corpus + manual ID lookup или LLM-assisted matching. Это deferred to v2.0.

**Tests verify:** 9/9 schema gates + 3/3 DeepEval schema gates pass. Quality gates skip (40 < 50, всё ещё в seed phase).

## golden_v1.json v1.0 — 2026-05-09

**Status:** initial seed (10 manual examples) — roadmap 260509 §2.2 partial closure.

**Schema (per item):**

```json
{
  "id": "gv1-NNN",
  "query": "natural-language",
  "expected_chunk_ids": ["..."],
  "expected_keywords": ["..."],
  "expected_answer_summary": "...",
  "difficulty": "easy|medium|hard",
  "category": "factual|conceptual|procedural|analytical|comparative",
  "domain": "rag-framework|1c|embeddings|infra"
}
```

**Coverage (10 items):**

| Difficulty | Domain | Count |
|---|---|---|
| easy | rag-framework, embeddings, 1c | 3 |
| medium | rag-framework × 2, infra | 3 |
| hard | rag-framework × 2, embeddings, infra | 4 |

**Known limitations:**

- `expected_chunk_ids` are empty arrays — needs grounding pass against actual indexed corpus (Qdrant `pdf_documents` collection).
- Quality metric on this seed = `expected_keywords` overlap with retrieved/generated answer (loose semantic check).
- Synthetic expansion to ≥100 items deferred until `dspy` is available in dev environment (`pip install dspy-ai` + LLM credentials).

**Use:**

- `tests/eval/test_smoke_gate.py` — CI smoke-gate (NDCG vs threshold; gracefully skips when dataset has < 50 items).
- Future: `evaluation-benchmark` skill workflows.

## bsl_eval_dataset.json — pre-existing

`data/eval/bsl/bsl_eval_dataset.json` — BSL semantic search baseline. Schema differs (BSL-specific). Not aligned with `golden_v1.json` schema; keep separate.

## sample_dataset.json — pre-existing

`data/eval/sample_dataset.json` — 5-item demo set with `relevant_chunk_ids` + `expected_keywords` + `category`. Used as schema reference for `golden_v1.json`. Keep as historical demo.

## hermes/phase4_queries.jsonl — pre-existing

64 queries × `relevant_entity_names` for graph-based eval. Different scope (graph entities, not chunks). Out of golden_v1 scope.

---

## Roadmap

- **v1.1** — populate `expected_chunk_ids` against indexed `pdf_documents` (manual or LLM-assisted grounding).
- **v2.0** — DSPy.Synthesize expansion to ≥100 items × 3 difficulty levels (requires `dspy` install).
- **v2.1** — manual review of synthetic items (~5-10h human work).
- **v3.0** — multilingual coverage (English ↔ Russian queries on same domain).
