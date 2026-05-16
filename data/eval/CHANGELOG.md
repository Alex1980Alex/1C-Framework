# Eval Datasets Changelog

Tracking versioned curated evaluation datasets for retrieval / RAG / smoke-gate benchmarks.

## golden_v1.json v2.0 — 2026-05-16 (LLM-assisted grounding pass)

**Status:** roadmap [260509 §2.2 v2.0 grounding](../../docs/roadmap/260509_ROADMAP_CONSOLIDATED_BACKLOG.md#22-p0--golden-eval-dataset-260423-c2--unblocker-для-b1b2b7) DONE. `expected_chunk_ids` populated через LLM-assisted relevance judgment в [`scripts/ground_golden_v1.py`](../../scripts/ground_golden_v1.py).

**Coverage:** **29/40 populated** (72.5%), **56 total chunk_ids**, distribution:
- `framework_code_v1`: 25 items (core RAG/agents/infra code)
- `bsl_code_v4_late`: 2 items (1C platform queries about specific BSL implementations)
- `pdf_documents`: 2 items (1C concept queries — регистр накопления, план обмена)
- empty (no relevant chunks in any tested corpus): 11 items (conceptual/cross-domain questions that don't map to single chunks — e.g., «5 phases of Learning Loop», «Self-RAG vs DeepEval» comparisons)

**Pipeline (replicable):**
1. TEI embed query (Qwen3 instruction prefix) → top-15 candidates from target Qdrant collection
2. LLM judge (Z.AI/zai-glm5 via `cheap_llm_call`, component=`grounding_judge`, temp=0.0, max_tokens=200) — strict prompt: imports/re-exports DON'T qualify, return JSON `relevant_indices` (0-3 indices)
3. Map indices → chunk IDs, write to `expected_chunk_ids`. Also added new field `target_collection: str` per item — eval pipeline uses to route query к правильной коллекции.

**Schema changes:**
- **NEW field**: `target_collection` (string) — Qdrant collection where ground-truth chunks live. Set when grounding populates `expected_chunk_ids`. Allows multi-corpus eval.
- `expected_chunk_ids: []` теперь имеет semantic meaning «no ground truth — skip in quality gate» (раньше означало «pending grounding»).

**Tests verify:** 12/12 schema gates PASS (9 smoke + 3 DeepEval). Quality gates still SKIP (need ≥50 items per `MIN_QUALITY_GATE_SIZE`, мы имеем 40 total / 29 grounded). Раскрытие quality gate требует expansion 40→50+ items с дополнительным grounding pass.

**Pipeline cost:** 40 queries × ~1.5s avg LLM call = ~60s total (zai-glm5 через rotation service).

**Tooling:**
- `python scripts/ground_golden_v1.py` — ground all unfilled (resumable, atomic per-item save)
- `python scripts/ground_golden_v1.py --force` — re-ground all
- `python scripts/ground_golden_v1.py --domains 1c --collection bsl_code_v4_late` — domain-specific corpus routing
- `python scripts/ground_golden_v1.py --dry-run --ids gv1-001,gv1-002` — preview without saving

**Unblocks (downstream items per roadmap):**
- §2.1 NDCG quality gate — auto-activates когда items ≥50
- §3.2.5 Contextual Retrieval benchmark — может measure NDCG@10 lift на 25 framework_code_v1 items
- §3.9 DeepEval quality gates — `faithfulness/hallucination` thresholds могут measure
- §4.1.5 Production Matryoshka migration — rank-sensitive NDCG comparison 4096d vs 1024d
- §4.2.4 RAPTOR + LLM rerank benchmark — measure rerank lift

**Known limitation:** 11 items remain empty (mostly conceptual/comparison queries). Future v2.1 expansion could either (a) re-craft these queries to be more code-specific, (b) add ground truth via manual annotation, (c) accept as "out-of-scope для retrieval benchmark — covered by RAG triad eval instead".

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
