# Phase 8.12.8 — Quality Regression A/B Pipeline

Synthetic golden-set construction + retrieval@10 evaluation across 3 arms:
- (a) E5 baseline → `bsl_code_v3` (1024d)
- (b) Qwen3 + A2 sliding-window → `bsl_code_v4` (4096d, standard pooling)
- (c) Qwen3 + A2-alt Late Chunking → `bsl_code_v4_late` (4096d, late-chunking)

## Pipeline (chain via JSONL artefacts in `tmp/phase8_12_8/`)

```
filter_chunks.py        scroll bsl_code_v4 → LLM-judge yes/no → chunks_filtered.jsonl
cluster_by_graph.py     load call_graph → WCC → clusters.jsonl
generate_queries.py     stratified anchor sample + Promptagator prompt → queries_pilot.jsonl
label_multipositive.py  primary (anchor) + secondary (1-hop callers∪callees) + KL validation → golden_set.jsonl
eval_pipeline.py        embed + query_points across 3 collections → recall@10/NDCG@10/MRR table
```

## Background research
- `.claude/skills/architecture-research/cache/code-retrieval-golden-set-construction-2025.md`
- Roadmap §21.6 task 8.12.8
